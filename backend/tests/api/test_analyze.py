"""`POST /api/analyze`: the engine behind one stateless request."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.domain.models import AnalyzeRequest
from app.main import create_app
from tests.engine.conftest import CLAIM_AT, DOOR, affidavit, away, fix, member, visit

AT_WORK = visit(CLAIM_AT - timedelta(hours=4), 480, away(14.0))
AT_HOME = visit(CLAIM_AT - timedelta(hours=1), 180, DOOR)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def body(fixes=None, household=None, confirmed: bool = True, **overrides: Any) -> dict[str, Any]:
    request = AnalyzeRequest(
        affidavit=affidavit(confirmed=confirmed, **overrides),
        fixes=fixes if fixes is not None else [AT_WORK],
        household=household or [],
    )
    return request.model_dump(mode="json")


# --- The happy path -------------------------------------------------------------------------


def test_a_confirmed_affidavit_and_a_days_fixes_produce_a_verdict(client: TestClient) -> None:
    response = client.post("/api/analyze", json=body())

    assert response.status_code == 200
    analysis = response.json()
    assert analysis["overall"] == "contradicted"
    assert analysis["verdicts"][0]["claim_ref"] == "served_at"
    assert analysis["findings"][0]["code"] == "F-VISIT"


def test_a_consistent_result_comes_back_as_readily(client: TestClient) -> None:
    """Bible §6. A route that only answered when it found something would be a route that
    could not be trusted when it did."""
    assert client.post("/api/analyze", json=body(fixes=[AT_HOME])).json()["overall"] == "consistent"


def test_the_response_carries_the_versions_a_verdict_can_be_traced_to(client: TestClient) -> None:
    analysis = client.post("/api/analyze", json=body()).json()
    health = client.get("/api/health").json()
    assert analysis["params_version"] == health["params_version"]
    assert analysis["engine_version"] == health["engine_version"]


def test_the_household_reaches_the_description_check(client: TestClient) -> None:
    analysis = client.post(
        "/api/analyze",
        json=body(
            fixes=[AT_HOME],
            household=[member("Me", sex="female", age=34, is_defendant=True)],
            recipient_description={"sex": "male", "age_min": 70, "age_max": 80},
        ),
    ).json()
    assert "F-DESC" in {f["code"] for f in analysis["findings"]}


def test_the_deadline_dates_reach_the_clock(client: TestClient) -> None:
    payload = body(fixes=[AT_HOME])
    payload["knowledge_date"] = "2026-03-14"
    payload["judgment_entry_date"] = "2025-01-15"
    deadlines = client.post("/api/analyze", json=payload).json()["deadlines"]
    assert deadlines["cplr_317_deadline"] == "2027-03-14"


# --- Guards ------------------------------------------------------------------------------------


def test_an_unconfirmed_affidavit_is_refused(client: TestClient) -> None:
    """Bible §10: every number in the result is built from fields the user confirmed, so
    analysing unconfirmed ones would put the extractor's guesses in a court document."""
    response = client.post("/api/analyze", json=body(confirmed=False))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "affidavit_not_confirmed"


def test_the_refusal_says_what_to_do_about_it(client: TestClient) -> None:
    message = client.post("/api/analyze", json=body(confirmed=False)).json()["error"]["message"]
    assert "confirm" in message.lower()


def test_too_many_fixes_is_refused_with_the_number(client: TestClient) -> None:
    """Bible §16 caps this at 5,000, and §13 means the browser should never send more."""
    limit = get_settings().max_fixes
    many = [fix(CLAIM_AT + timedelta(seconds=i), away(1.0)) for i in range(limit + 1)]
    response = client.post("/api/analyze", json=body(fixes=many))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_input"
    assert f"{limit:,}" in response.json()["error"]["message"]


def test_exactly_the_cap_is_allowed(client: TestClient) -> None:
    limit = get_settings().max_fixes
    many = [fix(CLAIM_AT + timedelta(seconds=i), away(1.0)) for i in range(limit)]
    assert client.post("/api/analyze", json=body(fixes=many)).status_code == 200


def test_an_implausible_household_is_refused(client: TestClient) -> None:
    roster = [member(f"Person {i}") for i in range(get_settings().max_household + 1)]
    response = client.post("/api/analyze", json=body(household=roster))
    assert response.status_code == 400


def test_a_malformed_request_never_echoes_what_was_sent(client: TestClient) -> None:
    """Bible §16: an error message may not carry an address, a name or a coordinate, and
    pydantic's own message quotes the input."""
    response = client.post("/api/analyze", json={"affidavit": {"defendant_name": "A Real Name"}})
    assert response.status_code == 422
    assert "A Real Name" not in response.text


def test_a_naive_datetime_is_refused_rather_than_guessed(client: TestClient) -> None:
    """Bible §11.1.1 normalises from a stated offset. A time with no offset is not a time."""
    payload = body()
    payload["affidavit"]["served_at"] = "2025-06-12T19:42:00"
    assert client.post("/api/analyze", json=payload).status_code == 422


# --- Shape ---------------------------------------------------------------------------------------


def test_the_route_is_a_post_so_no_location_data_is_ever_in_a_url() -> None:
    assert set(create_app().openapi()["paths"]["/api/analyze"]) == {"post"}


def test_the_route_is_rate_limited_like_the_others() -> None:
    """Analysis costs no upstream quota, but it does cost CPU, and one unauthenticated
    client should not be able to spend all of it."""
    settings = get_settings()
    with TestClient(create_app()) as client:
        payload = body(fixes=[AT_HOME])
        statuses = [
            client.post("/api/analyze", json=payload).status_code
            for _ in range(settings.rate_limit_burst + 1)
        ]
    assert statuses[-1] == 429


def test_nothing_is_stored_between_requests(client: TestClient) -> None:
    """Bible §16. There is no id to come back for, which is the point."""
    first = client.post("/api/analyze", json=body()).json()
    second = client.post("/api/analyze", json=body()).json()
    assert first["verdicts"] == second["verdicts"]
    assert "id" not in first
