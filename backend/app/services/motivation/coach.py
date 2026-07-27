"""10.4 — Weekly coach summary.

Uses the shared `ModelProviderRouter` from Phase 2, so this works the same
whether the user is on Local Full, Local Lite, or Cloud Assist — it never
touches litellm directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models.motivation import WeeklyCoachSummary as WeeklyCoachSummaryRow
from app.schemas.motivation import CoachSummary
from app.services.motivation._integration import get_recent_score_points
from app.services.provider import ModelProviderRouter, ModelRole  # Phase 2

COACH_SYSTEM_PROMPT = """You are an encouraging, specific interview-practice coach. \
Write a short weekly progress digest (120-180 words) for the user, in second person, \
warm but not saccharine. Reference actual numbers you're given. Never invent data. \
Never use generic filler like "keep up the good work" without pointing to something specific. \
End with one concrete thing to focus on next week."""


@dataclass
class _WeekTrends:
    score_direction: str
    weakest_dimensions: list[str]
    improvements: list[str]


class WeeklyCoach:
    def __init__(self, db: DBSession, provider: ModelProviderRouter):
        self.db = db
        self.provider = provider

    async def generate_summary(self, week_start: date, force_refresh: bool = False) -> CoachSummary:
        cached = self.db.execute(
            select(WeeklyCoachSummaryRow).where(WeeklyCoachSummaryRow.week_start == week_start)
        ).scalars().first()
        if cached and not force_refresh:
            return self._row_to_schema(cached)

        week_end = week_start + timedelta(days=7)
        points = [
            p for p in get_recent_score_points(self.db, mode=None, limit=500)
            if week_start <= p.session_date < week_end
        ]

        trends = self._calculate_trends(points)
        practice_hours = sum(p.duration_minutes for p in points) / 60.0

        if points:
            prompt = self._build_coach_prompt(points, trends, practice_hours)
            narrative = await self.provider.chat(
                messages=[
                    {"role": "system", "content": COACH_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model_role=ModelRole.REASONING,
                stream=False,
            )
            narrative = self._extract_text(narrative)
        else:
            narrative = (
                "No sessions logged this week. Even one 15-minute practice session "
                "keeps your streak alive and your skills sharp — pick a weak area "
                "from your last report and knock it out."
            )

        row = WeeklyCoachSummaryRow(
            week_start=week_start,
            sessions_count=len(points),
            practice_time_hours=round(practice_hours, 2),
            score_trend=trends.score_direction,
            narrative=narrative,
            focus_areas=json.dumps(trends.weakest_dimensions),
            celebration=json.dumps(trends.improvements),
            next_week_plan=json.dumps(self._suggest_next_week(trends)),
            generated_at=datetime.utcnow(),
        )
        if cached:
            for field in ("sessions_count", "practice_time_hours", "score_trend",
                           "narrative", "focus_areas", "celebration", "next_week_plan", "generated_at"):
                setattr(cached, field, getattr(row, field))
            row = cached
        else:
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._row_to_schema(row)

    # -- internals -----------------------------------------------------------

    def _calculate_trends(self, points) -> _WeekTrends:
        if len(points) < 2:
            direction = "no_data" if not points else "stable"
        else:
            ordered = sorted(points, key=lambda p: p.session_date)
            first_half = ordered[: len(ordered) // 2] or ordered[:1]
            second_half = ordered[len(ordered) // 2:] or ordered[-1:]
            delta = (
                sum(p.overall_score for p in second_half) / len(second_half)
                - sum(p.overall_score for p in first_half) / len(first_half)
            )
            direction = "improving" if delta > 2 else "declining" if delta < -2 else "stable"

        weakest = sorted(
            (p for p in points if p.weakest_dimension),
            key=lambda p: p.weakest_dimension_score or 100,
        )
        weakest_dims = list(dict.fromkeys(p.weakest_dimension for p in weakest))[:3]

        improvements = []
        if len(points) >= 2:
            ordered = sorted(points, key=lambda p: p.session_date)
            if ordered[-1].overall_score > ordered[0].overall_score:
                improvements.append(
                    f"Overall score moved from {ordered[0].overall_score:.0f} to {ordered[-1].overall_score:.0f}"
                )

        return _WeekTrends(score_direction=direction, weakest_dimensions=weakest_dims, improvements=improvements)

    def _build_coach_prompt(self, points, trends: _WeekTrends, practice_hours: float) -> str:
        scores = ", ".join(f"{p.overall_score:.0f}" for p in sorted(points, key=lambda p: p.session_date))
        return (
            f"This week: {len(points)} sessions, {practice_hours:.1f} practice hours.\n"
            f"Scores in chronological order: {scores}.\n"
            f"Trend: {trends.score_direction}.\n"
            f"Weakest areas: {', '.join(trends.weakest_dimensions) or 'none identified'}.\n"
            f"Notable improvements: {', '.join(trends.improvements) or 'none yet'}.\n"
            "Write the weekly digest now."
        )

    @staticmethod
    def _suggest_next_week(trends: _WeekTrends) -> list[str]:
        if trends.weakest_dimensions:
            return [f"Focus a session on: {d}" for d in trends.weakest_dimensions[:2]]
        return ["Keep the streak going with at least 3 sessions"]

    @staticmethod
    def _extract_text(response) -> str:
        if isinstance(response, str):
            return response.strip()
        # LiteLLM-style response object fallback
        try:
            return response.choices[0].message.content.strip()
        except AttributeError:
            return str(response).strip()

    @staticmethod
    def _row_to_schema(row: WeeklyCoachSummaryRow) -> CoachSummary:
        return CoachSummary(
            week_start=row.week_start,
            sessions_count=row.sessions_count,
            practice_time_hours=row.practice_time_hours,
            score_trend=row.score_trend,
            narrative=row.narrative,
            focus_areas=json.loads(row.focus_areas or "[]"),
            celebration=json.loads(row.celebration or "[]"),
            next_week_plan=json.loads(row.next_week_plan or "[]"),
            generated_at=row.generated_at,
        )
