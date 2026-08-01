import asyncio
from app.services.scoring.coverage import CoverageMatrixBuilder
from app.services.scoring.fusion import QuestionBreakdown

def run(c): return asyncio.get_event_loop().run_until_complete(c)

JD = """
We're looking for a backend engineer with strong Python and SQL skills,
experience with AWS and Docker, and familiarity with system design and
REST API design. Leadership and mentoring experience is a plus.
"""

BREAKDOWN = [
    QuestionBreakdown(question="Walk me through your Python and SQL experience.", user_answer="I've used Python for 5 years and SQL daily.", score=80, skill_tags=["python"]),
    QuestionBreakdown(question="How do you approach system design?", user_answer="I start with requirements, then scale.", score=75, skill_tags=["system design"]),
]


def test_covered_skills_have_evidence():
    matrix = run(CoverageMatrixBuilder().build(JD, BREAKDOWN))
    python_cov = next(c for c in matrix.coverage if c.skill == "python")
    assert python_cov.covered
    assert python_cov.evidence_question is not None


def test_uncovered_skills_appear_in_gaps():
    matrix = run(CoverageMatrixBuilder().build(JD, BREAKDOWN))
    assert "docker" in matrix.gaps
    assert "aws" in matrix.gaps


def test_coverage_pct_is_consistent_with_gaps():
    matrix = run(CoverageMatrixBuilder().build(JD, BREAKDOWN))
    covered_count = len(matrix.required_skills) - len(matrix.gaps)
    expected_pct = round((covered_count / len(matrix.required_skills)) * 100, 1)
    assert matrix.coverage_pct == expected_pct


def test_empty_jd_returns_empty_matrix():
    matrix = run(CoverageMatrixBuilder().build("", BREAKDOWN))
    assert matrix.required_skills == []
    assert matrix.coverage_pct == 0.0
