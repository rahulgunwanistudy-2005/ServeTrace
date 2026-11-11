"""v1.1 reading of a whole upload: page types, affidavit grouping, the judgment's entry
date, and where each value sits on the page. No provider is called over the network."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.domain.models import AffidavitDraft, PageType
from app.extraction import vision
from app.extraction.classify import THRESHOLD, classify_text, group, scores, starts_affidavit
from app.extraction.judgment import read_entry_date
from app.extraction.pdf_text import PageImage, Word, extract_text
from app.extraction.provenance import locate
from app.extraction.schema import draft_from_payload
from app.extraction.validators import agency_key, infer_method, validate
from app.extraction.vision import ExtractInput, classify_images, extract_document

A = PageType.AFFIDAVIT_OF_SERVICE
J = PageType.JUDGMENT
S = PageType.SUMMONS_COMPLAINT
O = PageType.OTHER  # noqa: E741

AFFIDAVIT_PAGE = (
    "AFFIDAVIT OF SERVICE. K. Aldersey, being duly sworn, deposes and says: that deponent is "
    "a licensed process server, and served the within Summons and Endorsed Complaint."
)
VERIFICATION_PAGE = (
    "WHEREFORE, plaintiff demands judgment. (Complaint, continued.) VERIFICATION. S. Rye, "
    "being duly sworn, deposes and says that deponent has read the foregoing complaint."
)
JUDGMENT_PAGE = (
    "JUDGMENT. The summons and complaint having been served on June 12, 2025, the Defendant "
    "is in default. Judgment entered on September 3, 2025 by the Clerk of the Civil Court."
)


class TestClassification:
    def test_an_affidavit_page_is_an_affidavit(self) -> None:
        assert classify_text(AFFIDAVIT_PAGE) is A

    def test_a_judgment_page_is_a_judgment(self) -> None:
        assert classify_text(JUDGMENT_PAGE) is J

    def test_a_complaint_verification_is_not_an_affidavit(self) -> None:
        """It is sworn, and says so in an affidavit's words. It is still the complaint."""
        assert classify_text(VERIFICATION_PAGE) is S

    def test_a_page_with_nothing_to_say_is_other(self) -> None:
        assert classify_text("Exhibit A. Account statement, page 4 of 9.") is O
        assert max(scores("one complaint").values()) < THRESHOLD

    def test_a_repeated_word_cannot_carry_a_page_alone(self) -> None:
        assert classify_text("judgment " * 40) is J
        assert scores("judgment " * 40)[J] == 3.0


class TestGrouping:
    def test_a_continuation_page_joins_the_affidavit_before_it(self) -> None:
        grouping = group([S, S, A, O, J], [False, False, True, False, False])
        assert grouping.affidavits == [[2, 3]]
        assert grouping.page_types == [S, S, A, A, J]
        assert grouping.continuations == [3]

    def test_a_second_opening_starts_a_second_affidavit(self) -> None:
        grouping = group([A, O, A, O], [True, False, True, False])
        assert grouping.affidavits == [[0, 1], [2, 3]]

    def test_pages_without_an_opening_stay_with_the_affidavit_they_follow(self) -> None:
        assert group([A, A, A], [True, False, False]).affidavits == [[0, 1, 2]]

    def test_unlabelled_pages_beyond_an_affidavits_length_are_left_alone(self) -> None:
        grouping = group([A, O, O, O, O], [True, False, False, False, False])
        assert grouping.affidavits == [[0, 1, 2]]
        assert grouping.page_types[3:] == [O, O]

    def test_other_pages_before_any_affidavit_are_not_read(self) -> None:
        assert group([O, O], [False, False]).affidavits == []

    def test_the_opening_is_recognised(self) -> None:
        assert starts_affidavit(AFFIDAVIT_PAGE)
        assert not starts_affidavit("Index No. 123 — Affidavit of Service, continued")


class TestJudgmentDate:
    @pytest.mark.parametrize(
        ("text", "expected", "quote"),
        [
            (
                "Judgment entered on September 3, 2025 by the Clerk.",
                date(2025, 9, 3),
                "September 3, 2025",
            ),
            ("Entered: 09/03/2025   ________ Clerk", date(2025, 9, 3), "09/03/2025"),
            (
                "CIVIL COURT ENTERED\nCOUNTY OF BRONX SEP 03 2025\nCLERK",
                date(2025, 9, 3),
                "SEP 03 2025",
            ),
        ],
    )
    def test_each_printed_form_is_read(self, text: str, expected: date, quote: str) -> None:
        found = read_entry_date({4: text})
        assert found is not None
        assert (found.value, found.quote, found.page) == (expected, quote, 4)

    def test_the_service_date_is_not_mistaken_for_the_entry_date(self) -> None:
        found = read_entry_date({0: JUDGMENT_PAGE})
        assert found is not None and found.value == date(2025, 9, 3)

    def test_a_judgment_with_no_entry_date_says_nothing(self) -> None:
        assert read_entry_date({0: "JUDGMENT. ADJUDGED that plaintiff recover $900."}) is None


def _words(*tokens: str) -> list[Word]:
    return [Word(t, 10.0 * i, 100.0, 10.0 * i + 8, 110.0) for i, t in enumerate(tokens)]


class TestProvenance:
    def test_an_exact_quote_gets_the_box_around_its_words(self) -> None:
        words = _words("served", "on", "June", "12,", "2025", "at", "7:42", "PM")
        assert locate("June 12, 2025", [words], [0]) == (0, (20.0, 100.0, 48.0, 110.0))

    def test_the_page_the_model_named_is_not_trusted_over_the_words(self) -> None:
        pages = [_words("nothing", "here"), _words("2100", "WHITE", "PLAINS", "ROAD")]
        found = locate("2100 White Plains Road", pages, [0, 1], preferred=0)
        assert found is not None and found[0] == 1

    def test_a_one_letter_slip_is_still_found(self) -> None:
        words = _words("2100", "WHITE", "PLAINS", "ROAD,", "Bronx")
        assert locate("2100 WHITE PLANS ROAD, Bronx", [words], [0]) is not None

    def test_words_that_are_not_there_get_no_box(self) -> None:
        assert locate("1600 Pennsylvania Avenue", [_words("2100", "WHITE", "PLAINS")], [0]) is None

    def test_on_the_demo_affidavit_the_served_address_is_boxed(self, demo_pdf: bytes) -> None:
        layer = extract_text(demo_pdf)
        found = locate("2100 WHITE PLAINS ROAD", layer.words, [0, 1])
        assert found is not None and found[0] == 0
        x0, top, x1, bottom = found[1]
        width, height = layer.sizes[0]
        assert 0 <= x0 < x1 <= width and 0 <= top < bottom <= height


class TestMethodCrossCheck:
    def _draft(self, method: str, checkbox: str | None = None) -> AffidavitDraft:
        return AffidavitDraft(
            method=method, method_checkbox=checkbox, field_confidence={"method": 0.95}
        )

    def test_a_ticked_box_that_disagrees_flags_the_method(self) -> None:
        draft, notes = validate(self._draft("308_2", checkbox="308_1"), None)
        assert draft.field_confidence["method"] == 0.5
        assert [n.field for n in notes if n.level == "warning"] == ["method"]

    def test_the_wording_is_the_witness_when_there_are_no_boxes(self) -> None:
        text = "deponent affixed a true copy to the door of said premises"
        draft, notes = validate(self._draft("308_1"), text)
        assert draft.field_confidence["method"] <= 0.5
        assert any(n.field == "method" and n.level == "warning" for n in notes)

    def test_agreement_raises_no_flag(self) -> None:
        text = "a person of suitable age and discretion"
        draft = self._draft("308_2", checkbox="308_2").model_copy(
            update={"evidence_quotes": {"method": "suitable age and discretion"}}
        )
        draft, notes = validate(draft, text)
        assert not [n for n in notes if n.field == "method"]

    def test_a_form_printing_every_method_proves_none_of_them(self) -> None:
        form = (
            "[X] Individual: delivered to the Defendant personally. [ ] a person of suitable "
            "age and discretion. [ ] affixing a true copy to the door."
        )
        assert infer_method(form) is None


class TestAgencyKey:
    @pytest.mark.parametrize(
        "name",
        [
            "Kestrel Legal Support Services Inc.",
            "KESTREL LEGAL SUPPORT SERVICES, INC",
            "kestrel legal support services llc",
        ],
    )
    def test_one_agency_however_it_was_typed(self, name: str) -> None:
        assert agency_key(name) == "KESTREL LEGAL SUPPORT SERVICES"

    def test_an_ampersand_is_part_of_the_name(self) -> None:
        assert (
            agency_key("Halloway & Finch Process Servers LLC") == "HALLOWAY & FINCH PROCESS SERVERS"
        )

    def test_nothing_is_nothing(self) -> None:
        assert agency_key(None) is None
        assert agency_key("  ,. ") is None


def test_the_model_numbers_pages_from_one_and_evidence_from_zero() -> None:
    draft = draft_from_payload(
        {
            "served_address": {
                "value": "1 Main St",
                "confidence": 0.9,
                "evidence_quote": "1 Main St",
                "page": 2,
            },
            "method_checkbox": {"value": "none", "confidence": 1, "evidence_quote": ""},
        }
    )
    assert draft.evidence["served_address"].page == 1
    assert draft.method_checkbox is None


class _FakeExtractor:
    """Answers like a provider would, and records what it was shown."""

    name = "fake"

    def __init__(self, classify: object = None, judgment: object = None) -> None:
        self.classify_answer = classify
        self.judgment_answer = judgment
        self.extracted: list[ExtractInput] = []
        self.asked: list[str] = []

    async def extract(self, doc: ExtractInput) -> AffidavitDraft:
        self.extracted.append(doc)
        return AffidavitDraft(
            served_address="2100 WHITE PLAINS ROAD, Bronx, NY 10462",
            evidence_quotes={"served_address": "2100 WHITE PLAINS ROAD, Bronx, NY 10462"},
            field_confidence={"served_address": 0.95},
        )

    async def ask_json(
        self, instruction: str, images: list[PageImage], schema: dict[str, Any]
    ) -> object:
        self.asked.append(instruction)
        if "sort the pages" in instruction:
            if isinstance(self.classify_answer, Exception):
                raise self.classify_answer
            return self.classify_answer
        return self.judgment_answer


@pytest.mark.asyncio
async def test_a_text_affidavit_is_read_from_its_own_pages_and_boxed(
    demo_pdf: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeExtractor()
    monkeypatch.setattr(vision, "get_extractor", lambda _: fake)
    result = await extract_document(demo_pdf, previews=False)

    (found,) = result.affidavits
    (shown,) = fake.extracted
    assert shown.text is not None and shown.text.startswith("=== Page 1 ===")
    assert "=== Page 2 ===" in shown.text
    evidence = found.draft.evidence["served_address"]
    assert evidence.page == 0 and evidence.bbox is not None
    assert fake.asked == []  # nothing about a text-layer file needs a model to classify it


@pytest.mark.asyncio
async def test_image_pages_are_classified_by_one_call(
    demo_scan: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeExtractor(classify={"pages": ["affidavit_of_service", "other"]})
    monkeypatch.setattr(vision, "get_extractor", lambda _: fake)
    result = await extract_document(demo_scan, previews=False)

    assert len([a for a in fake.asked if "sort the pages" in a]) == 1
    assert result.page_types == [A, A]  # the 'other' page continues the affidavit
    assert result.affidavits[0].pages == [0, 1]
    assert result.used_vision


@pytest.mark.parametrize(
    "answer",
    [
        RuntimeError("boom"),
        {"pages": ["affidavit_of_service"]},
        {"pages": ["menu", "other"]},
        "not json",
    ],
)
@pytest.mark.asyncio
async def test_an_unusable_classification_reads_every_page_as_the_affidavit(
    answer: object, demo_scan: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _FakeExtractor(classify=answer)
    if isinstance(answer, RuntimeError):
        from app.api.errors import ExtractionUnavailableError

        fake.classify_answer = ExtractionUnavailableError("down")
    monkeypatch.setattr(vision, "get_extractor", lambda _: fake)
    result = await extract_document(demo_scan, previews=False)
    assert result.page_types == [A, A]
    assert [n.field for n in result.notes] == ["pages"]


@pytest.mark.asyncio
async def test_classification_answers_are_checked_against_the_page_count() -> None:
    fake = _FakeExtractor(classify={"pages": ["judgment"]})
    thumbs = [PageImage(b"", "image/jpeg"), PageImage(b"", "image/jpeg")]
    assert await classify_images(fake, thumbs) is None


@pytest.mark.asyncio
async def test_a_file_with_no_affidavit_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    from weasyprint import HTML

    pdf = HTML(string=f"<p>{JUDGMENT_PAGE}</p>" * 3).write_pdf()
    fake = _FakeExtractor()
    monkeypatch.setattr(vision, "get_extractor", lambda _: fake)
    result = await extract_document(bytes(pdf), previews=False)

    assert result.affidavits == []
    assert fake.extracted == []
    assert result.notes[0].field == "pages"
    assert result.judgment_entry_date == date(2025, 9, 3)
    assert result.judgment_evidence is not None and result.judgment_evidence.bbox is not None
