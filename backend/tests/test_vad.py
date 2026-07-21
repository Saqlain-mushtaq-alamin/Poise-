"""EnergyVAD tested against synthetic PCM fixtures (sine-tone "speech" vs.
low-amplitude noise "silence") — no real recorded audio or model weights
needed, since this VAD is pure signal processing."""

from __future__ import annotations

import numpy as np
import pytest

from app.services.vad import SAMPLE_RATE_HZ, SAMPLES_PER_CHUNK, EnergyVAD, get_vad


def _silence(n: int = SAMPLES_PER_CHUNK, amplitude: float = 0.001, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(n) * amplitude).astype(np.float32)


def _tone(freq_hz: float = 200.0, amplitude: float = 0.3, n: int = SAMPLES_PER_CHUNK) -> np.ndarray:
    t = np.arange(n) / SAMPLE_RATE_HZ
    return (amplitude * np.sin(2 * np.pi * freq_hz * t)).astype(np.float32)


def test_chunk_size_matches_30ms_at_16khz():
    assert SAMPLES_PER_CHUNK == 480


def test_silence_is_not_classified_as_speech():
    vad = EnergyVAD()
    result = vad.process_chunk(_silence(), timestamp_ms=0)
    assert result.is_speech is False


def test_tone_is_classified_as_speech():
    vad = EnergyVAD()
    result = vad.process_chunk(_tone(), timestamp_ms=0)
    assert result.is_speech is True
    assert result.probability > 0.5


def test_empty_chunk_is_silence():
    vad = EnergyVAD()
    result = vad.process_chunk(np.array([], dtype=np.float32), timestamp_ms=0)
    assert result.is_speech is False
    assert result.probability == 0.0


def test_high_zcr_noise_is_rejected_even_if_loud():
    # White noise has a much higher zero-crossing rate than voiced speech;
    # a loud hiss shouldn't be mistaken for speech.
    rng = np.random.default_rng(1)
    hiss = (rng.standard_normal(SAMPLES_PER_CHUNK) * 0.3).astype(np.float32)
    vad = EnergyVAD(zcr_max=0.1)  # tighten to guarantee white noise fails it
    result = vad.process_chunk(hiss, timestamp_ms=0)
    assert result.is_speech is False


def test_noise_floor_adapts_upward_during_sustained_silence():
    vad = EnergyVAD(energy_threshold=0.02)
    for i in range(50):
        vad.process_chunk(_silence(amplitude=0.01, seed=i), timestamp_ms=i * 30)

    assert vad._noise_floor > 0.0


def test_reset_clears_noise_floor():
    vad = EnergyVAD()
    for i in range(20):
        vad.process_chunk(_silence(amplitude=0.01, seed=i), timestamp_ms=i * 30)
    assert vad._noise_floor > 0.0

    vad.reset()
    assert vad._noise_floor == 0.0


def test_timestamp_is_passed_through_unchanged():
    vad = EnergyVAD()
    result = vad.process_chunk(_tone(), timestamp_ms=12345)
    assert result.timestamp_ms == 12345


@pytest.mark.parametrize("freq", [100.0, 150.0, 200.0, 250.0, 300.0])
def test_a_range_of_speech_like_tones_are_all_detected(freq):
    vad = EnergyVAD()
    result = vad.process_chunk(_tone(freq_hz=freq), timestamp_ms=0)
    assert result.is_speech is True


def test_get_vad_returns_a_working_energy_vad_by_default():
    vad = get_vad()
    assert isinstance(vad, EnergyVAD)
    assert vad.process_chunk(_tone(), timestamp_ms=0).is_speech is True
