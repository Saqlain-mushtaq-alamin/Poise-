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


class WhisperSTT:
    def __init__(self, tier: HardwareTier = HardwareTier.LOCAL_LITE) -> None:
        self._tier = tier
        self._model = None
        self._loaded_model_name: str | None = None

    def set_tier(self, tier: HardwareTier) -> None:
        self._tier = tier

    @property
    def model_name(self) -> str:
        return TIER_MODEL_MAP[self._tier]

    def is_model_loaded(self) -> bool:
        return self._model is not None and self._loaded_model_name == self.model_name

    def _load_model(self):
        """Lazily imports and constructs the faster-whisper model. Raises
        `ModelNotAvailableError` if the library isn't installed or the
        model weights aren't present. Gracefully falls back to CPU if
        CUDA libraries (e.g. cublas64_12.dll on Windows) are missing.
        Prioritizes high-accuracy English models (small.en, base.en) for
        IELTS and interview practice."""
        if self.is_model_loaded():
            return self._model

        try:
            from faster_whisper import WhisperModel  # noqa: F401 — optional heavy dependency
        except ImportError as err:
            raise ModelNotAvailableError(self.model_name) from err

        candidate_names = []
        # For English speech (IELTS and interview practice), prioritize specialized
        # .en models (e.g. small.en, base.en) which offer significantly higher accuracy.
        if self.model_name in ("small", "small.en", "base", "base.en", "tiny", "tiny.en"):
            candidate_names.extend(["small.en", "base.en"])
        if self.model_name not in candidate_names:
            candidate_names.append(self.model_name)
        for fallback in ("base.en", "base", "tiny.en", "tiny"):
            if fallback not in candidate_names:
                candidate_names.append(fallback)

        model = None
        for candidate_name in candidate_names:
            # 1. Try loading on auto/cuda if available
            try:
                candidate = WhisperModel(candidate_name, device="auto", compute_type="auto")
                import numpy as np
                dummy_audio = np.zeros(1600, dtype=np.float32)
                try:
                    gen, _ = candidate.transcribe(dummy_audio, word_timestamps=False)
                    next(gen, None)
                    model = candidate
                    break
                except Exception as runtime_err:
                    logger.warning(
                        "Whisper CUDA runtime failed (%s). Trying CPU for %s.",
                        runtime_err,
                        candidate_name,
                    )
            except Exception as err:
                logger.info("WhisperModel(%s, device='auto') failed: %s", candidate_name, err)

            # 2. Try CPU int8 (fast and highly accurate on multi-core CPUs)
            try:
                model = WhisperModel(candidate_name, device="cpu", compute_type="int8", cpu_threads=8)
                break
            except Exception:
                try:
                    model = WhisperModel(candidate_name, device="cpu", compute_type="auto", cpu_threads=8)
                    break
                except Exception:
                    continue

        if model is None:
            raise ModelNotAvailableError(self.model_name)

        self._model = model
        self._loaded_model_name = self.model_name
        return self._model

    async def transcribe_complete(self, audio_path: Path) -> Transcription:
        """Full-file transcription with word-level timestamps — the shape
        Phase 7 (IELTS pronunciation analysis) needs."""
        import asyncio

        model = self._load_model()

        def _do_transcribe(m):
            try:
                return m.transcribe(
                    str(audio_path),
                    word_timestamps=True,
                    language="en",
                    beam_size=5,
                    best_of=5,
                    temperature=0.0,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    condition_on_previous_text=False,
                    compression_ratio_threshold=2.4,
                    log_prob_threshold=-1.0,
                    no_speech_threshold=0.6,
                    hallucination_silence_threshold=2.0,
                )
            except TypeError:
                return m.transcribe(str(audio_path), word_timestamps=True, language="en")

        def _run_transcription():
            try:
                raw_gen, info = _do_transcribe(model)
                return list(raw_gen), info
            except Exception as exc:
                logger.warning("transcribe_complete failed (%s). Retrying on CPU.", exc)
                from faster_whisper import WhisperModel
                self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8", cpu_threads=8)
                self._loaded_model_name = self.model_name
                raw_gen, info = _do_transcribe(self._model)
                return list(raw_gen), info

        raw_segments, info = await asyncio.to_thread(_run_transcription)

        segments: list[TranscriptionSegment] = []
        total_duration_ms = 0
        for raw in raw_segments:
            words = [
                WordTimestamp(
                    word=w.word,
                    start_ms=int(w.start * 1000),
                    end_ms=int(w.end * 1000),
                    confidence=float(getattr(w, "probability", 1.0)),
                )
                for w in (raw.words or [])
            ]
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

        # Anti-aliased resampling to 16kHz
        if sample_rate != 16000 and len(audio) > 0:
            if sample_rate == 48000:
                # Exact 3:1 decimation with 3-tap averaging to filter high-frequency noise
                trim = len(audio) - (len(audio) % 3)
                audio = audio[:trim].reshape(-1, 3).mean(axis=1).astype(np.float32)
            elif sample_rate == 32000:
                trim = len(audio) - (len(audio) % 2)
                audio = audio[:trim].reshape(-1, 2).mean(axis=1).astype(np.float32)
            elif sample_rate == 44100:
                target_len = int(len(audio) * 16000 / sample_rate)
                indices = np.linspace(0, len(audio) - 1, target_len)
                kernel = np.array([0.25, 0.5, 0.25], dtype=np.float32)
                filtered = np.convolve(audio, kernel, mode="same")
                audio = np.interp(indices, np.arange(len(filtered)), filtered).astype(np.float32)
            else:
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

        def _do_transcribe(m):
            try:
                return m.transcribe(
                    audio,
                    word_timestamps=False,
                    language="en",
                    beam_size=5,
                    best_of=5,
                    temperature=0.0,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=400),
                    condition_on_previous_text=False,
                    compression_ratio_threshold=2.4,
                    log_prob_threshold=-1.0,
                    no_speech_threshold=0.6,
                    hallucination_silence_threshold=2.0,
                )
            except TypeError:
                try:
                    return m.transcribe(audio, word_timestamps=False, language="en")
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
