"""Voice pipeline endpoints — see contracts/api/voice.yaml.

Two of these are WebSockets (real-time audio needs bidirectional, low-
latency framing that a request/response HTTP call can't give you), which
is also why they're tested with Starlette's `TestClient.websocket_connect`
in tests/test_voice_routes.py — that's a real WebSocket handshake and
real binary frames, not a mock, even though no browser is involved.
"""

from __future__ import annotations

import logging

import numpy as np
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.stt import ModelNotAvailableError, WhisperSTT, get_stt
from app.services.tts import TTSEngine, VoiceInfo, get_tts_engine
from app.services.vad import VAD, get_vad

logger = logging.getLogger("poise.voice")

router = APIRouter(prefix="/voice", tags=["voice"])

# 16-bit PCM mono @ 16kHz, matching MicCapture.ts's getUserMedia constraints
# and vad.py's SAMPLES_PER_CHUNK sizing.
BYTES_PER_SAMPLE = 2


class VoiceInfoResponse(BaseModel):
    id: str
    name: str
    language: str
    gender: str
    sample_url: str | None = None

    @classmethod
    def from_dataclass(cls, voice: VoiceInfo) -> VoiceInfoResponse:
        return cls(**voice.__dict__)


class SynthesizeRequest(BaseModel):
    text: str
    voice: str = "default"
    stream: bool = True


class AudioDeviceResponse(BaseModel):
    id: str
    name: str
    is_default: bool


@router.get("/tts/voices", response_model=list[VoiceInfoResponse])
def list_voices(tts: TTSEngine = Depends(get_tts_engine)) -> list[VoiceInfoResponse]:
    return [VoiceInfoResponse.from_dataclass(v) for v in tts.list_voices()]


@router.post("/tts/synthesize")
async def synthesize(
    body: SynthesizeRequest, tts: TTSEngine = Depends(get_tts_engine)
) -> StreamingResponse:
    """Streams WAV chunks as `audio/wav`. `stream=False` is honored by
    simply consuming the whole generator before responding — the frontend
    always receives the same media type either way."""

    async def full_body():
        async for chunk in tts.synthesize_stream(body.text, voice=body.voice):
            yield chunk

    if not body.stream:
        chunks = [c async for c in tts.synthesize_stream(body.text, voice=body.voice)]

        async def single_response():
            for c in chunks:
                yield c

        return StreamingResponse(single_response(), media_type="audio/wav")

    return StreamingResponse(full_body(), media_type="audio/wav")


@router.get("/devices", response_model=list[AudioDeviceResponse])
def list_devices() -> list[AudioDeviceResponse]:
    """Host-level audio input devices, for the backend's own recording
    fallback path (browser-side device selection uses
    `navigator.mediaDevices.enumerateDevices()` directly and doesn't need
    this). Returns an empty list rather than erroring when `sounddevice`
    isn't installed — no environment this app targets is guaranteed to
    have it, and an empty device list is a legitimate, handleable UI state."""
    try:
        import sounddevice as sd  # noqa: F401 — optional dependency
    except ImportError:
        return []

    try:
        devices = sd.query_devices()
        default_input = sd.default.device[0]
        return [
            AudioDeviceResponse(id=str(i), name=d["name"], is_default=(i == default_input))
            for i, d in enumerate(devices)
            if d.get("max_input_channels", 0) > 0
        ]
    except Exception:  # noqa: BLE001 — no audio subsystem reachable (common in containers/CI)
        return []


def _pcm16_bytes_to_float32(pcm_bytes: bytes) -> np.ndarray:
    if len(pcm_bytes) < BYTES_PER_SAMPLE:
        return np.array([], dtype=np.float32)
    ints = np.frombuffer(pcm_bytes, dtype=np.int16)
    return (ints.astype(np.float32) / 32768.0).copy()


@router.websocket("/vad/status")
async def vad_status_stream(websocket: WebSocket, vad: VAD = Depends(get_vad)) -> None:
    """Client sends binary PCM16 frames (ideally 480 samples / 30ms each,
    matching vad.SAMPLES_PER_CHUNK); server replies with one JSON VADResult
    per frame received."""
    await websocket.accept()
    timestamp_ms = 0
    try:
        while True:
            data = await websocket.receive_bytes()
            samples = _pcm16_bytes_to_float32(data)
            result = vad.process_chunk(samples, timestamp_ms=timestamp_ms)
            timestamp_ms += 30
            await websocket.send_json(
                {
                    "is_speech": result.is_speech,
                    "probability": result.probability,
                    "timestamp_ms": result.timestamp_ms,
                }
            )
    except WebSocketDisconnect:
        logger.debug("VAD status client disconnected")


@router.websocket("/stt/stream")
async def stt_stream(websocket: WebSocket, stt: WhisperSTT = Depends(get_stt)) -> None:
    """Client sends binary PCM16 audio frames; server replies with one JSON
    TranscriptionSegment message per buffered window (see
    WhisperSTT.transcribe_stream), and a final `{"error": ...}` message
    instead of crashing the socket if the tier's model isn't available."""
    await websocket.accept()

    async def receive_chunks():
        while True:
            try:
                yield await websocket.receive_bytes()
            except WebSocketDisconnect:
                return

    try:
        async for segment in stt.transcribe_stream(receive_chunks()):
            await websocket.send_json(
                {
                    "text": segment.text,
                    "start_ms": segment.start_ms,
                    "end_ms": segment.end_ms,
                    "confidence": segment.confidence,
                    "is_partial": segment.is_partial,
                    "language": segment.language,
                }
            )
    except ModelNotAvailableError as err:
        await websocket.send_json({"error": str(err), "model_name": err.model_name})
    except WebSocketDisconnect:
        logger.debug("STT stream client disconnected")
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass  # already closed by the client disconnecting
