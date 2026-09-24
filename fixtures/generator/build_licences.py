"""One-off: build `backend/app/licences/cache.json` from NYC Open Data.

    cd backend && PYTHONPATH=.. uv run python -m fixtures.generator.build_licences

Run this by hand when the register needs refreshing. The output is committed so that the
engine, the tests and the demo never touch the network (bible §16).

Source: DCWP "Legally Operating Businesses", dataset `w7w3-xahh` on
https://data.cityofnewyork.us — public, free, no key. Two categories are taken:
`Process Server Individual` and `Process Serving Agency`.

**Four fields only.** The published rows also carry `business_name` and a home address.
Those are real people, most of them at residential addresses, and the check this feeds
answers "is this licence number real and was it in force" — which needs neither. Bible
§18.7 says real personal data does not go in this repo, so it does not.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from app.licences.registry import CACHE_PATH, LicenceCategory

DATASET_URL = "https://data.cityofnewyork.us/resource/w7w3-xahh.json"

CATEGORIES: dict[str, LicenceCategory] = {
    "Process Server Individual": LicenceCategory.INDIVIDUAL,
    "Process Serving Agency": LicenceCategory.AGENCY,
}

FIELDS = "license_nbr,business_category,license_status,license_creation_date,lic_expir_dd"


def _day(value: str | None) -> str | None:
    """`2028-02-28T00:00:00.000` to `2028-02-28`. The time part is always midnight."""
    return value.split("T", 1)[0] if value else None


def fetch(url: str = DATASET_URL) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with httpx.Client(timeout=60.0) as client:
        for label, category in CATEGORIES.items():
            response = client.get(
                url,
                params={
                    "$select": FIELDS,
                    "$where": f"business_category = '{label}'",
                    "$limit": 5000,
                },
            )
            response.raise_for_status()
            for row in response.json():
                rows.append(
                    {
                        "number": row["license_nbr"],
                        "category": category.value,
                        "status": row.get("license_status", ""),
                        "issued": _day(row.get("license_creation_date")),
                        "expires": _day(row.get("lic_expir_dd")),
                    }
                )
    return rows


def build(out_path: Path = CACHE_PATH) -> int:
    rows = fetch()
    # Sorted so a refresh produces a reviewable diff rather than a reshuffled file.
    rows.sort(key=lambda r: (r["category"], r["number"]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return len(rows)


if __name__ == "__main__":
    written = build()
    print(f"wrote {written} licences to {CACHE_PATH}")
