"""Shared paths for the extraction tests. No test in this package touches the network."""

import json
from pathlib import Path
from typing import Any

import pytest

from app.extraction.pdf_text import extract_text

DEMO_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "demo_cases"
RECORDED_DIR = Path(__file__).resolve().parent / "recorded"


@pytest.fixture(scope="session")
def demo_pdf() -> bytes:
    return (DEMO_DIR / "maria_contradicted" / "affidavit.pdf").read_bytes()


@pytest.fixture(scope="session")
def demo_scan() -> bytes:
    return (DEMO_DIR / "maria_contradicted" / "affidavit_scanned.pdf").read_bytes()


@pytest.fixture(scope="session")
def demo_text(demo_pdf: bytes) -> str:
    return extract_text(demo_pdf).text


@pytest.fixture(scope="session")
def recorded_response() -> dict[str, Any]:
    payload = json.loads((RECORDED_DIR / "gemini_affidavit_response.json").read_text("utf-8"))
    assert isinstance(payload, dict)
    return payload
