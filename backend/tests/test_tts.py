"""TTSEngine: tier-to-backend mapping, honest voice-availability reporting,
and the placeholder-tone fallback that actually produces valid audio."""

from __future__ import annotations

import io
import wave

import pytest

from app.services.tier import HardwareTier
from app.services.tts import PLACEHOLDER_VOICE_ID, TTSEngine


def test_backend_name_matches_tier_table():
    assert TTSEngine(HardwareTier.LOCAL_FULL).backend_name == "xtts-v2"
    assert TTSEngine(HardwareTier.LOCAL_LITE).backend_name == "piper"
    assert TTSEngine(HardwareTier.CLOUD_ASSIST).backend_name == "edge-tts"


def test_set_tier_updates_backend_name():
    engine = TTSEngine(HardwareTier.CLOUD_ASSIST)
    engine.set_tier(HardwareTier.LOCAL_FULL)
    assert engine.backend_name == "xtts-v2"


def test_list_voices_reports_placeholder_when_no_real_backend_installed():
    # None of piper/xtts/edge-tts are installed in this environment, so this
    # exercises the real, honest fallback path — not a mock.
    engine = TTSEngine(HardwareTier.LOCAL_LITE)
    voices = engine.list_voices()
    assert len(voices) == 1
    assert voices[0].id == PLACEHOLDER_VOICE_ID


@pytest.mark.asyncio
async def test_synthesize_stream_yields_valid_wav_chunks():
    engine = TTSEngine(HardwareTier.CLOUD_ASSIST)
    chunks = [chunk async for chunk in engine.synthesize_stream("Hello, this is a test.")]

    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk[:4] == b"RIFF"
        with wave.open(io.BytesIO(chunk), "rb") as wav_file:
            assert wav_file.getnchannels() == 1


@pytest.mark.asyncio
async def test_synthesize_stream_duration_scales_with_text_length():
    engine = TTSEngine(HardwareTier.CLOUD_ASSIST)

    short_chunks = [c async for c in engine.synthesize_stream("Hi.")]
    long_text = " ".join(["word"] * 60)
    long_chunks = [c async for c in engine.synthesize_stream(long_text)]

    def total_frames(chunks: list[bytes]) -> int:
        total = 0
        for c in chunks:
            with wave.open(io.BytesIO(c), "rb") as wav_file:
                total += wav_file.getnframes()
        return total

    assert total_frames(long_chunks) > total_frames(short_chunks)


@pytest.mark.asyncio
async def test_synthesize_stream_falls_back_when_real_backend_raises(monkeypatch):
    engine = TTSEngine(HardwareTier.CLOUD_ASSIST)
    monkeypatch.setattr(engine, "_backend_available", lambda: True)

    # _synthesize_with_real_backend always raises TTSBackendUnavailable in
    # this build (see tts.py) — confirm synthesize_stream doesn't propagate
    # that, it falls back to the placeholder tone instead.
    chunks = [c async for c in engine.synthesize_stream("fallback check")]
    assert len(chunks) >= 1
    assert chunks[0][:4] == b"RIFF"


@pytest.mark.asyncio
async def test_synthesize_stream_handles_empty_text_without_crashing():
    engine = TTSEngine(HardwareTier.CLOUD_ASSIST)
    chunks = [c async for c in engine.synthesize_stream("")]
    assert len(chunks) >= 1
