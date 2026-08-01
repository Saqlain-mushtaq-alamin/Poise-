import pytest

from app.services.ielts.state_machine import (
    IELTSState,
    IELTSStateMachine,
    InvalidTransitionError,
)


def test_full_flow_reaches_complete():
    machine = IELTSStateMachine()
    expected_order = [
        IELTSState.PART1_INTRO, IELTSState.PART1_QA, IELTSState.PART2_CUE_CARD,
        IELTSState.PART2_PREP, IELTSState.PART2_SPEAKING, IELTSState.PART2_FOLLOW_UP,
        IELTSState.PART3_DISCUSSION, IELTSState.SCORING, IELTSState.COMPLETE,
    ]
    for expected in expected_order:
        result = machine.advance()
        assert result.to_state == expected
    assert machine.is_terminal()


def test_advance_from_complete_raises():
    machine = IELTSStateMachine(state=IELTSState.COMPLETE)
    with pytest.raises(InvalidTransitionError):
        machine.advance()


def test_part2_timing_matches_real_test():
    machine = IELTSStateMachine(state=IELTSState.PART2_PREP)
    assert machine.time_budget_s() == 60
    machine.advance()
    assert machine.state == IELTSState.PART2_SPEAKING
    assert machine.time_budget_s() == 120


def test_is_speaking_state():
    assert IELTSStateMachine(state=IELTSState.PART1_QA).is_speaking_state()
    assert IELTSStateMachine(state=IELTSState.PART2_PREP).is_speaking_state() is False
    assert IELTSStateMachine(state=IELTSState.PART3_DISCUSSION).is_speaking_state()
