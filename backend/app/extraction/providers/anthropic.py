"""Anthropic affidavit extraction provider. Bible §12.

A single tool whose input schema is the question's schema: the model fills the tool call
rather than writing JSON into prose, which is the same guarantee Gemini's structured
output gives. Nothing here logs the document, the prompt or the answer.
"""

from __future__ import annotations

import base64
from typing import Any

from app.api.errors import ExtractionUnavailableError
from app.config import get_settings
from app.domain.models import AffidavitDraft
from app.extraction.pdf_text import PageImage
from app.extraction.schema import response_json_schema
from app.extraction.vision import (
    REQUEST_TIMEOUT_S,
    TEMPERATURE,
    ExtractInput,
    page_label,
    prompt,
    request_draft,
)

UNAVAILABLE = "Automatic reading is unavailable right now. You can type the details in instead."

TOOL_NAME = "record_affidavit_fields"
ANSWER_TOOL = "record_answer"
MAX_TOKENS = 4096


def _content(text: str | None, images: list[PageImage]) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    if text:
        content.append({"type": "text", "text": text})
    for page in images:
        content.append({"type": "text", "text": page_label(page.page)})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": page.media_type,
                    "data": base64.b64encode(page.data).decode("ascii"),
                },
            }
        )
    return content


class AnthropicExtractor:
    name = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.anthropic_api_key
        self._model = model or settings.anthropic_model
        if not self._api_key:
            raise ExtractionUnavailableError(UNAVAILABLE)

    def _client(self) -> Any:
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # the LLM extras are optional at install time
            raise ExtractionUnavailableError(UNAVAILABLE) from exc
        return AsyncAnthropic(api_key=self._api_key, timeout=REQUEST_TIMEOUT_S)

    async def _call(
        self,
        system: str,
        parts: list[dict[str, Any]],
        tool_name: str,
        description: str,
        schema: dict[str, Any],
    ) -> object:
        client = self._client()
        tool = {"name": tool_name, "description": description, "input_schema": schema}
        try:
            message = await client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                system=system,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": parts}],
            )
        except Exception as exc:  # every SDK failure reaches the user the same way
            raise ExtractionUnavailableError(UNAVAILABLE) from exc
        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                return block.input
        return ""

    async def extract(self, doc: ExtractInput) -> AffidavitDraft:
        content = _content(doc.text, doc.page_images)
        if not content:
            return AffidavitDraft()

        async def send(feedback: str | None) -> object:
            parts = list(content)
            if feedback:
                parts.append({"type": "text", "text": feedback})
            return await self._call(
                prompt(),
                parts,
                TOOL_NAME,
                "Record the fields read from the affidavit of service.",
                response_json_schema(),
            )

        return await request_draft(send)

    async def ask_json(
        self, instruction: str, images: list[PageImage], schema: dict[str, Any]
    ) -> object:
        return await self._call(
            instruction, _content(None, images), ANSWER_TOOL, "Record the answer.", schema
        )
