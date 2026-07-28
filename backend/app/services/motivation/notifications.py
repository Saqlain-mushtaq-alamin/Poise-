"""10.7 — Notification system.

This module decides *what* to send and *whether* now is an okay time
(quiet hours, 1/day cap). Actually delivering it to the OS tray is a thin
Tauri-side call — see `frontend/src/lib/motivationApi.ts::pollNotifications`
which polls `GET /motivation/notifications/pending` and forwards any
result to Tauri's notification plugin.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models.motivation import NotificationLog, NotificationSettings as NotificationSettingsRow
from app.schemas.motivation import NotificationEvent, NotificationSettings
from app.services.motivation.goals import GoalTracker
from app.services.motivation.streaks import StreakTracker


class NotificationManager:
    def __init__(self, db: DBSession):
        self.db = db

    async def get_settings(self) -> NotificationSettings:
        row = self._settings_row()
        return NotificationSettings(
            streak_reminders=row.streak_reminders,
            weekly_summary=row.weekly_summary,
            goal_progress=row.goal_progress,
            achievements=row.achievements,
            quiet_hours_start=row.quiet_hours_start,
            quiet_hours_end=row.quiet_hours_end,
            max_per_day=row.max_per_day,
        )

    async def update_settings(self, settings: NotificationSettings) -> NotificationSettings:
        row = self._settings_row()
        row.streak_reminders = settings.streak_reminders
        row.weekly_summary = settings.weekly_summary
        row.goal_progress = settings.goal_progress
        row.achievements = settings.achievements
        row.quiet_hours_start = settings.quiet_hours_start
        row.quiet_hours_end = settings.quiet_hours_end
        row.max_per_day = settings.max_per_day
        self.db.commit()
        return settings

    async def get_pending(self, now: datetime | None = None) -> NotificationEvent | None:
        """At most one notification, only if quiet hours + daily cap allow it."""
        now = now or datetime.utcnow()
        settings = self._settings_row()

        if self._sent_today_count(now.date()) >= settings.max_per_day:
            return None
        if self._in_quiet_hours(now.time(), settings.quiet_hours_start, settings.quiet_hours_end):
            return None

        candidate = await self._pick_candidate(settings, now)
        if candidate is None:
            return None

        self.db.add(NotificationLog(notification_type=candidate.type, sent_at=now))
        self.db.commit()
        return candidate

    # -- candidate selection, priority order ---------------------------------

    async def _pick_candidate(self, settings: NotificationSettingsRow, now: datetime) -> NotificationEvent | None:
        if settings.streak_reminders:
            streak = StreakTracker(self.db).get_streak(today=now.date())
            if streak.streak_status == "at_risk" and streak.current_streak_days >= 2:
                return NotificationEvent(
                    type="streak_at_risk",
                    title="Don't break your streak!",
                    body=f"Your {streak.current_streak_days}-day streak ends today — practice for 10 minutes?",
                )

        if settings.goal_progress:
            goals = await GoalTracker(self.db).list_goals()
            for g in goals:
                if g.status == "active" and g.progress_percent >= 85:
                    return NotificationEvent(
                        type="goal_approaching",
                        title="Almost there!",
                        body=f"You're {g.progress_percent:.0f}% of the way to your {g.type.replace('_', ' ')} goal.",
                    )

        if settings.weekly_summary and now.weekday() == 0 and now.hour < 12:
            # Monday morning: nudge that last week's digest is ready.
            return NotificationEvent(
                type="weekly_summary_ready",
                title="Weekly summary ready",
                body="Your weekly coach summary is ready 📊",
            )

        return None

    # -- helpers --------------------------------------------------------------

    def _settings_row(self) -> NotificationSettingsRow:
        row = self.db.get(NotificationSettingsRow, 1)
        if row is None:
            row = NotificationSettingsRow(id=1)
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def _sent_today_count(self, today: date) -> int:
        rows = self.db.execute(
            select(NotificationLog).where(NotificationLog.sent_at >= datetime.combine(today, time.min))
        ).scalars().all()
        return len(rows)

    @staticmethod
    def _in_quiet_hours(now_t: time, start: str, end: str) -> bool:
        start_t = time.fromisoformat(start)
        end_t = time.fromisoformat(end)
        if start_t <= end_t:
            return start_t <= now_t <= end_t
        # wraps past midnight, e.g. 21:00 -> 09:00
        return now_t >= start_t or now_t <= end_t
