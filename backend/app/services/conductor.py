"""Q&A orchestration loop, per the Phase 4 spec's §4.4 and §4.3g
(interviewer reactions).

Question delivery (persona-appropriate transition phrasing) and reaction
picking are real, deterministic (seedable) logic — no LLM needed for
"what's a natural way to say 'got it, next question' in this persona's
voice". Evaluating an answer and generating a genuinely context-aware
follow-up both need an LLM call this environment can't make for real, so
those go through `ModelProviderRouter.chat` and are tested with the
provider mocked, same pattern as every other Phase 4 service.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

from app.services.framework import FrameworkAnalysis, FrameworkDetector
from app.services.personas import Persona
from app.services.planner import PlannedQuestion
from app.services.provider import ModelProviderRouter, ModelRole

FOLLOW_UP_SCORE_THRESHOLD = 0.6

# Phrase banks per persona style, used to introduce a question naturally
# instead of reading it cold — e.g. "Got it. Next up:" vs "Alright, let's
# dig into this:". Picked with a caller-supplied `random.Random` so tests
# can seed it for determinism; falls back to the module-level `random` in
# normal use.
_TRANSITION_PHRASES: dict[str, list[str]] = {
    "professional": [
        "Great, thank you. Let's move on.",
        "Got it. Next question:",
        "Thanks for sharing that.",
    ],
    "tough": ["Alright.", "Okay, moving on.", "Let's continue."],
    "friendly": [
        "Love that, thanks! Okay, next up:",
        "Nice, I appreciate you sharing that.",
        "Cool, let's keep going.",
    ],
}
_DEFAULT_TRANSITIONS = ["Let's continue.", "Next question:"]

_FOLLOW_UP_TRANSITIONS: dict[str, list[str]] = {
    "professional": [
        "Could you tell me a bit more about that?",
        "I'd like to dig into that a little further —",
    ],
    "tough": ["I want to push on that a bit.", "Let's go deeper there —"],
    "friendly": ["Ooh, I want to hear more about that!", "That's interesting — can you expand?"],
}

# Brief natural verbal cues an interviewer might give while listening,
# bucketed by how strong the just-evaluated answer was (weak/medium/strong
# reactions read differently — "interesting" reads as genuine curiosity
# for a strong answer and a bit loaded for a weak one).
_REACTIONS_BY_SCORE_BAND: dict[str, list[str]] = {
    "strong": ["Interesting.", "That's a great example.", "I like that."],
    "medium": ["I see.", "Mm-hmm.", "Okay, got it."],
    "weak": ["I see.", "Alright.", "Understood."],
}


@dataclass
class QuestionDelivery:
    text: str
    question_id: str
    is_follow_up: bool = False


@dataclass
class AnswerEvaluation:
    score: float
    feedback: str
    next_action: str  # "follow_up" | "next_question"
    follow_up_question: str | None = None
    framework_analysis: FrameworkAnalysis | None = None
    reaction: str | None = None


@dataclass
class _RawEvaluation:
    score: float
    feedback: str
    gaps: list[str] = field(default_factory=list)


def _score_band(score: float) -> str:
    if score >= 0.75:
        return "strong"
    if score >= 0.45:
        return "medium"
    return "weak"


def pick_reaction(score: float, rng: random.Random | None = None) -> str:
    rng = rng or random
    band = _score_band(score)
    return rng.choice(_REACTIONS_BY_SCORE_BAND[band])


def _pick_transition(persona: Persona, is_follow_up: bool, rng: random.Random | None = None) -> str:
    rng = rng or random
    bank = (_FOLLOW_UP_TRANSITIONS if is_follow_up else _TRANSITION_PHRASES).get(
        persona.id, _DEFAULT_TRANSITIONS
    )
    return rng.choice(bank)


EVALUATION_PROMPT_TEMPLATE = """You are evaluating an interview answer. Question: "{question}"
Evaluation criteria: {criteria}
Candidate's answer: "{answer}"

Respond with ONLY a JSON object (no markdown fences, no commentary):
{{"score": <float 0.0-1.0>, "feedback": "...", "gaps": ["what's missing or weak, if anything"]}}"""

FOLLOW_UP_PROMPT_TEMPLATE = """You are conducting an interview. The candidate was asked: \
"{question}" and answered: "{answer}"

Identified gaps in their answer: {gaps}

Generate ONE natural, specific follow-up question that probes one of these gaps, grounded \
in what they actually said — not a generic follow-up. Respond with ONLY the follow-up \
question text, no quotes, no preamble."""


class InterviewConductor:
    def __init__(
        self,
        provider: ModelProviderRouter,
        framework_detector: FrameworkDetector | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.provider = provider
        self.framework_detector = framework_detector or FrameworkDetector()
        self.rng = rng

    def deliver_question(
        self, question: PlannedQuestion, persona: Persona, is_follow_up: bool = False
    ) -> QuestionDelivery:
        transition = _pick_transition(persona, is_follow_up, self.rng)
        text = f"{transition} {question.text}".strip()
        return QuestionDelivery(text=text, question_id=question.id, is_follow_up=is_follow_up)

    async def _evaluate_answer(self, answer: str, question: PlannedQuestion) -> _RawEvaluation:
        prompt = EVALUATION_PROMPT_TEMPLATE.format(
            question=question.text,
            criteria=", ".join(question.evaluation_criteria) or "general quality and specificity",
            answer=answer,
        )
        raw = await self.provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model_role=ModelRole.REASONING,
            stream=False,
        )
        payload = json.loads(raw)
        return _RawEvaluation(
            score=float(payload["score"]),
            feedback=payload["feedback"],
            gaps=payload.get("gaps", []),
        )

    async def _generate_dynamic_follow_up(
        self, answer: str, question: PlannedQuestion, evaluation: _RawEvaluation
    ) -> str:
        prompt = FOLLOW_UP_PROMPT_TEMPLATE.format(
            question=question.text, answer=answer, gaps="; ".join(evaluation.gaps)
        )
        return await self.provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model_role=ModelRole.REASONING,
            stream=False,
        )

    async def process_answer(self, answer: str, question: PlannedQuestion) -> AnswerEvaluation:
        evaluation = await self._evaluate_answer(answer, question)
        reaction = pick_reaction(evaluation.score, self.rng)

        framework_analysis: FrameworkAnalysis | None = None
        if question.source == "behavioral_framework" or "behavioral" in question.skills_tested:
            framework_analysis = await self.framework_detector.analyze_structure(answer)

        needs_follow_up = evaluation.score < FOLLOW_UP_SCORE_THRESHOLD and bool(evaluation.gaps)

        if needs_follow_up:
            follow_up_text = await self._generate_dynamic_follow_up(answer, question, evaluation)
            return AnswerEvaluation(
                score=evaluation.score,
                feedback=evaluation.feedback,
                next_action="follow_up",
                follow_up_question=follow_up_text,
                framework_analysis=framework_analysis,
                reaction=reaction,
            )

        return AnswerEvaluation(
            score=evaluation.score,
            feedback=evaluation.feedback,
            next_action="next_question",
            framework_analysis=framework_analysis,
            reaction=reaction,
        )
