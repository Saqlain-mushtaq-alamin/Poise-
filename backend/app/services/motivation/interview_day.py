"""10.10 — Interview Day simulation: multiple rounds, breaks, fatigue.

This service owns the *day* record and its rounds; the rounds themselves
are ordinary Phase 4 (or 6/7) sessions started back-to-back through the
existing session-start flow, with `InterviewDayRound.session_id` linking
each one back here. Scores are pulled in once each round's report exists.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models.motivation import InterviewDayRound, InterviewDaySession
from app.schemas.motivation import (
    FatigueAnalysis,
    InterviewDayConfig,
    InterviewDayReport,
    RoundComparison,
)

BREAK_PRESETS = {
    "amazon": {"total_rounds": 5, "break_duration_minutes": 5, "include_lunch_break": True},
    "google": {"total_rounds": 4, "break_duration_minutes": 10, "include_lunch_break": True},
    "meta": {"total_rounds": 4, "break_duration_minutes": 10, "include_lunch_break": False},
    "custom": {},
}


class InterviewDaySimulator:
    def __init__(self, db: DBSession):
        self.db = db

    def start(self, config: InterviewDayConfig) -> InterviewDayReport:
        preset = BREAK_PRESETS.get(config.company_format, {})
        day = InterviewDaySession(
            company_format=config.company_format,
            total_rounds=preset.get("total_rounds", config.total_rounds),
            break_duration_minutes=preset.get("break_duration_minutes", config.break_duration_minutes),
            include_lunch_break=preset.get("include_lunch_break", config.include_lunch_break),
            fatigue_tracking=config.fatigue_tracking,
            status="in_progress",
            created_at=datetime.utcnow(),
        )
        self.db.add(day)
        self.db.commit()
        self.db.refresh(day)
        return self._to_report(day)

    def attach_round_session(self, day_id: str, round_number: int, session_id: str) -> InterviewDayReport:
        self._require(day_id)
        row = self.db.execute(
            select(InterviewDayRound)
            .where(InterviewDayRound.day_id == day_id)
            .where(InterviewDayRound.round_number == round_number)
        ).scalars().first()
        if row is None:
            row = InterviewDayRound(day_id=day_id, round_number=round_number)
            self.db.add(row)
        row.session_id = session_id
        self.db.commit()
        return self.get_report(day_id)

    def record_round_scores(self, day_id: str, round_number: int, confidence_score: float, quality_score: float) -> InterviewDayReport:
        row = self.db.execute(
            select(InterviewDayRound)
            .where(InterviewDayRound.day_id == day_id)
            .where(InterviewDayRound.round_number == round_number)
        ).scalars().first()
        if row is None:
            raise ValueError(f"round {round_number} not started for day {day_id}")
        row.confidence_score = confidence_score
        row.quality_score = quality_score
        self.db.commit()

        day = self._require(day_id)
        if len(day.rounds) >= day.total_rounds and all(r.quality_score is not None for r in day.rounds):
            day.status = "completed"
            day.completed_at = datetime.utcnow()
            self.db.commit()
        return self.get_report(day_id)

    def get_report(self, day_id: str) -> InterviewDayReport:
        return self._to_report(self._require(day_id))

    # -- internals -----------------------------------------------------------

    def _require(self, day_id: str) -> InterviewDaySession:
        day = self.db.get(InterviewDaySession, day_id)
        if day is None:
            raise ValueError(f"interview day {day_id} not found")
        return day

    def _to_report(self, day: InterviewDaySession) -> InterviewDayReport:
        rounds = sorted(day.rounds, key=lambda r: r.round_number)
        scored_rounds = [r for r in rounds if r.quality_score is not None]

        fatigue = self._analyze_fatigue(scored_rounds) if day.fatigue_tracking and len(scored_rounds) >= 2 else None
        stamina = self._stamina_score(scored_rounds)
        comparison = self._round_comparison(scored_rounds)

        return InterviewDayReport(
            id=day.id,
            status=day.status,
            rounds_completed=len(scored_rounds),
            total_rounds=day.total_rounds,
            fatigue_analysis=fatigue,
            overall_verdict=self._verdict(fatigue, stamina),
            stamina_score=stamina,
            round_comparison=comparison,
        )

    @staticmethod
    def _analyze_fatigue(rounds: list[InterviewDayRound]) -> FatigueAnalysis:
        confidence = [r.confidence_score or 0.0 for r in rounds]
        quality = [r.quality_score or 0.0 for r in rounds]

        first, last = confidence[0], confidence[-1]
        drop = first - last
        if drop < 5:
            trend = "sustained"
            recommendation = "Your performance held steady across rounds — good endurance."
        elif drop < 15:
            trend = "gradual_decline"
            recommendation = (
                f"Your confidence eased from {first:.0f} to {last:.0f} across the day. "
                "Try a short breathing exercise between rounds to reset."
            )
        else:
            trend = "sharp_drop"
            worst_round = confidence.index(min(confidence)) + 1
            recommendation = (
                f"Your performance drops significantly after round {max(1, worst_round - 1)}. "
                "Practice full-day endurance runs and build in real breaks, not just pauses."
            )

        return FatigueAnalysis(
            confidence_by_round=confidence,
            quality_by_round=quality,
            energy_trend=trend,
            recommendation=recommendation,
        )

    @staticmethod
    def _stamina_score(rounds: list[InterviewDayRound]) -> float | None:
        if len(rounds) < 2:
            return None
        quality = [r.quality_score or 0.0 for r in rounds]
        # 100 = no degradation at all; scales down with the drop from best to last round
        peak = max(quality)
        last = quality[-1]
        if peak == 0:
            return None
        return round(max(0.0, 100.0 - ((peak - last) / peak) * 100.0), 1)

    @staticmethod
    def _round_comparison(rounds: list[InterviewDayRound]) -> list[RoundComparison]:
        if not rounds:
            return []
        baseline = rounds[0].confidence_score
        out = []
        for r in rounds:
            delta = None if baseline is None or r.confidence_score is None else round(r.confidence_score - baseline, 1)
            out.append(RoundComparison(
                round_number=r.round_number,
                confidence_score=r.confidence_score,
                quality_score=r.quality_score,
                delta_from_round_1=delta,
            ))
        return out

    @staticmethod
    def _verdict(fatigue: FatigueAnalysis | None, stamina: float | None) -> str:
        if fatigue is None:
            return "Not enough rounds completed yet to assess stamina."
        if fatigue.energy_trend == "sustained":
            return "You maintained performance across all rounds."
        if fatigue.energy_trend == "gradual_decline":
            return "You held up reasonably well, with some fatigue setting in by the later rounds."
        return "Fatigue significantly affected your later rounds — this is your top area to train."
