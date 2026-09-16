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
        model weights aren't present — both of which are true in this
        sandbox, so this path is written but not exercised by a test that
        actually loads a model (see test_stt.py for the mocked equivalent)."""
        if self.is_model_loaded():
            return self._model

        try:
            from faster_whisper import WhisperModel  # noqa: F401 — optional heavy dependency
        except ImportError as err:
            raise ModelNotAvailableError(self.model_name) from err

        try:
            self._model = WhisperModel(self.model_name, device="auto", compute_type="auto")
            self._loaded_model_name = self.model_name
        except Exception as err:  # noqa: BLE001 — model files missing, corrupt, etc.
            raise ModelNotAvailableError(self.model_name) from err

        return self._model

    async def transcribe_complete(self, audio_path: Path) -> Transcription:
        """Full-file transcription with word-level timestamps — the shape
        Phase 7 (IELTS pronunciation analysis) needs."""
        model = self._load_model()

        raw_segments, info = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            language="en",  # explicit hint prevents auto-detect failures on short clips
        )

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

        faster-whisper doesn't natively stream partial results from a
        chunk-at-a-time input, so this buffers incoming PCM into
        `buffer_seconds`-sized windows and re-transcribes each window,
        marking every result but the last as partial — the same pattern
        faster-whisper-based streaming demos use. This orchestration logic
        (buffering, partial/final flagging, ordering) is exercised in
        test_stt.py with `_transcribe_buffer` mocked; the model call
        itself is not.
        """
        model = self._load_model()  # raises early if unavailable, before buffering anything
        buffer = bytearray()
        bytes_per_second = sample_rate * 2  # 16-bit mono PCM
        buffer_threshold = int(bytes_per_second * buffer_seconds)

        async for chunk in audio_chunks:
            buffer.extend(chunk)
            if len(buffer) >= buffer_threshold:
                segment = self._transcribe_buffer(
                    model, bytes(buffer), is_partial=True, sample_rate=sample_rate
                )
                buffer.clear()
                if segment is not None:
                    yield segment

        if buffer:
            segment = self._transcribe_buffer(
                model, bytes(buffer), is_partial=False, sample_rate=sample_rate
            )
            if segment is not None:
                yield segment

    def _transcribe_buffer(
        self, model, pcm_bytes: bytes, is_partial: bool, sample_rate: int = 16000
    ) -> TranscriptionSegment | None:  # pragma: no cover — needs a real model; mocked in tests
        import numpy as np

        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if sample_rate != 16000 and len(audio) > 0:
            target_len = int(len(audio) * 16000 / sample_rate)
            if target_len > 0:
                indices = np.linspace(0, len(audio) - 1, target_len)
                audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

        try:
            raw_segments, info = model.transcribe(audio, word_timestamps=False, language="en")
        except TypeError:
            raw_segments, info = model.transcribe(audio, word_timestamps=False)
        raw_segments = list(raw_segments)
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
