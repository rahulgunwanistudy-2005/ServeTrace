"""Access to the committed NYC address pool. Never hits the network."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.domain.models import LatLng

POOL_PATH = Path(__file__).resolve().parents[1] / "addresses_nyc.json"


@dataclass(frozen=True, slots=True)
class Address:
    address: str
    borough: str
    zip: str
    lat: float
    lng: float

    @property
    def latlng(self) -> LatLng:
        return LatLng(lat=self.lat, lng=self.lng)


@lru_cache(maxsize=1)
def load_addresses() -> tuple[Address, ...]:
    if not POOL_PATH.exists():
        raise FileNotFoundError(
            f"{POOL_PATH} is missing. Rebuild it with "
            "`python -m fixtures.generator.build_addresses` (needs network)."
        )
    rows = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    return tuple(Address(**row) for row in rows)


def by_borough(borough: str) -> tuple[Address, ...]:
    return tuple(a for a in load_addresses() if a.borough == borough)


def boroughs() -> tuple[str, ...]:
    return tuple(sorted({a.borough for a in load_addresses()}))
