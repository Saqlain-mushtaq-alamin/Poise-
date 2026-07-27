"""10.2 — Goal setting with trend-based projected-completion dates."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models.motivation import Goal as GoalRow
from app.schemas.motivation import Goal as GoalSchema
from app.services.motivation._integration import ScorePoint, get_recent_score_points

_MODE_FOR_TYPE = {
    "ielts_band": "ielts",
    "interview_score": "interview",
    "sessions_per_week": None,  # counted, not scored
}


class GoalTracker:
    def __init__(self, db: DBSession):
        self.db = db

    async def create_goal(self, goal_type: str, target: float, deadline: date | None = None) -> GoalSchema:
        starting = self._current_value(goal_type)
        row = GoalRow(
            type=goal_type,
            target_value=target,
            starting_value=starting,
            deadline=deadline,
            status="active",
            created_at=datetime.utcnow(),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_schema(row)

    async def list_goals(self) -> list[GoalSchema]:
        rows = self.db.execute(
            select(GoalRow).order_by(GoalRow.created_at.desc())
        ).scalars().all()
        return [self._to_schema(r) for r in rows]

    async def update_progress(self, session_id: str) -> list[GoalSchema]:
        """Recalculate progress for every active goal after a session."""
        rows = self.db.execute(select(GoalRow).where(GoalRow.status == "active")).scalars().all()
        updated: list[GoalSchema] = []
        for row in rows:
            current = self._current_value(row.type)
            if self._is_target_met(row.type, current, row.target_value) and row.status == "active":
                row.status = "achieved"
                row.achieved_at = datetime.utcnow()
            updated.append(self._to_schema(row))
        self.db.commit()
        return updated

    async def get_projections(self) -> list[GoalSchema]:
        return await self.list_goals()

    async def get_goal(self, goal_id: str) -> GoalSchema | None:
        row = self.db.get(GoalRow, goal_id)
        return self._to_schema(row) if row else None

    # -- internals ------------------------------------------------------

    def _current_value(self, goal_type: str) -> float:
        if goal_type == "sessions_per_week":
            week_start = date.today() - timedelta(days=date.today().weekday())
            points = get_recent_score_points(self.db, mode=None, limit=500)
            return float(len({p.session_id for p in points if p.session_date >= week_start}))

        mode = _MODE_FOR_TYPE.get(goal_type)
        points = get_recent_score_points(self.db, mode=mode, limit=1)
        if not points:
            return 0.0
        latest = points[0]
        if goal_type == "ielts_band":
            return latest.ielts_band or (latest.overall_score / 12.5)
        return latest.overall_score

    @staticmethod
    def _is_target_met(goal_type: str, current: float, target: float) -> bool:
        return current >= target

    def _to_schema(self, row: GoalRow) -> GoalSchema:
        current = self._current_value(row.type)
        span = max(row.target_value - row.starting_value, 1e-6)
        progress = max(0.0, min(1.0, (current - row.starting_value) / span)) * 100.0

        return GoalSchema(
            id=row.id,
            type=row.type,
            target_value=row.target_value,
            current_value=round(current, 2),
            starting_value=row.starting_value,
            deadline=row.deadline,
            created_at=row.created_at,
            status=row.status,
            progress_percent=round(progress, 1),
            projected_completion=self._project_completion(row, current),
        )

    def _project_completion(self, row: GoalRow, current: float) -> date | None:
        """Simple linear regression of score-over-time -> date the trend
        line crosses the target. Returns None if there isn't enough
        history or the trend is flat/negative."""
        if row.status == "achieved":
            return row.achieved_at.date() if row.achieved_at else date.today()
        if row.type == "sessions_per_week":
            return None  # projecting a weekly cadence goal isn't meaningful

        mode = _MODE_FOR_TYPE.get(row.type)
        points = get_recent_score_points(self.db, mode=mode, limit=30)
        points = sorted(points, key=lambda p: p.session_date)
        if len(points) < 3:
            return None

        xs = [(p.session_date - points[0].session_date).days for p in points]
        ys = [
            (p.ielts_band or p.overall_score / 12.5) if row.type == "ielts_band" else p.overall_score
            for p in points
        ]

        slope, intercept = self._linear_fit(xs, ys)
        if slope <= 1e-6:
            return None  # flat or declining trend -> no honest projection

        days_from_start_to_target = (row.target_value - intercept) / slope
        days_remaining = days_from_start_to_target - xs[-1]
        if days_remaining <= 0:
            return date.today()
        if days_remaining > 365 * 2:
            return None  # don't project multi-year timelines, it's not useful
        return date.today() + timedelta(days=round(days_remaining))

    @staticmethod
    def _linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
        n = len(xs)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        den = sum((x - mean_x) ** 2 for x in xs) or 1e-9
        slope = num / den
        intercept = mean_y - slope * mean_x
        return slope, intercept
