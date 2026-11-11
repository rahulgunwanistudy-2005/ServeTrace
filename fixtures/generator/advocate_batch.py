"""The advocate attorney-edition fixture: 60 affidavits of service. Build prompt §6.5.

Three agencies, two servers each, ten affidavits per server, every one synthetic. Patterns
are injected on purpose and written to an answer key, so the batch report can be scored
rather than eyeballed:

- **Kestrel** (agency 0): server 0 swears to two pairs of services minutes apart and
  boroughs apart (two impossible sequences); four substitute services show no mailing
  (R-T1); server 1 describes the same person at three different addresses.
- **Ironvale** (agency 1): five affix-and-mail affidavits whose attempts are two, on one
  day, inside office hours (R-D1). Nothing else.
- **Halloway & Finch** (agency 2): clean. Diligent attempts, timely mailing and filing,
  descriptions all different, and a schedule nobody would need a car chase to keep.

    cd backend && PYTHONPATH=.. uv run python -m fixtures.generator.advocate_batch

writes the committed truth (`fixtures/advocate_batch/affidavits.json`, `expected.json`
and `sample_extractions.json`, the drafts the browser's "sample batch" loads) and the 60
PDFs under `fixtures/out/advocate_batch/` (not committed: they rebuild from the seed).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.domain.models import (
    Affidavit,
    ExtractionResult,
    PersonDescription,
    ServiceAttempt,
    ServiceMethod,
)
from app.extraction.pdf_text import sha256_of
from app.extraction.vision import extract_document

from .addresses import Address, by_borough
from .affidavit import render_pdf
from .build_demo_extractions import DerivedExtractor
from .names import PLAINTIFFS, PROCESS_AGENCIES, SERVER_NAMES
from .people import TZ

ROOT = Path(__file__).resolve().parents[1]
TRUTH_DIR = ROOT / "advocate_batch"
PDF_DIR = ROOT / "out" / "advocate_batch"
SEED = 61

PER_SERVER = 10
START = date(2025, 3, 3)
DAY_STEP = 3
"""Each server serves on every third day; attempts land on the days between, so no two of
one server's filings share a day by accident. The injected pairs are the exception."""

FIRST_NAMES = ("Ana", "Ben", "Cleo", "Dev", "Eli", "Fay", "Gus", "Hana", "Ivo", "Jun")
LAST_NAMES = ("Arvel", "Brisk", "Corwin", "Dulane", "Eskar", "Fenmore", "Gaskill", "Holloran")

REPEATED = (
    "Sex: Male  Skin: Medium  Hair: Brown  Age: 45-55  Height: 5'8\"-5'10\"  Weight: 180-200 lbs"
)


@dataclass(frozen=True, slots=True)
class Plan:
    agency: int
    server: int
    slot: int
    method: ServiceMethod
    missing_mailing: bool = False
    thin_diligence: bool = False
    repeated_description: bool = False
    twin_of: int | None = None
    """Served minutes after the affidavit in this slot of the same server, boroughs away."""


def _plans() -> list[Plan]:
    sub, aff, per = ServiceMethod.SUBSTITUTE, ServiceMethod.AFFIX_AND_MAIL, ServiceMethod.PERSONAL
    plans: list[Plan] = []
    for slot in range(PER_SERVER):
        # Kestrel, server 0: slots 8 and 9 are sworn minutes after slots 2 and 5.
        twin = {8: 2, 9: 5}.get(slot)
        plans.append(
            Plan(0, 0, slot, sub if slot % 2 else per, missing_mailing=slot in (1, 3), twin_of=twin)
        )
        plans.append(
            Plan(
                0,
                1,
                slot,
                sub,
                missing_mailing=slot in (6, 8),
                repeated_description=slot in (0, 4, 7),
            )
        )
        plans.append(Plan(1, 2, slot, aff, thin_diligence=slot in (0, 2, 4, 6, 8)))
        plans.append(Plan(1, 3, slot, sub if slot % 3 else per))
        plans.append(Plan(2, 4, slot, aff if slot % 2 else sub))
        plans.append(Plan(2, 5, slot, per if slot % 2 else sub))
    plans.sort(key=lambda p: (p.agency, p.server, p.slot))
    return plans


def _description(index: int, rng: random.Random) -> PersonDescription:
    """A description no other affidavit in the batch shares: the age band is the index."""
    age_min = 20 + index
    sex = rng.choice(("male", "female"))
    hair = rng.choice(("Black", "Brown", "Gray", "Blonde"))
    raw = (
        f"Sex: {sex.capitalize()}  Skin: {rng.choice(('Light', 'Medium', 'Dark'))}  "
        f"Hair: {hair}  Age: {age_min}-{age_min + 5}  Height: 5'4\"-5'8\"  Weight: 140-160 lbs"
    )
    return PersonDescription(
        sex=sex,  # type: ignore[arg-type]
        age_min=age_min,
        age_max=age_min + 5,
        height_in_min=64,
        height_in_max=68,
        weight_lb_min=140,
        weight_lb_max=160,
        hair=hair,
        raw_text=raw,
    )


def _repeated() -> PersonDescription:
    return PersonDescription(
        sex="male",
        age_min=45,
        age_max=55,
        height_in_min=68,
        height_in_max=70,
        weight_lb_min=180,
        weight_lb_max=200,
        hair="Brown",
        raw_text=REPEATED,
    )


def _attempts(served: datetime, place: Address, thin: bool) -> list[ServiceAttempt]:
    """Diligent: three, on three days, morning, afternoon and evening. Thin: two, one
    weekday, both inside office hours (bible §5 L4)."""
    if thin:
        day = served - timedelta(days=1)
        while day.weekday() >= 5:
            day -= timedelta(days=1)
        times = [day.replace(hour=10, minute=30), day.replace(hour=11, minute=15)]
    else:
        times = [
            (served - timedelta(days=1)).replace(hour=7, minute=40),
            (served - timedelta(days=2)).replace(hour=19, minute=50),
            (served + timedelta(days=-4)).replace(hour=13, minute=10),
        ]
    return [
        ServiceAttempt(at=t, address=place.address, location=place.latlng, outcome="not_home")
        for t in times
    ]


def build() -> tuple[list[Affidavit], dict[str, Any], list[str]]:
    rng = random.Random(SEED)
    near = by_borough("Brooklyn")
    far = by_borough("Staten Island")
    affidavits: list[Affidavit] = []
    agencies: list[str] = []
    served_by_slot: dict[tuple[int, int], tuple[datetime, Address]] = {}

    for index, plan in enumerate(_plans()):
        # A server works one borough's worth of streets; the pool is drawn without
        # replacement so no address repeats inside the batch.
        place = near[(index * 7) % len(near)]
        day = START + timedelta(days=plan.slot * DAY_STEP)
        served = datetime(
            day.year, day.month, day.day, 9 + plan.slot % 8, 5 * plan.server, tzinfo=TZ
        )
        if plan.twin_of is not None:
            earlier, _ = served_by_slot[(plan.server, plan.twin_of)]
            served = earlier + timedelta(minutes=4)
            place = far[index % len(far)]
        served_by_slot[(plan.server, plan.slot)] = (served, place)

        mails = plan.method is not ServiceMethod.PERSONAL
        mailing = None if plan.missing_mailing or not mails else served.date() + timedelta(days=2)
        proof = (mailing or served.date()) + timedelta(days=5)
        description = _repeated() if plan.repeated_description else _description(index, rng)
        name = f"{FIRST_NAMES[index % len(FIRST_NAMES)]} {LAST_NAMES[index % len(LAST_NAMES)]}"

        affidavits.append(
            Affidavit(
                index_number=f"CV-{100000 + index * 37:06d}-25/KI",
                court="Civil Court of the City of New York, County of Kings",
                plaintiff=PLAINTIFFS[index % len(PLAINTIFFS)],
                defendant_name=name,
                server_name=SERVER_NAMES[plan.server],
                agency_name=PROCESS_AGENCIES[plan.agency],
                method=plan.method,
                served_at=served,
                served_address=place.address,
                served_location=place.latlng,
                recipient_name=name if plan.method is ServiceMethod.PERSONAL else None,
                recipient_relationship="Co-Tenant"
                if plan.method is ServiceMethod.SUBSTITUTE
                else None,
                recipient_description=None
                if plan.method is ServiceMethod.AFFIX_AND_MAIL
                else description,
                attempts=_attempts(served, place, plan.thin_diligence)
                if plan.method is ServiceMethod.AFFIX_AND_MAIL
                else [],
                mailing_date=mailing,
                mailing_address=place.address if mailing else None,
                proof_filed_date=proof,
                source_sha256="0" * 64,
                user_confirmed=True,
            )
        )
        agencies.append(PROCESS_AGENCIES[plan.agency])

    plans = _plans()
    expected = {
        "n_affidavits": len(affidavits),
        "agencies": list(PROCESS_AGENCIES),
        "clean_agency": PROCESS_AGENCIES[2],
        "impossible_pairs": {SERVER_NAMES[0]: 2},
        "flagged": {
            "R-T1": [i for i, p in enumerate(plans) if p.missing_mailing],
            "R-D1": [i for i, p in enumerate(plans) if p.thin_diligence],
        },
        "repeated_description": {"server": SERVER_NAMES[1], "text": REPEATED, "addresses": 3},
    }
    return affidavits, expected, agencies


async def _sample(affidavit: Affidavit, pdf: bytes, name: str) -> dict[str, Any]:
    """What `/api/extract` would hand back for this PDF if the reader read it perfectly:
    the same derived-draft path as the demo cases, located at the true point (the route
    geocodes; this skips the network), and no page images, to keep the file small."""
    payload = json.loads(affidavit.model_dump_json())
    result: ExtractionResult = await extract_document(
        pdf,
        previews=False,
        extractor=DerivedExtractor(payload),  # type: ignore[arg-type]
    )
    found = result.affidavits[0]
    draft = found.draft.model_copy(
        update={
            "served_location": affidavit.served_location,
            "agency_name": affidavit.agency_name,
            "attempts": [
                a.model_copy(update={"location": t.location})
                for a, t in zip(found.draft.attempts, affidavit.attempts, strict=False)
            ],
        }
    )
    located = result.model_copy(update={"affidavits": [found.model_copy(update={"draft": draft})]})
    return {"name": name, "extraction": json.loads(located.model_dump_json())}


async def generate(pdfs: bool = True) -> int:
    affidavits, expected, agencies = build()
    TRUTH_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    samples = []
    truth = []
    for index, affidavit in enumerate(affidavits):
        rng = random.Random(f"{SEED}:{index}")
        pdf = render_pdf(rng, affidavit, agencies[index])
        name = f"affidavit_{index:02d}.pdf"
        if pdfs:
            (PDF_DIR / name).write_bytes(pdf)
        stamped = affidavit.model_copy(update={"source_sha256": sha256_of(pdf)})
        truth.append(json.loads(stamped.model_dump_json()))
        samples.append(await _sample(stamped, pdf, name))

    def dump(path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    dump(TRUTH_DIR / "affidavits.json", truth)
    dump(TRUTH_DIR / "expected.json", expected)
    dump(TRUTH_DIR / "sample_extractions.json", samples)
    return len(affidavits)


def main() -> None:
    parser = argparse.ArgumentParser(prog="advocate_batch", description=__doc__)
    parser.add_argument("--no-pdfs", action="store_true", help="skip writing the PDFs")
    args = parser.parse_args()
    n = asyncio.run(generate(pdfs=not args.no_pdfs))
    print(f"wrote {n} affidavits to {TRUTH_DIR} and PDFs to {PDF_DIR}")


if __name__ == "__main__":
    main()
