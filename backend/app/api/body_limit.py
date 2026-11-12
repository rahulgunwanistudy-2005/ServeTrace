"""A ceiling on how many bytes any API request body may carry. Bible §16.

Each route already bounds what it *accepts* — 15 MB per upload, 5,000 fixes, 2,000
affidavits, a 3 MB map image — but those checks run after the body has been read and
parsed. Without a ceiling in front of them, one request with a 500 MB JSON array is held
in memory and parsed in full before any route gets to say no. This refuses it at the door:
on the declared `Content-Length` when there is one, and by counting as it streams when
there is not (chunked bodies), so neither way round is a way in.

The ceiling is the upload limit plus room for multipart framing and a map image, which
every legitimate request fits inside with a wide margin.
"""

from __future__ import annotations

import json
from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADROOM_BYTES: Final = 4 * 1024 * 1024


def body_ceiling(max_upload_bytes: int) -> int:
    return max_upload_bytes + HEADROOM_BYTES


def _refusal(limit: int) -> tuple[Message, Message]:
    body = json.dumps(
        {
            "error": {
                "code": "upload_too_large",
                "message": f"That request is larger than {limit // (1024 * 1024)} MB.",
            }
        }
    ).encode()
    start: Message = {
        "type": "http.response.start",
        "status": 413,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"connection", b"close"),
        ],
    }
    return start, {"type": "http.response.body", "body": body}


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, limit: int) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.limit:
            for message in _refusal(self.limit):
                await send(message)
            return

        # A chunked body has no length to check up front, so it is counted as it streams.
        # Raising mid-read would not work: FastAPI turns any error while reading a body
        # into a 400 of its own. So once the count passes the ceiling the stream is cut
        # short (the route sees an empty remainder and fails to parse), and whatever the
        # route answers is replaced, whole, by the 413.
        seen = 0
        too_large = False
        refusal = _refusal(self.limit)

        async def counted() -> Message:
            nonlocal seen, too_large
            if too_large:
                return {"type": "http.request", "body": b"", "more_body": False}
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.limit:
                    too_large = True
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def replacing(message: Message) -> None:
            if not too_large:
                await send(message)
            elif message["type"] == "http.response.start":
                await send(refusal[0])
            elif message["type"] == "http.response.body" and not message.get("more_body"):
                await send(refusal[1])

        await self.app(scope, counted, replacing)
