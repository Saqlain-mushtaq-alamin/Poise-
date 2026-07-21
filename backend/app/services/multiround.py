"""Multi-round interview day simulation, per the Phase 4 spec's §4.3f.

`build_interview_day` turns a company format's round structure into a
concrete, schedulable `InterviewDay` — assigning a distinct persona per
round (so "phone screen" doesn't sound like the same person as "hiring
manager") and a sensible per-round time budget. Pure data transformation,
no LLM call.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.company_formats import CompanyFormat, get_company_format
from app.services.personas import list_personas

# Maps a company format's structure entries to a human round "type" label
# and a default duration. Anything not in this table falls back to a
# generic 30-minute "technical" round rather than raising — new company
# formats shouldn't break multi-round scheduling just because this map
# hasn't been updated yet.
_ROUND_TYPE_DEFAULTS: dict[str, tuple[str, int]] = {
    "lp_behavioral": ("behavioral", 45),
    "behavioral": ("behavioral", 30),
    "technical": ("technical", 45),
    "coding": ("technical", 45),
    "system_design": ("technical", 45),
    "bar_raiser": ("hiring_manager", 45),
    "googleyness": ("culture_fit", 30),
    "product_sense": ("technical", 40),
    "culture_fit": ("culture_fit", 25),
    "technical_deep_dive": ("technical", 40),
    "live_problem_solving": ("technical", 45),
    "fit": ("culture_fit", 20),
    "case_study": ("technical", 45),
}

DEFAULT_BREAK_MINUTES = 5
MAX_ROUNDS = 5
MIN_ROUNDS = 1


@dataclass
class InterviewRound:
    round_number: int
    type: str
    persona: str
    duration_minutes: int
    focus_areas: list[str] = field(default_factory=list)


@dataclass
class InterviewDay:
    rounds: list[InterviewRound]
    company_format: str
    total_duration_minutes: int
    break_between_rounds_minutes: int = DEFAULT_BREAK_MINUTES


class InvalidRoundCountError(ValueError):
    pass


def build_interview_day(
    format_id: str,
    round_count: int | None = None,
    break_between_rounds_minutes: int = DEFAULT_BREAK_MINUTES,
) -> InterviewDay:
    """Builds a full interview day from a company format.

    `round_count`, if given, must be between 1 and 5 (per the spec's "2-5
    rounds" note — 1 is also allowed for a single-round practice session).
    Defaults to the company format's full structure length, capped at 5.
    """
    fmt: CompanyFormat = get_company_format(format_id)
    structure = fmt.structure

    if round_count is not None:
        if not (MIN_ROUNDS <= round_count <= MAX_ROUNDS):
            raise InvalidRoundCountError(
                f"round_count must be between {MIN_ROUNDS} and {MAX_ROUNDS}, got {round_count}"
            )
        structure = structure[:round_count]

    personas = list_personas()
    rounds: list[InterviewRound] = []
    for i, stage in enumerate(structure):
        round_type, duration = _ROUND_TYPE_DEFAULTS.get(stage, ("technical", 30))
        persona = personas[i % len(personas)].id
        rounds.append(
            InterviewRound(
                round_number=i + 1,
                type=round_type,
                persona=persona,
                duration_minutes=duration,
                focus_areas=[stage],
            )
        )

    total_duration = sum(r.duration_minutes for r in rounds)
    if len(rounds) > 1:
        total_duration += break_between_rounds_minutes * (len(rounds) - 1)

    return InterviewDay(
        rounds=rounds,
        company_format=format_id,
        total_duration_minutes=total_duration,
        break_between_rounds_minutes=break_between_rounds_minutes,
    )
