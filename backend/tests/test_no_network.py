"""The guard that keeps the suite offline is itself worth a test: a guard that quietly
stops working is worse than no guard, because the suite goes on passing."""

import httpx
import pytest


@pytest.mark.asyncio
async def test_an_unmocked_async_request_fails_loudly() -> None:
    async with httpx.AsyncClient() as client:
        with pytest.raises(AssertionError, match="tried to reach"):
            await client.get("https://geosearch.planninglabs.nyc/v2/search")


def test_an_unmocked_sync_request_fails_loudly() -> None:
    with httpx.Client() as client, pytest.raises(AssertionError, match="tried to reach"):
        client.get("https://example.invalid/")


@pytest.mark.asyncio
async def test_a_mock_transport_still_works() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
    async with httpx.AsyncClient(transport=transport) as client:
        assert (await client.get("https://example.invalid/")).json() == {"ok": True}
