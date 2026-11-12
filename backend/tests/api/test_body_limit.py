"""Bible §16: an oversized body is refused before anything reads it."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.body_limit import HEADROOM_BYTES
from app.config import get_settings

BATCH = Path(__file__).resolve().parents[3] / "fixtures" / "advocate_batch" / "affidavits.json"


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def _limit() -> int:
    return get_settings().max_upload_bytes + HEADROOM_BYTES


def test_a_declared_oversized_body_is_refused_with_the_usual_envelope(client: TestClient) -> None:
    body = b"[" + b" " * (_limit() + 1) + b"]"
    response = client.post(
        "/api/advocate/batch", content=body, headers={"content-type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "upload_too_large"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_a_streamed_oversized_body_is_refused_too(client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        yield b"["
        for _ in range(_limit() // (1024 * 1024) + 2):
            yield b" " * (1024 * 1024)
        yield b"]"

    response = client.post(
        "/api/analyze", content=chunks(), headers={"content-type": "application/json"}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "upload_too_large"


def test_an_ordinary_batch_is_untouched(client: TestClient) -> None:
    affidavits = json.loads(BATCH.read_text(encoding="utf-8"))
    assert client.post("/api/advocate/batch", json=affidavits).status_code == 200


def test_a_batch_over_the_configured_count_is_refused(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    affidavits = json.loads(BATCH.read_text(encoding="utf-8"))
    monkeypatch.setenv("MAX_BATCH_AFFIDAVITS", "10")
    get_settings.cache_clear()
    try:
        response = client.post("/api/advocate/batch", json=affidavits[:11])
    finally:
        monkeypatch.delenv("MAX_BATCH_AFFIDAVITS")
        get_settings.cache_clear()
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_input"
