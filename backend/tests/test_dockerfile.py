"""The image's frontend stage must copy every repository file the frontend bundles.

The frontend imports a few files from outside `frontend/` (the demo cases, the attorney
sample batch). The Docker build copies `frontend/` alone and then each of those by name,
so a new import that nobody adds to the Dockerfile builds fine on a laptop and ships an
empty glob: in 1.1 the sample batch on /advocate said "could not be loaded" in production
and worked everywhere else. This reads both sides and fails on the gap.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "frontend" / "src"
IMPORT = re.compile(r"""['"](?:\.\./)+(fixtures/[^'"*?]+?)(?:/\*[^'"]*)?(?:\?[a-z]+)?['"]""")


def bundled_fixture_paths() -> set[str]:
    found: set[str] = set()
    for path in SOURCE.rglob("*"):
        if path.suffix not in {".ts", ".svelte"} or path.name.endswith(".test.ts"):
            continue
        found.update(IMPORT.findall(path.read_text(encoding="utf-8")))
    return found


def copied_paths() -> list[str]:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    frontend_stage = dockerfile.split("FROM ", 2)[1]
    return re.findall(r"^COPY (fixtures/\S+) /build/", frontend_stage, flags=re.M)


def test_the_frontend_imports_fixtures_at_all() -> None:
    # Guards the regex: if it matched nothing, the test below would pass vacuously.
    assert "fixtures/advocate_batch/sample_extractions.json" in bundled_fixture_paths()
    assert any(p.startswith("fixtures/demo_cases") for p in bundled_fixture_paths())


def test_every_fixture_the_frontend_imports_is_copied_into_the_build_stage() -> None:
    copied = copied_paths()
    missing = sorted(
        path
        for path in bundled_fixture_paths()
        if not any(path == c or path.startswith(c.rstrip("/") + "/") for c in copied)
    )
    assert missing == [], f"add a COPY for these to the Dockerfile's frontend stage: {missing}"
