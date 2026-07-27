"""Phase 10 — Motivation Engine API routes.

Register in `app/main.py`:

    from app.routers import motivation
    app.include_router(motivation.router)

Also call `on_session_completed()` from wherever Phase 4/6/7 marks a
session as finished — it fans out to streaks, spaced repetition, goals,
and achievements so "called after every session completes" (per the
phase doc) actually happens in one place instead of four.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db  # Phase 1
from app.services.provider import ModelProviderRouter  # Phase 2

from app.schemas.motivation import (
    Achievement,
    ConfidenceCalibration,
    CoachSummary,
    Goal,
    GoalCreate,
    InterviewDayConfig,
    InterviewDayReport,
    NotificationEvent,
    NotificationSettings,
    PracticeItem,
    PracticeSuggestion,
    ReflectionPrompt,
    ReflectionSubmission,
    ReviewResult,
    StreakData,
    StreakUpdate,
)
from app.services.motivation.achievements import AchievementEngine
from app.services.motivation.anxiety_toolkit import AnxietyToolkitService
from app.services.motivation.calibration import CalibrationTracker
from app.services.motivation.coach import WeeklyCoach
from app.services.motivation.goals import GoalTracker
from app.services.motivation.interview_day import InterviewDaySimulator
from app.services.motivation.notifications import NotificationManager
from app.services.motivation.reflection import SelfReflectionService
from app.services.motivation.spaced_repetition import SpacedRepetitionScheduler
from app.services.motivation.streaks import StreakTracker
from app.services.motivation.suggestions import PracticeSuggestor

router = APIRouter(prefix="/motivation", tags=["motivation"])


def get_provider() -> ModelProviderRouter:
    """Thin indirection so this router doesn't hardcode how the provider
    router is constructed elsewhere in the app — wire this to whatever
    dependency Phase 2 already exposes (e.g. an app-level singleton)."""
    return ModelProviderRouter()


# ----------------------------------------------------------------- streaks --

@router.get("/streak", response_model=StreakData)
def get_streak(db: DBSession = Depends(get_db)):
    return StreakTracker(db).get_streak()


# ------------------------------------------------------------------- goals --

@router.get("/goals", response_model=list[Goal])
async def list_goals(db: DBSession = Depends(get_db)):
    return await GoalTracker(db).list_goals()


@router.post("/goals", response_model=Goal)
async def create_goal(body: GoalCreate, db: DBSession = Depends(get_db)):
    return await GoalTracker(db).create_goal(body.type, body.target_value, body.deadline)


@router.get("/goals/{goal_id}/progress", response_model=Goal)
async def get_goal_progress(goal_id: str, db: DBSession = Depends(get_db)):
    goal = await GoalTracker(db).get_goal(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="goal not found")
    return goal


# -------------------------------------------------------------- practice --

@router.get("/practice-queue", response_model=list[PracticeSuggestion])
async def get_practice_queue(limit: int = 3, db: DBSession = Depends(get_db)):
    return await PracticeSuggestor(db).get_suggestions(limit=limit)


@router.get("/spaced-repetition/due", response_model=list[PracticeItem])
def get_due_items(limit: int = 5, db: DBSession = Depends(get_db)):
    return SpacedRepetitionScheduler(db).get_due_items(limit=limit)


@router.post("/spaced-repetition/{item_id}/review", response_model=PracticeItem)
def review_item(item_id: str, body: ReviewResult, db: DBSession = Depends(get_db)):
    try:
        return SpacedRepetitionScheduler(db).record_review(item_id, body.score)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --------------------------------------------------------------- coach --

@router.get("/weekly-summary", response_model=CoachSummary)
async def get_weekly_summary(
    week_start: date | None = None,
    refresh: bool = False,
    db: DBSession = Depends(get_db),
    provider: ModelProviderRouter = Depends(get_provider),
):
    week_start = week_start or (date.today() - timedelta(days=date.today().weekday()))
    return await WeeklyCoach(db, provider).generate_summary(week_start, force_refresh=refresh)


# --------------------------------------------------------- achievements --

@router.get("/achievements", response_model=list[Achievement])
async def list_achievements(db: DBSession = Depends(get_db)):
    return await AchievementEngine(db).list_achievements()


# ----------------------------------------------------------- notifications --

@router.get("/notifications/settings", response_model=NotificationSettings)
async def get_notification_settings(db: DBSession = Depends(get_db)):
    return await NotificationManager(db).get_settings()


@router.put("/notifications/settings", response_model=NotificationSettings)
async def update_notification_settings(body: NotificationSettings, db: DBSession = Depends(get_db)):
    return await NotificationManager(db).update_settings(body)


@router.get("/notifications/pending", response_model=NotificationEvent | None)
async def get_pending_notification(db: DBSession = Depends(get_db)):
    return await NotificationManager(db).get_pending()


# ------------------------------------------------------------- reflection --

@router.get("/reflection/prompts", response_model=list[ReflectionPrompt])
def get_reflection_prompts(db: DBSession = Depends(get_db)):
    return SelfReflectionService(db).get_prompts()


@router.post("/reflection/submit")
async def submit_reflection(body: ReflectionSubmission, db: DBSession = Depends(get_db)):
    """Persist reflection answers, then — if a self-rating was given —
    feed the calibration tracker once the real score is known."""
    self_rating = SelfReflectionService(db).submit(body)
    return {"self_rating": self_rating, "session_id": body.session_id}


# ------------------------------------------------------------- calibration --

@router.get("/calibration", response_model=ConfidenceCalibration)
def get_calibration(db: DBSession = Depends(get_db)):
    return CalibrationTracker(db).get_calibration()


# ----------------------------------------------------------- anxiety toolkit --

@router.get("/anxiety-toolkit")
def get_anxiety_toolkit(db: DBSession = Depends(get_db)):
    return {"exercises": AnxietyToolkitService(db).list_exercises()}


# ------------------------------------------------------------- interview day --

@router.post("/interview-day", response_model=InterviewDayReport)
def start_interview_day(body: InterviewDayConfig, db: DBSession = Depends(get_db)):
    return InterviewDaySimulator(db).start(body)


@router.get("/interview-day/{day_id}", response_model=InterviewDayReport)
def get_interview_day(day_id: str, db: DBSession = Depends(get_db)):
    try:
        return InterviewDaySimulator(db).get_report(day_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/interview-day/{day_id}/rounds/{round_number}/attach", response_model=InterviewDayReport)
def attach_round(day_id: str, round_number: int, session_id: str, db: DBSession = Depends(get_db)):
    try:
        return InterviewDaySimulator(db).attach_round_session(day_id, round_number, session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/interview-day/{day_id}/rounds/{round_number}/scores", response_model=InterviewDayReport)
def record_round_scores(
    day_id: str, round_number: int, confidence_score: float, quality_score: float,
    db: DBSession = Depends(get_db),
):
    try:
        return InterviewDaySimulator(db).record_round_scores(day_id, round_number, confidence_score, quality_score)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --------------------------------------------------------- session hook --

async def on_session_completed(
    db: DBSession,
    session_id: str,
    duration_minutes: float,
    provider: ModelProviderRouter | None = None,
) -> dict:
    """Call this once, right after a session's report is generated,
    from Phase 4/6/7's completion handler:

        from app.routers.motivation import on_session_completed
        await on_session_completed(db, session.id, duration_minutes)

    Fans out to every Phase 10 subsystem that reacts to "a session just
    finished": streak, goals, spaced repetition, achievements.
    """
    streak_update = StreakTracker(db).record_practice(session_id, duration_minutes)
    goals = await GoalTracker(db).update_progress(session_id)
    new_items = SpacedRepetitionScheduler(db).ingest_session_weaknesses(session_id)
    new_achievements = await AchievementEngine(db).check_and_unlock(session_id)

    return {
        "streak": streak_update,
        "goals": goals,
        "new_practice_items": new_items,
        "new_achievements": new_achievements,
    }
