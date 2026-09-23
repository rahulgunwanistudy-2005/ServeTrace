"""Serving the prerendered bundle.

These build their own tiny bundle in a temp directory rather than relying on
`frontend/build`, so they pass whether or not `npm run build` has been run.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.static_site import _resolve, mount_frontend


@pytest.fixture
def bundle(tmp_path: Path) -> Path:
    root = tmp_path / "build"
    (root / "_app").mkdir(parents=True)
    (root / "index.html").write_text("<h1>home</h1>")
    (root / "200.html").write_text("<h1>spa fallback</h1>")
    (root / "methodology.html").write_text("<h1>methodology</h1>")
    (root / "nested").mkdir()
    (root / "nested" / "index.html").write_text("<h1>nested</h1>")
    (root / "favicon.svg").write_text("<svg/>")
    (root / "_app" / "version.json").write_text("{}")
    return root


def _client(bundle: Path) -> TestClient:
    app = FastAPI()

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    mount_frontend(app, bundle)
    return TestClient(app)


def test_root_serves_index(bundle: Path) -> None:
    assert "home" in _client(bundle).get("/").text


def test_extensionless_path_finds_the_prerendered_page(bundle: Path) -> None:
    """adapter-static writes `methodology.html`, but the link says `/methodology`."""
    assert "methodology" in _client(bundle).get("/methodology").text


def test_directory_index_is_served(bundle: Path) -> None:
    assert "nested" in _client(bundle).get("/nested").text


def test_static_asset_is_served(bundle: Path) -> None:
    response = _client(bundle).get("/favicon.svg")
    assert response.status_code == 200
    assert "svg" in response.headers["content-type"]


def test_hashed_assets_are_served(bundle: Path) -> None:
    assert _client(bundle).get("/_app/version.json").status_code == 200


def test_unknown_page_falls_back_to_the_client_router(bundle: Path) -> None:
    response = _client(bundle).get("/some/client/route")
    assert response.status_code == 200
    assert "spa fallback" in response.text


def test_api_routes_still_win_over_the_catch_all(bundle: Path) -> None:
    assert _client(bundle).get("/api/health").json() == {"status": "ok"}


def test_unknown_api_route_is_a_json_404_not_the_spa_fallback(bundle: Path) -> None:
    """An API client must never be handed an HTML page as if it were a response."""
    response = _client(bundle).get("/api/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_missing_bundle_leaves_the_api_alone(tmp_path: Path) -> None:
    app = FastAPI()

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    mount_frontend(app, tmp_path / "does-not-exist")
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
    assert client.get("/").status_code == 404


@pytest.mark.parametrize(
    "attack",
    [
        "../../etc/passwd",
        "../../../../../../etc/passwd",
        "/etc/passwd",
        "..%2f..%2fetc%2fpasswd",
        "nested/../../../etc/passwd",
    ],
)
def test_path_traversal_resolves_to_nothing(bundle: Path, attack: str) -> None:
    assert _resolve(bundle.resolve(), attack) is None


def test_symlink_out_of_the_bundle_is_refused(bundle: Path, tmp_path: Path) -> None:
    """Resolving before the containment check is what makes this hold."""
    secret = tmp_path / "secret.txt"
    secret.write_text("classified")
    (bundle / "evil.html").symlink_to(secret)
    assert _resolve(bundle.resolve(), "evil") is None
    assert _resolve(bundle.resolve(), "evil.html") is None


def test_traversal_over_http_never_leaks_a_file(bundle: Path) -> None:
    response = _client(bundle).get("/../../../etc/passwd")
    assert "root:" not in response.text
