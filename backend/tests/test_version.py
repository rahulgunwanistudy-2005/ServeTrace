"""One version, everywhere. Bible §19.

`APP_VERSION` is what `/api/health`, the OpenAPI document and every PDF print; the
frontend footer prints the newest release in `CHANGELOG.md`. This holds the two together,
so a release bumped in one place and not the other fails here rather than in front of
someone reading a PDF.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import APP_VERSION

CHANGELOG = Path(__file__).resolve().parents[2] / "CHANGELOG.md"
RELEASE = re.compile(r"^## \[(\d+\.\d+\.\d+)\] [\u2014\u2013-] (\d{4}-\d{2}-\d{2})$", re.MULTILINE)


def test_the_newest_changelog_release_is_the_app_version() -> None:
    releases = RELEASE.findall(CHANGELOG.read_text(encoding="utf-8"))
    assert releases, "CHANGELOG.md has no release headings"
    assert releases[0][0] == APP_VERSION
    assert {"1.0.0", "1.1.0"} <= {version for version, _ in releases}


def test_health_and_openapi_carry_the_app_version() -> None:
    from app.main import create_app

    with TestClient(create_app()) as client:
        assert APP_VERSION in client.get("/api/health").text
        assert client.get("/api/openapi.json").json()["info"]["version"] == APP_VERSION
