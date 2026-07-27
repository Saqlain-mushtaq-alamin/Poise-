"""10.9 — Pre-interview anxiety toolkit catalog.

The exercises themselves (breathing animation timing, power-pose timer,
etc.) are rendered client-side in
`frontend/src/components/motivation/AnxietyToolkit.tsx` — this module just
supplies the exercise metadata and, for "Positive Reframe", pulls a real
best-moment from the user's recent history so it's grounded in actual
data rather than a generic affirmation.
"""
from __future__ import annotations

from sqlalchemy.orm import Session as DBSession

from app.services.motivation._integration import get_recent_score_points

EXERCISES: list[dict] = [
    {
        "id": "breathing_478",
        "name": "4-7-8 Breathing",
        "type": "breathing",
        "description": "Inhale 4 seconds, hold 7, exhale 8. Three cycles calms the nervous system.",
        "duration_seconds": 90,
        "pattern": {"inhale": 4, "hold": 7, "exhale": 8, "cycles": 3},
    },
    {
        "id": "power_pose",
        "name": "Power Pose",
        "type": "body",
        "description": "Stand tall, hands on hips, chin up. Hold for 2 minutes.",
        "duration_seconds": 120,
    },
    {
        "id": "visualization",
        "name": "Visualization",
        "type": "mental",
        "description": "A guided 3-minute visualization: walking into the interview room confident and prepared.",
        "duration_seconds": 180,
    },
    {
        "id": "vocal_warmup",
        "name": "Quick Warm-Up",
        "type": "vocal",
        "description": "Tongue twisters and a pace-calibration read to loosen your voice.",
        "duration_seconds": 120,
        "warmup_text": (
            "Peter Piper picked a peck of pickled peppers. "
            "She sells seashells by the seashore. "
            "Red leather, yellow leather, red leather, yellow leather."
        ),
    },
    {
        "id": "positive_reframe",
        "name": "Positive Reframe",
        "type": "cognitive",
        "description": "A reminder of your best recent moment, grounded in your real scores.",
        "duration_seconds": 60,
    },
]


class AnxietyToolkitService:
    def __init__(self, db: DBSession):
        self.db = db

    def list_exercises(self) -> list[dict]:
        exercises = [dict(e) for e in EXERCISES]
        for e in exercises:
            if e["id"] == "positive_reframe":
                e["message"] = self._build_reframe_message()
        return exercises

    def _build_reframe_message(self) -> str:
        points = get_recent_score_points(self.db, mode=None, limit=10)
        if not points:
            return "You've prepared for this. Trust the work you've put in."
        best = max(points, key=lambda p: p.overall_score)
        return f"Remember: your {best.mode} score was {best.overall_score:.0f}. You CAN do this."
