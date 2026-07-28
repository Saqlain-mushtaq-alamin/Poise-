"""
Readiness assessor (spec §8.5) — answers "am I ready for the real
interview / test?" by looking at trend and consistency across a
candidate's session history, not just their latest score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, pstdev
from typing import Optional

from app.services.scoring.llm_client import ScoringLLMClient

MIN_SESSIONS_FOR_CONFIDENT_VERDICT = 3
DEFAULT_READY_THRESHOLD = 75.0
CONSISTENCY_STDEV_THRESHOLD = 12.0  # points; above this, scores are "erratic"


@dataclass
class SessionPoint:
    session_id: str
    overall_score: float
    generated_at: str  # ISO date string, kept as-is for display


@dataclass
class ReadinessVerdict:
    verdict: str            # "ready" | "almost_ready" | "not_ready" | "insufficient_data"
    confidence: float       # 0-1
    latest_score: float
    average_score: float
    trend: str               # "improving" | "stable" | "declining"
    is_consistent: bool
    evidence: list[str] = field(default_factory=list)
    recommendation: str = ""


class ReadinessAssessor:
    def __init__(self, llm_client: Optional[ScoringLLMClient] = None):
        self.llm_client = llm_client or ScoringLLMClient()

    async def assess(
        self, history: list[SessionPoint], target_score: float = DEFAULT_READY_THRESHOLD
    ) -> ReadinessVerdict:
        if len(history) < MIN_SESSIONS_FOR_CONFIDENT_VERDICT:
            return ReadinessVerdict(
                verdict="insufficient_data",
                confidence=0.0,
                latest_score=history[-1].overall_score if history else 0.0,
                average_score=round(mean(p.overall_score for p in history), 1) if history else 0.0,
                trend="stable",
                is_consistent=True,
                evidence=[
                    f"Only {len(history)} session(s) completed — "
                    f"{MIN_SESSIONS_FOR_CONFIDENT_VERDICT} or more give a reliable readiness signal."
                ],
                recommendation="Complete a few more practice sessions before drawing conclusions.",
            )

        scores = [p.overall_score for p in history]
        latest = scores[-1]
        avg = round(mean(scores), 1)
        stdev = pstdev(scores) if len(scores) > 1 else 0.0
        is_consistent = stdev <= CONSISTENCY_STDEV_THRESHOLD

        trend = self._trend(scores)

        evidence = [
            f"Latest session: {latest:.0f}/100 (average across last {len(scores)}: {avg:.0f}/100)",
            f"Score trend is {trend} across your recent sessions",
            f"Score consistency: {'stable' if is_consistent else 'variable'} (spread ±{stdev:.0f} points)",
        ]

        verdict, confidence = self._verdict(latest, avg, trend, is_consistent, target_score)

        recommendation = await self._recommendation(verdict, evidence) or self._default_recommendation(verdict, trend)

        return ReadinessVerdict(
            verdict=verdict, confidence=confidence, latest_score=latest, average_score=avg,
            trend=trend, is_consistent=is_consistent, evidence=evidence, recommendation=recommendation,
        )

    def _trend(self, scores: list[float]) -> str:
        # Compare the mean of the second half to the first half — robust to
        # single-session noise, simple enough to explain to a user.
        mid = len(scores) // 2
        first_half = scores[:mid] or scores[:1]
        second_half = scores[mid:]
        delta = mean(second_half) - mean(first_half)
        if delta >= 4:
            return "improving"
        if delta <= -4:
            return "declining"
        return "stable"

    def _verdict(
        self, latest: float, avg: float, trend: str, is_consistent: bool, target: float
    ) -> tuple[str, float]:
        if latest >= target and avg >= target - 5 and is_consistent:
            return "ready", 0.9 if trend != "declining" else 0.7
        if latest >= target - 10 and (trend == "improving" or avg >= target - 10):
            return "almost_ready", 0.6
        return "not_ready", 0.75 if trend == "declining" else 0.5

    def _default_recommendation(self, verdict: str, trend: str) -> str:
        if verdict == "ready":
            return "You're consistently hitting the target range — schedule the real interview/test."
        if verdict == "almost_ready":
            return "Close to target. A few more focused sessions on your weakest dimension should get you there."
        if trend == "declining":
            return "Recent scores are trending down — consider a short break, then a focused practice session."
        return "Keep practicing with attention to your lowest-scoring dimension before scheduling the real thing."

    async def _recommendation(self, verdict: str, evidence: list[str]) -> Optional[str]:
        return await self.llm_client.readiness_recommendation("\n".join(evidence) + f"\nVerdict: {verdict}")
