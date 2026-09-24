"""FastAPI application factory. Thin: wiring only, no logic."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_advocate,
    routes_analyze,
    routes_documents,
    routes_extract,
    routes_geocode,
    routes_health,
)
from app.api.errors import install_error_handlers
from app.api.security import security_headers_middleware
from app.api.static_site import mount_frontend
from app.config import get_settings
from app.logging import configure_logging, request_log_middleware

FRONTEND_BUILD = Path(__file__).resolve().parents[2] / "frontend" / "build"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title="ServeTrace",
        version="0.1.0",
        description="Check an affidavit of service against your own location history.",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
    )

    # Starlette inserts each middleware at the front of the stack, so the one registered
    # *last* is the outermost. The security headers go last deliberately: every response
    # leaves through them, including the ones CORS answers by itself and the ones an error
    # handler produces, and a response that skipped them is exactly the one nobody notices.
    # `tests/api/test_security_headers.py` asserts that rather than trusting this comment.
    app.middleware("http")(request_log_middleware)

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST"],
            allow_headers=["content-type"],
        )

    app.middleware("http")(security_headers_middleware)

    install_error_handlers(app)
    app.include_router(routes_health.router, prefix="/api")
    app.include_router(routes_extract.router, prefix="/api")
    app.include_router(routes_geocode.router, prefix="/api")
    app.include_router(routes_analyze.router, prefix="/api")
    app.include_router(routes_advocate.router, prefix="/api")
    app.include_router(routes_documents.router, prefix="/api")

    # Mounted last so that /api/* always wins over a same-named static path.
    mount_frontend(app, FRONTEND_BUILD)

    return app


app = create_app()
