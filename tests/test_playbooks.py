from app.services.scoring.fusion import FusedReport, ScoreDimension, QuestionBreakdown, AnnotatedAnswer, FrameworkAnalysis
from app.services.scoring.playbooks import match_playbooks, IMPROVEMENT_PLAYBOOKS


def make_report(dims, breakdown=None):
    return FusedReport(
        session_id="s1", mode="interview", overall_score=50, dimensions=dims,
        strengths=[], improvements=[], action_items=[], per_question_breakdown=breakdown or [],
        duration_minutes=10,
    )


def test_low_content_score_matches_vague_answers_playbook():
    report = make_report([ScoreDimension(name="Content Quality", score=40, max_score=100, weight=0.35)])
    matched = match_playbooks(report)
    assert any(p["key"] == "vague_answers" for p in matched)


def test_high_scores_match_no_playbooks():
    report = make_report([ScoreDimension(name="Content Quality", score=90, max_score=100, weight=0.35)])
    matched = match_playbooks(report)
    assert matched == []


def test_rambling_answers_trigger_star_playbook():
    rambling_qb = QuestionBreakdown(
        question="q", user_answer="a", score=40,
        annotated_answer=AnnotatedAnswer(sentences=[], overall_structure="rambling", framework_analysis=FrameworkAnalysis(framework="none_detected")),
    )
    report = make_report([], breakdown=[rambling_qb, rambling_qb])
    matched = match_playbooks(report)
    assert any(p["key"] == "missing_star_structure" for p in matched)


def test_coverage_gaps_trigger_low_jd_coverage_playbook():
    report = make_report([])
    matched = match_playbooks(report, coverage_gaps=["docker", "aws"])
    assert any(p["key"] == "low_jd_coverage" for p in matched)


def test_every_playbook_has_exercises():
    for key, playbook in IMPROVEMENT_PLAYBOOKS.items():
        assert playbook["exercises"], f"{key} has no exercises"
        for ex in playbook["exercises"]:
            assert ex["name"] and ex["duration_minutes"] > 0
