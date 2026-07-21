"""Company-specific interview formats — static data validation."""

from __future__ import annotations

import pytest

from app.services.company_formats import (
    DEFAULT_FORMAT_ID,
    UnknownCompanyFormatError,
    get_company_format,
    list_company_formats,
)


def test_all_spec_formats_are_present():
    ids = {f.id for f in list_company_formats()}
    assert {"amazon", "google", "meta", "startup", "consulting"} <= ids


def test_amazon_format_lists_leadership_principles():
    amazon = get_company_format("amazon")
    assert len(amazon.principles) >= 10
    assert "Customer Obsession" in amazon.principles


def test_non_amazon_formats_have_no_principles():
    google = get_company_format("google")
    assert google.principles == []


def test_every_format_has_a_non_empty_structure():
    for fmt in list_company_formats():
        assert len(fmt.structure) > 0


def test_default_format_id_is_valid():
    assert get_company_format(DEFAULT_FORMAT_ID) is not None


def test_unknown_format_raises_clear_error():
    with pytest.raises(UnknownCompanyFormatError) as exc_info:
        get_company_format("not-a-real-company")
    assert "amazon" in str(exc_info.value)
