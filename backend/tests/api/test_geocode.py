"""`POST /api/geocode`. The address is the whole request."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_a_cached_address_resolves_without_a_network_call(client: TestClient) -> None:
    response = client.post(
        "/api/geocode", json={"address": "100 East Fordham Road, Bronx, NY 10468"}
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["source"] == "cache"
    assert result["location"]["lat"] == pytest.approx(40.861821)


def test_an_address_too_short_to_mean_anything_is_refused(client: TestClient) -> None:
    response = client.post("/api/geocode", json={"address": "x"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_the_route_is_a_post_so_the_address_is_never_in_a_url() -> None:
    """Bible §16: no personal data in query strings, and an address is personal data.
    A GET would put one there, so the published contract offers no GET."""
    paths = create_app().openapi()["paths"]
    assert set(paths["/api/geocode"]) == {"post"}
