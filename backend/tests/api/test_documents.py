"""`POST /api/documents/{packet,affidavit}`: two PDFs, and nothing kept."""

from __future__ import annotations

import base64
import io
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes_documents import _filename
from app.config import get_settings
from app.main import create_app
from tests.documents.conftest import AT_WORK, demo_analysis, demo_fixes, statement

CASE = "maria_contradicted"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def packet_body(confirmed: bool = True, **overrides: Any) -> dict[str, Any]:
    analysis = demo_analysis(CASE)
    if not confirmed:
        analysis = analysis.model_copy(
            update={"affidavit": analysis.affidavit.model_copy(update={"user_confirmed": False})}
        )
    body: dict[str, Any] = {
        "analysis": analysis.model_dump(mode="json"),
        "fixes": [f.model_dump(mode="json") for f in demo_fixes(CASE)],
    }
    body.update(overrides)
    return body


def affidavit_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "analysis": demo_analysis(CASE).model_dump(mode="json"),
        "affiant": statement(name="Maria Delarmo").model_dump(mode="json"),
    }
    body.update(overrides)
    return body


def png() -> str:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (60, 30)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


# --- The happy path -------------------------------------------------------------------------


def test_the_packet_comes_back_as_a_pdf(client: TestClient, needs_pdf: None) -> None:
    response = client.post("/api/documents/packet", json=packet_body())

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_the_affidavit_comes_back_as_a_pdf(client: TestClient, needs_pdf: None) -> None:
    response = client.post("/api/documents/affidavit", json=affidavit_body())

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")


def test_a_map_captured_in_the_browser_is_accepted(client: TestClient, needs_pdf: None) -> None:
    response = client.post("/api/documents/packet", json=packet_body(map_png_base64=png()))
    assert response.status_code == 200


def test_the_download_is_named_after_the_case(client: TestClient, needs_pdf: None) -> None:
    disposition = client.post("/api/documents/packet", json=packet_body()).headers[
        "content-disposition"
    ]
    assert "attachment" in disposition
    assert ".pdf" in disposition


# --- Guards ---------------------------------------------------------------------------------


def test_an_unconfirmed_affidavit_is_refused(client: TestClient) -> None:
    """Bible §10, the same rule `/api/analyze` applies. Without it here, an affidavit could
    be confirmed for the analysis and a different one submitted for the document."""
    response = client.post("/api/documents/packet", json=packet_body(confirmed=False))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "affidavit_not_confirmed"


def test_too_many_location_points_are_refused(client: TestClient) -> None:
    """Bible §16."""
    over = get_settings().max_fixes + 1
    body = packet_body(fixes=[AT_WORK.model_dump(mode="json")] * over)
    response = client.post("/api/documents/packet", json=body)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_input"


def test_something_that_is_not_a_png_is_refused(client: TestClient) -> None:
    response = client.post(
        "/api/documents/packet", json=packet_body(map_png_base64="not a png at all")
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_input"


def test_a_body_that_is_not_an_analysis_is_refused_without_echoing_it(
    client: TestClient,
) -> None:
    response = client.post("/api/documents/packet", json={"analysis": {"nope": True}})

    assert response.status_code == 422
    assert "nope" not in response.text


# --- The filename ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("defendant", "expected"),
    [
        ("Maria Delarmo", "servetrace-packet-Maria-Delarmo.pdf"),
        ('bad"; rm -rf /', "servetrace-packet-bad-rm-rf.pdf"),
        ("line\r\nbreak", "servetrace-packet-line-break.pdf"),
        ("", "servetrace-packet.pdf"),
        ("的的的", "servetrace-packet.pdf"),
    ],
)
def test_the_filename_is_scrubbed_not_trusted(defendant: str, expected: str) -> None:
    """It comes off a scanned document and goes into a response header, and a newline in a
    header is a response-splitting bug in anybody's HTTP stack."""
    assert _filename("packet", defendant) == expected


def test_a_very_long_name_does_not_become_a_very_long_header() -> None:
    assert len(_filename("packet", "A" * 500)) < 80
