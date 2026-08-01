import asyncio
from app.services.scoring.readiness import ReadinessAssessor, SessionPoint

def run(c): return asyncio.get_event_loop().run_until_complete(c)


def pts(scores):
    return [SessionPoint(session_id=f"s{i}", overall_score=s, generated_at=f"2026-01-0{i+1}") for i, s in enumerate(scores)]


def test_insufficient_data_with_fewer_than_3_sessions():
    verdict = run(ReadinessAssessor().assess(pts([80, 82])))
    assert verdict.verdict == "insufficient_data"


def test_ready_verdict_for_consistent_high_scores():
    verdict = run(ReadinessAssessor().assess(pts([78, 80, 79, 81, 82]), target_score=75))
    assert verdict.verdict == "ready"
    assert verdict.trend in ("improving", "stable")


def test_not_ready_for_low_scores():
    verdict = run(ReadinessAssessor().assess(pts([40, 45, 42]), target_score=75))
    assert verdict.verdict == "not_ready"


def test_improving_trend_detected():
    verdict = run(ReadinessAssessor().assess(pts([50, 55, 60, 70, 75]), target_score=75))
    assert verdict.trend == "improving"


def test_declining_trend_detected():
    verdict = run(ReadinessAssessor().assess(pts([85, 80, 70, 60, 55]), target_score=75))
    assert verdict.trend == "declining"
