"""No-LLM provider. Returns an empty draft so the UI falls back to manual entry.

Bible §12: the app must be fully usable without any LLM. Session 2.
"""

from app.extraction.vision import ExtractInput, ExtractionResult


class NoneExtractor:
    async def extract(self, doc: ExtractInput) -> ExtractionResult:
        return ExtractionResult(affidavit=None, evidence_quotes={}, provider="none")
