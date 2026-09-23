"""Provider-agnostic affidavit extraction. The ONLY place an LLM is used. Bible §7, §12."""

from dataclasses import dataclass
from typing import Protocol

from app.domain.models import Affidavit


@dataclass(frozen=True, slots=True)
class ExtractInput:
    text: str | None
    page_images: list[bytes]
    source_sha256: str


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    affidavit: Affidavit | None
    evidence_quotes: dict[str, str]
    provider: str


class Extractor(Protocol):
    async def extract(self, doc: ExtractInput) -> ExtractionResult: ...


def get_extractor(provider: str) -> Extractor:
    """Resolve the configured provider. "none" yields the empty-draft extractor."""
    raise NotImplementedError("Session 2")
