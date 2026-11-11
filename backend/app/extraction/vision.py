"""Provider-agnostic affidavit extraction. The ONLY place an LLM is used. Bible §7, §12.

The pipeline (v1.1) is:

1. **Read the file** (`pdf_text.py`): a PDF's text layer page by page with word boxes, or
   a photo oriented and capped.
2. **Classify every page** (`classify.py`): text pages by keyword scoring; image-only pages
   by one model call over thumbnails, falling back to "every page might be the affidavit".
3. **Extract each affidavit** found, from its own pages only: their text when every page
   has a text layer, else images of those pages.
4. **Validate** each draft deterministically (`validators.py`) and **locate** each quote on
   its page (`provenance.py`).
5. **Read the judgment's entry date** when a judgment page is present (`judgment.py`).
6. Hand back small **previews** of the pages so the user can check against their own
   document.

Everything after a provider call is ordinary Python, and the app is fully usable with
`LLM_PROVIDER=none`, which skips the provider entirely.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Protocol

from pydantic import ValidationError

from app.api.errors import (
    BadInputError,
    ExtractionInvalidError,
    ExtractionUnavailableError,
    ServeTraceError,
)
from app.config import get_settings
from app.domain.models import (
    AffidavitDraft,
    ExtractedAffidavit,
    ExtractionResult,
    FieldEvidence,
    PagePreview,
    PageType,
    ValidationNote,
)
from app.extraction.classify import classify_text, group, starts_affidavit
from app.extraction.judgment import read_entry_date
from app.extraction.pdf_text import (
    PAGE_TEXT_MIN_CHARS,
    PREVIEW_EDGE,
    RASTER_MAX_PAGES,
    THUMBNAIL_EDGE,
    PageImage,
    PdfText,
    data_url,
    extract_text,
    image_page,
    rasterize,
    sha256_of,
    shrink,
    sniff,
)
from app.extraction.provenance import locate
from app.extraction.schema import draft_from_payload
from app.extraction.validators import parse_date, validate

PROMPT_PATH: Final = Path(__file__).resolve().parent / "prompt.md"

MAX_TEXT_CHARS: Final = 20_000
"""A real affidavit is two or three pages. Anything beyond this is not the affidavit."""

REQUEST_TIMEOUT_S: Final = 30.0
TEMPERATURE: Final = 0.0

THUMBNAIL_DPI: Final = 96
PREVIEW_DPI: Final = 110

RETRY_PREFACE: Final = (
    "Your previous answer could not be read as JSON matching the schema: {error}. "
    "Return only the JSON object, with every field present."
)

CLASSIFY_INSTRUCTION: Final = (
    "You sort the pages of a New York court file. For each page image, in the order given, "
    "say what it is: 'affidavit_of_service' (a process server's sworn statement of how "
    "papers were served, including its continuation, signature and notary pages), "
    "'summons_complaint' (a summons or a complaint), 'judgment' (a judgment or the clerk's "
    "entry of one), 'notice' (any other notice from the court), or 'other'. Return one entry "
    "per page and nothing else. Do not read or repeat anything else on the pages."
)

CLASSIFY_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "pages": {
            "type": "array",
            "items": {"type": "string", "enum": [t.value for t in PageType]},
        }
    },
    "required": ["pages"],
}

JUDGMENT_INSTRUCTION: Final = (
    "This is a page of a New York court judgment. Return the date the judgment was entered "
    "by the clerk, as YYYY-MM-DD in 'value', and the date exactly as printed in "
    "'evidence_quote'. If no entry date is printed, return empty strings. Never guess."
)

JUDGMENT_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {"value": {"type": "string"}, "evidence_quote": {"type": "string"}},
    "required": ["value", "evidence_quote"],
}


@lru_cache(maxsize=1)
def prompt() -> str:
    """Loaded once, from disk, so the prompt is reviewable as a file rather than a literal."""
    return PROMPT_PATH.read_text(encoding="utf-8")


def page_label(index: int) -> str:
    """How a page is introduced to the model. 1-based, as a person numbers pages."""
    return f"=== Page {index + 1} ==="


@dataclass(frozen=True, slots=True)
class ExtractInput:
    text: str | None
    page_images: list[PageImage] = field(default_factory=list)
    source_sha256: str = ""


class Extractor(Protocol):
    name: str

    async def extract(self, doc: ExtractInput) -> AffidavitDraft: ...

    async def ask_json(
        self, instruction: str, images: list[PageImage], schema: dict[str, Any]
    ) -> object: ...


Send = Callable[[str | None], Awaitable[object]]
"""Ask the provider once. The argument is feedback about the previous failed attempt."""


async def request_draft(send: Send) -> AffidavitDraft:
    """Call the provider, parse its answer, and retry exactly once on a schema violation.

    A bare retry would be pointless at temperature 0, so the second call is told what was
    wrong with the first. Transport and authentication failures are the provider's own to
    raise; they are not schema violations and are not retried here.
    """
    feedback: str | None = None
    last_error = ""
    for _ in range(2):
        answer = await send(feedback)
        try:
            payload = json.loads(answer) if isinstance(answer, str) else answer
            return draft_from_payload(payload)
        except (ValueError, TypeError, ValidationError) as exc:
            last_error = type(exc).__name__
            feedback = RETRY_PREFACE.format(error=last_error)
    raise ExtractionInvalidError(
        "We could not read the details off that document. You can type them in instead."
    )


def get_extractor(provider: str) -> Extractor:
    """Resolve the configured provider. "none" yields the empty-draft extractor."""
    if provider == "gemini":
        from app.extraction.providers.gemini import GeminiExtractor

        return GeminiExtractor()
    if provider == "anthropic":
        from app.extraction.providers.anthropic import AnthropicExtractor

        return AnthropicExtractor()

    from app.extraction.providers.none import NoneExtractor

    return NoneExtractor()


READER_NOTE: Final = "reader"
"""The document note set when field extraction failed and the drafts are empty because of
it. Evals read it so a reader outage is scored as a failure, not as every field wrong."""


@dataclass(frozen=True, slots=True)
class Source:
    """What the upload turned out to be, before any model sees it."""

    doc: ExtractInput
    n_pages: int
    has_text_layer: bool


def read_source(data: bytes) -> Source:
    """The whole file as one input: text layer if there is one, page images if not.

    Kept for callers that want the v1.0 view of a document (the demo fixtures and their
    tests). The v1.1 pipeline reads page by page through `extract_document`.
    """
    sha = sha256_of(data)
    if sniff(data) == "image":
        return Source(
            doc=ExtractInput(text=None, page_images=[image_page(data)], source_sha256=sha),
            n_pages=1,
            has_text_layer=False,
        )

    layer = extract_text(data)
    if layer.has_text_layer:
        doc = ExtractInput(text=layer.text[:MAX_TEXT_CHARS], page_images=[], source_sha256=sha)
    else:
        doc = ExtractInput(text=None, page_images=rasterize(data), source_sha256=sha)
    return Source(doc=doc, n_pages=layer.n_pages, has_text_layer=layer.has_text_layer)


def _loads(answer: object) -> object:
    return json.loads(answer) if isinstance(answer, str) else answer


async def classify_images(
    extractor: Extractor, thumbnails: list[PageImage]
) -> list[PageType] | None:
    """One call over every image-only page's thumbnail. None when the answer is unusable."""
    try:
        payload = _loads(
            await extractor.ask_json(CLASSIFY_INSTRUCTION, thumbnails, CLASSIFY_SCHEMA)
        )
    except (ServeTraceError, ValueError, TypeError):
        return None
    pages = payload.get("pages") if isinstance(payload, dict) else None
    if not isinstance(pages, list) or len(pages) != len(thumbnails):
        return None
    try:
        return [PageType(str(value)) for value in pages]
    except ValueError:
        return None


@dataclass(slots=True)
class _Document:
    """Everything known about the upload once it has been read, before any extraction."""

    data: bytes
    sha: str
    n_pages: int
    has_text_layer: bool
    layer: PdfText | None
    photo: PageImage | None
    text_pages: set[int]
    page_types: list[PageType]
    notes: list[ValidationNote] = field(default_factory=list)
    used_vision: bool = False


async def _read(
    data: bytes, extractor: Extractor, override: list[PageType] | None = None
) -> _Document:
    sha = sha256_of(data)
    if sniff(data) == "image":
        # A single photo is the page the person was asked for: the affidavit. Asking a
        # model what it is first would cost a call and could only ever skip it.
        if override is not None and len(override) != 1:
            raise BadInputError(f"Got {len(override)} page labels for a one-page photo.")
        return _Document(
            data=data,
            sha=sha,
            n_pages=1,
            has_text_layer=False,
            layer=None,
            photo=image_page(data),
            text_pages=set(),
            page_types=list(override or [PageType.AFFIDAVIT_OF_SERVICE]),
        )

    layer = extract_text(data)
    text_pages = {
        i for i, text in enumerate(layer.pages) if len(text.strip()) >= PAGE_TEXT_MIN_CHARS
    }
    types: list[PageType | None] = [
        classify_text(layer.pages[i]) if i in text_pages else None for i in range(layer.n_pages)
    ]
    if override is not None:
        # The person re-tagged the pages: their labels stand, and nobody is asked again.
        if len(override) != layer.n_pages:
            raise BadInputError(
                f"Got {len(override)} page labels for a file with {layer.n_pages} pages."
            )
        types = list(override)
    image_pages = [i for i, t in enumerate(types) if t is None]
    document = _Document(
        data=data,
        sha=sha,
        n_pages=layer.n_pages,
        has_text_layer=layer.has_text_layer,
        layer=layer,
        photo=None,
        text_pages=text_pages,
        page_types=[],
    )
    if image_pages:
        answered: list[PageType] | None = None
        if len(image_pages) > 1 or text_pages:
            thumbs = rasterize(
                data, dpi=THUMBNAIL_DPI, pages=image_pages, max_edge=THUMBNAIL_EDGE, media="jpeg"
            )
            answered = await classify_images(extractor, thumbs)
        if answered is None:
            answered = [PageType.AFFIDAVIT_OF_SERVICE] * len(image_pages)
            if len(image_pages) > 1:
                document.notes.append(
                    ValidationNote(
                        field="pages",
                        level="info",
                        message="We could not tell what every page was, so we read them all "
                        "as the affidavit. Please check the pages shown.",
                    )
                )
        for index, page_type in zip(image_pages, answered, strict=True):
            types[index] = page_type
    document.page_types = [t or PageType.OTHER for t in types]
    return document


def _input_for(document: _Document, pages: list[int]) -> tuple[ExtractInput, str | None]:
    """What the model sees for one affidavit, and the text the validators check it against."""
    if document.photo is not None:
        photo = ExtractInput(text=None, page_images=[document.photo], source_sha256=document.sha)
        return photo, None
    assert document.layer is not None
    if all(p in document.text_pages for p in pages):
        text = "\n".join(f"{page_label(p)}\n{document.layer.pages[p]}" for p in pages)
        return ExtractInput(text=text[:MAX_TEXT_CHARS], source_sha256=document.sha), text
    images = rasterize(document.data, pages=pages[:RASTER_MAX_PAGES])
    return ExtractInput(text=None, page_images=images, source_sha256=document.sha), None


def _with_boxes(
    draft: AffidavitDraft, document: _Document, pages: list[int], grounded: bool
) -> AffidavitDraft:
    """Fill each field's page and, on a text layer, the box around its words."""
    evidence: dict[str, FieldEvidence] = {}
    for name, quote in draft.evidence_quotes.items():
        known = draft.evidence.get(name, FieldEvidence(quote=quote))
        page = known.page if known.page in pages else None
        bbox = None
        if grounded and document.layer is not None:
            found = locate(quote, document.layer.words, pages, preferred=page)
            if found is not None:
                page, bbox = found
        evidence[name] = FieldEvidence(quote=quote, page=page, bbox=bbox)
    return draft.model_copy(update={"evidence": evidence})


async def _extract_one(
    document: _Document, extractor: Extractor, pages: list[int]
) -> ExtractedAffidavit:
    doc, source_text = _input_for(document, pages)
    if doc.page_images:
        document.used_vision = True
    try:
        draft = await extractor.extract(doc)
    except (ExtractionUnavailableError, ExtractionInvalidError) as exc:
        # The reader failing must not cost the person what needs no reader: the page types,
        # the page images, the judgment date and the method read off the form's own words.
        # They get an empty draft to type into, and a note saying why it is empty.
        draft = AffidavitDraft()
        if not any(note.field == READER_NOTE for note in document.notes):
            document.notes.append(
                ValidationNote(field=READER_NOTE, level="error", message=exc.message)
            )
    validated, notes = validate(draft, source_text)
    return ExtractedAffidavit(
        draft=_with_boxes(validated, document, pages, grounded=source_text is not None),
        notes=notes,
        pages=pages,
    )


async def _judgment_date(
    document: _Document, extractor: Extractor
) -> tuple[Any, FieldEvidence | None]:
    pages = [i for i, t in enumerate(document.page_types) if t is PageType.JUDGMENT]
    if not pages or document.layer is None:
        return None, None
    text_pages = {i: document.layer.pages[i] for i in pages if i in document.text_pages}
    found = read_entry_date(text_pages)
    if found is not None:
        located = locate(found.quote, document.layer.words, [found.page], preferred=found.page)
        return found.value, FieldEvidence(
            quote=found.quote, page=found.page, bbox=located[1] if located else None
        )
    image_pages = [i for i in pages if i not in document.text_pages]
    if not image_pages:
        return None, None
    page = rasterize(document.data, pages=image_pages[:1])
    try:
        payload = _loads(await extractor.ask_json(JUDGMENT_INSTRUCTION, page, JUDGMENT_SCHEMA))
    except (ServeTraceError, ValueError, TypeError):
        return None, None
    if not isinstance(payload, dict):
        return None, None
    value = parse_date(str(payload.get("value") or ""))
    quote = str(payload.get("evidence_quote") or "") or None
    if value is None:
        return None, None
    document.used_vision = True
    return value, FieldEvidence(quote=quote, page=image_pages[0])


def _previews(document: _Document) -> list[PagePreview]:
    if document.photo is not None:
        small = shrink(document.photo, PREVIEW_EDGE)
        # Units match the full-size page the model saw, so a box (none, on a photo) and a
        # preview always agree about scale.
        return [
            PagePreview(
                index=0,
                width=document.photo.width,
                height=document.photo.height,
                image=data_url(small),
            )
        ]
    assert document.layer is not None
    rendered = rasterize(
        document.data,
        dpi=PREVIEW_DPI,
        pages=list(range(document.n_pages)),
        max_edge=PREVIEW_EDGE,
        media="jpeg",
    )
    return [
        PagePreview(
            index=page.page,
            width=document.layer.sizes[page.page][0],
            height=document.layer.sizes[page.page][1],
            image=data_url(page),
        )
        for page in rendered
    ]


async def extract_document(
    data: bytes,
    *,
    previews: bool = True,
    page_types: list[PageType] | None = None,
    extract_pages: list[int] | None = None,
    extractor: Extractor | None = None,
) -> ExtractionResult:
    """The whole path: bytes in, every affidavit in the file out as a draft. No file is
    ever written, and nothing read is kept after the response.

    `page_types` replaces classification with the person's own labels (the review screen's
    re-tagging); their labels are taken as they are, with no continuation pages folded in.
    `extract_pages` limits field extraction to the affidavits that touch those pages, so
    re-tagging one range never re-reads the rest of the file.
    """
    extractor = extractor or get_extractor(get_settings().llm_provider)
    document = await _read(data, extractor, page_types)
    starts = [
        document.layer is not None
        and i in document.text_pages
        and starts_affidavit(document.layer.pages[i])
        for i in range(document.n_pages)
    ]
    grouping = group(document.page_types, starts, fold=page_types is None)
    document.page_types = grouping.page_types

    wanted = set(extract_pages) if extract_pages is not None else None
    runs = [pages for pages in grouping.affidavits if wanted is None or wanted.intersection(pages)]
    affidavits = [await _extract_one(document, extractor, pages) for pages in runs]
    if not grouping.affidavits:
        document.notes.append(
            ValidationNote(
                field="pages",
                level="warning",
                message="We could not find an affidavit of service in this file. You can type "
                "the details in, or upload the page that says Affidavit of Service.",
            )
        )
    judgment_pages = {i for i, t in enumerate(document.page_types) if t is PageType.JUDGMENT}
    entry_date, entry_evidence = (
        await _judgment_date(document, extractor)
        if wanted is None or wanted & judgment_pages
        else (None, None)
    )

    return ExtractionResult(
        page_types=document.page_types,
        affidavits=affidavits,
        judgment_entry_date=entry_date,
        judgment_evidence=entry_evidence,
        notes=document.notes,
        provider=extractor.name,
        source_sha256=document.sha,
        n_pages=document.n_pages,
        has_text_layer=document.has_text_layer,
        used_vision=document.used_vision,
        previews=_previews(document) if previews else [],
    )
