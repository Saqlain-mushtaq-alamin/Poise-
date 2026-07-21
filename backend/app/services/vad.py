"""Voice Activity Detection.

Two implementations behind one interface (`VAD`):

- `EnergyVAD` — real, dependency-free (numpy only) signal processing:
  RMS energy + zero-crossing rate against an adaptive noise floor. This is
  what actually runs today, and it's genuinely functional, not a stub — it
  correctly classifies the synthetic speech/silence fixtures in
  tests/test_vad.py.
- `SileroVAD` — the more accurate model-based approach from the Phase 3
  spec. It lazy-imports `torch` + downloads the Silero model on first use,
  neither of which is available in every deployment/dev environment (no
  GPU-heavy `torch` install, no network route to the model host). It's
  written to the same `VAD` interface so swapping the default is a one-line
  change in `get_vad()` once torch is an accepted dependency — but it is
  NOT exercised by any test that requires torch to actually be installed.

Both operate on 16kHz mono PCM16 chunks (matching the Web Audio capture
pipeline's `sampleRate: 16000` config in MicCapture.ts), sized to the
30ms-per-chunk cadence the spec calls out (480 samples at 16kHz).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

CHUNK_MS = 30
SAMPLE_RATE_HZ = 16_000
SAMPLES_PER_CHUNK = int(SAMPLE_RATE_HZ * CHUNK_MS / 1000)  # 480

# Tuned against tests/test_vad.py's synthetic tone-vs-silence fixtures, not
# against real recorded speech — treat these as a starting point, not a
# calibrated production threshold. A real deployment should let the
# Settings UI's "noise gate sensitivity" slider (Phase 3 spec §3.7) adjust
# this at runtime rather than trusting a single constant.
DEFAULT_ENERGY_THRESHOLD = 0.02
DEFAULT_ZCR_MAX = 0.35  # above this, treat high-energy signal as noise/hiss


@dataclass
class VADResult:
    is_speech: bool
    probability: float
    timestamp_ms: int


class VAD(Protocol):
    def process_chunk(self, audio_chunk: np.ndarray, timestamp_ms: int) -> VADResult: ...

    def reset(self) -> None: ...


def _rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(samples))))


def _zero_crossing_rate(samples: np.ndarray) -> float:
    if samples.size < 2:
        return 0.0
    signs = np.sign(samples)
    signs[signs == 0] = 1
    crossings = np.count_nonzero(np.diff(signs))
    return crossings / (samples.size - 1)


class EnergyVAD:
    """RMS energy + zero-crossing-rate VAD with an adaptive noise floor.

    Expects float32 PCM samples in [-1.0, 1.0], matching what the frontend
    worklet hands to `AudioWorkletNode` (Web Audio's native format) — the
    WebSocket endpoint (see routers/voice.py) converts incoming int16 bytes
    to this range before calling `process_chunk`.
    """

    def __init__(
        self,
        energy_threshold: float = DEFAULT_ENERGY_THRESHOLD,
        zcr_max: float = DEFAULT_ZCR_MAX,
        noise_floor_alpha: float = 0.05,
    ) -> None:
        self.energy_threshold = energy_threshold
        self.zcr_max = zcr_max
        self._noise_floor_alpha = noise_floor_alpha
        self._noise_floor = 0.0

    def process_chunk(self, audio_chunk: np.ndarray, timestamp_ms: int) -> VADResult:
        energy = _rms(audio_chunk)
        zcr = _zero_crossing_rate(audio_chunk)

        effective_threshold = max(self.energy_threshold, self._noise_floor * 2.5)
        is_speech = bool(energy > effective_threshold and zcr < self.zcr_max)

        # Only adapt the noise floor from chunks we believe are silence, so
        # a long, loud utterance doesn't drag the floor upward and desensitize us.
        if not is_speech:
            self._noise_floor = (
                1 - self._noise_floor_alpha
            ) * self._noise_floor + self._noise_floor_alpha * energy

        probability = min(energy / (effective_threshold * 2), 1.0) if effective_threshold else 0.0
        return VADResult(
            is_speech=is_speech, probability=round(probability, 4), timestamp_ms=timestamp_ms
        )

    def reset(self) -> None:
        self._noise_floor = 0.0


class SileroVAD:
    """Model-based VAD — see module docstring. Not used by default; not
    covered by any test that requires `torch` to be installed."""

    def __init__(self) -> None:
        self._model = None

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        import torch  # noqa: F401 — intentionally lazy; heavy optional dependency

        model, _utils = torch.hub.load("snakers4/silero-vad", "silero_vad")
        self._model = model
        return model

    def process_chunk(self, audio_chunk: np.ndarray, timestamp_ms: int) -> VADResult:
        import torch

        model = self._ensure_model()
        tensor = torch.from_numpy(audio_chunk.astype(np.float32))
        probability = float(model(tensor, SAMPLE_RATE_HZ).item())
        return VADResult(
            is_speech=bool(probability > 0.5), probability=probability, timestamp_ms=timestamp_ms
        )

    def reset(self) -> None:
        pass


def get_vad() -> VAD:
    """Returns the VAD implementation actually used by the app today.
    Swap this to `SileroVAD()` once torch is an accepted dependency and a
    model-download story exists for offline installs."""
    return EnergyVAD()
