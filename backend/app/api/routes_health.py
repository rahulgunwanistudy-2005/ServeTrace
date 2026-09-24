"""Liveness plus the version stamps a verdict can be traced back to."""

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.config import ENGINE_VERSION, get_settings
from app.engine.params import PARAMS_VERSION

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str
    engine_version: str
    params_version: str
    llm_provider: str


@router.get("/health", response_model=Health)
async def health() -> Health:
    return Health(
        status="ok",
        engine_version=ENGINE_VERSION,
        params_version=PARAMS_VERSION,
        llm_provider=get_settings().llm_provider,
    )


@router.head("/health", include_in_schema=False)
async def health_head() -> Response:
    """A platform probe or an uptime monitor sends HEAD, and FastAPI does not derive it
    from the GET route the way bare Starlette does — so without this the health path
    answers 405, which is how the first Render deploy looked in its own logs.

    A separate handler rather than `methods=["GET", "HEAD"]`: one decorator for both would
    emit two OpenAPI operations with the same id, and that schema is what generates the
    frontend's types. A HEAD response has no body to build anyway.
    """
    return Response(status_code=200)
