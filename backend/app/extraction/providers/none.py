"""No-LLM provider. Returns an empty draft so the UI falls back to manual entry.

Bible §12: the app must be fully usable without any LLM. This is not a stub; it is a
supported configuration, and `LLM_PROVIDER=none` is the default in `.env.example`.
"""

from app.domain.models import AffidavitDraft
from app.extraction.vision import ExtractInput


class NoneExtractor:
    name = "none"

    async def extract(self, doc: ExtractInput) -> AffidavitDraft:
        return AffidavitDraft()
