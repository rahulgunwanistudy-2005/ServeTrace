from fastapi.testclient import TestClient

from app.config import APP_VERSION, ENGINE_VERSION
from app.engine.params import PARAMS_VERSION
from app.main import create_app


def test_health_reports_the_versions_a_verdict_is_stamped_with() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_version": APP_VERSION,
        "engine_version": ENGINE_VERSION,
        "params_version": PARAMS_VERSION,
        "llm_provider": "none",
        "llm_real_data_allowed": False,
    }


def test_the_app_version_is_semver_and_matches_the_openapi_document() -> None:
    import re

    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)
    with TestClient(create_app()) as client:
        assert client.get("/api/openapi.json").json()["info"]["version"] == APP_VERSION


def test_every_response_carries_a_request_id() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/api/health").headers["x-request-id"]


def test_unknown_api_route_is_a_plain_404_not_a_stack_trace() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/api/nope").status_code == 404
