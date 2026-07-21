"""Pressure simulation — Exam Mode only, per the Phase 4 spec's §4.3c.

Every trigger here is a genuine, deterministic rule over things the
conductor already knows (elapsed time, answer length, evaluation score,
how many pressure events have already fired) — not an LLM judgment call.
That's a deliberate choice: these need to fire predictably and be testable
without a model, and "was that answer short" or "are we past 75% of the
time budget" don't actually need one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PressureTechnique(str, Enum):
    DELIBERATE_SILENCE = "deliberate_silence"
    PUSHBACK = "pushback"
    CURVEBALL = "curveball"
    TIME_PRESSURE = "time_pressure"
    CLARIFICATION_REQUEST = "clarification_request"


@dataclass
class SessionContext:
    """The subset of session state the pressure simulator needs — kept
    separate from the ORM model so this module has zero DB dependency and
    can be unit tested with plain values."""

    elapsed_seconds: int
    duration_budget_seconds: int
    last_answer_word_count: int
    last_evaluation_score: float | None  # 0.0-1.0, None if not yet evaluated
    last_answer_was_complex: bool = False  # e.g. long + technical vocabulary
    questions_asked_so_far: int = 0
    techniques_used_this_session: list[PressureTechnique] = field(default_factory=list)


@dataclass
class PressureEvent:
    technique: PressureTechnique
    prompt_hint: str  # guidance text handed to the persona/LLM layer, not spoken verbatim
    duration_seconds: int | None = None  # only meaningful for DELIBERATE_SILENCE


SHORT_ANSWER_WORD_THRESHOLD = 20
WEAK_JUSTIFICATION_SCORE_THRESHOLD = 0.5
TIME_PRESSURE_TRIGGER_RATIO = 0.75

# Each technique fires at most `max_uses` times per session — repeatedly
# hammering a candidate with the same pressure move stops being a useful
# simulation and starts being noise. Some techniques (silence, gentle
# clarification) are realistic to repeat a bit; curveballs and the
# "we're running low on time" moment are realistically once-per-session.
MAX_USES = {
    PressureTechnique.DELIBERATE_SILENCE: 3,
    PressureTechnique.PUSHBACK: 2,
    PressureTechnique.CURVEBALL: 1,
    PressureTechnique.TIME_PRESSURE: 1,
    PressureTechnique.CLARIFICATION_REQUEST: 2,
}


class PressureSimulator:
    def _uses_remaining(self, technique: PressureTechnique, ctx: SessionContext) -> bool:
        count = ctx.techniques_used_this_session.count(technique)
        return count < MAX_USES[technique]

    async def should_apply_pressure(self, context: SessionContext) -> PressureEvent | None:
        """Checked in a fixed priority order — time pressure and curveballs
        are the highest-signal moments and should win over the gentler
        clarification/silence nudges if multiple conditions are true at
        once on the same turn."""

        if (
            context.duration_budget_seconds > 0
            and context.elapsed_seconds / context.duration_budget_seconds
            >= TIME_PRESSURE_TRIGGER_RATIO
            and self._uses_remaining(PressureTechnique.TIME_PRESSURE, context)
        ):
            return PressureEvent(
                technique=PressureTechnique.TIME_PRESSURE,
                prompt_hint=(
                    "We're running short on time — ask the candidate to summarize their "
                    "approach quickly."
                ),
            )

        if (
            context.last_answer_was_complex
            and context.questions_asked_so_far >= 3
            and self._uses_remaining(PressureTechnique.CURVEBALL, context)
        ):
            return PressureEvent(
                technique=PressureTechnique.CURVEBALL,
                prompt_hint=(
                    "Pose an unexpected hypothetical that tests adaptability, related to "
                    "the current topic."
                ),
            )

        if (
            context.last_evaluation_score is not None
            and context.last_evaluation_score < WEAK_JUSTIFICATION_SCORE_THRESHOLD
            and self._uses_remaining(PressureTechnique.PUSHBACK, context)
        ):
            return PressureEvent(
                technique=PressureTechnique.PUSHBACK,
                prompt_hint=(
                    "Push back on the reasoning — express mild skepticism and ask the "
                    "candidate to convince you."
                ),
            )

        if context.last_answer_was_complex and self._uses_remaining(
            PressureTechnique.CLARIFICATION_REQUEST, context
        ):
            return PressureEvent(
                technique=PressureTechnique.CLARIFICATION_REQUEST,
                prompt_hint="Say you didn't quite follow and ask them to explain it differently.",
            )

        if (
            0 < context.last_answer_word_count < SHORT_ANSWER_WORD_THRESHOLD
            and self._uses_remaining(PressureTechnique.DELIBERATE_SILENCE, context)
        ):
            return PressureEvent(
                technique=PressureTechnique.DELIBERATE_SILENCE,
                prompt_hint="Wait before responding, to see if the candidate fills the silence.",
                duration_seconds=4,
            )

        return None
