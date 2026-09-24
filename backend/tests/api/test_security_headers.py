"""Bible §16, as assertions rather than as a comment in `main.py`.

The page's own Content-Security-Policy is not tested here, because it is not written here:
SvelteKit hashes its inline bootstrap into a `<meta>` tag at build time. What is tested is
everything the server is responsible for — the headers a meta tag cannot express, the far
stricter policy the API gets, the caching, and the ordering claim that makes all of it
apply to responses the route handlers never see.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.security import API_CSP, BASE_HEADERS, IMMUTABLE, REVALIDATE
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_every_base_header_is_on_an_ordinary_response(client: TestClient) -> None:
    response = client.get("/api/health")
    for header, value in BASE_HEADERS.items():
        assert response.headers.get(header) == value, header


def test_the_api_declares_that_it_loads_nothing(client: TestClient) -> None:
    """A JSON body has no scripts, no images and no frames, and says so."""
    response = client.get("/api/health")
    assert response.headers["content-security-policy"] == API_CSP


def test_a_typed_error_keeps_its_headers(client: TestClient) -> None:
    """The response most likely to be forgotten is the one produced by a handler.

    An error is turned into JSON by an exception handler that sits *inside* the middleware
    stack, so it only carries these headers if the middleware really is outside it. A 415
    served without `nosniff` would be the one response an attacker got to choose.
    """
    response = client.post(
        "/api/extract",
        files={"file": ("not-a-pdf.txt", b"plain text", "text/plain")},
    )
    assert response.status_code >= 400
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == API_CSP


def test_a_404_from_the_static_mount_keeps_its_headers(client: TestClient) -> None:
    response = client.get("/api/there-is-no-such-route")
    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"


def test_head_is_answered_wherever_get_is(client: TestClient) -> None:
    """A probe, an uptime monitor and a link preview all send HEAD, not GET.

    FastAPI does not derive HEAD from a GET route the way bare Starlette does, so both the
    health path and every page answered 405 — which is how the first Render deploy looked
    in its own logs.
    """
    for path in ("/api/health", "/", "/result"):
        response = client.head(path)
        assert response.status_code != 405, path


def test_hsts_only_when_the_browser_arrived_over_tls(client: TestClient) -> None:
    """Sent over plain HTTP it is both useless and a lie about the connection."""
    assert "strict-transport-security" not in client.get("http://testserver/api/health").headers
    assert "strict-transport-security" in client.get("https://testserver/api/health").headers


def test_hsts_believes_the_proxy_header_render_sets(client: TestClient) -> None:
    """Render terminates TLS, so the app itself only ever sees plain HTTP."""
    response = client.get("/api/health", headers={"x-forwarded-proto": "https"})
    assert "strict-transport-security" in response.headers


def test_api_responses_are_never_stored(client: TestClient) -> None:
    """Some of them say where a person was. None of them belongs in a shared cache."""
    assert client.get("/api/health").headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    ("path", "content_type", "expected"),
    [
        ("/_app/immutable/chunks/x.DEADBEEF.js", "text/javascript", IMMUTABLE),
        ("/", "text/html; charset=utf-8", REVALIDATE),
        ("/result", "text/html", REVALIDATE),
        ("/favicon.svg", "image/svg+xml", "public, max-age=3600"),
        ("/api/analyze", "application/json", "no-store"),
    ],
)
def test_cache_control_by_path(path: str, content_type: str, expected: str) -> None:
    """Hashed assets forever, HTML revalidated, everything else briefly.

    The pairing matters: caching HTML hard would pin a person to the build they first
    loaded, and revalidating hashed assets would spend a round trip proving that bytes
    which cannot change have not changed.
    """
    from app.api.security import cache_control_for

    assert cache_control_for(path, content_type) == expected
