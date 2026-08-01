import asyncio

from app.services.ielts.scorer import IELTSBandEvaluator

STRONG_ANSWER = (
    "Well, I grew up in a small coastal town, and although it was quiet, I "
    "really loved it because the community was so close-knit. For example, "
    "everyone knew each other, which meant that if you ever needed help, "
    "there was always someone around. However, as I got older, I moved to "
    "the city for university, and my perspective on my hometown changed "
    "quite a lot as a result of that experience."
)

WEAK_ANSWER = "um my town is uh like small um good uh yeah"


def test_strong_answer_outscores_weak_answer():
    evaluator = IELTSBandEvaluator()
    loop = asyncio.get_event_loop()

    strong = loop.run_until_complete(
        evaluator.score_response(transcript=STRONG_ANSWER, context="Part 1: hometown")
    )
    weak = loop.run_until_complete(
        evaluator.score_response(transcript=WEAK_ANSWER, context="Part 1: hometown")
    )

    assert strong.overall_band > weak.overall_band
    assert strong.fluency_and_coherence.band > weak.fluency_and_coherence.band


def test_overall_band_is_rounded_to_half_increment():
    evaluator = IELTSBandEvaluator()
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(
        evaluator.score_response(transcript=STRONG_ANSWER, context="Part 1: hometown")
    )
    assert (result.overall_band * 2) % 1 == 0  # i.e. a multiple of 0.5
