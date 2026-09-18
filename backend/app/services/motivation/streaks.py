"""10.1 — Practice streak tracking.

Streak math is computed from `motivation_practice_days`, a one-row-per-day
rollup, rather than scanning the full `sessions` table on every dashboard
load. `record_practice()` is the only writer and should be called from the
session-completion hook (Phase 4/6/7's "session finished" event) — see
`app/routers/motivation.py::_on_session_completed`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models.motivation import PracticeDay
from app.schemas.motivation import StreakData, StreakUpdate

HEATMAP_WINDOW_DAYS = 90


@dataclass
class _StreakInternal:
    current_streak_days: int
    longest_streak_days: int
    total_practice_days: int
    total_sessions: int
    total_practice_hours: float
    last_practice_date: date | None
    streak_status: str
    calendar: dict[str, int] = field(default_factory=dict)


class StreakTracker:
    def __init__(self, db: DBSession):
        self.db = db

    # -- writes ------------------------------------------------------------

    def record_practice(self, session_id: str, duration_minutes: float, on: date | None = None) -> StreakUpdate:
        """Called after every session completes."""
        practice_date = on or date.today()

        before = self._compute(reference=practice_date)

        row = self.db.get(PracticeDay, practice_date)
        if row is None:
            row = PracticeDay(practice_date=practice_date, session_count=0, practice_minutes=0.0)
            self.db.add(row)
        row.session_count += 1
        row.practice_minutes += max(0.0, duration_minutes)
        self.db.commit()

        after = self._compute(reference=practice_date)
        streak_extended = after.current_streak_days > before.current_streak_days
        new_record = after.longest_streak_days > before.longest_streak_days

        return StreakUpdate(
            streak=self._to_schema(after),
            streak_extended=streak_extended,
            new_record=new_record,
        )

    # -- reads ---------------------------------------------------------------

    def get_streak(self, today: date | None = None) -> StreakData:
        return self._to_schema(self._compute(reference=today or date.today()))

    # -- internals -------------------------------------------------------------

    def _compute(self, reference: date) -> _StreakInternal:
        rows = self.db.execute(
            select(PracticeDay).order_by(PracticeDay.practice_date.asc())
        ).scalars().all()

        if not rows:
            return _StreakInternal(0, 0, 0, 0, 0.0, None, "none", {})

        practiced_dates = {r.practice_date for r in rows}
        total_sessions = sum(r.session_count for r in rows)
        total_hours = sum(r.practice_minutes for r in rows) / 60.0
        last_date = max(practiced_dates)

        current = self._current_streak(practiced_dates, reference)
        longest = self._longest_streak(practiced_dates)

        if last_date == reference:
            status = "active"
        elif last_date == reference - timedelta(days=1):
            status = "at_risk"  # streak alive, but today isn't logged yet
        else:
            status = "broken"

        calendar = {
            r.practice_date.isoformat(): r.session_count
            for r in rows
            if r.practice_date >= reference - timedelta(days=HEATMAP_WINDOW_DAYS)
        }

        return _StreakInternal(
            current_streak_days=current,
            longest_streak_days=longest,
            total_practice_days=len(practiced_dates),
            total_sessions=total_sessions,
            total_practice_hours=round(total_hours, 2),
            last_practice_date=last_date,
            streak_status=status,
            calendar=calendar,
        )

    @staticmethod
    def _current_streak(practiced_dates: set[date], reference: date) -> int:
        # Anchor on today if practiced today, else yesterday (streak isn't
        # broken until a full day passes with no practice).
        anchor = reference if reference in practiced_dates else reference - timedelta(days=1)
        if anchor not in practiced_dates:
            return 0
        count = 0
        cursor = anchor
        while cursor in practiced_dates:
            count += 1
            cursor -= timedelta(days=1)
        return count

    @staticmethod
    def _longest_streak(practiced_dates: set[date]) -> int:
        longest = 0
        for d in practiced_dates:
            if d - timedelta(days=1) not in practiced_dates:
                run = 0
                cursor = d
                while cursor in practiced_dates:
                    run += 1
                    cursor += timedelta(days=1)
                longest = max(longest, run)
        return longest

    @staticmethod
    def _to_schema(internal: _StreakInternal) -> StreakData:
        return StreakData(
            current_streak_days=internal.current_streak_days,
            longest_streak_days=internal.longest_streak_days,
            total_practice_days=internal.total_practice_days,
            total_sessions=internal.total_sessions,
            total_practice_hours=internal.total_practice_hours,
            last_practice_date=internal.last_practice_date,
            streak_status=internal.streak_status,
            calendar=internal.calendar,
        )
