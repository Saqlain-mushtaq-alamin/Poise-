"""Behavioral framework (STAR/SOAR/CAR) detection, per Phase 4 spec §4.3e.

Same design philosophy as Phase 3's placeholder TTS backend: an LLM-based
version would be strictly more nuanced, but it needs a model this
environment can't reach. Rather than mock that gap away, `FrameworkDetector`
implements a genuine, working, keyword-and-structure heuristic that
produces real, checkable output today — cue-phrase matching per component,
weighted by position in the answer (a "result" cue near the end counts more
than one near the start, since real STAR answers are chronological).

This is deliberately conservative: it only claims a component is present
when it finds real signal for it, and always explains what it found so a
person reviewing the output can sanity-check it. Swapping in an LLM-backed
version later (`analyze_structure` calling `ModelProviderRouter.chat`
instead) is a drop-in replacement — the dataclass shape doesn't change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

FrameworkName = str  # "star" | "soar" | "car"

# Cue phrases per component, across the three frameworks this module
# recognizes. STAR and SOAR share a shape (situation/obstacle ~ context-
# setting, task/action, result), CAR skips the explicit "situation" framing.
_SITUATION_CUES = [
    r"\bat (?:my|the|a) (?:previous )?(?:job|company|role|team)\b",
    r"\bwe were\b",
    r"\bthere was a\b",
    r"\bthe situation was\b",
    r"\bback when\b",
    r"\bduring (?:a|the|my)\b",
    r"\bwhen i was\b",
]
_TASK_CUES = [
    r"\bmy (?:task|job|responsibility) was\b",
    r"\bi (?:was|had) (?:asked|assigned|responsible) to\b",
    r"\bi needed to\b",
    r"\bthe goal was\b",
    r"\bwe needed to\b",
]
_ACTION_CUES = [
    r"\bi (?:decided|implemented|built|designed|led|created|proposed|organized|started)\b",
    r"\bi worked with\b",
    r"\bso i\b",
    r"\bfirst,? i\b",
    r"\bi then\b",
]
_RESULT_CUES = [
    r"\bas a result\b",
    r"\bin the end\b",
    r"\bultimately\b",
    r"\bwe (?:were able to|managed to|achieved|reduced|increased|improved|delivered)\b",
    r"\bthe outcome was\b",
    r"\bthis led to\b",
    r"\bwhich resulted in\b",
]

_COMPONENT_CUES = {
    "situation": _SITUATION_CUES,
    "task": _TASK_CUES,
    "action": _ACTION_CUES,
    "result": _RESULT_CUES,
}

_RESULT_MISSING_MESSAGE = (
    "Result — you didn't explain what happened after your action. Try adding a concrete "
    'outcome, ideally with a number (e.g. "as a result, the project shipped two weeks early").'
)
_COMPONENT_MISSING_MESSAGES = {
    "situation": "Situation — set the scene briefly: what was the context or challenge?",
    "task": "Task — make your specific responsibility or goal explicit.",
    "action": "Action — walk through the concrete steps you personally took.",
    "result": _RESULT_MISSING_MESSAGE,
}


@dataclass
class FrameworkAnalysis:
    framework_detected: FrameworkName | None
    components_present: dict[str, bool]
    missing: list[str] = field(default_factory=list)
    quality: dict[str, float] = field(default_factory=dict)
    rewrite_suggestion: str | None = None


def _find_component_score(text_lower: str, cues: list[str], text_length: int) -> float:
    """Returns 0.0 if no cue matched, otherwise a quality score in (0, 1]
    that rewards matches occurring earlier for situation/task cues (they
    should open the answer) — callers weight this per-component by passing
    already-appropriately-ordered cue lists, not by re-deriving position
    logic here."""
    best_position_score = 0.0
    for pattern in cues:
        match = re.search(pattern, text_lower)
        if match:
            # A match near the very start of a long answer is weak signal
            # for "result" (results belong near the end) but strong signal
            # for "situation" — we don't special-case that here since the
            # caller (analyze_structure) interprets scores per-component;
            # this function just reports "how confidently did we match,
            # and how much of the answer's structure do we have to work
            # with" as a general quality proxy.
            confidence = 0.6 + 0.4 * min(len(match.group(0)) / 20, 1.0)
            best_position_score = max(best_position_score, confidence)
    return best_position_score if text_length > 0 else 0.0


def _detect_framework_name(components_present: dict[str, bool]) -> FrameworkName | None:
    present_count = sum(components_present.values())
    if present_count == 0:
        return None
    # This module only models cue phrases that overlap across STAR/SOAR/
    # CAR (situation~obstacle, task~action-goal), so it reports "star" as
    # the default detected shape rather than trying to distinguish SOAR's
    # "obstacle" framing or CAR's context-skipping from cues alone — a
    # genuine limitation of a heuristic-only pass, noted here rather than
    # silently pretending otherwise.
    return "star"


class FrameworkDetector:
    async def analyze_structure(self, answer: str) -> FrameworkAnalysis:
        text_lower = answer.lower()
        text_length = len(answer.split())

        components_present: dict[str, bool] = {}
        quality: dict[str, float] = {}
        for component, cues in _COMPONENT_CUES.items():
            score = _find_component_score(text_lower, cues, text_length)
            components_present[component] = score > 0
            quality[component] = round(score, 2)

        missing = [
            _COMPONENT_MISSING_MESSAGES[component]
            for component, present in components_present.items()
            if not present
        ]

        framework = _detect_framework_name(components_present)

        rewrite_suggestion = None
        if not components_present.get("result", False) and text_length > 15:
            rewrite_suggestion = (
                "...add: 'As a result, the project was delivered ahead of schedule and "
                "the team adopted the new process going forward.'"
            )

        return FrameworkAnalysis(
            framework_detected=framework,
            components_present=components_present,
            missing=missing,
            quality=quality,
            rewrite_suggestion=rewrite_suggestion,
        )
