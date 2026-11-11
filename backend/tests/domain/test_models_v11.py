"""v1.1 contract additions. Add, don't break: every v1.0 payload still validates."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.models import (
    Affidavit,
    FieldEvidence,
    FixKind,
    LatLng,
    LeadIn,
    LocationFix,
    PageType,
    ServiceMethod,
)


def test_a_v1_0_fix_reads_as_exact_and_zone_known() -> None:
    fix = LocationFix.model_validate(
        {
            "t": "2025-06-12T23:40:00Z",
            "loc": {"lat": 40.8, "lng": -73.9},
            "kind": "path",
            "source": "timeline_android",
        }
    )
    assert fix.time_uncertainty_s == 0
    assert fix.tz_assumed is False


def test_a_photo_fix_carries_its_uncertainty() -> None:
    fix = LocationFix(
        t=datetime(2025, 6, 12, 23, 40, tzinfo=UTC),
        loc=LatLng(lat=40.8, lng=-73.9),
        kind=FixKind.PHOTO,
        source="photo",
        time_uncertainty_s=3600,
        tz_assumed=True,
    )
    assert LocationFix.model_validate_json(fix.model_dump_json()) == fix


def test_uncertainty_is_bounded_and_never_negative() -> None:
    base = {"t": "2025-06-12T23:40:00Z", "loc": {"lat": 0, "lng": 0}, "kind": "photo"}
    with pytest.raises(ValidationError):
        LocationFix.model_validate({**base, "source": "photo", "time_uncertainty_s": -1})
    with pytest.raises(ValidationError):
        LocationFix.model_validate({**base, "source": "photo", "time_uncertainty_s": 86_401})


def test_affidavit_provenance_round_trips() -> None:
    affidavit = Affidavit(
        defendant_name="Test Defendant",
        method=ServiceMethod.PERSONAL,
        served_at=datetime(2025, 6, 12, 23, 42, tzinfo=UTC),
        served_address="1 Example St, Bronx, NY",
        source_sha256="0" * 64,
        agency_name="Example Process Agency",
        evidence={"served_address": FieldEvidence(quote="1 Example St", page=1, bbox=(1, 2, 3, 4))},
    )
    assert Affidavit.model_validate_json(affidavit.model_dump_json()) == affidavit


def test_page_types_are_the_five_the_classifier_may_answer() -> None:
    assert {p.value for p in PageType} == {
        "affidavit_of_service",
        "summons_complaint",
        "judgment",
        "notice",
        "other",
    }


def _lead(**overrides: object) -> LeadIn:
    body: dict[str, object] = {
        "name": "A Person",
        "email": "person@example.org",
        "role": "legal_aid",
        "consent": True,
    }
    body.update(overrides)
    return LeadIn.model_validate(body)


def test_a_lead_needs_consent() -> None:
    with pytest.raises(ValidationError):
        _lead(consent=False)


@pytest.mark.parametrize("email", ["nope", "a@b", "a b@example.org", "@example.org"])
def test_a_lead_needs_an_email_shaped_email(email: str) -> None:
    with pytest.raises(ValidationError):
        _lead(email=email)


def test_a_lead_needs_a_known_role_and_caps_its_message() -> None:
    with pytest.raises(ValidationError):
        _lead(role="debt_collector")
    with pytest.raises(ValidationError):
        _lead(message="x" * 2001)
    assert _lead(email=" person@example.org ").email == "person@example.org"
