"""
Sentence-level answer feedback (spec §8.8) — breaks an answer into
sentences and rates each one, plus STAR/SOAR framework detection.

Heuristic-first by design (like Phase 7's Fluency & Coherence scorer):
the rating logic below is deterministic and explainable without an LLM,
so a report always has real, non-generic sentence feedback. When a
provider is configured, `annotate()` prefers the LLM's finer-grained
judgement and falls back to the heuristic path if that call fails.
"""

from __future__ import annotations

import re
from typing import Optional

from app.services.scoring.fusion import AnnotatedAnswer, FrameworkAnalysis, SentenceAnnotation
from app.services.scoring.llm_client import ScoringLLMClient

FILLER_PHRASES = {"um", "uh", "erm", "you know", "sort of", "kind of", "basically", "i guess", "yeah it was good"}
VAGUE_PHRASES = {
    "it went well", "worked hard", "really hard", "a lot of", "kind of a lot",
    "did a good job", "went really well", "pretty good", "some stuff", "various things",
}
METRIC_PATTERN = re.compile(r"\d+(\.\d+)?\s*(%|percent|x|ms|seconds?|minutes?|hours?|days?|weeks?|months?|\$|k\b|million|users?|engineers?)", re.I)
TIMELINE_WORDS = {"week", "weeks", "month", "months", "year", "years", "day", "days", "quarter"}

HIGHLIGHT_COLOR = {"strong": "green", "adequate": "yellow", "weak": "red", "filler": "yellow", "off_topic": "gray"}

STAR_MARKERS = {
    "situation": {"situation", "at the time", "background", "context", "we had", "our team was"},
    "task": {"my task", "i needed to", "goal was", "responsible for", "had to"},
    "action": {"i led", "i built", "i designed", "i implemented", "i decided", "i created", "i worked"},
    "result": {"as a result", "resulted in", "which led to", "the outcome", "ultimately", "in the end"},
}


def _split_sentences(text: str) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw if s.strip()]


class AnswerAnnotator:
    def __init__(self, llm_client: Optional[ScoringLLMClient] = None):
        self.llm_client = llm_client or ScoringLLMClient()

    async def annotate(self, answer: str, question: str, criteria: Optional[list[str]] = None) -> AnnotatedAnswer:
        llm_result = await self.llm_client.annotate_sentences(answer, question)
        if llm_result:
            try:
                return self._from_llm_result(llm_result, answer)
            except (KeyError, TypeError):
                pass  # malformed LLM output — fall through to heuristic
        return self.annotate_heuristic(answer, question)

    def annotate_heuristic(self, answer: str, question: str) -> AnnotatedAnswer:
        sentences = _split_sentences(answer)
        annotations = [self._rate_sentence(s) for s in sentences]
        structure = self._assess_structure(annotations)
        framework = self._detect_framework(answer)
        return AnnotatedAnswer(sentences=annotations, overall_structure=structure, framework_analysis=framework)

    # -- heuristic rating ----------------------------------------------------

    def _rate_sentence(self, sentence: str) -> SentenceAnnotation:
        lower = sentence.lower()
        has_metric = bool(METRIC_PATTERN.search(sentence))
        is_filler = any(p in lower for p in FILLER_PHRASES) and len(sentence.split()) < 8
        is_vague = any(p in lower for p in VAGUE_PHRASES) and not has_metric

        if is_filler:
            return SentenceAnnotation(
                text=sentence, rating="filler",
                reason="Low-content filler — doesn't add new information",
                suggestion="Replace with a specific detail or cut entirely",
                highlight_color=HIGHLIGHT_COLOR["filler"],
            )
        if has_metric:
            return SentenceAnnotation(
                text=sentence, rating="strong",
                reason="Specific, measurable detail cited",
                suggestion=None,
                highlight_color=HIGHLIGHT_COLOR["strong"],
            )
        if is_vague:
            return SentenceAnnotation(
                text=sentence, rating="weak",
                reason="Vague — no concrete example, number, or name",
                suggestion="Add a specific number, name, or timeframe",
                highlight_color=HIGHLIGHT_COLOR["weak"],
            )
        if len(sentence.split()) >= 6:
            return SentenceAnnotation(
                text=sentence, rating="adequate",
                reason="Clear statement, but could be sharpened with a specific",
                suggestion=None,
                highlight_color=HIGHLIGHT_COLOR["adequate"],
            )
        return SentenceAnnotation(
            text=sentence, rating="adequate",
            reason="Brief but on-topic",
            suggestion=None,
            highlight_color=HIGHLIGHT_COLOR["adequate"],
        )

    def _assess_structure(self, annotations: list[SentenceAnnotation]) -> str:
        if not annotations:
            return "too_brief"
        if len(annotations) <= 2:
            return "too_brief"
        weak_or_filler = sum(1 for a in annotations if a.rating in ("weak", "filler", "off_topic"))
        ratio = weak_or_filler / len(annotations)
        if ratio > 0.5:
            return "rambling" if len(annotations) > 6 else "unfocused"
        return "well_structured"

    def _detect_framework(self, answer: str) -> FrameworkAnalysis:
        lower = answer.lower()
        situation = any(m in lower for m in STAR_MARKERS["situation"])
        task = any(m in lower for m in STAR_MARKERS["task"])
        action = any(m in lower for m in STAR_MARKERS["action"])
        result = any(m in lower for m in STAR_MARKERS["result"]) or bool(METRIC_PATTERN.search(answer))
        result_has_metric = bool(METRIC_PATTERN.search(answer))

        detected_count = sum([situation, task, action, result])
        framework = "STAR" if detected_count >= 3 else "none_detected"

        return FrameworkAnalysis(
            framework=framework, situation_present=situation, task_present=task,
            action_present=action, result_present=result, result_has_metric=result_has_metric,
        )

    # -- LLM result parsing ----------------------------------------------------

    def _from_llm_result(self, data: dict, fallback_answer: str) -> AnnotatedAnswer:
        sentences = [
            SentenceAnnotation(
                text=s["text"], rating=s["rating"], reason=s.get("reason", ""),
                suggestion=s.get("suggestion"),
                highlight_color=HIGHLIGHT_COLOR.get(s["rating"], "gray"),
            )
            for s in data["sentences"]
        ]
        framework = self._detect_framework(fallback_answer)
        return AnnotatedAnswer(
            sentences=sentences,
            overall_structure=data.get("overall_structure", self._assess_structure(sentences)),
            framework_analysis=framework,
        )
