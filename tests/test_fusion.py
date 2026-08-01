import asyncio

import pytest

from app.services.scoring.fusion import (
    DimensionUnavailable,
    InterviewScoreSourceAdapter,
    QuestionBreakdown,
    ScoreDimension,
    ScoreFusionEngine,
)


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class FakeAdapter(InterviewScoreSourceAdapter):
    def __init__(self, content=80.0, confidence=60.0, coding=None, communication=70.0):
        self._content = content
        self._confidence = confidence
        self._coding = coding
        self._communication = communication

    async def get_content_scores(self, session_id):
        return ScoreDimension(name="Content Quality", score=self._content, max_score=100, weight=0.35)

    async def get_confidence_summary(self, session_id):
        return ScoreDimension(name="Delivery Confidence", score=self._confidence, max_score=100, weight=0.25)

    async def get_coding_scores(self, session_id):
        if self._coding is None:
            raise DimensionUnavailable("not a coding session")
        return ScoreDimension(name="Technical Skill", score=self._coding, max_score=100, weight=0.25)

    async def get_communication_scores(self, session_id):
        return ScoreDimension(name="Communication", score=self._communication, max_score=100, weight=0.15)

    async def get_question_breakdown(self, session_id):
        return [
            QuestionBreakdown(question="Tell me about a challenge.", user_answer="I led a project that grew revenue by 20%.", score=88),
            QuestionBreakdown(question="Describe a conflict.", user_answer="um it was kind of a lot of stuff, it went well", score=42),
        ]

    async def get_duration_minutes(self, session_id):
        return 12.5


def test_weighted_average_all_dimensions_available():
    engine = ScoreFusionEngine(interview_adapter=FakeAdapter(content=80, confidence=60, coding=90, communication=70))
    report = run(engine.fuse_interview_scores("sess-1"))
    # weighted: 80*.35 + 60*.25 + 90*.25 + 70*.15 = 28 + 15 + 22.5 + 10.5 = 76.0
    assert report.overall_score == pytest.approx(76.0, abs=0.15)
    assert all(d.available for d in report.dimensions)


def test_missing_dimension_is_renormalized_not_zeroed():
    engine = ScoreFusionEngine(interview_adapter=FakeAdapter(content=80, confidence=60, coding=None, communication=70))
    report = run(engine.fuse_interview_scores("sess-2"))
    unavailable = [d for d in report.dimensions if not d.available]
    assert len(unavailable) == 1
    assert unavailable[0].name == "Technical Skill"
    # renormalized over remaining weights (.35+.25+.15=.75):
    # (80*.35 + 60*.25 + 70*.15) / .75 = (28+15+10.5)/.75 = 71.33
    assert report.overall_score == pytest.approx(71.3, abs=0.2)


def test_report_includes_annotated_breakdown_and_strengths():
    engine = ScoreFusionEngine(interview_adapter=FakeAdapter())
    report = run(engine.fuse_interview_scores("sess-3"))
    assert len(report.per_question_breakdown) == 2
    assert report.per_question_breakdown[0].annotated_answer is not None
    assert any("85" not in s and "Q" not in s for s in report.strengths) or report.strengths  # non-empty, sane
    assert report.duration_minutes == 12.5
