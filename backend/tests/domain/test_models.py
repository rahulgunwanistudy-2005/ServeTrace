"""Contract tests. Bible §10: these shapes are the seam between every module."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.domain.models import (
    Affidavit,
    AnalyzeRequest,
    ClaimTier,
    LatLng,
    LocationFix,
    ServiceMethod,
)

NY = timezone(timedelta(hours=-4))


def _affidavit(**overrides: object) -> Affidavit:
    base: dict[str, object] = {
        "defendant_name": "Test Defendant",
        "method": ServiceMethod.SUBSTITUTE,
        "served_at": datetime(2025, 6, 12, 19, 42, tzinfo=NY),
        "served_address": "100 Example St, Bronx, NY",
        "source_sha256": "0" * 64,
    }
    base.update(overrides)
    return Affidavit(**base)  # type: ignore[arg-type]


def test_affidavit_round_trips_through_json() -> None:
    original = _affidavit(index_number="CV-000123-25/BX")
    assert Affidavit.model_validate_json(original.model_dump_json()) == original


def test_analyze_request_round_trips_with_fixes() -> None:
    request = AnalyzeRequest(
        affidavit=_affidavit(),
        fixes=[
            LocationFix(
                t=datetime(2025, 6, 12, 19, 40, tzinfo=NY),
                loc=LatLng(lat=40.8448, lng=-73.8648),
                kind="visit",
                source="timeline_android",
            )
        ],
    )
    assert AnalyzeRequest.model_validate_json(request.model_dump_json()) == request


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _affidavit(served_at=datetime(2025, 6, 12, 19, 42))


def test_naive_datetime_is_rejected_on_fixes() -> None:
    with pytest.raises(ValidationError):
        LocationFix(
            t=datetime(2025, 6, 12, 19, 40),  # type: ignore[arg-type]
            loc=LatLng(lat=40.0, lng=-73.0),
            kind="path",
            source="test",
        )


@pytest.mark.parametrize(
    ("lat", "lng"),
    [(91.0, 0.0), (-91.0, 0.0), (0.0, 181.0), (0.0, -181.0)],
)
def test_latlng_bounds_are_enforced(lat: float, lng: float) -> None:
    with pytest.raises(ValidationError):
        LatLng(lat=lat, lng=lng)


def test_latlng_accepts_the_extremes() -> None:
    assert LatLng(lat=90.0, lng=180.0).lat == 90.0
    assert LatLng(lat=-90.0, lng=-180.0).lng == -180.0


def test_offset_datetimes_compare_across_zones() -> None:
    """The engine normalises to UTC, so equal instants must stay equal through the contract."""
    ny = LocationFix(
        t=datetime(2025, 6, 12, 19, 42, tzinfo=NY),
        loc=LatLng(lat=40.0, lng=-73.0),
        kind="path",
        source="test",
    )
    utc = LocationFix(
        t=datetime(2025, 6, 12, 23, 42, tzinfo=UTC),
        loc=LatLng(lat=40.0, lng=-73.0),
        kind="path",
        source="test",
    )
    assert ny.t == utc.t


def test_unconfirmed_is_the_default() -> None:
    """Bible §10: analysis refuses unconfirmed affidavits, so the default must be False."""
    assert _affidavit().user_confirmed is False


def test_mutable_defaults_are_not_shared_between_instances() -> None:
    first, second = _affidavit(), _affidavit()
    first.attempts.append(
        {  # type: ignore[arg-type]
            "at": datetime(2025, 6, 10, 9, 0, tzinfo=NY),
            "address": "x",
            "outcome": "not_home",
        }
    )
    assert second.attempts == []


def test_enum_values_are_the_wire_format() -> None:
    assert ServiceMethod.SUBSTITUTE == "308_2"
    assert ClaimTier.CONTRADICTED == "contradicted"
