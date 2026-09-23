"""The committed advocate demo file: a legible spreadsheet with a known answer.

    python -m fixtures.generator.advocate_demo

Different from `advocate.py`, which builds the 2,000-row scoring corpus. This one is what
a judge or a legal-aid worker actually opens: four servers, one week, few enough rows to
read, and a pattern that is obvious once the report points at it. It is committed as XLSX
because that is what a case-management system exports, and because it exercises the
openpyxl path rather than the CSV one.

Everything is synthetic — every licence number, every case reference, every description.
The addresses are real New York City streets used as geography and nothing else
(bible §16). The expected report is committed beside it, so the demo is also a test.
"""

from __future__ import annotations

import io
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import Workbook

from app.geo.distance import haversine_km

from .addresses import Address, boroughs, by_borough
from .writer import write_bytes, write_json

TZ = ZoneInfo("America/New_York")

OUT_DIR = Path(__file__).resolve().parents[1] / "demo_cases"
XLSX_PATH = OUT_DIR / "advocate_servers.xlsx"
EXPECTED_PATH = OUT_DIR / "advocate_expected.json"

SEED = 20260923
WEEK_START = datetime(2025, 3, 3, 9, 0, tzinfo=TZ)
DAYS = 5

COLUMNS = (
    "server_id",
    "service_datetime",
    "latitude",
    "longitude",
    "address",
    "case_number",
    "outcome",
    "person_served_description",
)

# The mapping the demo screen pre-fills, so nobody has to guess at the columns.
DEMO_MAPPING = {
    "server_id": "server_id",
    "at": "service_datetime",
    "lat": "latitude",
    "lng": "longitude",
    "address": "address",
    "case_ref": "case_number",
    "outcome": "outcome",
    "recipient_desc": "person_served_description",
}

SEX = ("M", "F")
BUILD = ("Slim", "Medium", "Heavy")
HAIR = ("Black", "Brown", "Blonde", "Gray", "Red")


@dataclass(frozen=True, slots=True)
class ServerSpec:
    server_id: str
    borough: str
    per_day: tuple[int, int]
    impossible_hops: int = 0
    reused_description_doors: int = 0


SPECS: tuple[ServerSpec, ...] = (
    ServerSpec("1387421", "Bronx", per_day=(7, 10)),
    ServerSpec(
        "1422908", "Brooklyn", per_day=(9, 13), impossible_hops=4, reused_description_doors=6
    ),
    ServerSpec("1390115", "Queens", per_day=(6, 9)),
    ServerSpec(
        "1451760", "Manhattan", per_day=(8, 12), impossible_hops=2, reused_description_doors=4
    ),
)


@dataclass
class Row:
    server_id: str
    at: datetime
    address: Address
    case_ref: str
    outcome: str
    description: str


@dataclass
class Truth:
    server_id: str
    n_records: int = 0
    impossible_hops: int = 0
    reused_description: str | None = None
    reused_description_doors: int = 0
    notes: list[str] = field(default_factory=list)


def _description(rng: random.Random) -> str:
    return (
        f"{rng.choice(SEX)}/{rng.choice(BUILD)}/{rng.choice(HAIR)}/"
        f"{rng.randrange(25, 70, 5)}/{rng.randrange(60, 76)}/{rng.randrange(120, 220, 10)}"
    )


def _far_from(rng: random.Random, origin: Address, min_km: float) -> Address:
    """An address at least `min_km` away, for a hop nobody could have driven."""
    pool = [a for borough in boroughs() for a in by_borough(borough)]
    for _ in range(300):
        candidate = rng.choice(pool)
        if haversine_km(origin.latlng, candidate.latlng) >= min_km:
            return candidate
    raise RuntimeError("no address far enough from the origin; the pool is too small")


def _week(rng: random.Random, spec: ServerSpec) -> list[Row]:
    """One ordinary working week: doors in one borough, sane gaps, mixed outcomes."""
    local = list(by_borough(spec.borough))
    if not local:
        raise RuntimeError(f"no committed addresses in {spec.borough}")

    rows: list[Row] = []
    for day in range(DAYS):
        when = WEEK_START + timedelta(days=day)
        for _ in range(rng.randint(*spec.per_day)):
            when += timedelta(minutes=rng.randint(16, 52))
            if when.hour >= 20:
                break
            place = rng.choice(local)
            rows.append(
                Row(
                    server_id=spec.server_id,
                    at=when,
                    address=place,
                    case_ref=f"CV-{rng.randrange(10000, 99999)}-25",
                    outcome=rng.choices(("served", "affixed", "not_home"), (0.62, 0.18, 0.20))[0],
                    description=_description(rng),
                )
            )
    return rows


def _inject_hops(rng: random.Random, rows: list[Row], truth: Truth) -> None:
    """Move some filings so that the step into them could not have been travelled.

    The filing is pulled *earlier*, to two to four minutes after the one before it, which
    is what a back-dated batch of paperwork looks like. Times only ever move backwards
    inside their own gap, so the day stays in order and the report stays readable.
    """
    candidates = rng.sample(range(1, len(rows) - 1), truth.impossible_hops)
    for index in sorted(candidates):
        previous = rows[index - 1]
        far = _far_from(rng, previous.address, min_km=9.0)
        minutes = rng.randint(2, 4)
        rows[index] = Row(
            server_id=rows[index].server_id,
            at=previous.at + timedelta(minutes=minutes),
            address=far,
            case_ref=rows[index].case_ref,
            outcome="served",
            description=rows[index].description,
        )
        distance = haversine_km(previous.address.latlng, far.latlng)
        truth.notes.append(
            f"{distance:.1f} km in {minutes} min at {rows[index].at:%-I:%M %p on %-d %B}"
        )


def _inject_reused_description(rng: random.Random, rows: list[Row], truth: Truth) -> None:
    """The same person of suitable age and discretion, at several different doors."""
    description = _description(rng)
    doors: set[str] = set()
    for index in rng.sample(range(len(rows)), len(rows)):
        if rows[index].address.address in doors:
            continue
        doors.add(rows[index].address.address)
        rows[index] = Row(**{**rows[index].__dict__, "description": description})
        if len(doors) >= truth.reused_description_doors:
            break
    truth.reused_description = description
    truth.reused_description_doors = len(doors)


def build() -> tuple[list[Row], list[Truth]]:
    rng = random.Random(SEED)
    all_rows: list[Row] = []
    truths: list[Truth] = []

    for spec in SPECS:
        rows = _week(rng, spec)
        truth = Truth(
            server_id=spec.server_id,
            impossible_hops=spec.impossible_hops,
            reused_description_doors=spec.reused_description_doors,
        )
        if spec.impossible_hops:
            _inject_hops(rng, rows, truth)
        if spec.reused_description_doors:
            _inject_reused_description(rng, rows, truth)
        rows.sort(key=lambda r: (r.at, r.address.address))
        truth.n_records = len(rows)
        all_rows.extend(rows)
        truths.append(truth)

    # Interleaved, the way an export sorted by date rather than by server arrives.
    all_rows.sort(key=lambda r: (r.at, r.server_id, r.address.address))
    return all_rows, truths


def to_xlsx(rows: list[Row]) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = "Service records"
    sheet.append(list(COLUMNS))
    for row in rows:
        sheet.append(
            [
                row.server_id,
                row.at.strftime("%Y-%m-%dT%H:%M:%S%z"),
                round(row.address.lat, 6),
                round(row.address.lng, 6),
                row.address.address,
                row.case_ref,
                row.outcome,
                row.description,
            ]
        )
    for column, width in zip("ABCDEFGH", (12, 26, 12, 12, 42, 16, 12, 30), strict=True):
        sheet.column_dimensions[column].width = width

    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def main() -> None:
    rows, truths = build()
    write_bytes(XLSX_PATH, to_xlsx(rows))
    write_json(
        EXPECTED_PATH,
        {
            "seed": SEED,
            "n_rows": len(rows),
            "mapping": DEMO_MAPPING,
            "servers": [
                {
                    "server_id": truth.server_id,
                    "n_records": truth.n_records,
                    "impossible_hops": truth.impossible_hops,
                    "reused_description": truth.reused_description,
                    "reused_description_doors": truth.reused_description_doors,
                    "notes": truth.notes,
                }
                for truth in truths
            ],
        },
    )
    print(f"wrote {len(rows)} rows for {len(truths)} servers to {XLSX_PATH}")
    for truth in truths:
        print(
            f"  {truth.server_id}: {truth.n_records} filings, "
            f"{truth.impossible_hops} impossible hops, "
            f"{truth.reused_description_doors} doors sharing one description"
        )


if __name__ == "__main__":
    main()
