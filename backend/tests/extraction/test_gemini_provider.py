"""The Gemini provider, against a fake client. No request leaves the machine.

What is pinned here is the shape of the call, because that is where the provider's real
decisions live: temperature 0, a JSON schema, the deadline, and thinking switched off.
The last one is not a tuning preference. Measured on gemini-3.8-flash, thinking took one
affidavit to 8,250 thought tokens and 31 seconds, past the 30-second deadline, where the
same call without it answered in 3.5 seconds with the same fields.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.api.errors import ExtractionUnavailableError
from app.extraction.providers import gemini
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


class _OverloadedError(Exception):
    """What the SDK raises when the model is refusing work: a `ServerError` with code 503."""

    code = 503


class _DeadlineExceededError(Exception):
    code = 504


@dataclass
class _FlakyModels(_FakeModels):
    failures: list[Exception] = field(default_factory=list)

    async def generate_content(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        if self.failures:
            raise self.failures.pop(0)
        return _Response(self.answer)


@pytest.fixture
def no_pauses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini, "OVERLOAD_BACKOFF_S", (0.0, 0.0))


@pytest.mark.asyncio
@pytest.mark.usefixtures("no_pauses")
async def test_a_model_under_high_demand_is_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """Seen live: two 503s, then an answer. One try would have sent that person to typing."""
    models = _FlakyModels(failures=[_OverloadedError(), _OverloadedError()])
    await _extractor(models, monkeypatch).extract(ExtractInput(text="AFFIDAVIT OF SERVICE"))
    assert len(models.calls) == 3


@pytest.mark.asyncio
@pytest.mark.usefixtures("no_pauses")
async def test_retries_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    models = _FlakyModels(failures=[_OverloadedError() for _ in range(5)])
    with pytest.raises(ExtractionUnavailableError):
        await _extractor(models, monkeypatch).extract(ExtractInput(text="AFFIDAVIT OF SERVICE"))
    assert len(models.calls) == 1 + len(gemini.OVERLOAD_BACKOFF_S)


@pytest.mark.asyncio
@pytest.mark.usefixtures("no_pauses")
async def test_a_deadline_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 504 has already spent the whole deadline; asking again would double the wait."""
    models = _FlakyModels(failures=[_DeadlineExceededError()])
    with pytest.raises(ExtractionUnavailableError):
        await _extractor(models, monkeypatch).extract(ExtractInput(text="AFFIDAVIT OF SERVICE"))
    assert len(models.calls) == 1


@pytest.mark.asyncio
async def test_an_image_without_the_sdk_answers_type_it_in_rather_than_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first production upload with a key set returned 500: the Docker image had no
    `google-genai`, and `extract` imported from it before `_client` could say so politely."""
    monkeypatch.setitem(sys.modules, "google", None)
    monkeypatch.setitem(sys.modules, "google.genai", None)
    with pytest.raises(ExtractionUnavailableError):
        await GeminiExtractor(api_key="test-key").extract(ExtractInput(text="AFFIDAVIT"))
