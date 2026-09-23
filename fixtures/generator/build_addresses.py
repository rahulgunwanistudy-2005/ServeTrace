"""One-off: build `fixtures/addresses_nyc.json` from NYC GeoSearch.

Run this by hand when the address pool needs rebuilding. The JSON output is committed so
that the generator, the tests and the demo never touch the network:

    uv run python -m fixtures.generator.build_addresses

These are real public street addresses used purely as geography. No person is associated
with any of them anywhere in this repo (bible §16).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

GEOSEARCH_URL = "https://geosearch.planninglabs.nyc/v2/search"
OUT_PATH = Path(__file__).resolve().parents[1] / "addresses_nyc.json"

# Queens uses hyphenated house numbers, so it needs its own set or it under-samples badly.
HOUSE_NUMBERS: dict[str, tuple[str, ...]] = {
    "Queens": (
        "37-25",
        "88-10",
        "104-20",
        "150-30",
        "215-05",
        "45-15",
        "97-40",
        "132-12",
        "188-22",
        "68-30",
    ),
    "*": ("100", "250", "450", "620", "900", "1400", "1750", "2100", "3100", "550"),
}

STREETS: dict[str, tuple[str, ...]] = {
    "Bronx": (
        "Grand Concourse",
        "East Tremont Avenue",
        "Webster Avenue",
        "White Plains Road",
        "Southern Boulevard",
        "Jerome Avenue",
        "Westchester Avenue",
        "East Fordham Road",
        "Bruckner Boulevard",
        "Morris Avenue",
        "Boston Road",
        "Castle Hill Avenue",
    ),
    "Brooklyn": (
        "Flatbush Avenue",
        "Atlantic Avenue",
        "Bedford Avenue",
        "Ocean Avenue",
        "Nostrand Avenue",
        "Fulton Street",
        "5th Avenue",
        "Church Avenue",
        "Myrtle Avenue",
        "Coney Island Avenue",
        "Kings Highway",
        "Bushwick Avenue",
    ),
    "Manhattan": (
        "Broadway",
        "Amsterdam Avenue",
        "Lexington Avenue",
        "1st Avenue",
        "2nd Avenue",
        "3rd Avenue",
        "8th Avenue",
        "Columbus Avenue",
        "Madison Avenue",
        "St Nicholas Avenue",
        "West 145th Street",
        "East 14th Street",
    ),
    "Queens": (
        "Northern Boulevard",
        "Queens Boulevard",
        "Jamaica Avenue",
        "Roosevelt Avenue",
        "Hillside Avenue",
        "Astoria Boulevard",
        "Liberty Avenue",
        "Merrick Boulevard",
        "Union Turnpike",
        "Woodhaven Boulevard",
        "37th Avenue",
        "Springfield Boulevard",
    ),
    "Staten Island": (
        "Richmond Avenue",
        "Victory Boulevard",
        "Hylan Boulevard",
        "Forest Avenue",
        "Amboy Road",
        "Bay Street",
        "Castleton Avenue",
        "Richmond Road",
        "New Dorp Lane",
        "Arthur Kill Road",
        "Clove Road",
        "Targee Street",
    ),
}


async def _lookup(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, borough: str, query: str
) -> dict[str, Any] | None:
    async with sem:
        try:
            response = await client.get(
                GEOSEARCH_URL, params={"text": query, "size": 1}, timeout=20.0
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"  skip {query!r}: {exc}")
            return None

    features = response.json().get("features") or []
    if not features:
        return None
    props = features[0]["properties"]
    lng, lat = features[0]["geometry"]["coordinates"]
    if not props.get("housenumber") or not props.get("street"):
        return None
    if props.get("borough") != borough:
        return None
    postcode = props.get("postalcode") or ""
    street = f"{props['housenumber']} {props['street']}"
    return {
        "address": f"{street}, {borough}, NY {postcode}".strip(),
        "borough": borough,
        "zip": props.get("postalcode") or "",
        # 6 dp is ~0.1 m. Rounding here is what keeps the generator byte-reproducible.
        "lat": round(float(lat), 6),
        "lng": round(float(lng), 6),
    }


async def main() -> None:
    queries = [
        (borough, f"{number} {street}, {borough}, NY")
        for borough, streets in STREETS.items()
        for street in streets
        for number in HOUSE_NUMBERS.get(borough, HOUSE_NUMBERS["*"])
    ]
    print(f"querying GeoSearch for {len(queries)} addresses")

    sem = asyncio.Semaphore(5)
    async with httpx.AsyncClient(headers={"user-agent": "servetrace-fixtures/0.1"}) as client:
        results = await asyncio.gather(
            *(_lookup(client, sem, borough, query) for borough, query in queries)
        )

    seen: set[tuple[float, float]] = set()
    rows: list[dict[str, Any]] = []
    for row in results:
        if row is None:
            continue
        key = (row["lat"], row["lng"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    rows.sort(key=lambda r: (r["borough"], r["address"]))
    OUT_PATH.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    by_borough: dict[str, int] = {}
    for row in rows:
        by_borough[row["borough"]] = by_borough.get(row["borough"], 0) + 1
    print(f"wrote {len(rows)} addresses to {OUT_PATH}")
    for borough in sorted(by_borough):
        print(f"  {borough}: {by_borough[borough]}")


if __name__ == "__main__":
    asyncio.run(main())
