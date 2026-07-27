"""
IELTS session state machine.

Implements the flow from the phase spec:

    SETUP -> PART1_INTRO -> PART1_QA ->
    PART2_CUE_CARD -> PART2_PREP (60s) -> PART2_SPEAKING (2min) -> PART2_FOLLOW_UP ->
    PART3_DISCUSSION ->
    SCORING -> COMPLETE

Implemented as a small dependency-free enum machine (equivalent in shape to
the `transitions`-based machine used in Phase 4's InterviewConductor, so the
two read the same way) — this avoids pulling in a second state-machine
library just for one linear flow with a couple of timed states.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IELTSState(str, Enum):
    SETUP = "setup"
    PART1_INTRO = "part1_intro"
    PART1_QA = "part1_qa"
    PART2_CUE_CARD = "part2_cue_card"
    PART2_PREP = "part2_prep"
    PART2_SPEAKING = "part2_speaking"
    PART2_FOLLOW_UP = "part2_follow_up"
    PART3_DISCUSSION = "part3_discussion"
    SCORING = "scoring"
    COMPLETE = "complete"


# Directed edges. Each state has exactly one "forward" transition except
# PART1_QA and PART3_DISCUSSION, which loop on themselves until their
# question list is exhausted (handled by the conductor, not the machine).
_TRANSITIONS: dict[IELTSState, IELTSState] = {
    IELTSState.SETUP: IELTSState.PART1_INTRO,
    IELTSState.PART1_INTRO: IELTSState.PART1_QA,
    IELTSState.PART1_QA: IELTSState.PART2_CUE_CARD,
    IELTSState.PART2_CUE_CARD: IELTSState.PART2_PREP,
    IELTSState.PART2_PREP: IELTSState.PART2_SPEAKING,
    IELTSState.PART2_SPEAKING: IELTSState.PART2_FOLLOW_UP,
    IELTSState.PART2_FOLLOW_UP: IELTSState.PART3_DISCUSSION,
    IELTSState.PART3_DISCUSSION: IELTSState.SCORING,
    IELTSState.SCORING: IELTSState.COMPLETE,
}

# Per-state time budgets in seconds. None = untimed (advances on an event,
# e.g. "candidate finished speaking" or "next question").
STATE_TIME_BUDGET_S: dict[IELTSState, int | None] = {
    IELTSState.SETUP: None,
    IELTSState.PART1_INTRO: 30,
    IELTSState.PART1_QA: 5 * 60,       # 4-5 min overall budget for the whole part
    IELTSState.PART2_CUE_CARD: 15,
    IELTSState.PART2_PREP: 60,          # exactly 60s per the real test
    IELTSState.PART2_SPEAKING: 120,     # exactly 2 min per the real test
    IELTSState.PART2_FOLLOW_UP: 30,
    IELTSState.PART3_DISCUSSION: 5 * 60,
    IELTSState.SCORING: None,
    IELTSState.COMPLETE: None,
}


@dataclass
class TransitionResult:
    from_state: IELTSState
    to_state: IELTSState
    time_budget_s: int | None = field(default=None)


class InvalidTransitionError(Exception):
    pass


class IELTSStateMachine:
    def __init__(self, state: IELTSState = IELTSState.SETUP):
        self.state = state

    def can_advance(self) -> bool:
        return self.state in _TRANSITIONS

    def advance(self) -> TransitionResult:
        if not self.can_advance():
            raise InvalidTransitionError(
                f"No transition defined from terminal/unknown state {self.state}"
            )
        next_state = _TRANSITIONS[self.state]
        result = TransitionResult(
            from_state=self.state,
            to_state=next_state,
            time_budget_s=STATE_TIME_BUDGET_S.get(next_state),
        )
        self.state = next_state
        return result

    def time_budget_s(self) -> int | None:
        return STATE_TIME_BUDGET_S.get(self.state)

    def is_terminal(self) -> bool:
        return self.state == IELTSState.COMPLETE

    def is_speaking_state(self) -> bool:
        """States where the candidate (not the examiner) should be talking."""
        return self.state in {
            IELTSState.PART1_QA,
            IELTSState.PART2_SPEAKING,
            IELTSState.PART2_FOLLOW_UP,
            IELTSState.PART3_DISCUSSION,
        }
