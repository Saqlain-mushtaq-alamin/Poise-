import asyncio

from app.services.ielts.topics import (
    PART1_TOPICS,
    PART2_CUE_CARDS,
    PART3_QUESTION_BANK,
    IELTSTopicGenerator,
)


def test_bank_has_200_plus_items():
    part1_count = sum(len(t["questions"]) for t in PART1_TOPICS)
    part2_count = len(PART2_CUE_CARDS)
    part3_count = sum(len(v) for v in PART3_QUESTION_BANK.values())
    total = part1_count + part2_count + part3_count
    assert total >= 200, f"expected 200+ items, got {total}"


def test_every_cue_card_theme_has_part3_questions():
    themes = {c["theme"] for c in PART2_CUE_CARDS}
    for theme in themes:
        assert theme in PART3_QUESTION_BANK, f"missing Part 3 bank for theme '{theme}'"
        assert len(PART3_QUESTION_BANK[theme]) >= 5


def test_generate_session_topics_is_thematically_linked():
    gen = IELTSTopicGenerator()
    topic_set = asyncio.get_event_loop().run_until_complete(
        gen.generate_session_topics(seed=42)
    )
    assert len(topic_set.part1_categories) == 4
    assert topic_set.part2_cue_card["topic"]
    linked_bank = PART3_QUESTION_BANK[topic_set.part2_cue_card["theme"]]
    # every generated part3 question either comes from the linked bank
    # or is an LLM bonus question (offline: no LLM configured, so all
    # should come from the linked bank)
    assert all(q in linked_bank for q in topic_set.part3_questions)


def test_generate_session_topics_deterministic_with_seed():
    gen = IELTSTopicGenerator()
    loop = asyncio.get_event_loop()
    a = loop.run_until_complete(gen.generate_session_topics(seed=7))
    b = loop.run_until_complete(gen.generate_session_topics(seed=7))
    assert a.part2_cue_card["topic"] == b.part2_cue_card["topic"]
