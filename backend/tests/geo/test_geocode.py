"""Address lookup. Every test here uses a mock transport: the suite never leaves the machine."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.api.errors import UpstreamError
from app.geo import geocode as geo
from app.geo.geocode import NYC_BBOX, cache_key, geocode, geocode_all

POOL_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "addresses_nyc.json"


def feature(lng: float, lat: float, label: str, confidence: float = 0.95) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {"label": label, "confidence": confidence},
    }


def transport(
    payload: dict[str, Any], calls: list[httpx.Request] | None = None, status: int = 200
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


def refusing_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"the network was used for {request.url}")

    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def clear_runtime_cache() -> Iterator[None]:
    geo._runtime_cache.clear()
    yield
    geo._runtime_cache.clear()


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("100 East Fordham Road, Bronx, NY 10468", "100 EAST FORDHAM ROAD, BRONX NY 10468"),
        ("2100  White Plains Road", "2100 white plains road"),
    ],
)
def test_the_same_address_written_two_ways_is_one_cache_entry(first: str, second: str) -> None:
    assert cache_key(first) == cache_key(second)


@pytest.mark.asyncio
async def test_a_cached_address_never_reaches_the_network() -> None:
    """Bible §17: the demo must never fail. Every address the fixtures can produce is on
    disk, so a live demonstration does not depend on an upstream service being awake."""
    async with httpx.AsyncClient(transport=refusing_transport()) as client:
        result = await geocode("100 East Fordham Road, Bronx, NY 10468", client)

    assert result is not None
    assert result.source == "cache"
    assert result.location.lat == pytest.approx(40.861821)


@pytest.mark.asyncio
async def test_an_unknown_address_is_looked_up_and_then_remembered() -> None:
    calls: list[httpx.Request] = []
    payload = {"features": [feature(-73.9857, 40.7484, "350 5 AVENUE, Manhattan, NY 10118")]}

    async with httpx.AsyncClient(transport=transport(payload, calls)) as client:
        first = await geocode("350 5 Avenue, Manhattan, NY 10118", client)
        second = await geocode("350  5  AVENUE,  Manhattan, NY 10118", client)

    assert first is not None and first.source == "geosearch"
    assert first.location.lng == pytest.approx(-73.9857)
    assert second is not None and second.source == "geosearch"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_only_the_address_is_sent_upstream() -> None:
    """Bible §13: a bank statement's merchant and amount stay on the device. What leaves
    is the address and nothing else, so the request is asserted, not assumed."""
    calls: list[httpx.Request] = []
    payload = {"features": [feature(-73.9857, 40.7484, "350 5 AVENUE")]}

    async with httpx.AsyncClient(transport=transport(payload, calls)) as client:
        await geocode("350 5 Avenue", client)

    assert dict(calls[0].url.params) == {"text": "350 5 Avenue", "size": "1"}
    assert not calls[0].content


@pytest.mark.asyncio
async def test_an_address_outside_new_york_city_is_not_a_result() -> None:
    """ServeTrace only claims to know New York City. A Philadelphia pin on a Bronx case
    would be worse than no pin."""
    payload = {"features": [feature(-75.1652, 39.9526, "Philadelphia City Hall")]}

    async with httpx.AsyncClient(transport=transport(payload)) as client:
        assert await geocode("1400 John F Kennedy Blvd, Philadelphia", client) is None


def test_the_bounding_box_covers_the_five_boroughs() -> None:
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    outside = [row for row in pool if not NYC_BBOX.contains(_point(row))]
    assert outside == []


def _point(row: dict[str, Any]) -> Any:
    from app.domain.models import LatLng

    return LatLng(lat=row["lat"], lng=row["lng"])


@pytest.mark.asyncio
async def test_an_address_nobody_recognises_is_not_a_result() -> None:
    async with httpx.AsyncClient(transport=transport({"features": []})) as client:
        assert await geocode("999999 Nowhere Street", client) is None


@pytest.mark.asyncio
async def test_a_malformed_feature_is_not_a_result() -> None:
    payload = {"features": [{"geometry": {"coordinates": []}, "properties": {}}]}
    async with httpx.AsyncClient(transport=transport(payload)) as client:
        assert await geocode("1 Somewhere Street", client) is None


@pytest.mark.asyncio
async def test_an_upstream_failure_is_a_typed_error() -> None:
    async with httpx.AsyncClient(transport=transport({}, status=503)) as client:
        with pytest.raises(UpstreamError):
            await geocode("1 Somewhere Street", client)


@pytest.mark.asyncio
async def test_an_unreachable_service_is_a_typed_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(UpstreamError):
            await geocode("1 Somewhere Street", client)


@pytest.mark.asyncio
async def test_a_batch_asks_once_per_distinct_address() -> None:
    calls: list[httpx.Request] = []
    payload = {"features": [feature(-73.9857, 40.7484, "350 5 AVENUE")]}

    async with httpx.AsyncClient(transport=transport(payload, calls)) as client:
        resolved = await geocode_all(["350 5 Avenue", "350 5 Avenue", "", "  "], client)

    assert list(resolved) == ["350 5 Avenue"]
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_one_failed_lookup_does_not_take_the_batch_down() -> None:
    """An unresolved address costs a pin on a map. A failed extraction costs the user the
    whole document, so the batch degrades instead."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "Somewhere" in str(request.url):
            raise httpx.ConnectError("no route", request=request)
        return httpx.Response(200, json={"features": [feature(-73.9857, 40.7484, "350 5 AVENUE")]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        resolved = await geocode_all(["1 Somewhere Street", "350 5 Avenue"], client)

    assert resolved["1 Somewhere Street"] is None
    assert resolved["350 5 Avenue"] is not None


def test_the_committed_cache_matches_the_committed_address_pool() -> None:
    """`build_geocache.py` derives one from the other. If they drift, the demo starts
    making network calls again without anything failing."""
    pool = json.loads(POOL_PATH.read_text(encoding="utf-8"))
    cached = geo._disk_cache()

    assert len(cached) == len({cache_key(row["address"]) for row in pool})
    for row in pool:
        hit = cached[cache_key(row["address"])]
        assert hit.location.lat == pytest.approx(row["lat"])
        assert hit.location.lng == pytest.approx(row["lng"])
