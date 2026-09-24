"""Bible §16: the logs never carry a name, an address, a coordinate or document text.

`logging.py` is written so that this is true by construction — it builds the payload from
a fixed list of five keys and never touches the request body. That is a good design and it
is not a guarantee: the next person to add a `logger.info(f"...{affidavit.defendant_name}")`
in a route will not have read that docstring, and nothing in a type check, a lint or any
other test in this suite would object.

So this drives a real case through every route that takes real data, captures everything
the process writes to its log stream, and greps the result for the things that must not be
in it. It uses the committed demo case rather than invented strings, because the point is
to search for the values that actually flowed through the request — an assertion about a
string the code never saw would pass for the wrong reason.
"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.logging import LOGGER_NAME, JsonFormatter
from app.main import create_app

DEMO = Path(__file__).resolve().parents[3] / "fixtures" / "demo_cases" / "maria_contradicted"

ALLOWED_KEYS = {"level", "msg", "request_id", "route", "method", "status", "latency_ms", "exc"}
"""Bible §16 names exactly what a log line may carry. Anything else is a new field nobody
reviewed against this rule, so the test fails on the key rather than waiting for the day
its value happens to be someone's address."""


@pytest.fixture
def captured_logs() -> Any:
    """Attach a handler to the app's own logger and keep what it writes.

    The real formatter, not a test double: a redaction that only works under the test
    formatter redacts nothing in production.
    """
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(handler)
    try:
        yield stream
    finally:
        logger.removeHandler(handler)


def _case() -> dict[str, Any]:
    affidavit = json.loads((DEMO / "affidavit.json").read_text())
    affidavit["user_confirmed"] = True
    return {
        "affidavit": affidavit,
        "fixes": json.loads((DEMO / "fixes.json").read_text()),
        "household": json.loads((DEMO / "household.json").read_text()),
        "knowledge_date": "2025-09-02",
        "judgment_entry_date": "2025-08-14",
    }


def _forbidden_strings(case: dict[str, Any]) -> set[str]:
    """Every name, address and coordinate that went into the request."""
    affidavit = case["affidavit"]
    forbidden: set[str] = set()

    for key in (
        "defendant_name",
        "served_address",
        "server_name",
        "plaintiff",
        "recipient_name",
        "index_number",
        "mailing_address",
    ):
        if value := affidavit.get(key):
            forbidden.add(str(value))
            # A surname on its own is the realistic leak: an f-string that logs
            # `defendant.split()[-1]` would pass a whole-string search.
            forbidden.update(part for part in str(value).split() if len(part) > 3)

    for member in case["household"]:
        forbidden.add(str(member["label"]))

    # Coordinates, to six places and to three — a truncated coordinate is still a place.
    points = [affidavit.get("served_location")] + [f["loc"] for f in case["fixes"]]
    for point in points:
        if not point:
            continue
        for value in (point["lat"], point["lng"]):
            forbidden.add(f"{value:.6f}".rstrip("0"))
            forbidden.add(f"{value:.3f}")

    return {s for s in forbidden if len(s) > 3}


def test_a_full_analysis_leaves_nothing_identifying_in_the_logs(captured_logs: Any) -> None:
    case = _case()
    client = TestClient(create_app())

    analysis = client.post("/api/analyze", json=case)
    assert analysis.status_code == 200, analysis.text

    # The documents routes see the same data again, plus the rendered findings.
    client.post(
        "/api/documents/packet",
        json={"analysis": analysis.json(), "map_png_data_uri": None},
    )
    client.post("/api/documents/affidavit", json={"analysis": analysis.json()})

    # And a geocode, which is the one route whose *input* is nothing but an address.
    client.get("/api/geocode", params={"text": case["affidavit"]["served_address"]})

    written = captured_logs.getvalue()
    assert written, "nothing was logged at all, so this test proved nothing"

    leaked = sorted(s for s in _forbidden_strings(case) if s in written)
    assert not leaked, f"these reached the log stream: {leaked}\n---\n{written}"


def test_the_log_line_carries_only_the_fields_bible_16_permits(captured_logs: Any) -> None:
    client = TestClient(create_app())
    client.post("/api/analyze", json=_case())

    lines = [json.loads(line) for line in captured_logs.getvalue().splitlines() if line.strip()]
    assert lines, "nothing was logged"
    for line in lines:
        assert set(line) <= ALLOWED_KEYS, f"unreviewed log field: {set(line) - ALLOWED_KEYS}"


def test_an_unhandled_error_does_not_log_the_body_that_caused_it(
    captured_logs: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The traceback path is the one that wants to be helpful, which is the risk.

    `logger.exception` writes a formatted traceback, and a traceback quotes the locals of
    no frame at all by default — but it does name the route, and a future `extra=` on that
    call is exactly how a request body reaches a log file.
    """
    from app.engine import verdict

    def explode(*_: Any, **__: Any) -> Any:
        raise RuntimeError("engine failed")

    monkeypatch.setattr(verdict, "analyze", explode)
    monkeypatch.setattr("app.api.routes_analyze.analyze", explode)

    case = _case()
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post("/api/analyze", json=case)
    assert response.status_code == 500

    written = captured_logs.getvalue()
    assert "unhandled" in written
    leaked = sorted(s for s in _forbidden_strings(case) if s in written)
    assert not leaked, f"these reached the log stream on the error path: {leaked}"
