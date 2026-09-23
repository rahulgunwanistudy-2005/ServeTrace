"""One-off: seed `backend/app/geo/cache.json` from the committed address pool.

    cd backend && PYTHONPATH=.. uv run python -m fixtures.generator.build_geocache

No network. `fixtures/addresses_nyc.json` was already resolved against NYC GeoSearch by
`build_addresses.py`, so this only re-keys those answers the way `geo/geocode.py` looks
them up. The point is bible §17's "the demo must never fail": every address a demo case
or a fixture can produce resolves from disk, with no upstream call in the path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.geo.geocode import CACHE_PATH, cache_key

POOL_PATH = Path(__file__).resolve().parents[1] / "addresses_nyc.json"


def build(pool_path: Path = POOL_PATH, out_path: Path = CACHE_PATH) -> int:
    pool: list[dict[str, Any]] = json.loads(pool_path.read_text(encoding="utf-8"))
    entries = {
        cache_key(row["address"]): {
            "lat": round(float(row["lat"]), 7),
            "lng": round(float(row["lng"]), 7),
            "label": row["address"],
            "confidence": 1.0,
        }
        for row in pool
    }
    out_path.write_text(
        json.dumps(dict(sorted(entries.items())), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return len(entries)


if __name__ == "__main__":
    count = build()
    print(f"wrote {count} cached addresses to {CACHE_PATH}")
