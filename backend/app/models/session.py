"""Session model — stub. Later phases (4, 6, 7) add mode-specific columns
and related tables (transcripts, scores, etc.) via Alembic migrations."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    mode: Mapped[str] = mapped_column(String, nullable=False)  # "interview" | "ielts"
    status: Mapped[str] = mapped_column(String, default="created")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=None, onupdate=lambda: datetime.now(timezone.utc)
    )
