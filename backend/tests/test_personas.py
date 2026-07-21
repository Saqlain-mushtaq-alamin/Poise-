"""Personas — static data validation + lookup helpers."""

from __future__ import annotations

import pytest

from app.services.personas import (
    DEFAULT_PERSONA_ID,
    UnknownPersonaError,
    get_persona,
    list_personas,
)


def test_at_least_three_personas_available():
    assert len(list_personas()) >= 3


def test_each_persona_has_distinct_style():
    personas = list_personas()
    styles = {p.style for p in personas}
    assert len(styles) == len(personas)


def test_each_persona_has_a_non_empty_system_prompt():
    for persona in list_personas():
        assert len(persona.system_prompt) > 50


def test_default_persona_id_is_valid():
    assert get_persona(DEFAULT_PERSONA_ID) is not None


def test_get_persona_raises_clear_error_for_unknown_id():
    with pytest.raises(UnknownPersonaError) as exc_info:
        get_persona("not-a-real-persona")
    assert "professional" in str(exc_info.value)  # lists available options


def test_persona_ids_are_internally_consistent():
    for key, persona in __import__("app.services.personas", fromlist=["PERSONAS"]).PERSONAS.items():
        assert key == persona.id
