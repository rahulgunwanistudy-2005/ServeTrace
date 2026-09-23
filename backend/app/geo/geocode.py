"""NYC GeoSearch lookups with an on-disk cache. Bible §8, §16.

Only the address is ever sent upstream: no name, no case, no coordinate, nothing about the
person asking. The on-disk cache is committed, so the demo and the fixtures resolve their
addresses without a network call at all, and `cache.json` is never written at runtime.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

import httpx

from app.api.errors import UpstreamError
from app.config import get_settings
from app.domain.models import GeocodeResult, LatLng

CACHE_PATH: Final = Path(__file__).resolve().parent / "cache.json"
TIMEOUT_S: Final = 5.0
RUNTIME_CACHE_MAX: Final = 5_000

MIN_CONFIDENCE: Final = 0.5
"""Below this GeoSearch is guessing at the street, so no `LatLng` is attached."""


@dataclass(frozen=True, slots=True)
class BBox:
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float

    def contains(self, point: LatLng) -> bool:
        return (
            self.min_lat <= point.lat <= self.max_lat and self.min_lng <= point.lng <= self.max_lng
        )


NYC_BBOX: Final = BBox(min_lat=40.44, max_lat=40.95, min_lng=-74.30, max_lng=-73.67)
"""The five boroughs with a little slack. ServeTrace only claims to know New York City,
so a result outside this box is reported as not found rather than as a location."""

_PUNCTUATION: Final = re.compile(r"[^A-Z0-9 ]+")
_WHITESPACE: Final = re.compile(r"\s+")

_runtime_cache: OrderedDict[str, GeocodeResult] = OrderedDict()


def cache_key(address: str) -> str:
    """Case, punctuation and spacing must not split one address into two cache entries."""
    return _WHITESPACE.sub(" ", _PUNCTUATION.sub(" ", address.upper())).strip()


@lru_cache(maxsize=1)
def _disk_cache() -> dict[str, GeocodeResult]:
    """Read once. A missing or unreadable cache is a cold cache, never a failed request."""
    try:
        raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries: dict[str, GeocodeResult] = {}
    for key, value in raw.items() if isinstance(raw, dict) else []:
        try:
            entries[key] = GeocodeResult(
                location=LatLng(lat=value["lat"], lng=value["lng"]),
                label=value.get("label", key),
                confidence=value.get("confidence", 1.0),
                source="cache",
            )
        except (KeyError, TypeError, ValueError):
            continue
    return entries


def _remember(key: str, result: GeocodeResult) -> None:
    _runtime_cache[key] = result
    _runtime_cache.move_to_end(key)
    while len(_runtime_cache) > RUNTIME_CACHE_MAX:
        _runtime_cache.popitem(last=False)


def _cached(key: str) -> GeocodeResult | None:
    hit = _disk_cache().get(key)
    if hit is not None:
        return hit
    hit = _runtime_cache.get(key)
    if hit is not None:
        _runtime_cache.move_to_end(key)
    return hit


def _first_feature(payload: Any) -> dict[str, Any] | None:
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list) or not features:
        return None
    return features[0] if isinstance(features[0], dict) else None


def _result_from(feature: dict[str, Any]) -> GeocodeResult | None:
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    properties = feature.get("properties") or {}
    if len(coordinates) != 2:
        return None
    try:
        location = LatLng(lat=float(coordinates[1]), lng=float(coordinates[0]))
    except (TypeError, ValueError):
        return None
    if not NYC_BBOX.contains(location):
        return None

    raw_confidence = properties.get("confidence")
    confidence = float(raw_confidence) if isinstance(raw_confidence, (int, float)) else 0.5
    return GeocodeResult(
        location=location,
        label=str(properties.get("label") or ""),
        confidence=min(1.0, max(0.0, confidence)),
        source="geosearch",
    )


async def geocode(address: str, client: httpx.AsyncClient | None = None) -> GeocodeResult | None:
    """Resolve a NYC street address. Only the address is ever sent upstream."""
    key = cache_key(address)
    if not key:
        return None
    hit = _cached(key)
    if hit is not None:
        return hit

    owned = client is None
    session = client or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        response = await session.get(
            get_settings().geosearch_url, params={"text": address, "size": 1}
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise UpstreamError("The address lookup service did not answer. Please try again.") from exc
    finally:
        if owned:
            await session.aclose()

    feature = _first_feature(payload)
    result = _result_from(feature) if feature else None
    if result is not None:
        _remember(key, result)
    return result


async def geocode_all(
    addresses: Iterable[str], client: httpx.AsyncClient | None = None
) -> dict[str, GeocodeResult | None]:
    """Resolve several addresses, each at most once, in order. Failures are not fatal.

    A lookup that cannot be completed leaves that address unresolved rather than failing
    the whole extraction: the user can still confirm the address by hand.
    """
    unique = list(dict.fromkeys(a for a in addresses if a and a.strip()))
    if not unique:
        return {}

    owned = client is None
    session = client or httpx.AsyncClient(timeout=TIMEOUT_S)
    resolved: dict[str, GeocodeResult | None] = {}
    try:
        for address in unique:
            try:
                resolved[address] = await geocode(address, session)
            except UpstreamError:
                resolved[address] = None
    finally:
        if owned:
            await session.aclose()
    return resolved
