"""10.5 — Achievement system.

The catalog is code, not data, so new badges ship without a migration.
`AchievementEngine.check_and_unlock()` is idempotent and cheap enough to
call after every session completion and every streak/goal update.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models.motivation import UserAchievement
from app.schemas.motivation import Achievement
from app.services.motivation._integration import get_recent_score_points
from app.services.motivation.streaks import StreakTracker

ACHIEVEMENTS: list[dict] = [
    # Getting Started
    {"id": "first_session", "name": "First Steps", "icon": "🎯", "desc": "Complete your first session", "category": "getting_started"},
    {"id": "setup_complete", "name": "All Set", "icon": "⚙️", "desc": "Complete the setup wizard", "category": "getting_started"},

    # Consistency
    {"id": "streak_7", "name": "Week Warrior", "icon": "🔥", "desc": "7-day practice streak", "category": "consistency"},
    {"id": "streak_30", "name": "Monthly Master", "icon": "💎", "desc": "30-day practice streak", "category": "consistency"},
    {"id": "streak_100", "name": "Centurion", "icon": "🏆", "desc": "100-day practice streak", "category": "consistency"},

    # IELTS
    {"id": "ielts_band_6", "name": "Band 6", "icon": "🥉", "desc": "Achieve IELTS Band 6.0", "category": "ielts"},
    {"id": "ielts_band_7", "name": "Band 7", "icon": "🥈", "desc": "Achieve IELTS Band 7.0", "category": "ielts"},
    {"id": "ielts_band_8", "name": "Band 8", "icon": "🥇", "desc": "Achieve IELTS Band 8.0", "category": "ielts"},

    # Interview
    {"id": "score_80", "name": "Strong Candidate", "icon": "⭐", "desc": "Score 80+ in an interview", "category": "interview"},
    {"id": "score_90", "name": "Outstanding", "icon": "🌟", "desc": "Score 90+ in an interview", "category": "interview"},
    {"id": "all_personas", "name": "Versatile", "icon": "🎭", "desc": "Practice with all personas", "category": "interview"},

    # Technical
    {"id": "code_perfect", "name": "Clean Code", "icon": "💻", "desc": "100% on a coding round", "category": "technical"},
    {"id": "confidence_90", "name": "Composed", "icon": "🧘", "desc": "90+ confidence score", "category": "technical"},

    # Improvement
    {"id": "improved_10", "name": "Getting Better", "icon": "📈", "desc": "Improve score by 10+ points", "category": "improvement"},
    {"id": "weakness_mastered", "name": "Overcame", "icon": "💪", "desc": "Master a previously weak area", "category": "improvement"},

    # Motivation-engine specific
    {"id": "goal_achieved", "name": "Goal Getter", "icon": "🏁", "desc": "Achieve a goal you set", "category": "improvement"},
    {"id": "well_calibrated", "name": "Self-Aware", "icon": "🪞", "desc": "Rate yourself within 1 point of your actual score", "category": "improvement"},
]

_ACHIEVEMENT_BY_ID = {a["id"]: a for a in ACHIEVEMENTS}


class AchievementEngine:
    def __init__(self, db: DBSession):
        self.db = db

    async def list_achievements(self) -> list[Achievement]:
        unlocked = {
            row.achievement_id: row.unlocked_at
            for row in self.db.execute(select(UserAchievement)).scalars().all()
        }
        return [
            Achievement(
                id=a["id"], name=a["name"], icon=a["icon"], desc=a["desc"], category=a["category"],
                unlocked=a["id"] in unlocked, unlocked_at=unlocked.get(a["id"]),
            )
            for a in ACHIEVEMENTS
        ]

    async def check_and_unlock(self, session_id: str | None = None) -> list[Achievement]:
        """Evaluate every achievement's condition and unlock any newly
        earned ones. Returns only the *newly* unlocked achievements (for
        the confetti/toast UI)."""
        already = {
            row.achievement_id for row in self.db.execute(select(UserAchievement)).scalars().all()
        }
        newly: list[Achievement] = []

        for achievement_id, condition in self._conditions().items():
            if achievement_id in already:
                continue
            if condition():
                self.db.add(UserAchievement(achievement_id=achievement_id, session_id=session_id))
                a = _ACHIEVEMENT_BY_ID[achievement_id]
                newly.append(Achievement(
                    id=a["id"], name=a["name"], icon=a["icon"], desc=a["desc"], category=a["category"],
                    unlocked=True, unlocked_at=datetime.utcnow(),
                ))
        if newly:
            self.db.commit()
        return newly

    # -- condition functions --------------------------------------------------
    # Each returns bool. Kept lazy (closures) so we only run the query for
    # achievements not already unlocked.

    def _conditions(self) -> dict:
        interview_points = lambda: get_recent_score_points(self.db, mode="interview", limit=500)
        ielts_points = lambda: get_recent_score_points(self.db, mode="ielts", limit=500)
        all_points = lambda: get_recent_score_points(self.db, mode=None, limit=500)
        streak = StreakTracker(self.db).get_streak()

        return {
            "first_session": lambda: len(all_points()) >= 1,
            "setup_complete": lambda: True,  # fire this explicitly from the setup-wizard completion handler
            "streak_7": lambda: streak.current_streak_days >= 7 or streak.longest_streak_days >= 7,
            "streak_30": lambda: streak.current_streak_days >= 30 or streak.longest_streak_days >= 30,
            "streak_100": lambda: streak.current_streak_days >= 100 or streak.longest_streak_days >= 100,
            "ielts_band_6": lambda: any((p.ielts_band or 0) >= 6.0 for p in ielts_points()),
            "ielts_band_7": lambda: any((p.ielts_band or 0) >= 7.0 for p in ielts_points()),
            "ielts_band_8": lambda: any((p.ielts_band or 0) >= 8.0 for p in ielts_points()),
            "score_80": lambda: any(p.overall_score >= 80 for p in interview_points()),
            "score_90": lambda: any(p.overall_score >= 90 for p in interview_points()),
            "all_personas": lambda: False,  # wire to your persona-tracking table
            "code_perfect": lambda: False,  # wire to CodeEvaluation == 100%
            "confidence_90": lambda: False,  # wire to ConfidenceSummary.overall >= 90
            "improved_10": lambda: self._improved_by(interview_points(), 10),
            "weakness_mastered": lambda: self._any_mastered_item(),
            "goal_achieved": lambda: self._any_goal_achieved(),
            "well_calibrated": lambda: self._well_calibrated(),
        }

    @staticmethod
    def _improved_by(points, delta: float) -> bool:
        if len(points) < 2:
            return False
        ordered = sorted(points, key=lambda p: p.session_date)
        return ordered[-1].overall_score - ordered[0].overall_score >= delta

    def _any_mastered_item(self) -> bool:
        from app.models.motivation import PracticeItem
        return self.db.query(PracticeItem).filter(PracticeItem.is_mastered == True).count() > 0  # noqa: E712

    def _any_goal_achieved(self) -> bool:
        from app.models.motivation import Goal
        return self.db.query(Goal).filter(Goal.status == "achieved").count() > 0

    def _well_calibrated(self) -> bool:
        from app.models.motivation import CalibrationRecord
        rows = self.db.query(CalibrationRecord).order_by(CalibrationRecord.created_at.desc()).limit(5).all()
        return any(abs(r.self_rating - r.actual_score / 10.0) <= 1.0 for r in rows)
