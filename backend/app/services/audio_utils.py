"""WAV encoding helpers shared by every TTS backend.

Kept dependency-free (stdlib `wave` + `struct` + `math` only) so it works
identically whether the actual synthesis engine behind it is Piper, XTTS,
Edge TTS, or the placeholder tone backend used when none of those are
installed (see tts.py).
"""

from __future__ import annotations

import io
import math
import struct
import wave

SAMPLE_RATE_HZ = 22_050  # common TTS output rate; distinct from STT's 16kHz input rate
SAMPLE_WIDTH_BYTES = 2  # 16-bit PCM
CHANNELS = 1


def pcm16_to_wav_bytes(samples: list[int], sample_rate: int = SAMPLE_RATE_HZ) -> bytes:
    """Wraps raw 16-bit PCM samples in a valid WAV container."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return buffer.getvalue()


def generate_tone_samples(
    duration_seconds: float,
    frequency_hz: float = 220.0,
    sample_rate: int = SAMPLE_RATE_HZ,
    amplitude: float = 0.2,
) -> list[int]:
    """Generates a simple sine-wave tone as 16-bit PCM sample values.

    Used by the placeholder TTS backend: it is NOT synthesized speech, just
    real, valid, audible audio that proves the whole pipeline (WAV
    encoding, HTTP/WebSocket streaming, frontend decode + playback,
    barge-in interruption) works end to end without needing Piper/XTTS
    model files that can't be fetched in every environment.
    """
    n_samples = max(int(duration_seconds * sample_rate), 0)
    max_amplitude = 32767
    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        # A short fade-in/out avoids an audible click at chunk boundaries.
        fade = min(1.0, i / 200, (n_samples - i) / 200) if n_samples > 400 else 1.0
        value = amplitude * fade * math.sin(2 * math.pi * frequency_hz * t)
        samples.append(int(value * max_amplitude))
    return samples


def estimate_speech_duration_seconds(text: str, words_per_minute: int = 155) -> float:
    """Rough duration estimate so the placeholder tone's length is at least
    proportional to what real TTS would take, instead of a fixed length
    regardless of input. ~155 wpm is a typical conversational speaking rate."""
    word_count = max(len(text.split()), 1)
    return round((word_count / words_per_minute) * 60, 2)


def wav_bytes_duration_seconds(wav_bytes: bytes) -> float:
    """Reads a WAV byte string back to confirm its declared duration —
    used by tests to verify the encoder round-trips correctly."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        return round(frames / rate, 4) if rate else 0.0


def chunk_wav_pcm(samples: list[int], chunk_size: int = 4410) -> list[list[int]]:
    """Splits PCM samples into fixed-size chunks for streaming — each chunk
    is independently wrapped in its own tiny WAV header by the caller (see
    TTSEngine.synthesize_stream), matching how a real streaming TTS engine
    would hand back audio incrementally rather than all at once."""
    return [samples[i : i + chunk_size] for i in range(0, len(samples), chunk_size)]
