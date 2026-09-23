"""Anthropic affidavit extraction provider. Bible §12. Session 2."""

from app.extraction.vision import ExtractInput, ExtractionResult


class AnthropicExtractor:
    async def extract(self, doc: ExtractInput) -> ExtractionResult:
        raise NotImplementedError("Session 2")
