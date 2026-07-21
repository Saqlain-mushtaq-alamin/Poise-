"""SessionStateMachine — pure, deterministic state graph testing, no LLM
or I/O involved. This is the most load-bearing piece of Phase 4 and the
most thoroughly tested."""

from __future__ import annotations

import pytest

from app.services.state_machine import InvalidTransitionError, SessionStateMachine


def test_starts_in_created():
    sm = SessionStateMachine(session_id="s1")
    assert sm.state == "created"


def test_happy_path_through_full_lifecycle():
    sm = SessionStateMachine(session_id="s1")
    sm.fire("start_session")
    assert sm.state == "setup"
    sm.fire("upload_complete")
    assert sm.state == "planning"
    sm.fire("plan_generated")
    assert sm.state == "ready"
    sm.fire("begin_interview")
    assert sm.state == "warm_up"
    sm.fire("warm_up_complete")
    assert sm.state == "in_progress_asking"
    sm.fire("question_delivered")
    assert sm.state == "in_progress_listening"
    sm.fire("answer_received")
    assert sm.state == "in_progress_evaluating"
    sm.fire("evaluation_next_question")
    assert sm.state == "in_progress_asking"
    sm.fire("end_interview")
    assert sm.state == "wrapping_up"
    sm.fire("wrap_up_questions")
    assert sm.state == "closing_chat"
    sm.fire("session_finalized")
    assert sm.state == "completed"
    sm.fire("archive")
    assert sm.state == "archived"


def test_follow_up_loop():
    sm = SessionStateMachine(session_id="s1")
    for trigger in [
        "start_session",
        "upload_complete",
        "plan_generated",
        "begin_interview",
        "warm_up_complete",
        "question_delivered",
        "answer_received",
    ]:
        sm.fire(trigger)
    assert sm.state == "in_progress_evaluating"

    sm.fire("evaluation_needs_follow_up")
    assert sm.state == "in_progress_follow_up"
    sm.fire("follow_up_delivered")
    assert sm.state == "in_progress_listening"
    sm.fire("answer_received")
    assert sm.state == "in_progress_evaluating"


def test_time_exceeded_ends_interview_from_any_in_progress_substate():
    for substate_path in [
        ["question_delivered"],  # -> listening
        ["question_delivered", "answer_received"],  # -> evaluating
    ]:
        sm = SessionStateMachine(session_id="s1")
        for trigger in [
            "start_session",
            "upload_complete",
            "plan_generated",
            "begin_interview",
            "warm_up_complete",
            *substate_path,
        ]:
            sm.fire(trigger)
        sm.fire("time_exceeded")
        assert sm.state == "wrapping_up"


def test_invalid_transition_raises_clear_error():
    sm = SessionStateMachine(session_id="s1")
    with pytest.raises(InvalidTransitionError) as exc_info:
        sm.fire("answer_received")  # can't answer before the session even starts

    assert "created" in str(exc_info.value)
    assert "s1" in str(exc_info.value)


def test_unknown_trigger_raises_clear_error():
    sm = SessionStateMachine(session_id="s1")
    with pytest.raises(InvalidTransitionError):
        sm.fire("not_a_real_trigger")


def test_is_in_progress_property():
    sm = SessionStateMachine(session_id="s1")
    assert sm.is_in_progress is False
    for trigger in [
        "start_session",
        "upload_complete",
        "plan_generated",
        "begin_interview",
        "warm_up_complete",
    ]:
        sm.fire(trigger)
    assert sm.is_in_progress is True


def test_is_active_property():
    sm = SessionStateMachine(session_id="s1")
    assert sm.is_active is True

    for trigger in [
        "start_session",
        "upload_complete",
        "plan_generated",
        "begin_interview",
        "warm_up_complete",
        "question_delivered",
        "answer_received",
        "evaluation_next_question",
        "end_interview",
        "wrap_up_questions",
        "session_finalized",
    ]:
        sm.fire(trigger)
    assert sm.state == "completed"
    assert sm.is_active is False


def test_pause_and_resume_returns_to_the_exact_prior_state():
    sm = SessionStateMachine(session_id="s1")
    for trigger in [
        "start_session",
        "upload_complete",
        "plan_generated",
        "begin_interview",
        "warm_up_complete",
        "question_delivered",
    ]:
        sm.fire(trigger)
    assert sm.state == "in_progress_listening"

    sm.pause()
    assert sm.state == "paused"
    assert sm.is_active is False

    sm.resume()
    assert sm.state == "in_progress_listening"


def test_pause_from_warm_up_is_allowed():
    sm = SessionStateMachine(session_id="s1")
    for trigger in ["start_session", "upload_complete", "plan_generated", "begin_interview"]:
        sm.fire(trigger)
    assert sm.state == "warm_up"

    sm.pause()
    sm.resume()
    assert sm.state == "warm_up"


def test_pause_from_created_is_rejected():
    sm = SessionStateMachine(session_id="s1")
    with pytest.raises(InvalidTransitionError):
        sm.pause()


def test_resume_without_a_pending_pause_is_rejected():
    sm = SessionStateMachine(session_id="s1")
    with pytest.raises(InvalidTransitionError):
        sm.resume()


def test_each_session_instance_has_independent_state():
    sm1 = SessionStateMachine(session_id="s1")
    sm2 = SessionStateMachine(session_id="s2")

    sm1.fire("start_session")
    assert sm1.state == "setup"
    assert sm2.state == "created"
