"""WAV encoding utilities — real audio bytes generated and validated by
reading them back with the stdlib `wave` module (no external tools)."""

from __future__ import annotations

import io
import wave

from app.services.audio_utils import (
    SAMPLE_RATE_HZ,
    chunk_wav_pcm,
    estimate_speech_duration_seconds,
    generate_tone_samples,
    pcm16_to_wav_bytes,
    wav_bytes_duration_seconds,
)


def test_generate_tone_samples_produces_correct_sample_count():
    samples = generate_tone_samples(duration_seconds=1.0, sample_rate=16000)
    assert len(samples) == 16000


def test_generate_tone_samples_stays_within_16bit_range():
    samples = generate_tone_samples(duration_seconds=0.5, amplitude=0.9)
    assert all(-32768 <= s <= 32767 for s in samples)


def test_generate_tone_samples_zero_duration_is_empty():
    assert generate_tone_samples(duration_seconds=0) == []


def test_pcm16_to_wav_bytes_produces_a_valid_wav_file():
    samples = generate_tone_samples(duration_seconds=0.2)
    wav_bytes = pcm16_to_wav_bytes(samples)

    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"

    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == SAMPLE_RATE_HZ
        assert wav_file.getnframes() == len(samples)


def test_wav_bytes_duration_matches_requested_duration():
    samples = generate_tone_samples(duration_seconds=1.5, sample_rate=16000)
    wav_bytes = pcm16_to_wav_bytes(samples, sample_rate=16000)

    assert abs(wav_bytes_duration_seconds(wav_bytes) - 1.5) < 0.01


def test_estimate_speech_duration_scales_with_word_count():
    short = estimate_speech_duration_seconds("Hello there")
    long = estimate_speech_duration_seconds(" ".join(["word"] * 100))
    assert long > short
    assert short > 0


def test_estimate_speech_duration_handles_empty_text():
    assert estimate_speech_duration_seconds("") > 0  # treated as 1 word, not zero-division


def test_chunk_wav_pcm_splits_into_expected_sizes():
    samples = list(range(10000))
    chunks = chunk_wav_pcm(samples, chunk_size=4410)
    assert len(chunks) == 3
    assert len(chunks[0]) == 4410
    assert len(chunks[-1]) == 10000 - 2 * 4410
    assert sum(len(c) for c in chunks) == len(samples)


def test_chunk_wav_pcm_each_chunk_is_a_valid_wav_when_wrapped():
    samples = generate_tone_samples(duration_seconds=1.0)
    for chunk in chunk_wav_pcm(samples, chunk_size=4410):
        wav_bytes = pcm16_to_wav_bytes(chunk)
        assert wav_bytes[:4] == b"RIFF"
