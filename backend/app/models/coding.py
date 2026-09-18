"""
SQLAlchemy ORM models for Phase 6 — Coding Sandbox.

Mount point: backend/app/models/coding.py in the main Poise repo.

These extend the shared `Base` declarative base defined in
`backend/app/database.py` (Phase 1). Import and register them the same
way other phase models are registered so Alembic autogenerate picks
them up:

    # backend/app/models/__init__.py
    from app.models.coding import CodingProblem, CodingSubmission, CodingRound

Run after merging:
    alembic revision --autogenerate -m "phase6_coding_sandbox"
    alembic upgrade head
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

# NOTE: `Base` comes from the main app's shared declarative base.
# Adjust this import path if your Phase 1 setup differs.
from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class CodingProblem(Base):
    """A generated (or bank) coding problem, optionally tied to a session."""

    __tablename__ = "coding_problems"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True, index=True)

    title = Column(String, nullable=False)
    description_md = Column(Text, nullable=False)
    difficulty = Column(String, nullable=False, default="medium")  # easy|medium|hard
    topics = Column(JSON, nullable=False, default=list)            # ["arrays", ...]

    examples = Column(JSON, nullable=False, default=list)          # list[Example]
    constraints = Column(JSON, nullable=False, default=list)       # list[str]
    hints = Column(JSON, nullable=False, default=list)             # list[str]
    starter_code = Column(JSON, nullable=False, default=dict)      # {lang: code}

    # Test cases stored together; `is_hidden` flag lives inside each entry.
    test_cases = Column(JSON, nullable=False, default=list)

    source = Column(String, default="generated")  # "generated" | "bank"
    created_at = Column(DateTime, default=datetime.utcnow)

    submissions = relationship(
        "CodingSubmission", back_populates="problem", cascade="all, delete-orphan"
    )


class CodingSubmission(Base):
    """A single run or submit action against a problem."""

    __tablename__ = "coding_submissions"

    id = Column(String, primary_key=True, default=_uuid)
    problem_id = Column(String, ForeignKey("coding_problems.id"), nullable=False, index=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=True, index=True)

    language = Column(String, nullable=False)
    code = Column(Text, nullable=False)
    action = Column(String, nullable=False, default="run")  # "run" | "submit"

    # Execution result snapshot
    status = Column(String, nullable=True)          # accepted|wrong_answer|runtime_error|...
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    memory_used_mb = Column(Float, nullable=True)
    test_results = Column(JSON, nullable=True, default=list)
    executor = Column(String, nullable=True)         # "judge0" | "subprocess"

    # LLM evaluation snapshot (only populated on "submit")
    correctness_score = Column(Float, nullable=True)
    style_score = Column(Float, nullable=True)
    efficiency_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)
    approach_assessment = Column(String, nullable=True)
    time_complexity = Column(String, nullable=True)
    space_complexity = Column(String, nullable=True)
    strengths = Column(JSON, nullable=True, default=list)
    improvements = Column(JSON, nullable=True, default=list)
    alternative_approaches = Column(JSON, nullable=True, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)

    problem = relationship("CodingProblem", back_populates="submissions")


class CodingRound(Base):
    """One coding round within an interview session — the Phase 4 handoff unit."""

    __tablename__ = "coding_rounds"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    problem_id = Column(String, ForeignKey("coding_problems.id"), nullable=False)

    status = Column(String, default="in_progress")  # in_progress|completed|skipped
    best_submission_id = Column(String, ForeignKey("coding_submissions.id"), nullable=True)

    # Final fused result for this round, consumed by Phase 8.
    final_evaluation = Column(JSON, nullable=True)  # CodeEvaluation dict
    screen_evaluations = Column(JSON, nullable=True, default=list)  # list[ScreenEvaluation]

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
