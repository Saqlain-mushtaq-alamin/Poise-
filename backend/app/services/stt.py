"""Speech-to-text.

`WhisperSTT` wraps `faster-whisper` behind the tier-appropriate model size
from the Phase 3 spec's `TIER_MODEL_MAP`. STT always runs locally — no
tier ever routes audio to a cloud API, including Cloud Assist, per the
spec's "raw audio never leaves device" note.

Model weights are pulled from Hugging Face on first use by `faster-whisper`
itself; that requires network access this environment doesn't have, so
model loading is lazy and any environment without the weights downloaded
gets `ModelNotAvailableError` — the exact "graceful fallback... show clear
message + download prompt" behavior the Phase 3 acceptance criteria calls
for, not a workaround for it.

What IS real and tested here: model selection per tier, the streaming
segment-assembly logic (turning a sequence of engine outputs into
`TranscriptionSegment`s with partial/final flags), and word-timestamp
plumbing for Phase 7. All of that is exercised with the underlying
`WhisperModel` mocked, since the orchestration logic is what this module
actually owns — transcription accuracy is faster-whisper's concern, not
ours.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, AsyncIterable
from dataclasses import dataclass, field
from pathlib import Path

from app.services.tier import HardwareTier

logger = logging.getLogger("poise.stt")

TIER_MODEL_MAP = {
    HardwareTier.LOCAL_FULL: "large-v3",
    HardwareTier.LOCAL_LITE: "base",
    HardwareTier.CLOUD_ASSIST: "tiny",
}


class ModelNotAvailableError(RuntimeError):
    """Raised when the tier-appropriate Whisper model isn't downloaded (or
    faster-whisper isn't installed). Callers — see routers/voice.py's
    WebSocket handler — turn this into a clear user-facing message plus a
    download prompt, rather than a generic 500."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        super().__init__(
            f"Whisper model '{model_name}' is not available. "
            "Download it from Settings > Hardware & Model Providers, or "
            "switch to a lower tier that uses a smaller model."
        )


@dataclass
class WordTimestamp:
    word: str
    start_ms: int
    end_ms: int
    confidence: float


@dataclass
class TranscriptionSegment:
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    is_partial: bool
    language: str | None = None
    words: list[WordTimestamp] = field(default_factory=list)


@dataclass
class Transcription:
    text: str
    language: str | None
    segments: list[TranscriptionSegment]
    duration_ms: int
    low_confidence_words: list[str] = field(default_factory=list)


class WhisperSTT:
    _cuda_available: bool | None = None

    def __init__(self, tier: HardwareTier = HardwareTier.LOCAL_LITE) -> None:
        self._tier = tier
        self._model = None
        self._loaded_model_name: str | None = None
        self._model_override: str | None = None

    def set_tier(self, tier: HardwareTier) -> None:
        self._tier = tier

    def set_model_override(self, model_name: str | None) -> None:
        self._model_override = model_name

    @property
    def model_name(self) -> str:
        return self._model_override or TIER_MODEL_MAP[self._tier]

    def is_model_loaded(self) -> bool:
        return self._model is not None and self._loaded_model_name is not None

    def _load_model(self):
        """Lazily imports and constructs the faster-whisper model. Raises
        `ModelNotAvailableError` if the library isn't installed or the
        model weights aren't present. Gracefully falls back to CPU if
        CUDA libraries (e.g. cublas64_12.dll on Windows) are missing.
        Multilingual models are prioritized for accent robustness."""
        if self.is_model_loaded():
            return self._model

        try:
            from faster_whisper import WhisperModel  # noqa: F401 — optional heavy dependency
        except ImportError as err:
            raise ModelNotAvailableError(self.model_name) from err

        candidate_names = []
        if self.model_name not in candidate_names:
            candidate_names.append(self.model_name)
        # Prioritize multilingual models over .en for accent robustness
        for fallback in ("small", "base", "tiny", "large-v3-turbo", "medium"):
            if fallback not in candidate_names:
                candidate_names.append(fallback)

        model = None
        loaded_name = self.model_name

        # 1. Try loading on auto/cuda if CUDA has not failed previously
        if WhisperSTT._cuda_available is not False:
            for candidate_name in candidate_names:
                try:
                    candidate = WhisperModel(candidate_name, device="auto", compute_type="auto")
                    import numpy as np
                    dummy_audio = np.zeros(1600, dtype=np.float32)
                    try:
                        gen, _ = candidate.transcribe(dummy_audio, word_timestamps=False)
                        next(gen, None)
                        model = candidate
                        loaded_name = candidate_name
                        WhisperSTT._cuda_available = True
                        break
                    except Exception as runtime_err:
                        logger.warning(
                            "Whisper CUDA runtime failed (%s). Falling back to CPU.",
                            runtime_err,
                        )
                        WhisperSTT._cuda_available = False
                        break
                except Exception as err:
                    logger.info("WhisperModel(%s, device='auto') failed: %s", candidate_name, err)
                    if "cublas" in str(err).lower() or "cuda" in str(err).lower():
                        WhisperSTT._cuda_available = False
                        break

        # 2. Try fast locally cached models on CPU to avoid blocking network downloads during interview
        if model is None:
            # Exclude massive models on CPU unless explicitly requested
            cpu_candidates = [c for c in candidate_names if c not in ("large-v3", "large-v2", "large")]
            for pref in ("small.en", "small", "base.en", "base", "tiny"):
                if pref not in cpu_candidates:
                    cpu_candidates.append(pref)
            for pref in reversed(["small.en", "small", "base.en", "base", "tiny"]):
                if pref in cpu_candidates:
                    cpu_candidates.remove(pref)
                    cpu_candidates.insert(0, pref)

            # Try local_files_only first so we load instantaneously without network stalls
            for candidate_name in cpu_candidates:
                try:
                    model = WhisperModel(candidate_name, device="cpu", compute_type="int8", cpu_threads=8, local_files_only=True)
                    loaded_name = candidate_name
                    break
                except Exception:
                    continue

            # If no cached model matched, try downloading standard small/base models
            if model is None:
                for candidate_name in ("small.en", "base.en", "base", "small", "tiny"):
                    try:
                        model = WhisperModel(candidate_name, device="cpu", compute_type="int8", cpu_threads=8)
                        loaded_name = candidate_name
                        break
                    except Exception:
                        continue

        if model is None:
            raise ModelNotAvailableError(self.model_name)

        self._model = model
        self._loaded_model_name = loaded_name
        return self._model

    async def transcribe_complete(
        self,
        audio_path: Path,
        initial_prompt: str | None = None,
        hotwords: str | None = None,
    ) -> Transcription:
        """Full-file transcription with word-level timestamps, prompt biasing,

        and confidence extraction for IELTS & interview scoring."""
        import asyncio

        model = self._load_model()
        prompt_str = initial_prompt or "Um, so, uh, I think, like, you know, well, actually... "
        if hotwords and hotwords not in prompt_str:
            prompt_str = f"{prompt_str} {hotwords}"

        def _do_transcribe(m):
            kwargs = {
                "word_timestamps": True,
                "language": "en",
                "beam_size": 1,
                "best_of": 1,
                "temperature": 0.0,
                "vad_filter": True,
                "vad_parameters": dict(min_silence_duration_ms=500),
                "condition_on_previous_text": False,
                "compression_ratio_threshold": 2.4,
                "log_prob_threshold": -1.0,
                "no_speech_threshold": 0.6,
                "hallucination_silence_threshold": 2.0,
                "initial_prompt": prompt_str,
            }
            if hotwords:
                kwargs["hotwords"] = hotwords
            try:
                return m.transcribe(str(audio_path), **kwargs)
            except TypeError:
                try:
                    kwargs.pop("hotwords", None)
                    return m.transcribe(str(audio_path), **kwargs)
                except TypeError:
                    return m.transcribe(str(audio_path), word_timestamps=True, language="en", initial_prompt=prompt_str)

        def _run_transcription():
            try:
                raw_gen, info = _do_transcribe(model)
                return list(raw_gen), info
            except Exception as exc:
                logger.warning("transcribe_complete failed (%s). Retrying on CPU.", exc)
                from faster_whisper import WhisperModel
                self._model = WhisperModel(self._loaded_model_name or "base", device="cpu", compute_type="int8", cpu_threads=8)
                raw_gen, info = _do_transcribe(self._model)
                return list(raw_gen), info

        raw_segments, info = await asyncio.to_thread(_run_transcription)

        segments: list[TranscriptionSegment] = []
        low_confidence_words: list[str] = []
        total_duration_ms = 0
        for raw in raw_segments:
            words = []
            for w in (raw.words or []):
                conf = float(getattr(w, "probability", 1.0))
                words.append(
                    WordTimestamp(
                        word=w.word,
                        start_ms=int(w.start * 1000),
                        end_ms=int(w.end * 1000),
                        confidence=conf,
                    )
                )
                if conf < 0.65 and w.word.strip():
                    clean_w = w.word.strip().lower()
                    if clean_w not in low_confidence_words:
                        low_confidence_words.append(clean_w)

            segment = TranscriptionSegment(
                text=raw.text.strip(),
                start_ms=int(raw.start * 1000),
                end_ms=int(raw.end * 1000),
                confidence=float(getattr(raw, "avg_logprob", 0.0)),
                is_partial=False,
                language=getattr(info, "language", None),
                words=words,
            )
            segments.append(segment)
            total_duration_ms = max(total_duration_ms, segment.end_ms)

        full_text = " ".join(s.text for s in segments).strip()
        return Transcription(
            text=full_text,
            language=getattr(info, "language", None),
            segments=segments,
            duration_ms=total_duration_ms,
            low_confidence_words=low_confidence_words,
        )

    async def transcribe_stream(
        self,
        audio_chunks: AsyncIterable[bytes],
        buffer_seconds: float = 1.5,
        sample_rate: int = 16000,
    ) -> AsyncGenerator[TranscriptionSegment, None]:
        """Streaming transcription for the live WebSocket endpoint.

        Maintains audio context without destructive chopping at arbitrary
        time boundaries, avoiding severed words and mid-syllable hallucinations.
        """
        import asyncio

        model = self._load_model()  # raises early if unavailable, before buffering anything
        buffer = bytearray()
        bytes_per_second = sample_rate * 2  # 16-bit mono PCM
        buffer_threshold = int(bytes_per_second * buffer_seconds)

        last_transcribed_len = 0
        last_yielded_text = ""

        async for chunk in audio_chunks:
            buffer.extend(chunk)
            if len(buffer) - last_transcribed_len >= buffer_threshold:
                segment = await asyncio.to_thread(
                    self._transcribe_buffer,
                    model, bytes(buffer), True, sample_rate
                )
                last_transcribed_len = len(buffer)
                if segment is not None and segment.text:
                    last_yielded_text = segment.text
                    yield segment

        if buffer:
            if len(buffer) > last_transcribed_len or not last_yielded_text:
                segment = await asyncio.to_thread(
                    self._transcribe_buffer,
                    model, bytes(buffer), False, sample_rate
                )
                if segment is not None and segment.text:
                    yield segment
            elif last_yielded_text:
                yield TranscriptionSegment(
                    text=last_yielded_text,
                    start_ms=0,
                    end_ms=int(len(buffer) / bytes_per_second * 1000),
                    confidence=1.0,
                    is_partial=False,
                    language="en",
                )

    def _transcribe_buffer(
        self, model, pcm_bytes: bytes, is_partial: bool, sample_rate: int = 16000
    ) -> TranscriptionSegment | None:  # pragma: no cover — needs a real model; mocked in tests
        import numpy as np

        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Remove DC bias offset common on desktop microphones
        if len(audio) > 0:
            audio = audio - np.mean(audio)

        # Anti-aliased high-fidelity resampling to 16kHz via scipy polyphase FIR filter
        if sample_rate != 16000 and len(audio) > 0:
            try:
                import scipy.signal
                gcd = int(np.gcd(16000, sample_rate))
                up = 16000 // gcd
                down = sample_rate // gcd
                audio = scipy.signal.resample_poly(audio, up, down).astype(np.float32)
            except Exception:
                target_len = int(len(audio) * 16000 / sample_rate)
                if target_len > 0:
                    indices = np.linspace(0, len(audio) - 1, target_len)
                    audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

        # Gentle gain normalization for low-volume microphones
        if len(audio) > 0:
            rms = np.sqrt(np.mean(audio**2))
            if 1e-4 < rms < 0.08:
                gain = min(0.08 / rms, 4.0)
                audio = np.clip(audio * gain, -1.0, 1.0)

        prompt_str = "Hello, well, I think that, um, actually, so, you know... "

        def _do_transcribe(m):
            try:
                return m.transcribe(
                    audio,
                    word_timestamps=False,
                    language="en",
                    beam_size=1,
                    best_of=1,
                    temperature=0.0,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=300),
                    condition_on_previous_text=False,
                    initial_prompt=prompt_str,
                )
            except TypeError:
                try:
                    return m.transcribe(audio, word_timestamps=False, language="en", initial_prompt=prompt_str)
                except TypeError:
                    return m.transcribe(audio, word_timestamps=False)

        try:
            raw_gen, info = _do_transcribe(model)
            raw_segments = list(raw_gen)
        except Exception as exc:
            logger.warning("Transcription failed (%s). Retrying on CPU.", exc)
            try:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8", cpu_threads=8)
                self._loaded_model_name = self.model_name
                model = self._model
                raw_gen, info = _do_transcribe(model)
                raw_segments = list(raw_gen)
            except Exception as retry_exc:
                logger.error("CPU transcription retry failed: %s", retry_exc)
                return None

        if not raw_segments:
            return None

        text = " ".join(s.text.strip() for s in raw_segments).strip()
        if not text:
            return None

        return TranscriptionSegment(
            text=text,
            start_ms=int(raw_segments[0].start * 1000),
            end_ms=int(raw_segments[-1].end * 1000),
            confidence=float(getattr(raw_segments[-1], "avg_logprob", 0.0)),
            is_partial=is_partial,
            language=getattr(info, "language", None),
        )


_stt_instance = WhisperSTT()


def get_stt() -> WhisperSTT:
    return _stt_instance
