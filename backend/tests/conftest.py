"""Suite-wide guards.

S2 acceptance gate: no test may touch the network. Mocking each call site is a promise;
blocking the transport is a guarantee, and it fails loudly at the call that broke the rule
rather than quietly passing on a machine that happens to be online.
"""

from collections.abc import Iterator
from typing import Any

import httpx
import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def refuse(self: Any, request: httpx.Request, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            f"a test tried to reach {request.url}. Use httpx.MockTransport, or a fixture."
        )

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refuse)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)
    yield
