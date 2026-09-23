"""Liveness plus the version stamps a verdict can be traced back to."""

from fastapi import APIRouter
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
