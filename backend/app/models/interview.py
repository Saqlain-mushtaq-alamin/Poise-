"""Interview engine persistence, per Phase 4.

`InterviewSessionDetail` is a 1:1 companion table to Phase 1's generic
`sessions` table (keyed on the same id) rather than new columns bolted
onto `Session` — that keeps `Session` mode-agnostic (Phase 7's IELTS mode
gets its own companion table later instead of a `sessions` table full of
nullable interview-only columns).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    filename: Mapped[str | None] = mapped_column(String, nullable=True)
    full_text: Mapped[str] = mapped_column(String)
    structured_json: Mapped[str] = mapped_column(String)  # serialized ResumeData
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class JobDescriptionRecord(Base):
    __tablename__ = "job_descriptions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    raw_text: Mapped[str] = mapped_column(String)
    structured_json: Mapped[str] = mapped_column(String)  # serialized JobDescription
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class InterviewSessionDetail(Base):
    __tablename__ = "interview_session_details"

    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), primary_key=True)
    resume_id: Mapped[str | None] = mapped_column(String, ForeignKey("resumes.id"), nullable=True)
    jd_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("job_descriptions.id"), nullable=True
    )
    config_json: Mapped[str] = mapped_column(String)  # serialized InterviewConfig
    plan_json: Mapped[str | None] = mapped_column(String, nullable=True)  # serialized InterviewPlan
    persona_id: Mapped[str] = mapped_column(String, default="professional")
    session_mode: Mapped[str] = mapped_column(String, default="practice")  # practice | exam
    company_format: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String, default="created")
    current_section_index: Mapped[int] = mapped_column(Integer, default=0)
    current_question_index: Mapped[int] = mapped_column(Integer, default=0)
    warm_up_stage: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=None, onupdate=lambda: datetime.now(timezone.utc)
    )


class QuestionTurn(Base):
    """One row per question (or follow-up) actually delivered in a
    session — this is what Phase 8's `GET /interview/sessions/{id}/
    evaluations` reads to build the final report."""

    __tablename__ = "question_turns"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"))
    question_id: Mapped[str] = mapped_column(String)
    question_text: Mapped[str] = mapped_column(String)
    is_follow_up: Mapped[bool] = mapped_column(default=False)
    answer_text: Mapped[str | None] = mapped_column(String, nullable=True)
    evaluation_json: Mapped[str | None] = mapped_column(String, nullable=True)
    asked_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
