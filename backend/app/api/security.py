"""Security and caching headers. Bible §16.

**Why the page's Content-Security-Policy is not here.** SvelteKit emits one inline
bootstrap script per page and hashes it into a `<meta>` CSP at build time
(`frontend/svelte.config.js`). A second policy in a header would not replace that one —
browsers enforce the *intersection* of every policy they are given — so a header written
by hand would have to stay in step with the bundler by hand, and the first time it drifted
it would either blank the app or silently stop enforcing anything.

What a `<meta>` tag cannot express is here instead: `frame-ancestors`, which browsers
ignore in meta, and HSTS, which is a transport instruction rather than a page policy. And
the API gets its own policy, because a JSON response has no business loading anything at
all and saying so costs one header.
"""

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; sandbox"
"""A JSON body or a PDF loads nothing, frames nothing and runs nothing.

`sandbox` matters for the documents: a PDF opened from this origin is inert, so a crafted
one cannot use the response to reach anything of the user's."""

BASE_HEADERS = {
    # A response typed application/json must never be sniffed into something executable.
    "x-content-type-options": "nosniff",
    # Bible §16 forbids leaking addresses. A referer would carry the path a person was on
    # to every outbound link on the page, including the legal-aid sites the result screen
    # sends them to — so no referer leaves this app at all.
    "referrer-policy": "no-referrer",
    # `frame-ancestors 'none'` in the page's own CSP says the same thing to a modern
    # browser. This is the older instruction, kept because clickjacking a court-document
    # download is cheap to prevent and expensive to discover.
    "x-frame-options": "DENY",
    "cross-origin-opener-policy": "same-origin",
    # The app reads a file the user chooses. It never asks the browser for the device's
    # own location, camera or microphone, and a page that cannot ask cannot be tricked
    # into asking.
    "permissions-policy": "geolocation=(), camera=(), microphone=(), payment=(), usb=()",
}

HSTS = "max-age=31536000; includeSubDomains"

IMMUTABLE = "public, max-age=31536000, immutable"
"""Vite writes a content hash into every asset filename, so a given URL's bytes can never
change. A year is the longest a browser will honour anyway."""

REVALIDATE = "no-cache"
"""HTML and anything unhashed. `no-cache` is not "do not store": the browser keeps the
copy and asks whether it is still good, which is what makes a deploy visible immediately
while still costing a 304 rather than a download."""

STATIC_MAX_AGE = "public, max-age=3600"

HASHED_PREFIXES = ("/_app/immutable/",)


def _is_https(request: Request) -> bool:
    """True when the browser reached us over TLS, directly or through Render's proxy."""
    if request.url.scheme == "https":
        return True
    return request.headers.get("x-forwarded-proto", "").split(",")[0].strip() == "https"


def cache_control_for(path: str, content_type: str) -> str:
    if path.startswith(HASHED_PREFIXES):
        return IMMUTABLE
    if content_type.startswith("text/html"):
        return REVALIDATE
    if path.startswith("/api/"):
        # Every API response is a function of the request body and nothing else, and some
        # of them describe where a person was. None of it belongs in a shared cache.
        return "no-store"
    return STATIC_MAX_AGE


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)

    for header, value in BASE_HEADERS.items():
        response.headers.setdefault(header, value)

    if _is_https(request):
        response.headers.setdefault("strict-transport-security", HSTS)

    path = request.url.path
    if path.startswith("/api/"):
        response.headers.setdefault("content-security-policy", API_CSP)

    response.headers.setdefault(
        "cache-control",
        cache_control_for(path, response.headers.get("content-type", "")),
    )
    return response
