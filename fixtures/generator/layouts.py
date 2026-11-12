"""Eight affidavit layouts for the v1.1 extraction eval. Synthetic only.

v1.0 measured extraction on one clean template and a simulated scan of it, and scored
100%. That says the reader can read that template; it says nothing about the papers people
actually hold. Each layout here renders the *same kind* of ground-truth `Affidavit` in a
different way, each stressing one thing real uploads do:

| ID | Layout | Stresses |
|----|--------|----------|
| L1 | the v1.0 template | regression |
| L2 | agency letterhead, two-column header, method as ticked boxes | reading a ticked box |
| L3 | description as a label/value grid ("Approx. 30-40", "5 ft 3 in") | table parsing |
| L4 | values handwritten (OFL Caveat) over printed labels, image only | handwriting |
| L5 | forced onto two pages; description, attempts, mailing on page 2 | cross-page fields |
| L6 | fax: 150 dpi, binarized, speckle, slight rotation | low quality |
| L7 | phone photo: perspective, shadow, JPEG q70, and the same as HEIC | real uploads |
| L8 | whole court file: summons, complaint, affidavit, default judgment | page types, entry date |

**Labels describe the document as rendered** (lessons.md, 2026-09-28): the agency printed
on the page is the agency in the label, and the judgment's entry date is the one printed
on it — or none, for the judgment that prints no date.

    cd backend && PYTHONPATH=.. uv run python -m fixtures.generator.layouts --per-layout 25

Writes `fixtures/out/layouts/<Lx>/<case>/` (gitignored): the document and `truth.json`.
"""

from __future__ import annotations

import argparse
import io
import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.domain.models import Affidavit, PageType, ServiceMethod

from .affidavit import SKIN, render_pdf
from .cases import make_case
from .names import PROCESS_AGENCIES, SERVER_NAMES
from .writer import write_bytes, write_json

FIXTURES = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).resolve().parent / "templates"
FONT = FIXTURES / "fonts" / "Caveat.ttf"
OUT = FIXTURES / "out" / "layouts"

LAYOUTS = ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8")

METHOD_CYCLE: dict[str, tuple[ServiceMethod, ...]] = {
    "L2": (ServiceMethod.PERSONAL, ServiceMethod.SUBSTITUTE, ServiceMethod.AFFIX_AND_MAIL),
    "L5": (ServiceMethod.AFFIX_AND_MAIL, ServiceMethod.AFFIX_AND_MAIL, ServiceMethod.SUBSTITUTE),
}
"""L2 needs every box ticked somewhere; L5 needs attempts to carry onto page 2."""

AGENCY_ADDRESSES = (
    "88 Synthetic Plaza, Suite 400, New York, NY 10001",
    "12 Fixture Lane, Brooklyn, NY 11201",
    "450 Example Avenue, Bronx, NY 10451",
)


@dataclass(frozen=True, slots=True)
class Rendered:
    files: dict[str, bytes]
    """File name -> bytes. The first is the document the eval uploads."""
    page_types: list[PageType]
    affidavit_pages: list[list[int]]
    judgment_entry_date: date | None
    text_layer: bool


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _pdf_document(html: str) -> Any:
    from weasyprint import HTML

    return HTML(string=html, base_url=str(TEMPLATES)).render()


def _n_pages(pdf: bytes) -> int:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(pdf)
    try:
        return len(document)
    finally:
        document.close()


def _county(aff: Affidavit) -> str:
    return (aff.court or "").split("County of ")[-1] or "New York"


def _desc(aff: Affidavit, rng: random.Random, style: str) -> dict[str, str] | None:
    d = aff.recipient_description
    if d is None:
        return None
    skin = rng.choice(SKIN)
    sex = (d.sex or "unknown").capitalize()
    if style == "grid":

        def feet(inches: int | None) -> str:
            return f"{(inches or 0) // 12} ft {(inches or 0) % 12} in"

        return {
            "sex": sex,
            "skin": skin,
            "hair": d.hair or "",
            "age": f"Approx. {d.age_min} to {d.age_max} yrs",
            "height": f"{feet(d.height_in_min)} to {feet(d.height_in_max)}",
            "weight": f"{d.weight_lb_min} to {d.weight_lb_max} lbs",
        }

    def ft(inches: int | None) -> str:
        return f"{(inches or 0) // 12}'{(inches or 0) % 12}\""

    return {
        "sex": sex,
        "skin": skin,
        "hair": d.hair or "",
        "age": f"{d.age_min}-{d.age_max}",
        "height": f"{ft(d.height_in_min)}-{ft(d.height_in_max)}",
        "weight": f"{d.weight_lb_min}-{d.weight_lb_max} lbs",
    }


def render_variant(
    rng: random.Random,
    aff: Affidavit,
    agency: str,
    *,
    letterhead: bool = False,
    checkboxes: bool = False,
    desc_style: str = "columns",
    hand: bool = False,
    page_break: bool = False,
    compact: bool = False,
) -> bytes:
    html = (
        _env()
        .get_template("affidavit_layouts.html.j2")
        .render(
            aff=aff,
            agency=agency,
            agency_address=rng.choice(AGENCY_ADDRESSES),
            file_no=f"{rng.randint(100000, 999999)}",
            county=_county(aff).upper(),
            desc=_desc(aff, rng, desc_style),
            desc_style=desc_style,
            letterhead=letterhead,
            checkboxes=checkboxes,
            hand=hand,
            page_break=page_break,
            compact=compact,
            notary_name=rng.choice(SERVER_NAMES),
            font_url=FONT.as_uri(),
        )
    )
    return bytes(_pdf_document(html).write_pdf())


def _pages_as_images(pdf: bytes, dpi: int) -> list[Any]:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(pdf)
    try:
        return [
            document[i].render(scale=dpi / 72).to_pil().convert("RGB") for i in range(len(document))
        ]
    finally:
        document.close()


def _images_to_pdf(pages: list[Any], dpi: float) -> bytes:
    out = io.BytesIO()
    pages[0].save(out, format="PDF", save_all=True, append_images=pages[1:], resolution=dpi)
    return out.getvalue()


def image_only(pdf: bytes, dpi: int = 200) -> bytes:
    """The same pages with no text layer, as a scanner would hand them over."""
    return _images_to_pdf(_pages_as_images(pdf, dpi), float(dpi))


def fax(rng: random.Random, pdf: bytes) -> bytes:
    """150 dpi, thresholded to black and white, speckled, slightly rotated."""
    from PIL import Image

    pages = []
    for page in _pages_as_images(pdf, 150):
        page = page.rotate(
            rng.uniform(-2.0, 2.0), resample=Image.Resampling.BICUBIC, fillcolor="white"
        )
        grey = page.convert("L")
        threshold = rng.randint(150, 185)
        bw = grey.point(lambda v, t=threshold: 255 if v > t else 0, mode="L")
        pixels = bw.load()
        assert pixels is not None
        width, height = bw.size
        for _ in range(width * height // 900):
            x, y = rng.randrange(width), rng.randrange(height)
            pixels[x, y] = 0 if rng.random() < 0.7 else 255
        pages.append(bw.convert("RGB"))
    return _images_to_pdf(pages, 150.0)


def phone_photo(rng: random.Random, pdf: bytes) -> tuple[bytes, bytes]:
    """A photo of the printed page: perspective, a shadow across it, JPEG q70; and as HEIC."""
    import pillow_heif
    from PIL import Image

    (page,) = _pages_as_images(pdf, 200)
    width, height = page.size
    margin = int(width * 0.08)
    canvas = Image.new("RGB", (width + 2 * margin, height + 2 * margin), (96, 84, 70))
    canvas.paste(page, (margin, margin))

    # Corner jitter: the phone is never square to the page.
    def jitter() -> float:
        return float(rng.uniform(-0.035, 0.035) * width)

    w, h = canvas.size
    quad = (
        margin * 0.6 + jitter(),
        margin * 0.6 + jitter(),
        margin * 0.6 + jitter(),
        h - margin * 0.6 + jitter(),
        w - margin * 0.6 + jitter(),
        h - margin * 0.6 + jitter(),
        w - margin * 0.6 + jitter(),
        margin * 0.6 + jitter(),
    )
    warped = canvas.transform((w, h), Image.Transform.QUAD, quad, Image.Resampling.BICUBIC)

    # A soft shadow from one side: the hand holding the phone.
    shade = Image.linear_gradient("L").resize((w, h))
    if rng.random() < 0.5:
        shade = shade.rotate(90, expand=False)
    strength = rng.uniform(0.25, 0.45)
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    mask = shade.point(lambda v, s=strength: int(v * s))
    shot = Image.composite(dark, warped, mask)
    shot.thumbnail((2000, 2000))

    jpeg = io.BytesIO()
    shot.save(jpeg, format="JPEG", quality=70)
    pillow_heif.register_heif_opener()
    heic = io.BytesIO()
    shot.save(heic, format="HEIF", quality=70)
    return jpeg.getvalue(), heic.getvalue()


def _court_file(rng: random.Random, aff: Affidavit, affidavit_pdf: bytes) -> Rendered:
    """Summons + complaint (3 pp), the affidavit, and the default judgment (1 p)."""
    entry = aff.served_at.date() + timedelta(days=rng.randint(45, 140))
    style = ("prose", "numeric", "stamp", "prose", "numeric", "stamp", "none")[rng.randrange(7)]
    printed = {
        "prose": entry.strftime("%B %-d, %Y"),
        "numeric": entry.strftime("%m/%d/%Y"),
        "stamp": entry.strftime("%b %d %Y").upper(),
        "none": "",
    }[style]
    balance = rng.randint(900, 9000)
    interest, costs = round(balance * 0.09), rng.choice((145, 170, 195))
    shared = {
        "aff": aff,
        "county": _county(aff).upper(),
        "balance": f"{balance:,}",
        "interest": f"{interest:,}",
        "costs": f"{costs}",
        "total": f"{balance + interest + costs:,}",
        "agent_name": rng.choice(SERVER_NAMES),
        "summons_date": (aff.served_at.date() - timedelta(days=rng.randint(5, 30))).strftime(
            "%B %-d, %Y"
        ),
        "judgment_style": style,
        "entry_printed": printed,
    }
    template = _env().get_template("court_file.html.j2")
    front = _pdf_document(template.render(part="summons_complaint", **shared))
    back = _pdf_document(template.render(part="judgment", **shared))

    import pypdfium2 as pdfium

    merged = pdfium.PdfDocument.new()
    for part in (bytes(front.write_pdf()), affidavit_pdf, bytes(back.write_pdf())):
        source = pdfium.PdfDocument(part)
        merged.import_pages(source)
    buffer = io.BytesIO()
    merged.save(buffer)

    n_front = len(front.pages)
    n_aff = _n_pages(affidavit_pdf)
    types = (
        [PageType.SUMMONS_COMPLAINT] * n_front
        + [PageType.AFFIDAVIT_OF_SERVICE] * n_aff
        + [PageType.JUDGMENT] * len(back.pages)
    )
    return Rendered(
        files={"document.pdf": buffer.getvalue()},
        page_types=types,
        affidavit_pages=[list(range(n_front, n_front + n_aff))],
        judgment_entry_date=entry if style != "none" else None,
        text_layer=True,
    )


def render_layout(layout: str, rng: random.Random, aff: Affidavit, agency: str) -> Rendered:
    def single(pdf: bytes, *, text: bool, name: str = "document.pdf") -> Rendered:
        n = _n_pages(pdf)
        return Rendered(
            files={name: pdf},
            page_types=[PageType.AFFIDAVIT_OF_SERVICE] * n,
            affidavit_pages=[list(range(n))],
            judgment_entry_date=None,
            text_layer=text,
        )

    if layout == "L1":
        return single(render_pdf(rng, aff, agency=agency), text=True)
    if layout == "L2":
        return single(render_variant(rng, aff, agency, letterhead=True, checkboxes=True), text=True)
    if layout == "L3":
        return single(render_variant(rng, aff, agency, desc_style="grid"), text=True)
    if layout == "L4":
        return single(image_only(render_variant(rng, aff, agency, hand=True)), text=False)
    if layout == "L5":
        pdf = render_variant(rng, aff, agency, page_break=True)
        assert _n_pages(pdf) >= 2, "L5 must span two pages"
        return single(pdf, text=True)
    if layout == "L6":
        return single(fax(rng, render_variant(rng, aff, agency, letterhead=True)), text=False)
    if layout == "L7":
        pdf = render_variant(rng, aff, agency, compact=True)
        assert _n_pages(pdf) == 1, "L7 is a photo of one page; the affidavit must fit on it"
        jpeg, heic = phone_photo(rng, pdf)
        return Rendered(
            files={"document.jpg": jpeg, "document.heic": heic},
            page_types=[PageType.AFFIDAVIT_OF_SERVICE],
            affidavit_pages=[[0]],
            judgment_entry_date=None,
            text_layer=False,
        )
    if layout == "L8":
        return _court_file(rng, aff, render_pdf(rng, aff, agency=agency))
    raise ValueError(layout)


def _pool(seed: int) -> Iterator[Affidavit]:
    index = 0
    while True:
        kind = ("contradicted", "consistent", "no_data")[index % 3]
        case = make_case(random.Random(seed * 1_000_003 + index), f"layout_{index:04d}", kind)
        index += 1
        yield case.affidavit


def affidavits_for(layout: str, n: int, seed: int) -> list[Affidavit]:
    """`n` ground-truth affidavits for one layout, with the method mix it needs."""
    pool = _pool(seed + LAYOUTS.index(layout))
    cycle = METHOD_CYCLE.get(layout)
    picked: list[Affidavit] = []
    while len(picked) < n:
        aff = next(pool)
        if cycle is None or aff.method is cycle[len(picked) % len(cycle)]:
            picked.append(aff)
    return picked


def truth_for(
    layout: str, case_id: str, aff: Affidavit, agency: str, r: Rendered
) -> dict[str, object]:
    return {
        "layout": layout,
        "case_id": case_id,
        "files": sorted(r.files),
        "text_layer": r.text_layer,
        "affidavit": aff.model_copy(update={"agency_name": agency}).model_dump(mode="json"),
        "page_types": [t.value for t in r.page_types],
        "affidavit_pages": r.affidavit_pages,
        "judgment_entry_date": r.judgment_entry_date.isoformat() if r.judgment_entry_date else None,
    }


def generate(out: Path, per_layout: int, seed: int, layouts: tuple[str, ...] = LAYOUTS) -> int:
    count = 0
    for layout in layouts:
        for index, aff in enumerate(affidavits_for(layout, per_layout, seed)):
            rng = random.Random(f"{seed}:{layout}:{index}")
            agency = rng.choice(PROCESS_AGENCIES)
            rendered = render_layout(layout, rng, aff, agency)
            case_dir = out / layout / f"{layout.lower()}_{index:03d}"
            for name, data in rendered.files.items():
                write_bytes(case_dir / name, data)
            write_json(
                case_dir / "truth.json", truth_for(layout, case_dir.name, aff, agency, rendered)
            )
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(prog="layouts", description=__doc__)
    parser.add_argument("--per-layout", type=int, default=25)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--only", nargs="*", default=list(LAYOUTS))
    args = parser.parse_args()
    n = generate(args.out, args.per_layout, args.seed, tuple(args.only))
    print(f"wrote {n} documents to {args.out}")


if __name__ == "__main__":
    main()
