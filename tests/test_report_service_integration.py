import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ielts as ielts_models  # noqa: F401 - register tables
from app.models import scoring as scoring_models  # noqa: F401
from app.models import session as session_models  # noqa: F401
from app.services.ielts.conductor import IELTSSessionConductor
from app.services.scoring.debrief import DebriefService
from app.services.scoring.report_service import ReportService


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


def _complete_full_ielts_session(db) -> str:
    """Drives a Phase 7 IELTS session to completion and returns its parent `session_id`."""
    conductor = IELTSSessionConductor(db=db)
    ielts_session = run(conductor.create_session(target_band=7.0))
    run(conductor.start_session(ielts_session.id))
    run(conductor.advance(ielts_session.id))  # -> PART1_QA

    row = conductor._get(ielts_session.id)
    n_part1 = sum(len(c["questions"]) for c in row.part1_categories)
    for _ in range(n_part1):
        run(conductor.submit_answer(ielts_session.id, "/tmp/a.wav", "I think my hometown is a lovely, quiet place."))

    run(conductor.advance(ielts_session.id))  # cue card -> prep
    run(conductor.advance(ielts_session.id))  # prep -> speaking
    run(conductor.submit_answer(ielts_session.id, "/tmp/a.wav", "I'd like to describe a time I helped a neighbour carry groceries up the stairs."))
    run(conductor.submit_answer(ielts_session.id, "/tmp/a.wav", "It made me feel genuinely useful and connected to my community."))

    row = conductor._get(ielts_session.id)
    for _ in range(len(row.part3_questions)):
        run(conductor.submit_answer(ielts_session.id, "/tmp/a.wav", "I believe community spirit matters because it builds trust between people."))

    run(conductor.finalize_score(ielts_session.id))
    return ielts_session.session_id


def test_report_generated_and_cached(db_session):
    session_id = _complete_full_ielts_session(db_session)
    service = ReportService(db=db_session)

    report = run(service.get_report(session_id))
    assert report.mode == "ielts"
    assert 0 <= report.overall_score <= 100
    assert len(report.dimensions) == 4
    assert len(report.per_question_breakdown) > 0
    # every breakdown item got sentence-level annotation for free via fusion
    assert all(qb.annotated_answer is not None for qb in report.per_question_breakdown)

    cache_row = service._get_cache_row(session_id)
    assert cache_row is not None
    assert cache_row.overall_score == report.overall_score

    # second call should come from cache and be identical
    report2 = run(service.get_report(session_id))
    assert report2.overall_score == report.overall_score
    assert report2.dimensions[0].name == report.dimensions[0].name


def test_history_and_trends_across_multiple_sessions(db_session):
    ids = [_complete_full_ielts_session(db_session) for _ in range(3)]
    service = ReportService(db=db_session)
    for sid in ids:
        run(service.get_report(sid))

    history = service.list_history(mode="ielts")
    assert len(history) == 3

    trends = service.get_trends(mode="ielts")
    assert len(trends.points) == 3
    assert trends.overall_trend in ("improving", "stable", "declining")
    assert "Fluency & Coherence" in trends.dimension_averages


def test_readiness_reflects_history(db_session):
    ids = [_complete_full_ielts_session(db_session) for _ in range(3)]
    service = ReportService(db=db_session)
    for sid in ids:
        run(service.get_report(sid))

    verdict = run(service.get_readiness(mode="ielts", target_score=1.0))  # trivially met target
    assert verdict.verdict in ("ready", "almost_ready")
    assert len(verdict.evidence) >= 2


def test_coverage_matrix_against_jd(db_session):
    session_id = _complete_full_ielts_session(db_session)
    service = ReportService(db=db_session)
    matrix = run(service.get_coverage(session_id, "We need strong communication and leadership skills."))
    assert "communication" in matrix.required_skills
    assert matrix.coverage_pct >= 0


def test_replay_has_events_in_order(db_session):
    session_id = _complete_full_ielts_session(db_session)
    service = ReportService(db=db_session)
    replay = run(service.get_replay(session_id))
    assert len(replay.events) > 0
    timestamps = [e.timestamp_s for e in replay.events]
    assert timestamps == sorted(timestamps)


def test_debrief_conversation_persists(db_session):
    session_id = _complete_full_ielts_session(db_session)
    service = ReportService(db=db_session)
    report = run(service.get_report(session_id))

    debrief = DebriefService(db=db_session)
    opening = run(debrief.start_or_continue(session_id, report))
    assert opening.role == "assistant"
    assert len(opening.content) > 0

    reply = run(debrief.reply(session_id, report, "What should I focus on most?"))
    assert reply.role == "assistant"

    history = debrief.get_history(session_id)
    # opening + user message + reply
    assert len(history) == 3
    assert history[1].role == "user"


def test_model_answer_and_diff(db_session):
    session_id = _complete_full_ielts_session(db_session)
    service = ReportService(db=db_session)
    model_answer, diff = run(service.get_model_answer(session_id, 0))
    assert model_answer.is_placeholder  # no LLM configured in this test
    assert 0 <= diff.similarity_ratio <= 1


def test_model_answer_out_of_range_raises(db_session):
    session_id = _complete_full_ielts_session(db_session)
    service = ReportService(db=db_session)
    with pytest.raises(IndexError):
        run(service.get_model_answer(session_id, 999))
