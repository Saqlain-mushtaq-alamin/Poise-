"""10.6 — Context-aware practice suggestions for the dashboard queue."""
from __future__ import annotations

from sqlalchemy.orm import Session as DBSession

from app.schemas.motivation import PracticeSuggestion
from app.services.motivation._integration import get_recent_score_points, get_untested_jd_skills
from app.services.motivation.spaced_repetition import SpacedRepetitionScheduler


class PracticeSuggestor:
    def __init__(self, db: DBSession):
        self.db = db
        self.sr_scheduler = SpacedRepetitionScheduler(db)

    async def get_suggestions(self, limit: int = 3) -> list[PracticeSuggestion]:
        suggestions: list[PracticeSuggestion] = []

        # 1. Spaced repetition due items (highest priority)
        due = self.sr_scheduler.get_due_items(limit=3)
        for item in due:
            suggestions.append(PracticeSuggestion(
                type="review",
                title=f"Review: {item.content}",
                reason="Due for review based on your learning schedule",
                priority="high",
                action={"practice_item_id": item.id},
            ))
            if len(suggestions) >= limit:
                return suggestions

        # 2. Untested JD skills
        untested = get_untested_jd_skills(self.db)
        for skill in untested:
            suggestions.append(PracticeSuggestion(
                type="new_skill",
                title=f"Practice: {skill}",
                reason="Not yet tested from your target job description",
                priority="medium",
                action={"skill": skill},
            ))
            if len(suggestions) >= limit:
                return suggestions

        # 3. Low confidence / weakest dimensions
        weak = self._weakest_dimensions(limit=2)
        for name, score in weak:
            suggestions.append(PracticeSuggestion(
                type="improvement",
                title=f"Improve: {name}",
                reason=f"Your weakest area at {score:.0f}/100",
                priority="medium",
                action={"dimension": name},
            ))
            if len(suggestions) >= limit:
                return suggestions

        if not suggestions:
            suggestions.append(PracticeSuggestion(
                type="new_skill",
                title="Start a practice session",
                reason="No history yet — your first session builds your practice queue",
                priority="low",
            ))

        return suggestions[:limit]

    def _weakest_dimensions(self, limit: int) -> list[tuple[str, float]]:
        points = get_recent_score_points(self.db, mode=None, limit=20)
        scored = [
            (p.weakest_dimension, p.weakest_dimension_score)
            for p in points
            if p.weakest_dimension and p.weakest_dimension_score is not None
        ]
        scored.sort(key=lambda t: t[1])
        seen = set()
        out: list[tuple[str, float]] = []
        for name, score in scored:
            if name in seen:
                continue
            seen.add(name)
            out.append((name, score))
            if len(out) >= limit:
                break
        return out
