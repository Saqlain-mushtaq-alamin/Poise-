import asyncio
from app.services.scoring.answer_annotator import AnswerAnnotator

def run(c): return asyncio.get_event_loop().run_until_complete(c)

STAR_ANSWER = (
    "At the time, our checkout flow had a 40% drop-off rate. My task was to reduce it "
    "within a quarter. I led a redesign of the payment form and ran three A/B tests. "
    "As a result, drop-off fell to 22% within 8 weeks."
)

RAMBLING_ANSWER = "um it was kind of a lot of stuff, yeah it was good, worked hard, pretty good honestly"


def test_star_framework_detected():
    result = AnswerAnnotator().annotate_heuristic(STAR_ANSWER, "Tell me about a time you improved a metric.")
    assert result.framework_analysis.framework == "STAR"
    assert result.framework_analysis.result_has_metric
    assert result.overall_structure == "well_structured"


def test_filler_and_vague_sentences_flagged():
    result = AnswerAnnotator().annotate_heuristic(RAMBLING_ANSWER, "How did the project go?")
    ratings = {s.rating for s in result.sentences}
    assert "filler" in ratings or "weak" in ratings
    assert result.overall_structure in ("rambling", "unfocused", "too_brief")


def test_metric_sentence_rated_strong():
    result = AnswerAnnotator().annotate_heuristic(
        "We shipped the feature. Revenue increased by 15% in the first month.",
        "What was the impact?",
    )
    strong = [s for s in result.sentences if s.rating == "strong"]
    assert len(strong) >= 1
    assert "15%" in strong[0].text
