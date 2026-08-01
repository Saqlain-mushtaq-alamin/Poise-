from datetime import datetime
from app.services.scoring.fusion import FusedReport, ScoreDimension, ActionItem, QuestionBreakdown
from app.services.scoring.pdf_export import render_report_pdf


def test_renders_nonempty_pdf():
    report = FusedReport(
        session_id="abcdef123456", mode="interview", overall_score=76,
        dimensions=[ScoreDimension(name="Content Quality", score=80, max_score=100, weight=0.35)],
        strengths=["Clear structure"], improvements=["Add more metrics"],
        action_items=[ActionItem(priority="high", category="content", description="Add metrics", suggested_practice="Metric inventory")],
        per_question_breakdown=[QuestionBreakdown(question="Tell me about yourself.", user_answer="...", score=80)],
        duration_minutes=15, generated_at=datetime.utcnow(),
    )
    pdf_bytes = render_report_pdf(report)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000
