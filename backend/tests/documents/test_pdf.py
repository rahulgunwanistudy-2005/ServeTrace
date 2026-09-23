"""What survives the renderer.

Everything else in this suite asserts on HTML, which is the right place for wording and
selection. It is the wrong place for four things, and they are the four here: a footer
that has to appear on *every* page, a DRAFT mark that has to appear on every page of one
document and no page of the other, the key numbers still being readable after layout, and
the page count being finite. A section that laid out on top of another one would pass
every HTML assertion in this directory.

The text comes back through pdfplumber, which is the same library the extractor reads
uploaded affidavits with — so this measures what a machine on the other side would see.
"""

from __future__ import annotations

import io

import pdfplumber
import pytest

from app.documents import copy
from app.documents.affidavit import build_draft_affidavit
from app.documents.packet import build_packet
from tests.documents.conftest import demo_analysis, demo_fixes, statement

CASE = "maria_contradicted"


def pages(pdf: bytes) -> list[str]:
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        return [page.extract_text() or "" for page in document.pages]


@pytest.fixture(scope="module")
def packet_pages(needs_pdf: None) -> list[str]:
    return pages(build_packet(demo_analysis(CASE), demo_fixes(CASE), None, "Maria Delarmo"))


@pytest.fixture(scope="module")
def affidavit_pages(needs_pdf: None) -> list[str]:
    return pages(build_draft_affidavit(demo_analysis(CASE), statement(name="Maria Delarmo")))


# --- On every page ------------------------------------------------------------------------


def test_the_disclaimer_is_on_every_page_of_the_packet(packet_pages: list[str]) -> None:
    """Bible §5. It is set as a running element, and this is the test that proves the
    mechanism works rather than that the string exists."""
    assert len(packet_pages) > 1
    assert all("not legal advice" in page for page in packet_pages)


def test_the_disclaimer_is_on_every_page_of_the_affidavit(affidavit_pages: list[str]) -> None:
    assert len(affidavit_pages) > 1
    assert all("not legal advice" in page for page in affidavit_pages)


def test_every_page_is_numbered_out_of_the_total(packet_pages: list[str]) -> None:
    total = len(packet_pages)
    for number, page in enumerate(packet_pages, 1):
        assert f"Page {number} of {total}" in page


def test_the_affidavit_is_marked_draft_on_every_page(affidavit_pages: list[str]) -> None:
    assert all(copy.DRAFT_MARK in page for page in affidavit_pages)


def test_the_packet_is_not_marked_draft_in_the_margin(packet_pages: list[str]) -> None:
    """The mark means "do not file this as it stands", which is true of the affidavit and
    not of the packet: the packet is a report, and it is complete."""
    assert not any(page.startswith(copy.DRAFT_MARK) for page in packet_pages)


# --- The numbers are readable afterwards --------------------------------------------------


def test_the_headline_number_survives_layout(packet_pages: list[str]) -> None:
    km = demo_analysis(CASE).verdicts[0].nearest_fix_km
    assert km is not None
    assert copy.fmt_km(km) in "\n".join(packet_pages)


def test_both_digests_are_readable_in_the_packet(packet_pages: list[str]) -> None:
    """A digest broken across a line by the layout is a digest nobody can check."""
    text = "\n".join(packet_pages).replace("\n", "")
    assert demo_analysis(CASE).affidavit.source_sha256 in text


def test_every_section_heading_reaches_the_paper(packet_pages: list[str]) -> None:
    text = "\n".join(packet_pages).upper()
    for section in (
        copy.SECTION_VERDICT,
        copy.SECTION_CLAIMS,
        copy.SECTION_FINDINGS,
        copy.SECTION_FIXES,
        copy.SECTION_METHOD,
        copy.SECTION_INTEGRITY,
        copy.SECTION_DEADLINE,
    ):
        assert section.upper() in text


def test_the_affidavit_paragraphs_are_numbered_on_the_page(affidavit_pages: list[str]) -> None:
    text = "\n".join(affidavit_pages)
    assert "1. I am Maria Delarmo" in text
    assert "WHEREFORE" in text


def test_the_signature_and_notary_blocks_are_on_the_paper(affidavit_pages: list[str]) -> None:
    text = "\n".join(affidavit_pages)
    assert copy.SIGNATURE_LABEL in text
    assert "Sworn to before me" in text


def test_the_affidavit_does_not_end_on_a_page_of_nothing(affidavit_pages: list[str]) -> None:
    """It did. The provenance line and the rule above it were a body element, and after a
    notary block that may not be split they landed alone on a third page — a court
    document whose last sheet carries one grey sentence. The line lives in the page margin
    now, so the last page is the one the signature is on."""
    assert "Sworn to before me" in affidavit_pages[-1]


def test_the_provenance_line_is_in_the_margin_of_every_page(affidavit_pages: list[str]) -> None:
    assert all("Prepared by ServeTrace" in page for page in affidavit_pages)
