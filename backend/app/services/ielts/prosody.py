"""
Prosody analyzer — pace, pauses, filler words, and intonation variety.

Uses `librosa` for pitch (f0) extraction when available (real signal
analysis on the actual audio). Falls back to transcript-only heuristics
(no pitch data) if `librosa`/audio decoding isn't available, so filler-word
and pace metrics — which only need the transcript + word timestamps — are
always returned even without full audio access.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, pstdev

logger = logging.getLogger(__name__)

try:
    import librosa
    import numpy as np

    _LIBROSA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LIBROSA_AVAILABLE = False

FILLER_PATTERNS = ["um", "uh", "erm", "like", "you know", "sort of", "kind of", "basically"]

WPM_TOO_SLOW = 110
WPM_TOO_FAST = 190


@dataclass
class WordTimestamp:
    word: str
    start_s: float
    end_s: float


@dataclass
class FillerWord:
    text: str
    timestamp_s: float


@dataclass
class PauseEvent:
    start_s: float
    duration_s: float


@dataclass
class PauseAnalysis:
    total_pause_time_s: float
    avg_pause_duration_s: float
    long_pauses: list[PauseEvent] = field(default_factory=list)  # >2s
    natural_pauses: int = 0     # at sentence/clause boundaries
    unnatural_pauses: int = 0   # mid-sentence hesitations


@dataclass
class ProsodyAnalysis:
    speaking_rate_wpm: float
    pace_assessment: str          # "too_fast" | "good" | "too_slow"
    pause_analysis: PauseAnalysis
    filler_words: list[FillerWord] = field(default_factory=list)
    filler_ratio: float = 0.0
    intonation_variety: float = 0.0   # 0-1, pitch range variance


class ProsodyAnalyzer:
    async def analyze(
        self,
        audio_path: Path,
        transcript: str,
        word_timestamps: list[WordTimestamp] | None = None,
    ) -> ProsodyAnalysis:
        words = re.findall(r"[a-zA-Z']+", transcript.lower())
        word_count = len(words)

        # If the caller (STT service, from Phase 3) didn't supply
        # timestamps, fabricate evenly-spaced ones from audio duration so
        # pause detection degrades gracefully instead of crashing.
        duration_s = self._get_duration_s(audio_path) or max(1.0, word_count / 2.5)
        if not word_timestamps:
            word_timestamps = self._even_timestamps(words, duration_s)

        speaking_rate_wpm = (word_count / duration_s) * 60 if duration_s else 0.0
        pace_assessment = self._assess_pace(speaking_rate_wpm)

        pause_analysis = self._analyze_pauses(word_timestamps, transcript)
        filler_words = self._find_fillers(transcript, word_timestamps)
        filler_ratio = len(filler_words) / word_count if word_count else 0.0

        intonation_variety = (
            self._pitch_variance(audio_path) if _LIBROSA_AVAILABLE else self._synthetic_intonation(transcript)
        )

        return ProsodyAnalysis(
            speaking_rate_wpm=round(speaking_rate_wpm, 1),
            pace_assessment=pace_assessment,
            pause_analysis=pause_analysis,
            filler_words=filler_words,
            filler_ratio=round(filler_ratio, 3),
            intonation_variety=round(intonation_variety, 2),
        )

    # -- helpers -------------------------------------------------------------

    def _get_duration_s(self, audio_path: Path) -> float | None:
        if not audio_path or not Path(audio_path).exists():
            return None
        if _LIBROSA_AVAILABLE:
            try:
                return float(librosa.get_duration(path=str(audio_path)))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not read audio duration: %s", exc)
        return None

    def _even_timestamps(self, words: list[str], duration_s: float) -> list[WordTimestamp]:
        if not words:
            return []
        step = duration_s / len(words)
        return [
            WordTimestamp(word=w, start_s=i * step, end_s=(i + 1) * step)
            for i, w in enumerate(words)
        ]

    def _assess_pace(self, wpm: float) -> str:
        if wpm < WPM_TOO_SLOW:
            return "too_slow"
        if wpm > WPM_TOO_FAST:
            return "too_fast"
        return "good"

    def _analyze_pauses(self, timestamps: list[WordTimestamp], transcript: str) -> PauseAnalysis:
        if len(timestamps) < 2:
            return PauseAnalysis(total_pause_time_s=0.0, avg_pause_duration_s=0.0)

        boundary_words = {".", "!", "?", ","}
        pauses: list[PauseEvent] = []
        natural, unnatural = 0, 0

        for i in range(1, len(timestamps)):
            gap = timestamps[i].start_s - timestamps[i - 1].end_s
            if gap <= 0.25:
                continue
            pauses.append(PauseEvent(start_s=timestamps[i - 1].end_s, duration_s=round(gap, 2)))
            preceding = timestamps[i - 1].word
            if any(preceding.endswith(b) for b in boundary_words) or gap > 1.0 and i == len(timestamps) - 1:
                natural += 1
            else:
                unnatural += 1

        long_pauses = [p for p in pauses if p.duration_s > 2.0]
        total = sum(p.duration_s for p in pauses)
        avg = total / len(pauses) if pauses else 0.0

        return PauseAnalysis(
            total_pause_time_s=round(total, 2),
            avg_pause_duration_s=round(avg, 2),
            long_pauses=long_pauses,
            natural_pauses=natural,
            unnatural_pauses=unnatural,
        )

    def _find_fillers(self, transcript: str, timestamps: list[WordTimestamp]) -> list[FillerWord]:
        lower = transcript.lower()
        found: list[FillerWord] = []
        for pattern in FILLER_PATTERNS:
            for match in re.finditer(rf"\b{re.escape(pattern)}\b", lower):
                # locate approximate timestamp via word index
                idx = lower[: match.start()].count(" ")
                ts = timestamps[idx].start_s if idx < len(timestamps) else 0.0
                found.append(FillerWord(text=pattern, timestamp_s=round(ts, 2)))
        return sorted(found, key=lambda f: f.timestamp_s)

    def _pitch_variance(self, audio_path: Path) -> float:
        try:
            y, sr = librosa.load(str(audio_path), sr=None)
            f0, voiced_flag, _ = librosa.pyin(
                y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7")
            )
            voiced = f0[voiced_flag] if voiced_flag is not None else f0[~np.isnan(f0)]
            voiced = voiced[~np.isnan(voiced)]
            if len(voiced) < 5:
                return 0.5
            normalized_std = pstdev(voiced.tolist()) / max(1.0, mean(voiced.tolist()))
            return max(0.0, min(1.0, normalized_std * 2.5))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Pitch analysis failed, using neutral estimate: %s", exc)
            return 0.5

    def _synthetic_intonation(self, transcript: str) -> float:
        """No-audio fallback: reward varied sentence types as a weak proxy."""
        sentence_enders = len(re.findall(r"[.!?]", transcript))
        words = max(1, len(transcript.split()))
        variety = min(1.0, (sentence_enders / words) * 8)
        return max(0.3, variety)
