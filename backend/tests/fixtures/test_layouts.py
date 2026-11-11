"""The v1.1 layout fixtures: one document per layout, rendered and read back without a
model. What can be checked deterministically is checked here; per-field accuracy needs a
provider and lives in `eval/layout_eval.py`."""

from __future__ import annotations

import io
import random

import pytest
from PIL import Image

from app.domain.models import Affidavit, PageType, ServiceMethod
from app.extraction.pdf_text import extract_text, is_heic
from app.extraction.vision import extract_document
from fixtures.generator.layouts import LAYOUTS, Rendered, affidavits_for, render_layout, truth_for

SEED = 11


@pytest.fixture(scope="module")
def rendered() -> dict[str, tuple[Affidavit, Rendered]]:
    out: dict[str, tuple[Affidavit, Rendered]] = {}
    for layout in LAYOUTS:
        (aff,) = affidavits_for(layout, 1, SEED)
        out[layout] = (
            aff,
            render_layout(
                layout, random.Random(f"test:{layout}"), aff, "Ironvale Attorney Service Corp."
            ),
        )
    return out


def test_every_layout_renders(rendered: dict[str, tuple[Affidavit, Rendered]]) -> None:
    assert set(rendered) == set(LAYOUTS)


@pytest.mark.parametrize("layout", ["L4", "L6"])
def test_handwriting_and_fax_have_no_text_layer(
    layout: str, rendered: dict[str, tuple[Affidavit, Rendered]]
) -> None:
    _, r = rendered[layout]
    assert not extract_text(r.files["document.pdf"]).has_text_layer


def test_the_phone_photo_comes_as_jpeg_and_heic(
    rendered: dict[str, tuple[Affidavit, Rendered]],
) -> None:
    _, r = rendered["L7"]
    assert r.files["document.jpg"].startswith(b"\xff\xd8\xff")
    assert is_heic(r.files["document.heic"])
    with Image.open(io.BytesIO(r.files["document.jpg"])) as photo:
        assert photo.width > photo.height * 0.6  # a page, photographed whole


def test_the_checkbox_form_ticks_exactly_the_method(
    rendered: dict[str, tuple[Affidavit, Rendered]],
) -> None:
    aff, r = rendered["L2"]
    assert aff.method is ServiceMethod.PERSONAL  # the first of L2's method cycle
    # Small caps come through a text layer in mixed case ("IndIvIdual"), as in real PDFs.
    text = extract_text(r.files["document.pdf"]).text.lower()
    assert "x individual" in text
    assert "x suitable" not in text and "x affixing" not in text


def test_l5_puts_the_mailing_on_page_two(rendered: dict[str, tuple[Affidavit, Rendered]]) -> None:
    aff, r = rendered["L5"]
    layer = extract_text(r.files["document.pdf"])
    assert layer.n_pages >= 2
    if aff.mailing_date is not None:
        assert "mailing" in layer.pages[1].lower() and "mailing" not in layer.pages[0].lower()


@pytest.mark.parametrize("layout", ["L1", "L2", "L3", "L5", "L8"])
@pytest.mark.asyncio
async def test_text_layouts_are_classified_and_grouped_without_a_model(
    layout: str, rendered: dict[str, tuple[Affidavit, Rendered]]
) -> None:
    _, r = rendered[layout]
    result = await extract_document(r.files["document.pdf"], previews=False)
    assert result.page_types == r.page_types
    assert [a.pages for a in result.affidavits] == r.affidavit_pages


@pytest.mark.asyncio
async def test_the_court_file_judgment_date_is_the_printed_one(
    rendered: dict[str, tuple[Affidavit, Rendered]],
) -> None:
    _, r = rendered["L8"]
    result = await extract_document(r.files["document.pdf"], previews=False)
    assert result.page_types[:3] == [PageType.SUMMONS_COMPLAINT] * 3
    assert result.judgment_entry_date == r.judgment_entry_date


def test_the_label_carries_the_agency_printed_on_the_page(
    rendered: dict[str, tuple[Affidavit, Rendered]],
) -> None:
    aff, r = rendered["L2"]
    truth = truth_for("L2", "x", aff, "Ironvale Attorney Service Corp.", r)
    assert truth["affidavit"]["agency_name"] == "Ironvale Attorney Service Corp."  # type: ignore[index]
    assert "IRONVALE ATTORNEY SERVICE CORP." in extract_text(r.files["document.pdf"]).text


def test_the_layouts_are_a_pure_function_of_the_seed() -> None:
    first = [a.model_dump() for a in affidavits_for("L5", 3, SEED)]
    again = [a.model_dump() for a in affidavits_for("L5", 3, SEED)]
    assert first == again
    assert [a["method"] for a in first] == ["308_4", "308_4", "308_2"]
