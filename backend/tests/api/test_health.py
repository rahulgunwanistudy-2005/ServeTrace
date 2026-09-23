from fastapi.testclient import TestClient

from app.config import ENGINE_VERSION
from app.engine.params import PARAMS_VERSION
from app.main import create_app


def test_health_reports_the_versions_a_verdict_is_stamped_with() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "params_version": PARAMS_VERSION,
        "llm_provider": "none",
    }


def test_every_response_carries_a_request_id() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/api/health").headers["x-request-id"]


def test_unknown_api_route_is_a_plain_404_not_a_stack_trace() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/api/nope").status_code == 404
