"""The Gemini provider, against a fake client. No request leaves the machine.

What is pinned here is the shape of the call, because that is where the provider's real
decisions live: temperature 0, a JSON schema, the deadline, and thinking switched off.
The last one is not a tuning preference. Measured on gemini-3.8-flash, thinking took one
affidavit to 8,250 thought tokens and 31 seconds, past the 30-second deadline, where the
same call without it answered in 3.5 seconds with the same fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from app.api.errors import ExtractionUnavailableError
from app.extraction.providers.gemini import GeminiExtractor
from app.extraction.vision import REQUEST_TIMEOUT_S, ExtractInput


@dataclass
class _Response:
    text: str


@dataclass
class _FakeModels:
    answer: str = "{}"
    fail: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def generate_content(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        if self.fail is not None:
            raise self.fail
        return _Response(self.answer)


class _FakeClient:
    def __init__(self, models: _FakeModels) -> None:
        self.aio = type("Aio", (), {"models": models})()


def _extractor(models: _FakeModels, monkeypatch: pytest.MonkeyPatch) -> GeminiExtractor:
    extractor = GeminiExtractor(api_key="test-key", model="gemini-test")
    monkeypatch.setattr(extractor, "_client", lambda: _FakeClient(models))
    return extractor


@pytest.mark.asyncio
async def test_the_call_is_deterministic_structured_bounded_and_does_not_think(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    models = _FakeModels()
    await _extractor(models, monkeypatch).extract(ExtractInput(text="AFFIDAVIT OF SERVICE"))

    (call,) = models.calls
    config = call["config"]
    assert call["model"] == "gemini-test"
    assert config.temperature == 0
    assert config.response_mime_type == "application/json"
    assert config.response_schema is not None
    assert config.thinking_config.thinking_budget == 0
    assert config.http_options.timeout == int(REQUEST_TIMEOUT_S * 1000)


@pytest.mark.asyncio
async def test_any_sdk_failure_reaches_the_user_as_type_it_in_instead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deadline, a quota or a retired model all mean the same thing to the person at the
    form: nothing was read, and the check still works if they type the details."""
    models = _FakeModels(fail=RuntimeError("504 DEADLINE_EXCEEDED"))
    with pytest.raises(ExtractionUnavailableError):
        await _extractor(models, monkeypatch).extract(ExtractInput(text="AFFIDAVIT OF SERVICE"))


def test_no_key_means_no_provider_rather_than_a_failed_request() -> None:
    with pytest.raises(ExtractionUnavailableError):
        GeminiExtractor(api_key="")
