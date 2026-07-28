"""10.11 — Structured self-reflection, shown BEFORE the score report.

The self-rating prompt (`rate_before_report`) doubles as the input to the
confidence calibration feature (10.12) — see `router.submit_reflection`.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from app.models.motivation import ReflectionEntry
from app.schemas.motivation import ReflectionPrompt, ReflectionSubmission

SELF_REFLECTION_PROMPTS: list[ReflectionPrompt] = [
    ReflectionPrompt(
        prompt_id="hardest_question",
        prompt="Which question felt hardest? Why?",
        purpose="Builds awareness of weak spots",
    ),
    ReflectionPrompt(
        prompt_id="rate_before_report",
        prompt="Rate your own performance 1-10 before seeing the report.",
        purpose="Calibrates self-awareness (compared to actual score later)",
    ),
    ReflectionPrompt(
        prompt_id="redo_answer",
        prompt="What would you say differently if you could redo one answer?",
        purpose="Activates reflective learning",
    ),
    ReflectionPrompt(
        prompt_id="nervous_moment",
        prompt="Did you feel nervous at any point? When and why?",
        purpose="Connects emotions to performance data",
    ),
    ReflectionPrompt(
        prompt_id="next_focus",
        prompt="What's ONE thing you'll focus on in your next session?",
        purpose="Creates intention for improvement",
    ),
]

_SELF_RATING_PROMPT_ID = "rate_before_report"


class SelfReflectionService:
    def __init__(self, db: DBSession):
        self.db = db

    def get_prompts(self) -> list[ReflectionPrompt]:
        return SELF_REFLECTION_PROMPTS

    def submit(self, submission: ReflectionSubmission) -> float | None:
        """Persist the reflection answers. Returns the self-rating (1-10)
        if the user answered that prompt, so the caller can immediately
        feed it into CalibrationTracker once the report is generated."""
        self_rating = None
        prompt_text_by_id = {p.prompt_id: p.prompt for p in SELF_REFLECTION_PROMPTS}

        for answer in submission.answers:
            self.db.add(ReflectionEntry(
                session_id=submission.session_id,
                prompt_id=answer.prompt_id,
                prompt_text=prompt_text_by_id.get(answer.prompt_id, ""),
                response=answer.response,
                self_rating=answer.self_rating,
                created_at=datetime.utcnow(),
            ))
            if answer.prompt_id == _SELF_RATING_PROMPT_ID and answer.self_rating is not None:
                self_rating = answer.self_rating

        self.db.commit()
        return self_rating
