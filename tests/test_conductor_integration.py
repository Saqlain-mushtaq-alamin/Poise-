import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ielts as ielts_models  # noqa: F401 - register tables on Base
from app.models import session as session_models  # noqa: F401
from app.services.ielts.conductor import IELTSSessionConductor
from app.services.ielts.state_machine import IELTSState


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


def run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)



def test_full_session_lifecycle_reaches_complete_with_scores(db_session):
    conductor = IELTSSessionConductor(db=db_session)

    session = run(conductor.create_session(target_band=7.0, topics_preference=None))
    assert session.status == IELTSState.SETUP.value

    prompt = run(conductor.start_session(session.id))
    assert prompt.state == IELTSState.PART1_INTRO.value

    prompt = run(conductor.advance(session.id))  # -> PART1_QA
    assert prompt.state == IELTSState.PART1_QA.value
    assert prompt.question is not None

    # Answer every Part 1 question (4 categories x 3 questions = 12 answers)
    row = conductor._get(session.id)
    n_part1_questions = sum(len(c["questions"]) for c in row.part1_categories)
    for _ in range(n_part1_questions):
        _, prompt = run(
            conductor.submit_answer(
                session.id,
                audio_path="/tmp/fake.wav",
                transcript="I think my hometown is a lovely, quiet place with friendly people.",
            )
        )

    assert prompt.state == IELTSState.PART2_CUE_CARD.value
    assert prompt.cue_card is not None

    prompt = run(conductor.advance(session.id))  # -> PART2_PREP
    assert prompt.state == IELTSState.PART2_PREP.value
    assert prompt.time_budget_s == 60

    prompt = run(conductor.advance(session.id))  # -> PART2_SPEAKING
    assert prompt.state == IELTSState.PART2_SPEAKING.value
    assert prompt.time_budget_s == 120

    _, prompt = run(
        conductor.submit_answer(
            session.id,
            audio_path="/tmp/fake.wav",
            transcript=(
                "I'd like to talk about a time I helped my elderly neighbour carry "
                "groceries up several flights of stairs because the lift was broken."
            ),
        )
    )
    assert prompt.state == IELTSState.PART2_FOLLOW_UP.value

    _, prompt = run(
        conductor.submit_answer(
            session.id, audio_path="/tmp/fake.wav", transcript="It made me feel genuinely useful."
        )
    )
    assert prompt.state == IELTSState.PART3_DISCUSSION.value

    row = conductor._get(session.id)
    n_part3 = len(row.part3_questions)
    for _ in range(n_part3):
        _, prompt = run(
            conductor.submit_answer(
                session.id,
                audio_path="/tmp/fake.wav",
                transcript="I believe community spirit matters because it builds trust between people.",
            )
        )

    assert prompt.state == IELTSState.SCORING.value

    score = run(conductor.finalize_score(session.id))
    assert 0 <= score.overall_band <= 9
    assert (score.overall_band * 2) % 1 == 0

    row = conductor._get(session.id)
    assert row.status == IELTSState.COMPLETE.value
    assert row.completed_at is not None
    assert row.overall_band_score["overall_band"] == score.overall_band
