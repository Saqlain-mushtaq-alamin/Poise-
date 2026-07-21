"""FrameworkDetector — real heuristic STAR-cue matching against hand-
written sample answers (no LLM call involved)."""

from __future__ import annotations

import pytest

from app.services.framework import FrameworkDetector

FULL_STAR_ANSWER = (
    "At my previous company, we were facing a major production outage affecting "
    "checkout for all customers. My task was to identify the root cause quickly and "
    "restore service. So I decided to roll back the last deployment and dig through "
    "the logs with two teammates. As a result, we reduced downtime to under ten "
    "minutes and the team adopted a new rollback checklist afterward."
)

MISSING_RESULT_ANSWER = (
    "At my previous company, we were facing a major production outage affecting "
    "checkout for all customers. My task was to identify the root cause quickly and "
    "restore service. So I decided to roll back the last deployment and dig through "
    "the logs with two teammates."
)

VAGUE_ANSWER = "I worked on some stuff and it was fine, we did our best I think."

SHORT_ANSWER = "I fixed a bug once."


@pytest.mark.asyncio
async def test_full_star_answer_detects_all_four_components():
    detector = FrameworkDetector()
    result = await detector.analyze_structure(FULL_STAR_ANSWER)

    assert result.components_present == {
        "situation": True,
        "task": True,
        "action": True,
        "result": True,
    }
    assert result.missing == []
    assert result.rewrite_suggestion is None
    assert result.framework_detected == "star"


@pytest.mark.asyncio
async def test_missing_result_is_flagged_with_a_specific_message():
    detector = FrameworkDetector()
    result = await detector.analyze_structure(MISSING_RESULT_ANSWER)

    assert result.components_present["result"] is False
    assert any("result" in m.lower() for m in result.missing)
    assert result.rewrite_suggestion is not None


@pytest.mark.asyncio
async def test_vague_answer_detects_no_framework():
    detector = FrameworkDetector()
    result = await detector.analyze_structure(VAGUE_ANSWER)

    assert result.framework_detected is None
    assert all(not present for present in result.components_present.values())
    assert len(result.missing) == 4


@pytest.mark.asyncio
async def test_quality_scores_are_between_zero_and_one():
    detector = FrameworkDetector()
    result = await detector.analyze_structure(FULL_STAR_ANSWER)

    for score in result.quality.values():
        assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_short_answer_does_not_crash_and_gets_no_rewrite_suggestion():
    detector = FrameworkDetector()
    result = await detector.analyze_structure(SHORT_ANSWER)

    # Short answers still get analyzed, but a rewrite suggestion requires
    # enough substance (>15 words) that suggesting an addition makes sense.
    assert result.rewrite_suggestion is None


@pytest.mark.asyncio
async def test_empty_answer_does_not_crash():
    detector = FrameworkDetector()
    result = await detector.analyze_structure("")
    assert result.framework_detected is None
    assert result.missing == [
        "Situation — set the scene briefly: what was the context or challenge?",
        "Task — make your specific responsibility or goal explicit.",
        "Action — walk through the concrete steps you personally took.",
        "Result — you didn't explain what happened after your action. Try adding a concrete "
        'outcome, ideally with a number (e.g. "as a result, the project shipped two weeks '
        'early").',
    ]


@pytest.mark.asyncio
async def test_case_insensitive_matching():
    detector = FrameworkDetector()
    result = await detector.analyze_structure(FULL_STAR_ANSWER.upper())
    assert result.components_present["situation"] is True
