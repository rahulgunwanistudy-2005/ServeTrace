"""The orchestrator: how the document reaches a provider, and what happens when one
answers badly. No provider is called over the network anywhere in this file."""

import json
from typing import Any

import pytest

from app.api.errors import ExtractionInvalidError, ExtractionUnavailableError
from app.domain.models import AffidavitDraft
from app.extraction.providers.none import NoneExtractor
from app.extraction.vision import (
    MAX_TEXT_CHARS,
    ExtractInput,
    extract_affidavit,
    get_extractor,
    prompt,
    read_source,
    request_draft,
)


def test_a_pdf_with_a_text_layer_is_sent_as_text(demo_pdf: bytes) -> None:
    source = read_source(demo_pdf)
    assert source.has_text_layer
    assert source.doc.text is not None
    assert source.doc.page_images == []
    assert len(source.doc.text) <= MAX_TEXT_CHARS


def test_a_scan_is_sent_as_images(demo_scan: bytes) -> None:
    source = read_source(demo_scan)
    assert not source.has_text_layer
    assert source.doc.text is None
    assert source.doc.page_images
    assert source.doc.source_sha256


def test_a_photo_is_one_page_of_images() -> None:
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
        "00000049454e44ae426082"
    )
    source = read_source(png)
    assert source.n_pages == 1
    assert len(source.doc.page_images) == 1


def test_the_prompt_is_a_file_on_disk_not_a_literal() -> None:
    """Bible §12 makes the prompt reviewable, so it is kept where it can be read in a diff."""
    text = prompt()
    assert "evidence_quote" in text
    assert "308_4" in text
    assert "Never guess" in text


@pytest.mark.asyncio
async def test_a_good_answer_is_parsed_on_the_first_call(recorded_response: dict[str, Any]) -> None:
    calls: list[str | None] = []

    async def send(feedback: str | None) -> object:
        calls.append(feedback)
        return json.dumps(recorded_response)

    draft = await request_draft(send)

    assert draft.defendant_name == "Maria Delarmo"
    assert calls == [None]


@pytest.mark.asyncio
async def test_a_schema_violation_is_retried_once_with_the_reason(
    recorded_response: dict[str, Any],
) -> None:
    """A bare retry at temperature 0 would just get the same answer back, so the second
    call is told what was wrong with the first."""
    calls: list[str | None] = []

    async def send(feedback: str | None) -> object:
        calls.append(feedback)
        return "here is the JSON you asked for" if feedback is None else recorded_response

    draft = await request_draft(send)

    assert draft.defendant_name == "Maria Delarmo"
    assert len(calls) == 2
    assert calls[1] is not None and "JSON" in calls[1]


@pytest.mark.asyncio
async def test_two_bad_answers_give_up_rather_than_loop() -> None:
    calls: list[str | None] = []

    async def send(feedback: str | None) -> object:
        calls.append(feedback)
        return "still not JSON"

    with pytest.raises(ExtractionInvalidError):
        await request_draft(send)
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_a_provider_failure_is_not_retried_as_a_schema_violation() -> None:
    """A dead provider is not going to answer better the second time, and the user gets
    the manual entry form either way."""
    calls: list[str | None] = []

    async def send(feedback: str | None) -> object:
        calls.append(feedback)
        raise ExtractionUnavailableError("down")

    with pytest.raises(ExtractionUnavailableError):
        await request_draft(send)
    assert len(calls) == 1


def test_the_default_provider_is_the_one_that_needs_no_key() -> None:
    assert get_extractor("none").name == "none"
    assert get_extractor("something-else").name == "none"


@pytest.mark.asyncio
async def test_the_none_provider_returns_an_empty_draft(demo_pdf: bytes) -> None:
    draft = await NoneExtractor().extract(ExtractInput(text="anything", source_sha256="x"))
    assert draft == AffidavitDraft()


@pytest.mark.asyncio
async def test_without_an_llm_the_document_still_yields_what_can_be_read(demo_pdf: bytes) -> None:
    """Bible §12: the app is fully usable with no LLM. The deterministic half still runs,
    so the method comes off the form's own wording and the user types the rest."""
    result = await extract_affidavit(demo_pdf)

    assert result.provider == "none"
    assert result.has_text_layer
    assert not result.used_vision
    assert result.n_pages == 2
    assert len(result.source_sha256) == 64
    assert result.draft.method == "308_2"
    assert result.draft.defendant_name is None
