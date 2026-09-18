"""10.3 — SM-2 spaced repetition for interview weaknesses.

Standard SM-2 (SuperMemo-2), scores 0-5:
  0-2 -> forgotten: reset repetitions and interval to day 1
  3   -> maintain: interval grows, but EF barely moves (borderline recall)
  4-5 -> remembered well: EF increases, interval grows faster

EF (easiness factor) floors at 1.3 per the original algorithm — below that
the item would get *more* frequent forever, which isn't useful here.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.models.motivation import PracticeItem as PracticeItemRow
from app.models.motivation import PracticeItemSource
from app.schemas.motivation import PracticeItem as PracticeItemSchema
from app.services.motivation._integration import get_session_weaknesses

MIN_EF = 1.3
MASTERED_REPETITIONS = 5
MASTERED_INTERVAL_DAYS = 60


class SpacedRepetitionScheduler:
    def __init__(self, db: DBSession):
        self.db = db

    # -- reads --------------------------------------------------------------

    def get_due_items(self, limit: int = 5, today: date | None = None) -> list[PracticeItemSchema]:
        today = today or date.today()
        rows = self.db.execute(
            select(PracticeItemRow)
            .where(PracticeItemRow.next_review_date <= today)
            .where(PracticeItemRow.is_mastered == False)  # noqa: E712
            .order_by(PracticeItemRow.next_review_date.asc())
            .limit(limit)
        ).scalars().all()
        return [self._to_schema(r) for r in rows]

    # -- writes ---------------------------------------------------------------

    def record_review(self, item_id: str, score: float, today: date | None = None) -> PracticeItemSchema:
        """Update interval based on performance (SM-2 algorithm)."""
        today = today or date.today()
        row = self.db.get(PracticeItemRow, item_id)
        if row is None:
            raise ValueError(f"practice item {item_id} not found")

        score = max(0.0, min(5.0, score))

        if score < 3:
            row.repetitions = 0
            row.interval_days = 1
        else:
            if row.repetitions == 0:
                row.interval_days = 1
            elif row.repetitions == 1:
                row.interval_days = 6
            else:
                row.interval_days = round(row.interval_days * row.easiness_factor)
            row.repetitions += 1

        row.easiness_factor = max(
            MIN_EF,
            row.easiness_factor + (0.1 - (5 - score) * (0.08 + (5 - score) * 0.02)),
        )
        row.last_score = score
        row.last_reviewed_at = datetime.utcnow()
        row.next_review_date = today + timedelta(days=row.interval_days)

        if row.repetitions >= MASTERED_REPETITIONS and row.interval_days >= MASTERED_INTERVAL_DAYS:
            row.is_mastered = True

        self.db.commit()
        self.db.refresh(row)
        return self._to_schema(row)

    def ingest_session_weaknesses(self, session_id: str, today: date | None = None) -> list[PracticeItemSchema]:
        """Create/update practice items from a completed session's report."""
        today = today or date.today()
        weaknesses = get_session_weaknesses(self.db, session_id)

        buckets = [
            ("behavioral", weaknesses.behavioral),
            ("technical", weaknesses.technical),
            ("pronunciation", weaknesses.pronunciation),
            ("topic", weaknesses.topics),
        ]

        results: list[PracticeItemSchema] = []
        for category, contents in buckets:
            for content in contents:
                results.append(self._upsert(category, content, session_id, today))
        return results

    # -- internals ---------------------------------------------------------

    def _upsert(self, category: str, content: str, session_id: str, today: date) -> PracticeItemSchema:
        existing = self.db.execute(
            select(PracticeItemRow)
            .where(PracticeItemRow.category == category)
            .where(PracticeItemRow.content == content)
        ).scalars().first()

        if existing is None:
            existing = PracticeItemRow(
                category=category,
                content=content,
                source_session_id=session_id,
                difficulty=0.5,
                easiness_factor=2.5,
                interval_days=0,
                repetitions=0,
                next_review_date=today,  # due immediately the first time
                created_at=datetime.utcnow(),
            )
            self.db.add(existing)
            self.db.flush()
        else:
            # Resurfacing a known weakness -> nudge it due again soon,
            # capped so we don't spam the queue with the same item.
            existing.next_review_date = min(existing.next_review_date, today + timedelta(days=2))
            existing.is_mastered = False

        self.db.add(PracticeItemSource(item_id=existing.id, session_id=session_id))
        self.db.commit()
        self.db.refresh(existing)
        return self._to_schema(existing)

    def _to_schema(self, row: PracticeItemRow) -> PracticeItemSchema:
        sources = self.db.execute(
            select(PracticeItemSource.session_id).where(PracticeItemSource.item_id == row.id)
        ).scalars().all()
        return PracticeItemSchema(
            id=row.id,
            category=row.category,
            content=row.content,
            source_sessions=list(dict.fromkeys(sources)),
            difficulty=row.difficulty,
            easiness_factor=round(row.easiness_factor, 2),
            interval_days=row.interval_days,
            repetitions=row.repetitions,
            next_review_date=row.next_review_date,
            last_score=row.last_score,
            is_mastered=row.is_mastered,
        )
