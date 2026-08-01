import asyncio
from app.services.scoring.model_answer import ModelAnswerGenerator

def run(c): return asyncio.get_event_loop().run_until_complete(c)


def test_placeholder_when_no_llm_configured():
    result = run(ModelAnswerGenerator().generate("Tell me about a challenge.", "", ""))
    assert result.is_placeholder


def test_diff_identical_answers_has_similarity_1():
    gen = ModelAnswerGenerator()
    diff = gen.diff("I led the project and delivered on time.", "I led the project and delivered on time.")
    assert diff.similarity_ratio == 1.0
    assert all(seg.kind == "unchanged" for seg in diff.segments)


def test_diff_flags_additions_and_removals():
    gen = ModelAnswerGenerator()
    diff = gen.diff("I worked on the project.", "I led the project and delivered a 20% improvement.")
    kinds = {seg.kind for seg in diff.segments}
    assert "added" in kinds
    assert 0 <= diff.similarity_ratio <= 1
