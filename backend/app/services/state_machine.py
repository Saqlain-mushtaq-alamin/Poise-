"""Interview session state machine, built with the `transitions` library.

This is pure, deterministic state logic — no LLM, no I/O — so unlike most
of Phase 4 (which leans on LLM calls this environment can't make for
real), the state graph itself is 100% real and fully tested.

State graph, exactly per the Phase 4 spec's §4.3:

    CREATED -> SETUP -> PLANNING -> READY ->
    WARM_UP -> IN_PROGRESS -> (ASKING -> LISTENING -> EVALUATING -> FOLLOW_UP) ->
    WRAPPING_UP -> CLOSING_CHAT -> COMPLETED -> ARCHIVED

`IN_PROGRESS` is modeled as a nested set of sub-states (asking/listening/
evaluating/follow_up) using dotted state names, since `transitions`
doesn't require a separate hierarchical-state-machine subclass for a graph
this shallow — dotted names keep `session.state` human-readable
(`"in_progress_evaluating"`) without extra machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from transitions import Machine, MachineError

STATES = [
    "created",
    "setup",
    "planning",
    "ready",
    "warm_up",
    "in_progress_asking",
    "in_progress_listening",
    "in_progress_evaluating",
    "in_progress_follow_up",
    "wrapping_up",
    "closing_chat",
    "completed",
    "archived",
    # Terminal-ish side state reachable from anywhere in an active session.
    "paused",
]

# (trigger, source(s), dest) — matches the spec's transition table 1:1,
# with IN_PROGRESS's internal loop expanded into its four sub-states.
TRANSITIONS = [
    {"trigger": "start_session", "source": "created", "dest": "setup"},
    {"trigger": "upload_complete", "source": "setup", "dest": "planning"},
    {"trigger": "plan_generated", "source": "planning", "dest": "ready"},
    {"trigger": "begin_interview", "source": "ready", "dest": "warm_up"},
    {"trigger": "warm_up_complete", "source": "warm_up", "dest": "in_progress_asking"},
    {
        "trigger": "question_delivered",
        "source": "in_progress_asking",
        "dest": "in_progress_listening",
    },
    {
        "trigger": "answer_received",
        "source": "in_progress_listening",
        "dest": "in_progress_evaluating",
    },
    {
        "trigger": "evaluation_needs_follow_up",
        "source": "in_progress_evaluating",
        "dest": "in_progress_follow_up",
    },
    {
        "trigger": "evaluation_next_question",
        "source": "in_progress_evaluating",
        "dest": "in_progress_asking",
    },
    {
        "trigger": "follow_up_delivered",
        "source": "in_progress_follow_up",
        "dest": "in_progress_listening",
    },
    # end_interview()/time_exceeded() can fire from any IN_PROGRESS sub-state.
    {
        "trigger": "end_interview",
        "source": [
            "in_progress_asking",
            "in_progress_listening",
            "in_progress_evaluating",
            "in_progress_follow_up",
        ],
        "dest": "wrapping_up",
    },
    {
        "trigger": "time_exceeded",
        "source": [
            "in_progress_asking",
            "in_progress_listening",
            "in_progress_evaluating",
            "in_progress_follow_up",
        ],
        "dest": "wrapping_up",
    },
    {"trigger": "wrap_up_questions", "source": "wrapping_up", "dest": "closing_chat"},
    {"trigger": "session_finalized", "source": "closing_chat", "dest": "completed"},
    {"trigger": "archive", "source": "completed", "dest": "archived"},
    # NOTE: pause/resume are deliberately NOT declared here. They're
    # hand-written methods below (need to remember which state to resume
    # into), and an auto-generated `transitions` trigger of the same name
    # would silently shadow them via instance-attribute lookup.
]

IN_PROGRESS_STATES = {
    "in_progress_asking",
    "in_progress_listening",
    "in_progress_evaluating",
    "in_progress_follow_up",
}


class InvalidTransitionError(RuntimeError):
    """Raised when an event is fired from a state that doesn't allow it —
    wraps `transitions.MachineError` with a message that names the actual
    current state, since that's what a caller debugging a 400 needs."""


@dataclass
class SessionStateMachine:
    """One instance per interview session. `session_id` is carried along
    purely for error messages / logging; persistence of `state` to the DB
    is the router's job (see routers/interview.py), not this class's."""

    session_id: str
    state: str = "created"
    _paused_from: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._machine = Machine(
            model=self,
            states=STATES,
            transitions=TRANSITIONS,
            initial=self.state,
            auto_transitions=False,
            send_event=False,
        )

    @property
    def is_in_progress(self) -> bool:
        return self.state in IN_PROGRESS_STATES

    @property
    def is_active(self) -> bool:
        """True for any state where the session is still "live" (not yet
        completed/archived and not sitting paused)."""
        return self.state not in {"completed", "archived", "paused"}

    def fire(self, trigger: str) -> None:
        """Fires a named trigger, raising a clear error on an invalid
        transition instead of `transitions`' more generic MachineError."""
        method = getattr(self, trigger, None)
        if method is None:
            raise InvalidTransitionError(f"Unknown trigger: {trigger!r}")
        try:
            method()
        except MachineError as err:
            raise InvalidTransitionError(
                f"Cannot fire {trigger!r} from state {self.state!r} (session {self.session_id})"
            ) from err

    def pause(self) -> None:
        """Overridden (rather than left as a bare `transitions` trigger) so
        we can remember which state to return to on resume()."""
        if self.state not in {
            "warm_up",
            *IN_PROGRESS_STATES,
        }:
            raise InvalidTransitionError(
                f"Cannot pause from state {self.state!r} (session {self.session_id})"
            )
        self._paused_from = self.state
        self.state = "paused"

    def resume(self) -> None:
        if self.state != "paused" or self._paused_from is None:
            raise InvalidTransitionError(f"Cannot resume — session {self.session_id} is not paused")
        self.state = self._paused_from
        self._paused_from = None
