"""Anthropic affidavit extraction provider. Bible §12.

A single tool whose input schema is the extraction schema: the model fills the tool call
rather than writing JSON into prose, which is the same guarantee Gemini's structured
output gives. Nothing here logs the document, the prompt or the answer.
"""

from __future__ import annotations

import base64
from typing import Any

from app.api.errors import ExtractionUnavailableError
from app.config import get_settings
from app.domain.models import AffidavitDraft
from app.extraction.schema import response_json_schema
from app.extraction.vision import (
    REQUEST_TIMEOUT_S,
    TEMPERATURE,
    ExtractInput,
    prompt,
    request_draft,
)

UNAVAILABLE = "Automatic reading is unavailable right now. You can type the details in instead."

TOOL_NAME = "record_affidavit_fields"
MAX_TOKENS = 4096


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

    async def extract(self, doc: ExtractInput) -> AffidavitDraft:
        client = self._client()
        content: list[dict[str, Any]] = []
        if doc.text:
            content.append({"type": "text", "text": doc.text})
        for page in doc.page_images:
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
        if not content:
            return AffidavitDraft()

        tool = {
            "name": TOOL_NAME,
            "description": "Record the fields read from the affidavit of service.",
            "input_schema": response_json_schema(),
        }

        async def send(feedback: str | None) -> object:
            parts = list(content)
            if feedback:
                parts.append({"type": "text", "text": feedback})
            try:
                message = await client.messages.create(
                    model=self._model,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                    system=prompt(),
                    tools=[tool],
                    tool_choice={"type": "tool", "name": TOOL_NAME},
                    messages=[{"role": "user", "content": parts}],
                )
            except Exception as exc:  # every SDK failure reaches the user the same way
                raise ExtractionUnavailableError(UNAVAILABLE) from exc
            for block in message.content:
                if getattr(block, "type", None) == "tool_use":
                    return block.input
            return ""

        return await request_draft(send)
