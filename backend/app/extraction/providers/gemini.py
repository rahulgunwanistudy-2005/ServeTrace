"""Gemini affidavit extraction provider. Bible §12.

Structured output: the schema from `extraction/schema.py` is handed to the model, so a
well-formed answer is the model's default rather than something we parse out of prose.
Nothing here logs the document, the prompt or the answer.
"""

from __future__ import annotations

import asyncio
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

OVERLOAD_BACKOFF_S: tuple[float, ...] = (1.0, 3.0)
"""Pauses before retrying a 503. Measured with a new key on 2026-09-28: two of three calls
were refused with "This model is currently experiencing high demand" and the third answered
in 5 s. A 503 is refused in well under a second, so two short retries fit inside the 30 s
deadline. Nothing else is retried: a 504 has already spent the deadline, and a 4xx — a bad
key, a spend cap, a retired model — will not change by asking again."""


def _is_overloaded(exc: Exception) -> bool:
    return getattr(exc, "code", None) == 503


class GeminiExtractor:
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.gemini_api_key
        self._model = model or settings.gemini_model
        if not self._api_key:
            raise ExtractionUnavailableError(UNAVAILABLE)

    def _client(self) -> Any:
        try:
            from google import genai
        except ImportError as exc:  # the LLM extras are optional at install time
            raise ExtractionUnavailableError(UNAVAILABLE) from exc
        return genai.Client(api_key=self._api_key)

    async def extract(self, doc: ExtractInput) -> AffidavitDraft:
        from google.genai import types

        client = self._client()
        parts: list[Any] = []
        if doc.text:
            parts.append(types.Part.from_text(text=doc.text))
        for page in doc.page_images:
            parts.append(types.Part.from_bytes(data=page.data, mime_type=page.media_type))
        if not parts:
            return AffidavitDraft()

        async def send(feedback: str | None) -> object:
            contents = list(parts)
            if feedback:
                contents.append(types.Part.from_text(text=feedback))
            config = types.GenerateContentConfig(
                system_instruction=prompt(),
                temperature=TEMPERATURE,
                response_mime_type="application/json",
                response_schema=response_json_schema(),
                # Copying fields off a page needs no reasoning, and thinking is
                # what made latency unbounded: measured on gemini-3.8-flash, one
                # affidavit spent 8,250 thought tokens and 31 s — past the 30 s
                # deadline — where the same call without it took 3.5 s and
                # returned the same answer.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                http_options=types.HttpOptions(timeout=int(REQUEST_TIMEOUT_S * 1000)),
            )
            for pause in (*OVERLOAD_BACKOFF_S, None):
                try:
                    response = await client.aio.models.generate_content(
                        model=self._model, contents=contents, config=config
                    )
                    return response.text or ""
                except Exception as exc:  # every SDK failure reaches the user the same way
                    if pause is None or not _is_overloaded(exc):
                        raise ExtractionUnavailableError(UNAVAILABLE) from exc
                    await asyncio.sleep(pause)
            raise AssertionError("unreachable")  # pragma: no cover

        return await request_draft(send)
