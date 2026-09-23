"""Builders for engine tests.

Every fixture is placed in *polar* coordinates around the claimed point — a bearing and a
distance in kilometres — rather than by typing latitudes. Two reasons, and the second is
the important one:

- a test that says "0.45 km east of the door" is readable, and its intent survives a
  refactor in a way that `lat=40.7131` does not;
- moving a fix "further away" then means increasing one number, and `haversine_km` is
  exactly monotone in it. The property tests in bible §11.1 are about that monotonicity,
  so they need an operation that is provably a move away and not approximately one.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.models import (
    Affidavit,
    FixKind,
    HouseholdMember,
    LatLng,
    LocationFix,
    ServiceMethod,
)
from app.engine.params import PARAMS, EngineParams
from app.geo.distance import EARTH_RADIUS_KM

NY = ZoneInfo("America/New_York")

DOOR = LatLng(lat=40.853454, lng=-73.867397)
"""A real Bronx address from the committed pool. Geography only: no person is attached."""


def destination(origin: LatLng, bearing_deg: float, km: float) -> LatLng:
    """The point `km` from `origin` along `bearing_deg`, on the same sphere as the engine."""
    angular = km / EARTH_RADIUS_KM
    lat1, lng1 = math.radians(origin.lat), math.radians(origin.lng)
    bearing = math.radians(bearing_deg)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular) + math.cos(lat1) * math.sin(angular) * math.cos(bearing)
    )
    lng2 = lng1 + math.atan2(
        math.sin(bearing) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )
    return LatLng(lat=math.degrees(lat2), lng=(math.degrees(lng2) + 540) % 360 - 180)


def away(km: float, bearing_deg: float = 90.0, origin: LatLng = DOOR) -> LatLng:
    return destination(origin, bearing_deg, km)


def ny(
    hour: int, minute: int = 0, day: int = 12, month: int = 6, year: int = 2025, fold: int = 0
) -> datetime:
    """A New York wall-clock time, which is the only kind an affidavit ever states."""
    return datetime(year, month, day, hour, minute, tzinfo=NY, fold=fold)


CLAIM_AT = ny(19, 42)
"""7:42 PM on 12 June 2025, the moment on the Maria demo affidavit."""


def fix(
    when: datetime,
    loc: LatLng,
    *,
    kind: FixKind = FixKind.PATH,
    minutes: float | None = None,
    accuracy_m: float | None = None,
    label: str | None = None,
    source: str = "timeline_android",
) -> LocationFix:
    """One location fix. `minutes` makes it an interval starting at `when`."""
    return LocationFix(
        t=when,
        t_end=when + timedelta(minutes=minutes) if minutes is not None else None,
        loc=loc,
        accuracy_m=accuracy_m,
        kind=kind,
        source=source,
        label=label,
    )


def visit(
    start: datetime, minutes: float, loc: LatLng, *, accuracy_m: float | None = None
) -> LocationFix:
    return fix(
        start,
        loc,
        kind=FixKind.VISIT,
        minutes=minutes,
        accuracy_m=accuracy_m,
        label="Timeline visit: WORK",
    )


def affidavit(
    *,
    method: ServiceMethod = ServiceMethod.SUBSTITUTE,
    served_at: datetime | None = None,
    served_location: LatLng | None = DOOR,
    confirmed: bool = True,
    **overrides: object,
) -> Affidavit:
    """A minimal, confirmed affidavit. Every field a rule reads can be overridden."""
    served = served_at or CLAIM_AT
    fields: dict[str, object] = {
        "defendant_name": "A. Defendant",
        "method": method,
        "served_at": served,
        "served_address": "2100 WHITE PLAINS ROAD, Bronx, NY 10462",
        "served_location": served_location,
        "mailing_date": served.date() + timedelta(days=2),
        "proof_filed_date": served.date() + timedelta(days=9),
        "source_sha256": "0" * 64,
        "user_confirmed": confirmed,
    }
    fields.update(overrides)
    return Affidavit.model_validate(fields)


def member(
    label: str = "Someone",
    *,
    sex: str | None = None,
    age: int | None = None,
    height_in: int | None = None,
    is_defendant: bool = False,
) -> HouseholdMember:
    return HouseholdMember.model_validate(
        {
            "label": label,
            "sex": sex,
            "age": age,
            "height_in": height_in,
            "is_defendant": is_defendant,
        }
    )


@pytest.fixture
def params() -> EngineParams:
    return PARAMS
