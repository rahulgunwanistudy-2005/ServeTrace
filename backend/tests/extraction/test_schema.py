"""The provider contract: what a model may say, and what we make of it."""

from typing import Any

import pytest

from app.domain.models import AffidavitDraft
from app.extraction.schema import (
    METHOD_VALUES,
    SCALAR_FIELDS,
    draft_from_payload,
    response_json_schema,
)


def test_every_requested_field_exists_on_the_draft() -> None:
    """The schema and the model are one contract. If they drift, extraction silently loses
    a field, so this is checked rather than trusted."""
    for name in SCALAR_FIELDS:
        assert name in AffidavitDraft.model_fields, name


def test_schema_asks_for_a_value_a_confidence_and_a_quote_for_every_field() -> None:
    schema = response_json_schema()
    for name in SCALAR_FIELDS:
        field = schema["properties"][name]
        assert field["required"] == ["value", "confidence", "evidence_quote"], name


def test_method_is_constrained_to_the_four_service_methods() -> None:
    assert response_json_schema()["properties"]["method"]["properties"]["value"]["enum"] == list(
        METHOD_VALUES
    )
    assert METHOD_VALUES == ("308_1", "308_2", "308_4", "unknown")


def test_recorded_response_parses_into_a_draft(recorded_response: dict[str, Any]) -> None:
    draft = draft_from_payload(recorded_response)

    assert draft.index_number == "CV-025236-25/BX"
    assert draft.defendant_name == "Maria Delarmo"
    assert draft.method == "308_2"
    assert draft.served_date == "2025-06-12"
    assert draft.served_time == "19:42"
    assert draft.served_address == "2100 WHITE PLAINS ROAD, Bronx, NY 10462"
    assert draft.server_name == "T. Ockham-Doyle"
    assert draft.attempts == []


def test_recorded_response_carries_confidence_and_quotes(recorded_response: dict[str, Any]) -> None:
    draft = draft_from_payload(recorded_response)

    assert draft.field_confidence["served_time"] == pytest.approx(0.96)
    assert draft.evidence_quotes["served_time"] == "at 7:42 PM"
    assert set(draft.field_confidence) >= {"index_number", "method", "recipient_description"}


def test_description_ranges_come_back_as_numbers(recorded_response: dict[str, Any]) -> None:
    description = draft_from_payload(recorded_response).recipient_description
    assert description is not None
    assert (description.age_min, description.age_max) == (56, 66)
    assert (description.height_in_min, description.height_in_max) == (71, 75)
    assert description.sex == "male"


def test_attempts_are_indexed_so_each_carries_its_own_confidence() -> None:
    payload: dict[str, Any] = {
        "attempts": [
            {
                "at_date": "2025-06-05",
                "at_time": "10:30",
                "address": "1 Somewhere Street",
                "outcome": "not_home",
                "confidence": 0.7,
                "evidence_quote": "06/05/2025 10:30 AM",
            },
            {"at_date": "2025-06-07", "at_time": "11:00", "confidence": 0.6},
        ]
    }
    draft = draft_from_payload(payload)

    assert len(draft.attempts) == 2
    assert draft.attempts[0].outcome == "not_home"
    assert draft.field_confidence["attempts[0]"] == pytest.approx(0.7)
    assert draft.evidence_quotes["attempts[0]"] == "06/05/2025 10:30 AM"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "not json at all",
        [],
        {},
        {"defendant_name": None},
        {"defendant_name": {"value": "", "confidence": 0, "evidence_quote": ""}},
        {"attempts": "three"},
        {"recipient_description": {"age_min": "not a number"}},
    ],
)
def test_a_useless_answer_costs_a_field_not_the_document(payload: object) -> None:
    """A model that omits, flattens or garbles a field must not take the rest down with it."""
    draft = draft_from_payload(payload)
    assert isinstance(draft, AffidavitDraft)
    assert draft.defendant_name is None
    assert draft.attempts == []


def test_a_flattened_field_is_still_read() -> None:
    """Models sometimes ignore the wrapper. The value is worth keeping; the confidence
    it did not give is not invented."""
    draft = draft_from_payload({"defendant_name": "Maria Delarmo", "served_time": " 19:42 "})
    assert draft.defendant_name == "Maria Delarmo"
    assert draft.served_time == "19:42"
    assert "defendant_name" not in draft.field_confidence


def test_confidence_outside_zero_to_one_is_clamped_not_rejected() -> None:
    draft = draft_from_payload(
        {"court": {"value": "Civil Court", "confidence": 4.2, "evidence_quote": "Civil Court"}}
    )
    assert draft.field_confidence["court"] == 1.0
