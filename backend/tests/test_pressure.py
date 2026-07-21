"""PressureSimulator — pure heuristic decisions, no LLM needed, so these
run fast and deterministically."""

from __future__ import annotations

import pytest

from app.services.pressure import (
    PressureSimulator,
    PressureTechnique,
    SessionContext,
)


def _ctx(**overrides) -> SessionContext:
    defaults = dict(
        elapsed_seconds=600,
        duration_budget_seconds=2700,  # 45 min
        last_answer_word_count=80,
        last_evaluation_score=0.8,
        last_answer_was_complex=False,
        questions_asked_so_far=2,
        techniques_used_this_session=[],
    )
    defaults.update(overrides)
    return SessionContext(**defaults)


@pytest.mark.asyncio
async def test_no_pressure_when_nothing_triggers():
    sim = PressureSimulator()
    event = await sim.should_apply_pressure(_ctx())
    assert event is None


@pytest.mark.asyncio
async def test_time_pressure_fires_past_75_percent_elapsed():
    sim = PressureSimulator()
    ctx = _ctx(elapsed_seconds=2100, duration_budget_seconds=2700)  # 77.7%
    event = await sim.should_apply_pressure(ctx)
    assert event is not None
    assert event.technique == PressureTechnique.TIME_PRESSURE


@pytest.mark.asyncio
async def test_time_pressure_does_not_fire_before_75_percent():
    sim = PressureSimulator()
    ctx = _ctx(elapsed_seconds=1000, duration_budget_seconds=2700)  # 37%
    event = await sim.should_apply_pressure(ctx)
    assert event is None


@pytest.mark.asyncio
async def test_time_pressure_only_fires_once_per_session():
    sim = PressureSimulator()
    ctx = _ctx(
        elapsed_seconds=2100,
        duration_budget_seconds=2700,
        techniques_used_this_session=[PressureTechnique.TIME_PRESSURE],
    )
    event = await sim.should_apply_pressure(ctx)
    assert event is None


@pytest.mark.asyncio
async def test_pushback_fires_on_weak_evaluation_score():
    sim = PressureSimulator()
    ctx = _ctx(last_evaluation_score=0.3)
    event = await sim.should_apply_pressure(ctx)
    assert event is not None
    assert event.technique == PressureTechnique.PUSHBACK


@pytest.mark.asyncio
async def test_pushback_does_not_fire_on_strong_evaluation_score():
    sim = PressureSimulator()
    ctx = _ctx(last_evaluation_score=0.9)
    event = await sim.should_apply_pressure(ctx)
    assert event is None


@pytest.mark.asyncio
async def test_pushback_caps_at_max_uses():
    sim = PressureSimulator()
    ctx = _ctx(
        last_evaluation_score=0.2,
        techniques_used_this_session=[PressureTechnique.PUSHBACK, PressureTechnique.PUSHBACK],
    )
    event = await sim.should_apply_pressure(ctx)
    assert event is None  # max_uses for PUSHBACK is 2


@pytest.mark.asyncio
async def test_curveball_requires_complex_answer_and_at_least_3_questions():
    sim = PressureSimulator()
    ctx = _ctx(last_answer_was_complex=True, questions_asked_so_far=2)
    event = await sim.should_apply_pressure(ctx)
    # Falls through to clarification_request instead, since curveball's
    # question-count gate isn't met yet.
    assert event is not None
    assert event.technique == PressureTechnique.CLARIFICATION_REQUEST


@pytest.mark.asyncio
async def test_curveball_fires_once_gates_are_met():
    sim = PressureSimulator()
    ctx = _ctx(last_answer_was_complex=True, questions_asked_so_far=4)
    event = await sim.should_apply_pressure(ctx)
    assert event is not None
    assert event.technique == PressureTechnique.CURVEBALL


@pytest.mark.asyncio
async def test_deliberate_silence_fires_on_short_answer():
    sim = PressureSimulator()
    ctx = _ctx(last_answer_word_count=5, last_evaluation_score=0.9)
    event = await sim.should_apply_pressure(ctx)
    assert event is not None
    assert event.technique == PressureTechnique.DELIBERATE_SILENCE
    assert event.duration_seconds == 4


@pytest.mark.asyncio
async def test_deliberate_silence_does_not_fire_on_zero_word_answer():
    # An empty/skipped answer isn't "short", it's a different problem
    # (silence handling elsewhere) — don't double up on it here.
    sim = PressureSimulator()
    ctx = _ctx(last_answer_word_count=0, last_evaluation_score=0.9)
    event = await sim.should_apply_pressure(ctx)
    assert event is None


@pytest.mark.asyncio
async def test_priority_order_time_pressure_beats_everything_else():
    sim = PressureSimulator()
    ctx = _ctx(
        elapsed_seconds=2200,
        duration_budget_seconds=2700,
        last_answer_word_count=3,  # would also trigger silence
        last_evaluation_score=0.1,  # would also trigger pushback
    )
    event = await sim.should_apply_pressure(ctx)
    assert event.technique == PressureTechnique.TIME_PRESSURE


@pytest.mark.asyncio
async def test_zero_duration_budget_does_not_crash():
    sim = PressureSimulator()
    ctx = _ctx(duration_budget_seconds=0)
    event = await sim.should_apply_pressure(ctx)
    assert event is None  # no ZeroDivisionError, no false trigger
