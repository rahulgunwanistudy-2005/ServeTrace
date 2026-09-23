"""Provider-agnostic affidavit extraction. The ONLY place an LLM is used. Bible §7, §12.

The pipeline is: bytes -> text layer or page images -> provider -> deterministic
validation. Everything after the provider call is ordinary Python, and the app is fully
usable with `LLM_PROVIDER=none`, which skips the provider entirely.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Final, Protocol

from pydantic import ValidationError

from app.api.errors import ExtractionInvalidError
from app.config import get_settings
from app.domain.models import AffidavitDraft, ExtractionResult
from app.extraction.pdf_text import (
    PageImage,
    extract_text,
    image_page,
    rasterize,
    sha256_of,
    sniff,
)
from app.extraction.schema import draft_from_payload
from app.extraction.validators import validate

PROMPT_PATH: Final = Path(__file__).resolve().parent / "prompt.md"

MAX_TEXT_CHARS: Final = 20_000
"""A real affidavit is two or three pages. Anything beyond this is not the affidavit."""

REQUEST_TIMEOUT_S: Final = 30.0
TEMPERATURE: Final = 0.0

RETRY_PREFACE: Final = (
    "Your previous answer could not be read as JSON matching the schema: {error}. "
    "Return only the JSON object, with every field present."
)


@lru_cache(maxsize=1)
def prompt() -> str:
    """Loaded once, from disk, so the prompt is reviewable as a file rather than a literal."""
    return PROMPT_PATH.read_text(encoding="utf-8")


@dataclass(frozen=True, slots=True)
class ExtractInput:
    text: str | None
    page_images: list[PageImage] = field(default_factory=list)
    source_sha256: str = ""


class Extractor(Protocol):
    name: str

    async def extract(self, doc: ExtractInput) -> AffidavitDraft: ...


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


@dataclass(frozen=True, slots=True)
class Source:
    """What the upload turned out to be, before any model sees it."""

    doc: ExtractInput
    n_pages: int
    has_text_layer: bool


def read_source(data: bytes) -> Source:
    """Text layer if there is one, page images if there is not. Bible §12."""
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


async def extract_affidavit(data: bytes) -> ExtractionResult:
    """The whole path: bytes in, validated draft out. No file is ever written."""
    source = read_source(data)
    extractor = get_extractor(get_settings().llm_provider)
    draft = await extractor.extract(source.doc)
    validated, notes = validate(draft, source.doc.text)

    return ExtractionResult(
        draft=validated,
        notes=notes,
        provider=extractor.name,
        source_sha256=source.doc.source_sha256,
        n_pages=source.n_pages,
        has_text_layer=source.has_text_layer,
        used_vision=bool(source.doc.page_images),
    )
