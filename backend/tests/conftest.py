"""Suite-wide guards.

S2 acceptance gate: no test may touch the network. Mocking each call site is a promise;
blocking the transport is a guarantee, and it fails loudly at the call that broke the rule
rather than quietly passing on a machine that happens to be online.

S7 adds a second guard of the same kind. WeasyPrint needs pango, cairo and harfbuzz, and
a macOS machine usually has them installed by Homebrew under `/opt/homebrew/lib`, which is
not on dyld's default search path — so they are present and invisible. The temptation is
`pytest.importorskip`, and it is the wrong answer: a skip is a green suite that proved
nothing, and this is the suite that decides whether the document a person hands to a court
renders at all. So `needs_pdf` *fails*, and its message is the fix.
"""

import os
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from app.api.rate_limit import get_limiter
from app.documents.render import pdf_available

SKIP_PDF_ENV = "SERVETRACE_SKIP_PDF_TESTS"


@pytest.fixture(scope="session")
def needs_pdf() -> None:
    """Refuse to pretend the PDF gate ran when it did not."""
    if pdf_available():
        return
    if os.environ.get(SKIP_PDF_ENV):
        pytest.skip(
            f"{SKIP_PDF_ENV} is set: the PDF rendering gate did NOT run on this machine, "
            f"and neither document has been proven to render."
        )
    pytest.fail(
        "WeasyPrint could not load pango/cairo/harfbuzz, so no PDF could be rendered.\n"
        "  macOS:  brew install pango cairo gdk-pixbuf libffi\n"
        "          export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib\n"
        "  Debian: the Dockerfile's runtime stage installs them already.\n"
        f"To run the rest of the suite without this gate, set {SKIP_PDF_ENV}=1 — and know "
        "that the documents are then untested.",
        pytrace=False,
    )


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def refuse(self: Any, request: httpx.Request, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            f"a test tried to reach {request.url}. Use httpx.MockTransport, or a fixture."
        )

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)
    yield


@pytest.fixture(autouse=True)
def fresh_rate_limiter() -> Iterator[None]:
    """One test's requests must never spend another test's budget.

    The limiter is a process-wide singleton, which is the point of it in production and a
    source of order-dependent failures in a suite, so every test starts with empty buckets.
    """
    get_limiter.cache_clear()
    yield
    get_limiter.cache_clear()
