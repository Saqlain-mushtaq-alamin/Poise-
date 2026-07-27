"""
LLM code evaluator — Phase 6.

Mount point: backend/app/services/code_evaluator.py

Wraps the shared `ModelProviderRouter` from Phase 2
(backend/app/services/provider.py) to score submitted code on
correctness, style, and efficiency, and to describe its approach.

This module does not know or care whether the router is pointed at
Ollama or a cloud model — that's the whole point of the router
abstraction. It just calls `provider.chat(..., model_role=ModelRole.REASONING)`.
"""
from __future__ import annotations

import json
import logging

from app.schemas.coding import (
    CodeEvaluation,
    CodingProblem,
    ExecutionResult,
)

logger = logging.getLogger("poise.code_evaluator")

CODE_EVAL_SYSTEM_PROMPT = """You are a senior software engineer acting as a technical interviewer's \
code reviewer. You will be given a coding problem, a candidate's submitted solution, and the result \
of running it against test cases. Evaluate the submission across four dimensions and respond with \
STRICT JSON ONLY — no markdown fences, no commentary outside the JSON object.

JSON schema:
{
  "correctness_score": float 0-100,
  "style_score": float 0-100,
  "efficiency_score": float 0-100,
  "approach_assessment": "brute_force" | "near_optimal" | "optimal",
  "time_complexity": string (e.g. "O(n log n)"),
  "space_complexity": string (e.g. "O(n)"),
  "strengths": [string, ...],
  "improvements": [string, ...],
  "alternative_approaches": [string, ...],
  "overall_score": float 0-100
}

Scoring guidance:
- correctness_score should heavily weight the actual test pass rate, but also account for
  edge-case handling visible in the code even if hidden tests were not all provided.
- style_score covers naming, readability, decomposition, and idiom-appropriateness for the language.
- efficiency_score covers time/space complexity relative to the optimal known solution for this
  problem class.
- overall_score is your holistic judgment, not a strict average — weight correctness most heavily.
- Keep strengths/improvements concrete and specific to this code, not generic advice.
- alternative_approaches should name at least one different algorithmic strategy when one exists.
"""


class CodeEvaluator:
    """Multi-dimensional code evaluation via the shared model provider router."""

    def __init__(self, provider):
        # `provider` is the ModelProviderRouter singleton from Phase 2.
        # Injected rather than imported directly so this service is easy
        # to unit test with a stub/mock provider.
        self.provider = provider

    async def evaluate(
        self,
        code: str,
        problem: CodingProblem,
        execution: ExecutionResult,
        language: str,
    ) -> CodeEvaluation:
        prompt = self._build_evaluation_prompt(code, problem, execution, language)

        # Local import to avoid a hard dependency on Phase 2's enum location
        # if this file is unit-tested in isolation before the merge.
        from app.services.provider import ModelRole  # noqa: PLC0415

        response = await self.provider.chat(
            messages=[
                {"role": "system", "content": CODE_EVAL_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model_role=ModelRole.REASONING,
            stream=False,
        )

        text = _extract_text(response)
        return self._parse(text)

    def _build_evaluation_prompt(
        self, code: str, problem: CodingProblem, execution: ExecutionResult, language: str
    ) -> str:
        test_summary = (
            f"{execution.passed_count}/{execution.total_count} test cases passed "
            f"(status: {execution.status.value})."
        )
        visible_failures = [
            tc for tc in execution.test_results if not tc.passed and not tc.is_hidden
        ][:3]
        failures_text = "\n".join(
            f"- input={f.input!r} expected={f.expected_output!r} got={f.actual_output!r}"
            for f in visible_failures
        ) or "None shown."

        return f"""## Problem
Title: {problem.title}
Difficulty: {problem.difficulty}
Topics: {', '.join(problem.topics) or 'unspecified'}

{problem.description}

## Candidate Submission (language: {language})
```{language}
{code}
```

## Execution Result
{test_summary}
Runtime: {execution.execution_time_ms}ms, Memory: {execution.memory_used_mb}MB
Sample visible failures (if any):
{failures_text}

Evaluate this submission now. Respond with the JSON object only."""

    def _parse(self, text: str) -> CodeEvaluation:
        cleaned = _strip_code_fence(text)
        try:
            data = json.loads(cleaned)
            return CodeEvaluation.model_validate(data)
        except Exception:
            logger.exception("Failed to parse code evaluation response, using fallback")
            return _fallback_evaluation()


def _extract_text(response) -> str:
    """Normalize whatever shape the provider returns into a plain string."""
    if isinstance(response, str):
        return response
    # LiteLLM-style response object
    try:
        return response.choices[0].message.content
    except AttributeError:
        pass
    if isinstance(response, dict):
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            pass
    return str(response)


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)
        t = t[1] if len(t) > 1 else t[0]
        if t.startswith("json"):
            t = t[4:]
    return t.strip()


def _fallback_evaluation() -> CodeEvaluation:
    """Degraded but valid response if the LLM output can't be parsed, so the
    round never hard-fails just because of a malformed model response."""
    return CodeEvaluation(
        correctness_score=0,
        style_score=0,
        efficiency_score=0,
        approach_assessment="brute_force",
        time_complexity="unknown",
        space_complexity="unknown",
        strengths=[],
        improvements=["Automated evaluation was unavailable for this submission."],
        alternative_approaches=[],
        overall_score=0,
    )
