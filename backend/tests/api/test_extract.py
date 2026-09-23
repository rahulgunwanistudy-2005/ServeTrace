"""`POST /api/extract`. Upload limits first, because they are the only thing between the
server and whatever a browser feels like sending."""

import logging
from collections.abc import Iterator
from io import StringIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.logging import LOGGER_NAME, JsonFormatter
from app.main import create_app

DEMO = Path(__file__).resolve().parents[3] / "fixtures" / "demo_cases" / "maria_contradicted"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_settings() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_an_affidavit_with_a_text_layer_comes_back_as_a_draft(client: TestClient) -> None:
    """With `LLM_PROVIDER=none` the draft is empty except for what the deterministic half
    can read off the form. That is a supported configuration, not a degraded one."""
    files = {"file": ("affidavit.pdf", (DEMO / "affidavit.pdf").read_bytes(), "application/pdf")}
    response = client.post("/api/extract", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "none"
    assert body["has_text_layer"] is True
    assert body["used_vision"] is False
    assert body["n_pages"] == 2
    assert len(body["source_sha256"]) == 64
    assert body["draft"]["method"] == "308_2"
    assert body["notes"][0]["field"] == "method"


def test_a_scan_takes_the_vision_path(client: TestClient) -> None:
    files = {"file": ("scan.pdf", (DEMO / "affidavit_scanned.pdf").read_bytes(), "application/pdf")}
    response = client.post("/api/extract", files=files)

    assert response.status_code == 200
    assert response.json()["has_text_layer"] is False


def test_an_empty_file_is_refused(client: TestClient) -> None:
    response = client.post("/api/extract", files={"file": ("empty.pdf", b"", "application/pdf")})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_input"


def test_a_spreadsheet_is_refused_by_its_bytes_not_its_name(client: TestClient) -> None:
    files = {"file": ("affidavit.pdf", b"case,date\n1,2025-06-12\n", "application/pdf")}
    response = client.post("/api/extract", files=files)

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file"


def test_an_oversized_upload_is_refused_before_it_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        files = {"file": ("big.pdf", b"%PDF-1.7" + b"\0" * (2 << 20), "application/pdf")}
        response = client.post("/api/extract", files=files)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "upload_too_large"
    assert "1 MB" in response.json()["error"]["message"]


def test_demo_only_deployments_take_no_uploads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_ONLY", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        files = {"file": ("a.pdf", (DEMO / "affidavit.pdf").read_bytes(), "application/pdf")}
        response = client.post("/api/extract", files=files)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "demo_only"


def test_a_request_with_no_file_is_a_plain_422(client: TestClient) -> None:
    response = client.post("/api/extract")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_nothing_about_the_document_reaches_the_log(client: TestClient) -> None:
    """Bible §16: the log line carries a route, a status and a latency. Never a name.

    The real formatter writes to a buffer here, so this checks the bytes that would have
    gone to the log, not a summary of them.
    """
    buffer = StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(handler)
    try:
        files = {
            "file": ("affidavit.pdf", (DEMO / "affidavit.pdf").read_bytes(), "application/pdf")
        }
        client.post("/api/extract", files=files)
    finally:
        logger.removeHandler(handler)

    logged = buffer.getvalue()
    assert '"route":"/api/extract"' in logged
    assert "Delarmo" not in logged
    assert "WHITE PLAINS" not in logged
    assert "2100" not in logged
