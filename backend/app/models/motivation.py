"""
Phase 10 — Motivation Engine ORM models.

Depends on `app.database.Base` (Phase 1) and `app.models.session.Session`
(Phase 1 / Phase 8) for the FK relationship to a completed practice session.

Add this module's import to `app/models/__init__.py` so Alembic autogenerate
picks it up:

    from app.models import motivation  # noqa: F401
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid4())


class PracticeDay(Base):
    """One row per calendar day the user completed >=1 session. Backs the
    streak counter and the contribution heatmap without recomputing from
    the full session table every time."""

    __tablename__ = "motivation_practice_days"

    practice_date = Column(Date, primary_key=True)
    session_count = Column(Integer, nullable=False, default=0)
    practice_minutes = Column(Float, nullable=False, default=0.0)


class Goal(Base):
    __tablename__ = "motivation_goals"

    id = Column(String, primary_key=True, default=_uuid)
    type = Column(String, nullable=False)  # ielts_band | interview_score | sessions_per_week
    target_value = Column(Float, nullable=False)
    starting_value = Column(Float, nullable=False, default=0.0)
    deadline = Column(Date, nullable=True)
    status = Column(String, nullable=False, default="active")  # active | achieved | abandoned
    created_at = Column(DateTime, default=datetime.utcnow)
    achieved_at = Column(DateTime, nullable=True)


class PracticeItem(Base):
    """A spaced-repetition item: one identified weakness, tracked with the
    SM-2 algorithm."""

    __tablename__ = "motivation_practice_items"

    id = Column(String, primary_key=True, default=_uuid)
    category = Column(String, nullable=False)  # behavioral | technical | pronunciation | topic
    content = Column(Text, nullable=False)
    source_session_id = Column(String, ForeignKey("sessions.id"), nullable=True)
    difficulty = Column(Float, nullable=False, default=0.5)  # 0-1, informational only
    easiness_factor = Column(Float, nullable=False, default=2.5)  # SM-2 EF, floor 1.3
    interval_days = Column(Integer, nullable=False, default=0)
    repetitions = Column(Integer, nullable=False, default=0)
    next_review_date = Column(Date, nullable=False, default=date.today)
    last_score = Column(Float, nullable=True)  # 0-5 SM-2 recall score
    last_reviewed_at = Column(DateTime, nullable=True)
    is_mastered = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    source_sessions = relationship(
        "PracticeItemSource", back_populates="item", cascade="all, delete-orphan"
    )


class PracticeItemSource(Base):
    """Many-to-many: the same weakness can resurface across multiple
    sessions before it's mastered — we keep every session that fed it."""

    __tablename__ = "motivation_practice_item_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String, ForeignKey("motivation_practice_items.id"), nullable=False)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)

    item = relationship("PracticeItem", back_populates="source_sessions")


class UserAchievement(Base):
    """Unlocked achievements. The catalog itself (ACHIEVEMENTS) lives in
    code, not the DB, so shipping new badges never needs a migration."""

    __tablename__ = "motivation_user_achievements"
    __table_args__ = (UniqueConstraint("achievement_id", name="uq_achievement_once"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    achievement_id = Column(String, nullable=False)
    unlocked_at = Column(DateTime, default=datetime.utcnow)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True)


class WeeklyCoachSummary(Base):
    """Cached AI-generated weekly digest so we don't regenerate (and
    re-bill, on cloud tiers) every time the dashboard is opened."""

    __tablename__ = "motivation_weekly_summaries"
    __table_args__ = (UniqueConstraint("week_start", name="uq_week_start"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    week_start = Column(Date, nullable=False)
    sessions_count = Column(Integer, nullable=False, default=0)
    practice_time_hours = Column(Float, nullable=False, default=0.0)
    score_trend = Column(String, nullable=False, default="stable")
    narrative = Column(Text, nullable=False, default="")
    focus_areas = Column(Text, nullable=False, default="[]")  # JSON list[str]
    celebration = Column(Text, nullable=False, default="[]")  # JSON list[str]
    next_week_plan = Column(Text, nullable=False, default="[]")  # JSON list[str]
    generated_at = Column(DateTime, default=datetime.utcnow)


class ReflectionEntry(Base):
    """Structured self-reflection answers, captured before the score
    report is revealed (see 10.11)."""

    __tablename__ = "motivation_reflections"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    prompt_id = Column(String, nullable=False)
    prompt_text = Column(Text, nullable=False)
    response = Column(Text, nullable=True)  # free text, nullable for skip
    self_rating = Column(Float, nullable=True)  # only set on the self-rating prompt, 1-10
    created_at = Column(DateTime, default=datetime.utcnow)


class CalibrationRecord(Base):
    """One row per session with a self-rating: pairs the user's
    pre-report guess with the actual fused score (see 10.12)."""

    __tablename__ = "motivation_calibration"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, unique=True)
    self_rating = Column(Float, nullable=False)  # 1-10, rescaled from ReflectionEntry
    actual_score = Column(Float, nullable=False)  # 0-100, rescaled to 1-10 for comparison
    created_at = Column(DateTime, default=datetime.utcnow)


class InterviewDaySession(Base):
    """A multi-round simulated interview day (see 10.10)."""

    __tablename__ = "motivation_interview_days"

    id = Column(String, primary_key=True, default=_uuid)
    company_format = Column(String, nullable=False, default="custom")
    total_rounds = Column(Integer, nullable=False, default=3)
    break_duration_minutes = Column(Integer, nullable=False, default=10)
    include_lunch_break = Column(Boolean, nullable=False, default=False)
    fatigue_tracking = Column(Boolean, nullable=False, default=True)
    status = Column(String, nullable=False, default="in_progress")  # in_progress | completed | abandoned
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    rounds = relationship(
        "InterviewDayRound", back_populates="day", cascade="all, delete-orphan",
        order_by="InterviewDayRound.round_number",
    )


class InterviewDayRound(Base):
    __tablename__ = "motivation_interview_day_rounds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    day_id = Column(String, ForeignKey("motivation_interview_days.id"), nullable=False)
    round_number = Column(Integer, nullable=False)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True)
    confidence_score = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)

    day = relationship("InterviewDaySession", back_populates="rounds")


class NotificationSettings(Base):
    """Singleton row (id=1) of notification preferences."""

    __tablename__ = "motivation_notification_settings"

    id = Column(Integer, primary_key=True, default=1)
    streak_reminders = Column(Boolean, nullable=False, default=True)
    weekly_summary = Column(Boolean, nullable=False, default=True)
    goal_progress = Column(Boolean, nullable=False, default=True)
    achievements = Column(Boolean, nullable=False, default=True)
    quiet_hours_start = Column(String, nullable=False, default="21:00")
    quiet_hours_end = Column(String, nullable=False, default="09:00")
    max_per_day = Column(Integer, nullable=False, default=1)


class NotificationLog(Base):
    """Sent-notification ledger, used to enforce the 1/day cap."""

    __tablename__ = "motivation_notification_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_type = Column(String, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    payload = Column(Text, nullable=True)
