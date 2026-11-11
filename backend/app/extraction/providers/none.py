"""No-LLM provider. Returns an empty draft so the UI falls back to manual entry.

Bible §12: the app must be fully usable without any LLM. This is not a stub; it is a
supported configuration, and `LLM_PROVIDER=none` is the default in `.env.example`.
Questions only a model could answer — what an image-only page is, a date on a photo of a
judgment — are refused, and the pipeline takes its conservative fallback.
"""

from typing import Any

from app.api.errors import ExtractionUnavailableError
from app.domain.models import AffidavitDraft
from app.extraction.pdf_text import PageImage
from app.extraction.vision import ExtractInput


class NoneExtractor:
    name = "none"

    async def extract(self, doc: ExtractInput) -> AffidavitDraft:
        return AffidavitDraft()

    async def ask_json(
        self, instruction: str, images: list[PageImage], schema: dict[str, Any]
    ) -> object:
        raise ExtractionUnavailableError("No reader is configured.")
