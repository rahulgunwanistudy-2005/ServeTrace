"""The cached demo extractions. Bible §17: the demo must never fail, which means it must
never need a model, a key or a network at all."""

import json
from pathlib import Path

import pytest

from app.domain.models import AffidavitDraft, ExtractionResult, PageType
from app.extraction.pdf_text import sha256_of
from app.extraction.validators import GROUNDING_MIN_RATIO, grounding_ratio
from app.extraction.vision import read_source

DEMO_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "demo_cases"
CASE_IDS = json.loads((DEMO_DIR / "index.json").read_text(encoding="utf-8"))["cases"]


def load(case_id: str) -> ExtractionResult:
    raw = (DEMO_DIR / case_id / "extraction.json").read_text(encoding="utf-8")
    return ExtractionResult.model_validate_json(raw)


def draft(case_id: str) -> AffidavitDraft:
    (found,) = load(case_id).affidavits
    return found.draft


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_every_demo_case_has_a_cached_extraction(case_id: str) -> None:
    assert draft(case_id).served_at is not None


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_cached_extraction_says_where_it_came_from(case_id: str) -> None:
    """A draft derived from the ground truth must never be mistaken for a model's answer."""
    assert load(case_id).provider in {"derived_from_ground_truth", "gemini", "anthropic"}


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_cached_extraction_is_of_the_committed_pdf(case_id: str) -> None:
    pdf = (DEMO_DIR / case_id / "affidavit.pdf").read_bytes()
    assert load(case_id).source_sha256 == sha256_of(pdf)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_cached_extraction_matches_the_case_it_belongs_to(case_id: str) -> None:
    affidavit = json.loads((DEMO_DIR / case_id / "affidavit.json").read_text(encoding="utf-8"))
    got = draft(case_id)

    assert got.defendant_name == affidavit["defendant_name"]
    assert got.served_address == affidavit["served_address"]
    assert got.method == affidavit["method"]
    assert got.served_at is not None
    assert got.served_at.isoformat() == affidavit["served_at"]
    assert len(got.attempts) == len(affidavit["attempts"])


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_every_cached_quote_is_on_the_demo_document(case_id: str) -> None:
    """The demo shows the user where each field came from. Those pointers have to be real."""
    text = read_source((DEMO_DIR / case_id / "affidavit.pdf").read_bytes()).doc.text or ""
    for field, quote in draft(case_id).evidence_quotes.items():
        assert grounding_ratio(text, quote) >= GROUNDING_MIN_RATIO, field


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_demo_shows_a_clean_extraction(case_id: str) -> None:
    """Nothing in the curated demo should be flagged: a warning there is a bug in the
    fixture, not a lesson for the user."""
    result = load(case_id)
    assert result.notes == []
    assert all(found.notes == [] for found in result.affidavits)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_demo_review_has_pages_and_boxes_to_show(case_id: str) -> None:
    """The review screen draws each field's box on its page. The demo must have both."""
    result = load(case_id)
    assert result.page_types == [PageType.AFFIDAVIT_OF_SERVICE] * result.n_pages
    assert [p.index for p in result.previews] == list(range(result.n_pages))
    assert all(p.image.startswith("data:image/jpeg;base64,") for p in result.previews)
    evidence = draft(case_id).evidence
    assert evidence and all(e.bbox is not None and e.page is not None for e in evidence.values())
