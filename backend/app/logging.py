"""JSON request logging. Never logs names, addresses, coordinates or document text.

Bible §16: the log line carries a request id, the route, the status and the latency.
Nothing that identifies a person or a place is permitted through this module.
"""

import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

LOGGER_NAME = "servetrace"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "route", "method", "status", "latency_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def configure_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


async def request_log_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach a request id, time the handler, emit one PII-free line."""
    request_id = uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        configure_logging().exception(
            "unhandled",
            extra={
                "request_id": request_id,
                "route": request.url.path,
                "method": request.method,
                "status": 500,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        raise
    response.headers["x-request-id"] = request_id
    configure_logging().info(
        "request",
        extra={
            "request_id": request_id,
            "route": request.url.path,
            "method": request.method,
            "status": response.status_code,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        },
    )
    return response
