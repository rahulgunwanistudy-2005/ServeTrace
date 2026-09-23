"""Typed errors and the single error envelope: `{"error": {"code", "message"}}`."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ServeTraceError(Exception):
    """Base for every error the API deliberately returns.

    `message` is shown to the user, so it must stay plain-language and must never
    echo document text, an address or a coordinate.
    """

    code = "internal_error"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.headers = headers
        """Response headers this error needs to be actionable, e.g. `retry-after`."""


class BadInputError(ServeTraceError):
    code = "bad_input"
    status_code = status.HTTP_400_BAD_REQUEST


class UploadTooLargeError(ServeTraceError):
    code = "upload_too_large"
    status_code = status.HTTP_413_CONTENT_TOO_LARGE


class UnsupportedFileError(ServeTraceError):
    code = "unsupported_file"
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE


class AffidavitNotConfirmedError(ServeTraceError):
    code = "affidavit_not_confirmed"
    status_code = status.HTTP_409_CONFLICT


class ExtractionUnavailableError(ServeTraceError):
    """The extractor could not be reached or is not configured. Manual entry still works."""

    code = "extraction_unavailable"
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class ExtractionInvalidError(ServeTraceError):
    """The extractor answered, but not with anything matching the schema, twice."""

    code = "extraction_invalid"
    status_code = status.HTTP_502_BAD_GATEWAY


class DemoOnlyError(ServeTraceError):
    """`DEMO_ONLY=true`: this deployment serves the bundled demo cases and takes no uploads."""

    code = "demo_only"
    status_code = status.HTTP_403_FORBIDDEN


class UpstreamError(ServeTraceError):
    code = "upstream_error"
    status_code = status.HTTP_502_BAD_GATEWAY


class RateLimitedError(ServeTraceError):
    code = "rate_limited"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


def envelope(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServeTraceError)
    async def _handled(_: Request, exc: ServeTraceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(exc.code, exc.message),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # The raw pydantic error can quote submitted values, so it never reaches the client.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=envelope(
                "invalid_request", "Some of the details sent were not in the expected format."
            ),
        )
