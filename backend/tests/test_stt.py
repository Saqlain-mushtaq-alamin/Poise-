"""WhisperSTT: tier-to-model mapping, the honest "model not available"
fallback (genuinely triggered — faster-whisper isn't installed in this
environment), and the streaming/complete orchestration logic with the
underlying model mocked out."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.stt import ModelNotAvailableError, WhisperSTT
from app.services.tier import HardwareTier


def test_model_name_matches_tier_table():
    assert WhisperSTT(HardwareTier.LOCAL_FULL).model_name == "large-v3"
    assert WhisperSTT(HardwareTier.LOCAL_LITE).model_name == "base"
    assert WhisperSTT(HardwareTier.CLOUD_ASSIST).model_name == "tiny"


def test_set_tier_updates_model_name():
    stt = WhisperSTT(HardwareTier.CLOUD_ASSIST)
    stt.set_tier(HardwareTier.LOCAL_FULL)
    assert stt.model_name == "large-v3"


@pytest.mark.asyncio
async def test_transcribe_complete_raises_clear_error_when_model_unavailable():
    # faster-whisper genuinely isn't installed here — this is the real
    # fallback path, not a simulated one.
    stt = WhisperSTT(HardwareTier.CLOUD_ASSIST)
    with pytest.raises(ModelNotAvailableError) as exc_info:
        await stt.transcribe_complete(Path("/tmp/does-not-matter.wav"))

    assert "tiny" in str(exc_info.value)
    assert "Settings" in str(exc_info.value)


@pytest.mark.asyncio
async def test_transcribe_stream_raises_immediately_when_model_unavailable():
    stt = WhisperSTT(HardwareTier.LOCAL_LITE)

    async def one_chunk():
        yield b"\x00\x00" * 100

    with pytest.raises(ModelNotAvailableError):
        async for _ in stt.transcribe_stream(one_chunk()):
            pass


def _fake_word(word, start, end, prob=0.95):
    return SimpleNamespace(word=word, start=start, end=end, probability=prob)


def _fake_segment(text, start, end, words=None, avg_logprob=-0.2):
    return SimpleNamespace(
        text=text, start=start, end=end, words=words or [], avg_logprob=avg_logprob
    )


@pytest.mark.asyncio
async def test_transcribe_complete_assembles_segments_and_words(monkeypatch):
    stt = WhisperSTT(HardwareTier.LOCAL_FULL)

    fake_model = MagicMock()
    fake_info = SimpleNamespace(language="en")
    fake_segments = [
        _fake_segment(
            "Hello there",
            0.0,
            1.2,
            words=[_fake_word("Hello", 0.0, 0.5), _fake_word("there", 0.5, 1.2)],
        ),
        _fake_segment("How are you", 1.3, 2.5),
    ]
    fake_model.transcribe.return_value = (fake_segments, fake_info)
    monkeypatch.setattr(stt, "_load_model", lambda: fake_model)

    result = await stt.transcribe_complete(Path("/tmp/fake.wav"))

    assert result.text == "Hello there How are you"
    assert result.language == "en"
    assert len(result.segments) == 2
    assert result.segments[0].words[0].word == "Hello"
    assert result.segments[0].words[0].end_ms == 500
    assert result.duration_ms == 2500
    assert all(not s.is_partial for s in result.segments)


@pytest.mark.asyncio
async def test_transcribe_stream_buffers_and_yields_partial_then_final(monkeypatch):
    stt = WhisperSTT(HardwareTier.CLOUD_ASSIST)

    fake_model = MagicMock()
    fake_info = SimpleNamespace(language="en")

    call_count = {"n": 0}

    def fake_transcribe(audio, word_timestamps=False):
        call_count["n"] += 1
        text = "partial result" if call_count["n"] == 1 else "final result"
        return ([_fake_segment(text, 0.0, 1.0)], fake_info)

    fake_model.transcribe.side_effect = fake_transcribe
    monkeypatch.setattr(stt, "_load_model", lambda: fake_model)

    # 2 seconds of PCM16 mono @16kHz = 64000 bytes triggers the first
    # partial flush at the default buffer_seconds=2.0 threshold.
    async def chunks():
        yield b"\x00\x00" * 32000  # 64000 bytes -> crosses threshold -> partial
        yield b"\x00\x00" * 100  # small tail -> final flush at stream end

    results = [seg async for seg in stt.transcribe_stream(chunks(), buffer_seconds=2.0)]

    assert len(results) == 2
    assert results[0].is_partial is True
    assert results[0].text == "partial result"
    assert results[1].is_partial is False
    assert results[1].text == "final result"


@pytest.mark.asyncio
async def test_transcribe_stream_skips_empty_segments(monkeypatch):
    stt = WhisperSTT(HardwareTier.CLOUD_ASSIST)
    fake_model = MagicMock()
    fake_model.transcribe.return_value = ([], SimpleNamespace(language="en"))
    monkeypatch.setattr(stt, "_load_model", lambda: fake_model)

    async def chunks():
        yield b"\x00\x00" * 100

    results = [seg async for seg in stt.transcribe_stream(chunks())]
    assert results == []


def test_is_model_loaded_false_initially():
    stt = WhisperSTT()
    assert stt.is_model_loaded() is False
