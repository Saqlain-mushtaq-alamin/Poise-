"""ORM models. Import every model module here so Alembic autogenerate and
Base.metadata.create_all can discover all tables."""

from app.models import motivation
from app.models.coding import CodingProblem, CodingRound, CodingSubmission
from app.models.confidence import ConfidenceFrameRecord
from app.models.ielts import IELTSAnswer, IELTSSession
from app.models.interview import (
    InterviewSessionDetail,
    JobDescriptionRecord,
    QuestionTurn,
    Resume,
)
from app.models.scoring import DebriefMessage, SessionReportCache
from app.models.session import Session
from app.models.settings import AppSettings

__all__ = [
    "Session",
    "AppSettings",
    "Resume",
    "JobDescriptionRecord",
    "InterviewSessionDetail",
    "QuestionTurn",
    "ConfidenceFrameRecord",
    "IELTSSession",
    "IELTSAnswer",
    "SessionReportCache",
    "DebriefMessage",
    "motivation",
    "CodingProblem",
    "CodingRound",
    "CodingSubmission",
]
