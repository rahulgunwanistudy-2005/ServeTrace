"""The deterministic half of extraction. One test per rule in bible §12."""

from datetime import UTC, date, datetime, time
from typing import Any

import pytest

from app.domain.models import AffidavitDraft, AttemptDraft
from app.extraction.schema import draft_from_payload
from app.extraction.validators import (
    FLAGGED_CAP,
    GROUNDING_MIN_RATIO,
    NO_TEXT_LAYER_CAP,
    UNGROUNDED_CAP,
    grounding_ratio,
    infer_method,
    localize,
    normalize_method,
    parse_date,
    parse_time,
    validate,
)

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def notes_for(notes: list[Any], field: str) -> list[Any]:
    return [note for note in notes if note.field == field]


# --- dates and times --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2025-06-12", date(2025, 6, 12)),
        ("06/12/2025", date(2025, 6, 12)),
        ("June 12, 2025", date(2025, 6, 12)),
        ("Jun. 12, 2025", date(2025, 6, 12)),
        ("12 June 2025", date(2025, 6, 12)),
        ("sometime in June", None),
        ("", None),
        (None, None),
    ],
)
def test_dates_are_read_the_ways_a_form_writes_them(
    text: str | None, expected: date | None
) -> None:
    assert parse_date(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("19:42", time(19, 42)),
        ("7:42 PM", time(19, 42)),
        ("7:42PM", time(19, 42)),
        ("07:42", time(7, 42)),
        ("evening", None),
    ],
)
def test_times_are_read_the_ways_a_form_writes_them(text: str, expected: time | None) -> None:
    assert parse_time(text) == expected


def test_a_plain_local_time_gets_new_york_and_is_not_ambiguous() -> None:
    when, ambiguous = localize(date(2025, 6, 12), time(19, 42))
    assert not ambiguous
    assert when.isoformat() == "2025-06-12T19:42:00-04:00"


def test_a_time_inside_the_autumn_fold_is_flagged_not_guessed() -> None:
    """Bible §11.1: 01:30 happened twice that night. The engine takes the weaker reading;
    this module's job is only to say that there are two."""
    _, ambiguous = localize(date(2025, 11, 2), time(1, 30))
    assert ambiguous


def test_a_time_that_never_happened_is_flagged_too() -> None:
    """02:30 does not exist on the spring-forward date, so the affidavit misstates something."""
    _, ambiguous = localize(date(2025, 3, 9), time(2, 30))
    assert ambiguous


# --- method -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("308_2", "308_2"),
        ("308(2)", "308_2"),
        ("CPLR 308(4)", "308_4"),
        ("Substituted Service", "308_2"),
        ("personal", "308_1"),
        ("nail and mail", "308_4"),
        ("by carrier pigeon", None),
        (None, None),
    ],
)
def test_however_the_model_writes_the_method_it_lands_on_one_of_four(
    value: str | None, expected: str | None
) -> None:
    assert normalize_method(value) == expected


def test_the_method_is_inferred_from_the_form_wording_with_its_quote(demo_text: str) -> None:
    inferred = infer_method(demo_text)
    assert inferred is not None
    method, quote = inferred
    assert method == "308_2"
    assert quote in demo_text


def test_affix_and_mail_wins_over_the_words_it_also_contains() -> None:
    """A 308(4) affidavit says "unable ... to find a person of suitable age and discretion".
    Reading that as substituted service would misclassify every affix-and-mail case."""
    text = (
        "By affixing a true copy of each to the door of said premises. Deponent was unable "
        "with due diligence to find the Defendant or a person of suitable age and discretion."
    )
    inferred = infer_method(text)
    assert inferred is not None
    assert inferred[0] == "308_4"


def test_an_unreadable_method_becomes_unknown_rather_than_a_guess() -> None:
    draft, notes = validate(AffidavitDraft(method="served somehow"), None, now=NOW)
    assert draft.method == "unknown"
    assert notes_for(notes, "method")[0].level == "warning"


def test_no_method_and_no_text_leaves_the_field_empty() -> None:
    draft, notes = validate(AffidavitDraft(), None, now=NOW)
    assert draft.method is None
    assert notes == []


# --- evidence grounding -----------------------------------------------------------------


def test_a_quote_copied_off_the_document_is_grounded(demo_text: str) -> None:
    assert grounding_ratio(demo_text, "at 7:42 PM") == 1.0


def test_grounding_ignores_case_line_breaks_and_curly_quotes(demo_text: str) -> None:
    assert grounding_ratio(demo_text, "SUITABLE AGE\n   AND   DISCRETION") == 1.0


def test_a_near_miss_still_grounds(demo_text: str) -> None:
    """OCR drops a character or two. That is not an invented quote."""
    assert grounding_ratio(demo_text, "at 2100 WHlTE PLAINS ROAD, Bronx, NY 10462") >= (
        GROUNDING_MIN_RATIO
    )


def test_an_invented_quote_does_not_ground(demo_text: str) -> None:
    assert grounding_ratio(demo_text, "served the defendant at Union Square at noon") < (
        GROUNDING_MIN_RATIO
    )


def test_every_recorded_quote_grounds_against_the_document(
    demo_text: str, recorded_response: dict[str, Any]
) -> None:
    """The recorded answer is only a fair test if its quotes really are on the page."""
    draft = draft_from_payload(recorded_response)
    for field, quote in draft.evidence_quotes.items():
        assert grounding_ratio(demo_text, quote) >= GROUNDING_MIN_RATIO, field


def test_an_ungrounded_value_is_capped_and_flagged(demo_text: str) -> None:
    draft = AffidavitDraft(
        defendant_name="Someone Else",
        field_confidence={"defendant_name": 0.99},
        evidence_quotes={"defendant_name": "upon Someone Else, the Defendant therein named"},
    )
    validated, notes = validate(draft, demo_text, now=NOW)

    assert validated.field_confidence["defendant_name"] == UNGROUNDED_CAP
    assert notes_for(notes, "defendant_name")[0].level == "warning"


def test_a_value_with_no_quote_at_all_is_capped_too(demo_text: str) -> None:
    draft = AffidavitDraft(defendant_name="Maria Delarmo", field_confidence={"defendant_name": 1.0})
    validated, notes = validate(draft, demo_text, now=NOW)

    assert validated.field_confidence["defendant_name"] == UNGROUNDED_CAP
    assert notes_for(notes, "defendant_name")


def test_nothing_read_off_a_scan_is_trusted_above_the_cap(
    recorded_response: dict[str, Any],
) -> None:
    """Bible §12: with no text layer there is nothing to check a quote against."""
    validated, _ = validate(draft_from_payload(recorded_response), None, now=NOW)
    assert validated.field_confidence
    assert max(validated.field_confidence.values()) <= NO_TEXT_LAYER_CAP


# --- sanity checks ----------------------------------------------------------------------


def test_a_seven_digit_licence_passes_and_anything_else_is_flagged(demo_text: str) -> None:
    _, notes = validate(AffidavitDraft(server_license="1401648"), demo_text, now=NOW)
    assert not notes_for(notes, "server_license") or all(
        "seven digits" not in note.message for note in notes_for(notes, "server_license")
    )

    bad, bad_notes = validate(AffidavitDraft(server_license="14-016"), demo_text, now=NOW)
    assert bad.field_confidence["server_license"] == FLAGGED_CAP
    assert any("seven digits" in note.message for note in notes_for(bad_notes, "server_license"))
    assert bad.server_license == "14-016"  # kept, so the user can see and correct it


def test_service_in_the_future_is_flagged() -> None:
    draft = AffidavitDraft(served_date="2027-01-04", served_time="10:00")
    validated, notes = validate(draft, None, now=NOW)

    assert validated.served_at is not None
    assert any("future" in note.message for note in notes_for(notes, "served_date"))


def test_a_mailing_months_away_from_the_service_is_flagged() -> None:
    draft = AffidavitDraft(served_date="2025-06-12", served_time="19:42", mailing_date="2025-11-30")
    validated, notes = validate(draft, None, now=NOW)

    assert validated.mailing_date == "2025-11-30"
    assert notes_for(notes, "mailing_date")
    assert validated.field_confidence["mailing_date"] == FLAGGED_CAP


def test_a_mailing_a_fortnight_later_is_not_this_modules_business() -> None:
    """R-T2 in the engine judges the 20-day rule. This module only catches nonsense."""
    draft = AffidavitDraft(served_date="2025-06-12", served_time="19:42", mailing_date="2025-06-26")
    _, notes = validate(draft, None, now=NOW)
    assert not notes_for(notes, "mailing_date")


def test_an_unreadable_date_is_flagged_and_the_raw_text_is_kept() -> None:
    draft = AffidavitDraft(served_date="sometime in June", served_time="7:42 PM")
    validated, notes = validate(draft, None, now=NOW)

    assert validated.served_at is None
    assert validated.served_date == "sometime in June"
    assert notes_for(notes, "served_date")[0].level == "error"


# --- normalisation ----------------------------------------------------------------------


def test_a_good_draft_comes_back_normalised(
    demo_text: str, recorded_response: dict[str, Any]
) -> None:
    validated, notes = validate(draft_from_payload(recorded_response), demo_text, now=NOW)

    assert validated.served_at is not None
    assert validated.served_at.isoformat() == "2025-06-12T19:42:00-04:00"
    assert not validated.served_at_ambiguous
    assert validated.method == "308_2"
    assert validated.mailing_date == "2025-06-14"
    assert validated.proof_filed_date == "2025-06-23"
    assert [note.level for note in notes] == []


def test_attempts_get_their_own_timestamps(demo_text: str) -> None:
    draft = AffidavitDraft(
        attempts=[
            AttemptDraft(at_date="06/05/2025", at_time="10:30 AM", address="1 Somewhere Street"),
            AttemptDraft(at_date="not a date", at_time="10:30 AM"),
        ]
    )
    validated, notes = validate(draft, demo_text, now=NOW)

    first = validated.attempts[0]
    assert first.at is not None
    assert first.at.isoformat() == "2025-06-05T10:30:00-04:00"
    assert first.at_date == "2025-06-05"
    assert validated.attempts[1].at is None
    assert notes_for(notes, "attempts[1]")


def test_validation_never_throws_a_field_away(recorded_response: dict[str, Any]) -> None:
    """A draft that fails every check still comes back: the user can only correct what
    they can see."""
    payload = dict(recorded_response)
    payload["served_date"] = {"value": "whenever", "confidence": 0.9, "evidence_quote": "x"}
    payload["server_license"] = {"value": "nope", "confidence": 0.9, "evidence_quote": "y"}

    validated, notes = validate(draft_from_payload(payload), "unrelated text", now=NOW)

    assert validated.defendant_name == "Maria Delarmo"
    assert validated.served_date == "whenever"
    assert validated.server_license == "nope"
    assert len(notes) > 3
