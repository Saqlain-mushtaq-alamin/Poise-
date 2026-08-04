"""Text-to-speech.

`TTSEngine` picks a backend per the Phase 3 spec's tier table and exposes
one streaming interface regardless of which backend answers:

| Backend  | Tier                  | Status here                                       |
|----------|-----------------------|----------------------------------------------------|
| Piper    | All tiers (default)   | Lazy subprocess call; needs the `piper` binary +  |
|          |                       | a voice model on disk — neither is bundled, so    |
|          |                       | this raises `TTSBackendUnavailable` here.         |
| XTTS-v2  | Local Full            | Lazy `TTS` (coqui-tts) import; needs torch + a    |
|          |                       | multi-GB model download — same story.             |
| Edge TTS | Cloud Assist fallback | Lazy `edge_tts` import; needs network access to   |
|          |                       | Microsoft's endpoint.                              |
| Placeholder tone | Automatic fallback | **Actually works, right now, dependency-free.**  |
|          |                       | Generates real, valid, audible WAV audio scaled to |
|          |                       | the text's estimated speech duration — not real   |
|          |                       | synthesized speech, but genuine audio proving the  |
|          |                       | encoding/streaming/playback/barge-in pipeline.     |

`synthesize_stream` always falls back to the placeholder tone if the
tier-appropriate backend can't run, rather than raising — a broken/missing
TTS backend shouldn't block someone from testing the rest of the app. The
one exception is `list_voices`, which reports what's *actually* available
so the Settings UI can show honest status instead of pretending Piper
voices exist when Piper isn't installed.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from app.services.audio_utils import (
    chunk_wav_pcm,
    estimate_speech_duration_seconds,
    generate_tone_samples,
    pcm16_to_wav_bytes,
)
from app.services.tier import HardwareTier

logger = logging.getLogger("poise.tts")

TIER_BACKEND_MAP = {
    HardwareTier.LOCAL_FULL: "xtts-v2",
    HardwareTier.LOCAL_LITE: "piper",
    HardwareTier.CLOUD_ASSIST: "edge-tts",
}

PLACEHOLDER_VOICE_ID = "placeholder-tone"


class TTSBackendUnavailable(RuntimeError):
    """Raised by list_voices()/a specific backend probe when the real
    engine for the current tier isn't installed/reachable. Never raised
    from synthesize_stream(), which always has the placeholder fallback."""


@dataclass
class VoiceInfo:
    id: str
    name: str
    language: str
    gender: str
    sample_url: str | None = None


_PLACEHOLDER_VOICE = VoiceInfo(
    id=PLACEHOLDER_VOICE_ID,
    name="Placeholder tone (no TTS engine installed)",
    language="n/a",
    gender="n/a",
    sample_url=None,
)


class TTSEngine:
    def __init__(self, tier: HardwareTier = HardwareTier.CLOUD_ASSIST) -> None:
        self._tier = tier

    def set_tier(self, tier: HardwareTier) -> None:
        self._tier = tier

    @property
    def backend_name(self) -> str:
        return TIER_BACKEND_MAP[self._tier]

    def _probe_piper(self) -> bool:
        import shutil

        return shutil.which("piper") is not None

    def _probe_xtts(self) -> bool:
        try:
            import TTS  # noqa: F401  — coqui-tts package, imports as `TTS`
        except ImportError:
            return False
        return True

    def _probe_edge_tts(self) -> bool:
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False
        return True

    def _backend_available(self) -> bool:
        probes = {
            "piper": self._probe_piper,
            "xtts-v2": self._probe_xtts,
            "edge-tts": self._probe_edge_tts,
        }
        return probes[self.backend_name]()

    def list_voices(self) -> list[VoiceInfo]:
        if not self._backend_available():
            return [_PLACEHOLDER_VOICE]

        if self.backend_name == "piper":
            return self._list_piper_voices()
        if self.backend_name == "xtts-v2":
            return self._list_xtts_voices()
        return self._list_edge_voices()

    def _list_piper_voices(self) -> list[VoiceInfo]:  # pragma: no cover — needs the piper binary
        raise TTSBackendUnavailable("Piper voice enumeration not implemented for this build")

    def _list_xtts_voices(self) -> list[VoiceInfo]:  # pragma: no cover — needs coqui-tts + model
        raise TTSBackendUnavailable("XTTS voice enumeration not implemented for this build")

    def _list_edge_voices(self) -> list[VoiceInfo]:
        try:
            import asyncio
            import concurrent.futures
            import edge_tts

            async def _fetch() -> list[VoiceInfo]:
                raw = await edge_tts.list_voices()
                res: list[VoiceInfo] = []
                for v in raw:
                    locale = v.get("Locale", "")
                    short_name = v.get("ShortName", "")
                    friendly = v.get("FriendlyName", short_name)
                    gender = v.get("Gender", "female").lower()
                    if locale.startswith("en-"):
                        res.append(
                            VoiceInfo(
                                id=short_name,
                                name=friendly,
                                language=locale,
                                gender=gender,
                            )
                        )
                return res or [_PLACEHOLDER_VOICE]

            try:
                loop = asyncio.get_running_loop()
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(lambda: asyncio.run(_fetch())).result(timeout=4)
            except RuntimeError:
                return asyncio.run(_fetch())
        except Exception as e:
            logger.warning("Failed to fetch Edge TTS voices: %s", e)
            return [_PLACEHOLDER_VOICE]

    async def synthesize_stream(
        self, text: str, voice: str = "default", chunk_samples: int = 4410
    ) -> AsyncGenerator[bytes, None]:
        """Yields audio byte chunks. Uses Edge TTS if available and requested,
        falling back to placeholder tone whenever real synthesis isn't available
        or when default/placeholder voice is selected."""
        is_edge_voice = voice and voice.startswith("en-")

        if is_edge_voice and self._probe_edge_tts():
            try:
                async for chunk in self._synthesize_edge_tts(text, voice):
                    yield chunk
                return
            except Exception:  # noqa: BLE001
                logger.exception("Edge TTS synthesis failed; falling back to placeholder tone")

        if self._backend_available() and is_edge_voice:
            try:
                async for chunk in self._synthesize_with_real_backend(text, voice, chunk_samples):
                    yield chunk
                return
            except Exception:  # noqa: BLE001
                logger.exception(
                    "TTS backend %s failed; falling back to placeholder tone", self.backend_name
                )

        async for chunk in self._synthesize_placeholder(text or " ", chunk_samples):
            yield chunk

    async def _synthesize_edge_tts(self, text: str, voice: str) -> AsyncGenerator[bytes, None]:
        import edge_tts

        edge_voice = (
            voice
            if voice and voice != "default" and voice != PLACEHOLDER_VOICE_ID
            else "en-US-AvaNeural"
        )
        communicate = edge_tts.Communicate(text, edge_voice)
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                yield chunk["data"]

    async def _synthesize_with_real_backend(
        self, text: str, voice: str, chunk_samples: int
    ) -> AsyncGenerator[bytes, None]:  # pragma: no cover — needs a real installed backend
        raise TTSBackendUnavailable(f"{self.backend_name} synthesis not implemented for this build")
        yield b""  # pragma: no cover — makes this an async generator for type-checkers

    async def _synthesize_placeholder(
        self, text: str, chunk_samples: int
    ) -> AsyncGenerator[bytes, None]:
        duration = estimate_speech_duration_seconds(text)
        samples = generate_tone_samples(duration_seconds=duration)
        for chunk in chunk_wav_pcm(samples, chunk_size=chunk_samples):
            yield pcm16_to_wav_bytes(chunk)

    async def synthesize_complete(self, text: str, voice: str = "default") -> bytes:
        """Returns a single, browser-decodable audio blob for the full text.

        - Edge TTS path: collects raw MP3/OGG data as-is (content type is
          handled by the caller) — this is already a valid MP3 stream.
        - Placeholder path: generates one full WAV (not chunked) so the
          browser can decode it without issues.

        Use this for HTTP (non-streaming) responses. Use `synthesize_stream`
        for WebSocket streaming where chunks are played progressively.
        """
        is_edge_voice = voice and voice.startswith("en-")

        # Edge TTS — concatenate raw audio bytes (MP3 format, not WAV)
        if is_edge_voice and self._probe_edge_tts():
            try:
                chunks: list[bytes] = []
                async for chunk in self._synthesize_edge_tts(text, voice):
                    chunks.append(chunk)
                if chunks:
                    return b"".join(chunks)
            except Exception:  # noqa: BLE001
                logger.exception("Edge TTS complete synthesis failed; falling back")

        # Placeholder — generate a single full WAV (not split into chunks)
        duration = estimate_speech_duration_seconds(text or " ")
        samples = generate_tone_samples(duration_seconds=duration)
        return pcm16_to_wav_bytes(samples)


_engine_instance = TTSEngine()


def get_tts_engine() -> TTSEngine:
    return _engine_instance
