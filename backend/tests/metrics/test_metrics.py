"""Usage counts and the contact form, against a mocked PostgREST. Build prompt §8.4.

The suite is offline (`conftest.no_network`); every store here gets an `httpx.MockTransport`
that records what would have been sent, so the assertions are about the actual bodies.
"""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.domain.models import UsageEventKind
from app.logging import LOGGER_NAME, JsonFormatter
from app.metrics import events
from app.metrics.store import PostgrestStore, set_store

DEMO = Path(__file__).resolve().parents[3] / "fixtures" / "demo_cases" / "maria_contradicted"
BATCH = Path(__file__).resolve().parents[3] / "fixtures" / "advocate_batch" / "affidavits.json"

LEAD = {
    "name": "Pat Example",
    "email": "pat@example.org",
    "organization": "Example Legal Aid",
    "role": "legal_aid",
    "message": "We have forty affidavits from one agency and would like to talk.",
    "consent": True,
}


class FakePostgrest:
    """Records every request; answers with whatever `respond` returns."""

    def __init__(self, respond: Callable[[httpx.Request], httpx.Response] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.respond = respond or (lambda request: httpx.Response(204))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.respond(request)

    def bodies(self, path: str) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests if r.url.path.endswith(path)]


@pytest.fixture
def fake() -> Iterator[FakePostgrest]:
    server = FakePostgrest()
    set_store(
        PostgrestStore(
            url="https://store.example.invalid",
            key="service-key",
            transport=httpx.MockTransport(server),
        )
    )
    yield server


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def _demo_analyze() -> dict[str, Any]:
    affidavit = json.loads((DEMO / "affidavit.json").read_text(encoding="utf-8"))
    affidavit["user_confirmed"] = True
    fixes = json.loads((DEMO / "fixes.json").read_text(encoding="utf-8"))
    return {"affidavit": affidavit, "fixes": fixes}


# --- events -----------------------------------------------------------------------------


def test_a_completed_check_counts_its_tier_and_nothing_else(
    client: TestClient, fake: FakePostgrest
) -> None:
    response = client.post("/api/analyze", json=_demo_analyze())
    assert response.status_code == 200
    [body] = fake.bodies("/rpc/bump_usage")
    assert set(body) == {"p_day", "p_kind", "p_tier", "p_bucket"}
    assert body["p_kind"] == UsageEventKind.CHECK_COMPLETED
    assert body["p_tier"] == response.json()["overall"]
    assert body["p_bucket"] == ""
    assert len(body["p_day"]) == 10  # a day, never a time


def test_a_demo_is_counted_apart(client: TestClient, fake: FakePostgrest) -> None:
    client.post("/api/analyze", json=_demo_analyze(), headers={"x-servetrace-demo": "1"})
    [body] = fake.bodies("/rpc/bump_usage")
    assert body["p_bucket"] == "demo"


def test_a_downloaded_packet_is_counted(
    needs_pdf: None, client: TestClient, fake: FakePostgrest
) -> None:
    analysis = client.post("/api/analyze", json=_demo_analyze()).json()
    response = client.post("/api/documents/packet", json={"analysis": analysis, "fixes": []})
    assert response.status_code == 200
    kinds = [b["p_kind"] for b in fake.bodies("/rpc/bump_usage")]
    assert kinds == [UsageEventKind.CHECK_COMPLETED, UsageEventKind.PACKET_DOWNLOADED]


@pytest.mark.parametrize(("n", "bucket"), [(1, "1-10"), (10, "1-10"), (11, "11-50"), (60, "51+")])
def test_a_batch_is_counted_by_size_bucket(
    client: TestClient, fake: FakePostgrest, n: int, bucket: str
) -> None:
    affidavits = json.loads(BATCH.read_text(encoding="utf-8"))[:n]
    assert client.post("/api/advocate/batch", json=affidavits).status_code == 200
    [body] = fake.bodies("/rpc/bump_usage")
    assert (body["p_kind"], body["p_bucket"]) == (UsageEventKind.ADVOCATE_BATCH, bucket)


def test_a_store_outage_never_fails_the_request(client: TestClient) -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    set_store(PostgrestStore(url="https://x.invalid", key="k", transport=httpx.MockTransport(down)))
    assert client.post("/api/analyze", json=_demo_analyze()).status_code == 200


def test_a_store_error_status_never_fails_the_request(client: TestClient) -> None:
    server = FakePostgrest(lambda request: httpx.Response(500, json={"message": "no"}))
    set_store(
        PostgrestStore(url="https://x.invalid", key="k", transport=httpx.MockTransport(server))
    )
    assert client.post("/api/analyze", json=_demo_analyze()).status_code == 200
    assert len(server.requests) == 1


def test_nothing_is_sent_when_the_store_is_off(client: TestClient) -> None:
    """conftest puts a NullStore in place: the default for any deployment."""
    assert client.post("/api/analyze", json=_demo_analyze()).status_code == 200
    assert client.get("/api/stats").json() == {"enabled": False, "since": None, "totals": []}


def test_the_service_key_goes_in_headers_only(client: TestClient, fake: FakePostgrest) -> None:
    client.post("/api/analyze", json=_demo_analyze())
    [request] = fake.requests
    assert request.headers["apikey"] == "service-key"
    assert "service-key" not in str(request.url)


# --- stats ------------------------------------------------------------------------------


def test_stats_sum_real_and_demo_apart_and_cache(client: TestClient) -> None:
    def row(day: str, kind: str, tier: str, bucket: str, count: int) -> dict[str, Any]:
        return {"day": day, "kind": kind, "tier": tier, "bucket": bucket, "count": count}

    rows = [
        row("2026-11-10", "check_completed", "contradicted", "", 3),
        row("2026-11-11", "check_completed", "consistent", "", 2),
        row("2026-11-11", "check_completed", "contradicted", "demo", 9),
        row("2026-11-12", "advocate_batch", "", "51+", 1),
        row("2026-11-12", "something_new", "", "", 7),
    ]
    server = FakePostgrest(lambda request: httpx.Response(200, json=rows))
    set_store(
        PostgrestStore(url="https://x.invalid", key="k", transport=httpx.MockTransport(server))
    )
    body = client.get("/api/stats").json()
    totals = {t["kind"]: (t["real"], t["demo"]) for t in body["totals"]}
    assert body["enabled"] is True
    assert body["since"] == "2026-11-10"
    assert totals == {
        "check_completed": (5, 9),
        "packet_downloaded": (0, 0),
        "advocate_batch": (1, 0),
    }
    client.get("/api/stats")
    assert len(server.requests) == 1  # cached


def test_stats_say_unavailable_when_the_store_does_not_answer(client: TestClient) -> None:
    server = FakePostgrest(lambda request: httpx.Response(503))
    set_store(
        PostgrestStore(url="https://x.invalid", key="k", transport=httpx.MockTransport(server))
    )
    assert client.get("/api/stats").json()["enabled"] is False


# --- leads ------------------------------------------------------------------------------


def test_a_lead_is_stored_with_a_day_and_nothing_else(
    client: TestClient, fake: FakePostgrest
) -> None:
    response = client.post("/api/leads", json=LEAD)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    [row] = fake.bodies("/leads")
    assert set(row) == {"created_day", "name", "email", "organization", "role", "message"}
    assert row["email"] == LEAD["email"]
    assert len(row["created_day"]) == 10


def test_the_honeypot_is_thanked_and_dropped(client: TestClient, fake: FakePostgrest) -> None:
    response = client.post("/api/leads", json={**LEAD, "website": "http://spam.example"})
    assert response.status_code == 200
    assert fake.requests == []


@pytest.mark.parametrize(
    "change",
    [
        {"consent": False},
        {"email": "not an address"},
        {"name": ""},
        {"role": "judge"},
        {"message": "x" * 2001},
    ],
)
def test_bad_leads_are_refused(
    client: TestClient, fake: FakePostgrest, change: dict[str, Any]
) -> None:
    response = client.post("/api/leads", json={**LEAD, **change})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert fake.requests == []


def test_leads_are_limited_per_client(client: TestClient, fake: FakePostgrest) -> None:
    codes = [client.post("/api/leads", json=LEAD).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]
    assert len(fake.bodies("/leads")) == 5


def test_a_lead_with_the_store_off_says_so(client: TestClient) -> None:
    response = client.post("/api/leads", json=LEAD)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "contact_unavailable"


def test_a_lead_the_store_refuses_says_so(client: TestClient) -> None:
    server = FakePostgrest(lambda request: httpx.Response(500))
    set_store(
        PostgrestStore(url="https://x.invalid", key="k", transport=httpx.MockTransport(server))
    )
    response = client.post("/api/leads", json=LEAD)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "contact_unavailable"


# --- logs -------------------------------------------------------------------------------


def test_no_lead_content_names_or_coordinates_reach_the_logs(
    client: TestClient, fake: FakePostgrest
) -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(handler)
    try:
        client.post("/api/leads", json=LEAD)
        client.post("/api/leads", json={**LEAD, "email": "broken"})
        payload = _demo_analyze()
        client.post("/api/analyze", json=payload)
        affidavits = json.loads(BATCH.read_text(encoding="utf-8"))
        client.post("/api/advocate/batch", json=affidavits)
        # and once more with the store failing, so the warning path is in the capture too
        set_store(
            PostgrestStore(
                url="https://x.invalid",
                key="k",
                transport=httpx.MockTransport(lambda r: httpx.Response(500, json=LEAD)),
            )
        )
        client.post("/api/analyze", json=payload)
    finally:
        logger.removeHandler(handler)

    text = stream.getvalue()
    assert text, "nothing was logged, so this test proved nothing"
    forbidden = [
        LEAD["name"],
        LEAD["email"],
        LEAD["organization"],
        str(LEAD["message"])[:20],
        payload["affidavit"]["defendant_name"],
        payload["affidavit"]["served_address"],
        str(payload["affidavit"]["served_location"]["lat"]),
        affidavits[0]["defendant_name"],
        "service-key",
    ]
    for value in forbidden:
        assert value not in text, f"{value!r} reached the logs"
    assert "metrics bump failed" in text


def test_events_module_never_reads_the_body() -> None:
    """The counter takes a kind, a tier word and a bucket word. Nothing else is possible."""
    assert events.batch_bucket(0) == "1-10"
