"""Pydantic request/response models for `app/routers/motivation.py`.

These mirror `contracts/api/motivation.yaml` 1:1 — if you change a field
here, update the OpenAPI spec (or regenerate it, since FastAPI can emit
the spec directly from these models) so other phases' contract stays true.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- streaks --

class StreakData(BaseModel):
    current_streak_days: int
    longest_streak_days: int
    total_practice_days: int
    total_sessions: int
    total_practice_hours: float
    last_practice_date: date | None
    streak_status: Literal["active", "at_risk", "broken", "none"]
    calendar: dict[str, int] = Field(
        description="ISO date string -> session count, last 90 days, for the heatmap"
    )


class StreakUpdate(BaseModel):
    streak: StreakData
    streak_extended: bool
    new_record: bool


# ------------------------------------------------------------------ goals --

class GoalCreate(BaseModel):
    type: Literal["ielts_band", "interview_score", "sessions_per_week"]
    target_value: float
    deadline: date | None = None


class Goal(BaseModel):
    id: str
    type: str
    target_value: float
    current_value: float
    starting_value: float
    deadline: date | None
    created_at: datetime
    status: Literal["active", "achieved", "abandoned"]
    progress_percent: float
    projected_completion: date | None


# ----------------------------------------------------- spaced repetition --

class PracticeItem(BaseModel):
    id: str
    category: Literal["behavioral", "technical", "pronunciation", "topic"]
    content: str
    source_sessions: list[str]
    difficulty: float
    easiness_factor: float
    interval_days: int
    repetitions: int
    next_review_date: date
    last_score: float | None
    is_mastered: bool


class ReviewResult(BaseModel):
    score: float = Field(ge=0, le=5, description="0=forgotten .. 5=perfect recall")


# ------------------------------------------------------------ coach summ --

class CoachSummary(BaseModel):
    week_start: date
    sessions_count: int
    practice_time_hours: float
    score_trend: Literal["improving", "stable", "declining", "no_data"]
    narrative: str
    focus_areas: list[str]
    celebration: list[str]
    next_week_plan: list[str]
    generated_at: datetime


# ---------------------------------------------------------- achievements --

class Achievement(BaseModel):
    id: str
    name: str
    icon: str
    desc: str
    category: str
    unlocked: bool
    unlocked_at: datetime | None = None


# ------------------------------------------------------------ suggestions --

class PracticeSuggestion(BaseModel):
    type: Literal["review", "new_skill", "improvement"]
    title: str
    reason: str
    priority: Literal["high", "medium", "low"]
    action: dict | None = Field(
        default=None, description="e.g. {'practice_item_id': '...'} for deep-linking the CTA"
    )


# --------------------------------------------------------------- notifs --

class NotificationSettings(BaseModel):
    streak_reminders: bool = True
    weekly_summary: bool = True
    goal_progress: bool = True
    achievements: bool = True
    quiet_hours_start: str = "21:00"
    quiet_hours_end: str = "09:00"
    max_per_day: int = 1


class NotificationEvent(BaseModel):
    type: Literal["streak_at_risk", "weekly_summary_ready", "goal_approaching", "achievement_unlocked"]
    title: str
    body: str


# ---------------------------------------------------------- self-reflect --

class ReflectionPrompt(BaseModel):
    prompt_id: str
    prompt: str
    purpose: str


class ReflectionAnswer(BaseModel):
    prompt_id: str
    response: str | None = None
    self_rating: float | None = Field(default=None, ge=1, le=10)


class ReflectionSubmission(BaseModel):
    session_id: str
    answers: list[ReflectionAnswer]


# --------------------------------------------------------- calibration --

class ConfidenceCalibration(BaseModel):
    self_rating: float
    actual_score: float
    calibration_gap: float
    calibration_trend: Literal["over_confident", "under_confident", "well_calibrated"]
    historical_gaps: list[float]
    insight: str


# ------------------------------------------------------------ interview day --

class InterviewDayConfig(BaseModel):
    company_format: Literal["amazon", "google", "meta", "custom"] = "custom"
    total_rounds: int = Field(default=3, ge=3, le=5)
    break_duration_minutes: int = Field(default=10, ge=5, le=10)
    include_lunch_break: bool = False
    fatigue_tracking: bool = True


class RoundComparison(BaseModel):
    round_number: int
    confidence_score: float | None
    quality_score: float | None
    delta_from_round_1: float | None


class FatigueAnalysis(BaseModel):
    confidence_by_round: list[float]
    quality_by_round: list[float]
    energy_trend: Literal["sustained", "gradual_decline", "sharp_drop", "insufficient_data"]
    recommendation: str


class InterviewDayReport(BaseModel):
    id: str
    status: str
    rounds_completed: int
    total_rounds: int
    fatigue_analysis: FatigueAnalysis | None
    overall_verdict: str
    stamina_score: float | None
    round_comparison: list[RoundComparison]
