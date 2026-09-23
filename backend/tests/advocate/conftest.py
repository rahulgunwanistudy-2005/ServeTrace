"""Builders for advocate-mode tests.

Records are placed in *polar* coordinates around one Bronx door, the same convention
`tests/engine/conftest.py` uses and for the same reason: "8 km north of the depot" survives
a refactor where `lat=40.9` does not, and moving a record further away is one number.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.models import LatLng, ServiceRecord
from tests.engine.conftest import destination

NY = ZoneInfo("America/New_York")

DEPOT = LatLng(lat=40.853454, lng=-73.867397)
"""Geography only: a real Bronx address from the committed pool, no person attached."""

DAY_START = datetime(2025, 3, 4, 9, 0, tzinfo=NY)


def at(minutes: float) -> datetime:
    return DAY_START + timedelta(minutes=minutes)


def km_away(km: float, bearing_deg: float = 90.0) -> LatLng:
    return destination(DEPOT, bearing_deg, km)


def record(
    minutes: float,
    km: float = 0.0,
    *,
    server_id: str = "SRV-001",
    outcome: str | None = "served",
    address: str | None = None,
    desc: str | None = None,
    bearing: float = 90.0,
    case_ref: str | None = None,
) -> ServiceRecord:
    return ServiceRecord(
        server_id=server_id,
        at=at(minutes),
        loc=km_away(km, bearing) if km else DEPOT,
        address=address if address is not None else f"{int(km * 100) or 1} SYNTHETIC STREET",
        case_ref=case_ref,
        outcome=outcome,
        recipient_desc=desc,
    )
