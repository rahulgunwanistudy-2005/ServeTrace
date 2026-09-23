"""Gemini affidavit extraction provider. Bible §12. Session 2."""

from app.extraction.vision import ExtractInput, ExtractionResult


class GeminiExtractor:
    async def extract(self, doc: ExtractInput) -> ExtractionResult:
        raise NotImplementedError("Session 2")
