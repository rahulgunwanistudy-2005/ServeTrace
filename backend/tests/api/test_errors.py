"""The error envelope is a contract: the frontend switches on `error.code`."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.api.errors import (
    BadInputError,
    ServeTraceError,
    UploadTooLargeError,
    install_error_handlers,
)


class _Body(BaseModel):
    n: int


def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise BadInputError("We could not read that file.")

    @app.get("/toobig")
    async def toobig() -> None:
        raise UploadTooLargeError("That file is larger than 15 MB.")

    @app.post("/typed")
    async def typed(body: _Body) -> dict[str, int]:
        return {"n": body.n}

    return app


def test_typed_error_becomes_the_envelope() -> None:
    response = TestClient(_app(), raise_server_exceptions=False).get("/boom")
    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "bad_input", "message": "We could not read that file."}
    }


def test_status_code_travels_with_the_error_class() -> None:
    response = TestClient(_app(), raise_server_exceptions=False).get("/toobig")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "upload_too_large"


def test_validation_errors_do_not_echo_the_submitted_value() -> None:
    """Bible §16: a rejected payload may hold an address, so it must never be reflected."""
    response = TestClient(_app(), raise_server_exceptions=False).post(
        "/typed", json={"n": "221B Baker Street"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "Baker" not in response.text


def test_error_hierarchy_keeps_a_usable_message() -> None:
    assert ServeTraceError("x").message == "x"
    assert isinstance(BadInputError("x"), ServeTraceError)
