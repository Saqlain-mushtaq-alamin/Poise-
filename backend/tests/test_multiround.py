"""Multi-round interview day builder — pure data transformation."""

from __future__ import annotations

import pytest

from app.services.company_formats import UnknownCompanyFormatError
from app.services.multiround import InvalidRoundCountError, build_interview_day


def test_full_amazon_day_has_four_rounds():
    day = build_interview_day("amazon")
    assert len(day.rounds) == 4
    assert [r.type for r in day.rounds] == [
        "behavioral",
        "technical",
        "technical",
        "hiring_manager",
    ]


def test_round_numbers_are_sequential_starting_at_one():
    day = build_interview_day("google")
    assert [r.round_number for r in day.rounds] == [1, 2, 3, 4, 5]


def test_limiting_round_count_truncates_the_structure():
    day = build_interview_day("google", round_count=2)
    assert len(day.rounds) == 2
    assert day.rounds[0].type == "behavioral"


def test_round_count_below_minimum_is_rejected():
    with pytest.raises(InvalidRoundCountError):
        build_interview_day("startup", round_count=0)


def test_round_count_above_maximum_is_rejected():
    with pytest.raises(InvalidRoundCountError):
        build_interview_day("startup", round_count=6)


def test_total_duration_includes_breaks_between_rounds_only():
    day = build_interview_day("startup")  # 3 rounds -> 2 breaks
    expected_round_time = sum(r.duration_minutes for r in day.rounds)
    expected_breaks = day.break_between_rounds_minutes * (len(day.rounds) - 1)
    assert day.total_duration_minutes == expected_round_time + expected_breaks


def test_single_round_has_no_break_time_added():
    day = build_interview_day("startup", round_count=1)
    assert day.total_duration_minutes == day.rounds[0].duration_minutes


def test_different_rounds_get_different_personas_when_multiple_available():
    day = build_interview_day("amazon")  # 4 rounds, 3 personas -> cycles
    persona_sequence = [r.persona for r in day.rounds]
    assert len(set(persona_sequence)) > 1


def test_custom_break_duration_is_respected():
    day = build_interview_day("startup", break_between_rounds_minutes=10)
    assert day.break_between_rounds_minutes == 10


def test_unknown_company_format_propagates_the_clear_error():
    with pytest.raises(UnknownCompanyFormatError):
        build_interview_day("not-a-real-company")
