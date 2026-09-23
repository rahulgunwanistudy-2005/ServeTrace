"""Synthetic affidavits of service: the ground-truth object and a rendered PDF.

Every affidavit here is invented. The layout imitates a New York City Civil Court
affidavit of service closely enough that extraction is a fair test, but no real case,
server, licence number or party appears anywhere.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.domain.models import (
    Affidavit,
    PersonDescription,
    ServiceAttempt,
    ServiceMethod,
)

from .addresses import Address
from .names import PLAINTIFFS, PROCESS_AGENCIES, SERVER_NAMES
from .people import Person

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

COUNTY_OF_BOROUGH = {
    "Bronx": ("Bronx", "BX"),
    "Brooklyn": ("Kings", "KI"),
    "Manhattan": ("New York", "NY"),
    "Queens": ("Queens", "QU"),
    "Staten Island": ("Richmond", "RI"),
}

HAIR = ("Black", "Brown", "Blonde", "Gray", "Red", "Bald")
SKIN = ("Light", "Medium", "Dark", "Olive")
"""Reproduced only because the real form has this line. Nothing in ServeTrace reads it:
the description check (bible §11.2) compares sex, age and height, and never appearance."""


@dataclass(frozen=True, slots=True)
class AffidavitTruth:
    """What the generator deliberately built into this affidavit."""

    description_matches_household: bool
    seeded_rule_codes: tuple[str, ...]
    """Timing/diligence rules the affidavit is built to trip. Bible §11.3."""


DescribedSex = Literal["male", "female", "unknown"]


def _description_for(
    rng: random.Random, sex: str, age: int, height_in: int, matching: bool
) -> tuple[PersonDescription, str]:
    """A description block, either bracketing the real person or clearly not."""
    desc_sex: DescribedSex
    if matching:
        age_min, age_max = max(18, age - 5), age + 5
        h_min, h_max = height_in - 2, height_in + 2
        desc_sex = "male" if sex == "male" else "female" if sex == "female" else "unknown"
    else:
        # Shift far enough that no tolerance in the check could close the gap.
        desc_sex = "female" if sex == "male" else "male"
        age_min, age_max = age + 22, age + 32
        h_min, h_max = height_in + 8, height_in + 12

    weight_min, weight_max = rng.choice(((120, 140), (140, 160), (160, 180), (180, 200)))
    hair = rng.choice(HAIR)
    raw = (
        f"Sex: {desc_sex.capitalize()}  Skin: {rng.choice(SKIN)}  Hair: {hair}  "
        f"Age: {age_min}-{age_max}  "
        f"Height: {h_min // 12}'{h_min % 12}\"-{h_max // 12}'{h_max % 12}\"  "
        f"Weight: {weight_min}-{weight_max} lbs"
    )
    return (
        PersonDescription(
            sex=desc_sex,
            age_min=age_min,
            age_max=age_max,
            height_in_min=h_min,
            height_in_max=h_max,
            weight_lb_min=weight_min,
            weight_lb_max=weight_max,
            hair=hair,
            raw_text=raw,
        ),
        raw,
    )


def _attempts(
    rng: random.Random, served_at: datetime, address: Address, diligent: bool
) -> list[ServiceAttempt]:
    """Prior attempts for 308(4). `diligent` decides whether R-D1 should fire.

    Bible §5 L4: courts commonly expect three attempts across at least two different days
    at different times of day. A non-diligent set is two attempts, same weekday, both
    inside office hours.
    """
    attempts: list[ServiceAttempt] = []
    offsets = ((-8, 7, 40), (-5, 13, 15), (-2, 20, 5)) if diligent else ((-7, 10, 30), (-14, 11, 0))
    for days_back, hour, minute in offsets:
        when = (served_at + timedelta(days=days_back)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        attempts.append(
            ServiceAttempt(
                at=when,
                address=address.address,
                location=address.latlng,
                outcome="not_home",
            )
        )
    return attempts


def make_affidavit(
    rng: random.Random,
    person: Person,
    method: ServiceMethod,
    served_at: datetime,
    served_place: Address,
    description_matches: bool,
    seed_rule_violations: bool,
) -> tuple[Affidavit, AffidavitTruth]:
    county, county_code = COUNTY_OF_BOROUGH[served_place.borough]
    seeded: list[str] = []

    recipient_name: str | None = None
    recipient_relationship: str | None = None
    description: PersonDescription | None = None

    if method is ServiceMethod.PERSONAL:
        description, _ = _description_for(
            rng, person.sex, person.age, person.height_in, description_matches
        )
        recipient_name = person.name
    elif method is ServiceMethod.SUBSTITUTE:
        others = [m for m in person.household if not m.is_defendant and (m.age or 0) >= 18]
        if description_matches and others:
            member = rng.choice(others)
            description, _ = _description_for(
                rng, member.sex or "unknown", member.age or 40, member.height_in or 66, True
            )
            recipient_relationship = member.label
        else:
            description, _ = _description_for(rng, person.sex, person.age, person.height_in, False)
            recipient_relationship = rng.choice(("Co-Tenant", "Relative", "Person in Charge"))
            description_matches = False
        recipient_name = "Jane Doe (refused name)" if rng.random() < 0.4 else None
    else:
        description, _ = _description_for(rng, person.sex, person.age, person.height_in, False)
        description_matches = False

    attempts: list[ServiceAttempt] = []
    diligent = True
    if method is ServiceMethod.AFFIX_AND_MAIL:
        diligent = not (seed_rule_violations and rng.random() < 0.6)
        attempts = _attempts(rng, served_at, served_place, diligent)
        if not diligent:
            seeded.append("R-D1")

    mailing_date: date | None = None
    mailing_address: str | None = None
    proof_filed_date: date | None = None

    if method is not ServiceMethod.PERSONAL:
        mailing_address = served_place.address
        if seed_rule_violations and rng.random() < 0.25:
            mailing_date = None
            seeded.append("R-T1")
        elif seed_rule_violations and rng.random() < 0.35:
            mailing_date = served_at.date() + timedelta(days=rng.randint(24, 45))
            seeded.append("R-T2")
        else:
            mailing_date = served_at.date() + timedelta(days=rng.randint(0, 6))

    later = max(d for d in (served_at.date(), mailing_date) if d is not None)
    if seed_rule_violations and rng.random() < 0.3:
        proof_filed_date = later + timedelta(days=rng.randint(22, 60))
        seeded.append("R-T3")
    else:
        proof_filed_date = later + timedelta(days=rng.randint(1, 18))

    affidavit = Affidavit(
        index_number=f"CV-{rng.randint(1000, 99999):06d}-25/{county_code}",
        court=f"Civil Court of the City of New York, County of {county}",
        plaintiff=rng.choice(PLAINTIFFS),
        defendant_name=person.name,
        server_name=rng.choice(SERVER_NAMES),
        server_license=f"{rng.randint(1000000, 9999999)}",
        agency_license=f"{rng.randint(1000000, 9999999)}",
        method=method,
        served_at=served_at,
        served_address=served_place.address,
        served_location=served_place.latlng,
        recipient_name=recipient_name,
        recipient_relationship=recipient_relationship,
        recipient_description=description,
        attempts=attempts,
        mailing_date=mailing_date,
        mailing_address=mailing_address,
        proof_filed_date=proof_filed_date,
        source_sha256="0" * 64,
        field_confidence={},
        user_confirmed=False,
    )
    return affidavit, AffidavitTruth(
        description_matches_household=description_matches,
        seeded_rule_codes=tuple(sorted(set(seeded))),
    )


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_pdf(rng: random.Random, affidavit: Affidavit) -> bytes:
    """Render the affidavit to a PDF that looks like the real form."""
    from weasyprint import HTML  # imported lazily: it pulls in pango at import time

    county = (affidavit.court or "").split("County of ")[-1] or "New York"
    html = (
        _environment()
        .get_template("affidavit.html.j2")
        .render(
            aff=affidavit,
            county=county.upper(),
            agency=rng.choice(PROCESS_AGENCIES),
            notary_name=rng.choice(SERVER_NAMES),
            notary_county=county,
            commission_expiry=date(2027, rng.randint(1, 12), rng.randint(1, 28)),
            description_lines=(affidavit.recipient_description.raw_text or "").split("  ")
            if affidavit.recipient_description
            else [],
        )
    )
    return bytes(HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf())


def scanned_variant(rng: random.Random, pdf_bytes: bytes) -> bytes:
    """A photocopied-then-photographed version: rotation, blur and JPEG noise.

    This is what most users will actually upload, so the extraction path has to survive it.
    """
    import io

    import pypdfium2 as pdfium
    from PIL import Image, ImageFilter

    document = pdfium.PdfDocument(pdf_bytes)
    pages: list[Image.Image] = []
    for index in range(len(document)):
        page = document[index].render(scale=200 / 72).to_pil().convert("RGB")
        page = page.rotate(
            rng.uniform(-1.5, 1.5), resample=Image.Resampling.BICUBIC, fillcolor=(248, 247, 244)
        )
        page = page.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.3, 0.9)))
        buffer = io.BytesIO()
        page.save(buffer, format="JPEG", quality=rng.randint(45, 70))
        pages.append(Image.open(io.BytesIO(buffer.getvalue())).convert("RGB"))
    document.close()

    out = io.BytesIO()
    pages[0].save(out, format="PDF", save_all=True, append_images=pages[1:], resolution=200.0)
    return out.getvalue()


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
