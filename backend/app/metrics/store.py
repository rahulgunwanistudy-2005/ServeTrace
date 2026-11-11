"""The one small store: day-level usage counts and voluntary contact leads. Build prompt §8.

Supabase Postgres, reached through its REST layer (PostgREST) over `httpx` — no SDK, no
database driver. The schema is `infra/supabase/001_v1_1.sql`; both tables have row-level
security on and no policies, so only the service-role key used here can touch them.

What this store can hold is narrow by construction:

- **Counts**, one row per (day, kind, tier, bucket). A day, never a time. No IP, no user
  agent, no coordinates, no field from any affidavit. A tier is one of four words.
- **Leads**: what a person typed into the contact form and agreed to have kept, with the
  day it arrived. Never a case.

Two rules that the rest of the app relies on:

- **A metrics failure never fails a user request.** `bump` swallows every error and gives
  up after two seconds; it is called after the response has been sent.
- **Off is the default.** Without `METRICS_ENABLED=true` and both Supabase settings, the
  store is a `NullStore` that records nothing and reports itself unavailable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import lru_cache
from typing import Any, Final, Protocol
from zoneinfo import ZoneInfo

import httpx

from app.config import get_settings
from app.domain.models import LeadIn, UsageEventKind
from app.logging import LOGGER_NAME

TIMEOUT_S: Final = 2.0
NY: Final = ZoneInfo("America/New_York")

log = logging.getLogger(LOGGER_NAME)


def today() -> date:
    """The counting day, in New York, which is the only place this product serves."""
    return datetime.now(NY).date()


@dataclass(frozen=True, slots=True)
class UsageRow:
    day: date
    kind: str
    tier: str
    bucket: str
    count: int


class Store(Protocol):
    available: bool

    async def bump(self, kind: UsageEventKind, tier: str = "", bucket: str = "") -> None: ...

    async def insert_lead(self, lead: LeadIn) -> None: ...

    async def usage(self) -> list[UsageRow]: ...


class StoreError(Exception):
    """The store refused or did not answer. Carries no request or response content."""


@dataclass(slots=True)
class NullStore:
    """Metrics switched off: nothing is sent anywhere, and the form says so."""

    available: bool = False

    async def bump(self, kind: UsageEventKind, tier: str = "", bucket: str = "") -> None:
        return None

    async def insert_lead(self, lead: LeadIn) -> None:
        raise StoreError("store not configured")

    async def usage(self) -> list[UsageRow]:
        return []


@dataclass(slots=True)
class PostgrestStore:
    url: str
    key: str
    transport: httpx.AsyncBaseTransport | None = None
    available: bool = True
    _headers: dict[str, str] = field(init=False)

    def __post_init__(self) -> None:
        self.url = self.url.rstrip("/")
        self._headers = {
            "apikey": self.key,
            "authorization": f"Bearer {self.key}",
            "content-type": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=f"{self.url}/rest/v1",
            headers=self._headers,
            timeout=TIMEOUT_S,
            transport=self.transport,
        )

    async def _post(self, path: str, body: dict[str, Any], prefer: str | None = None) -> None:
        headers = {"prefer": prefer} if prefer else None
        try:
            async with self._client() as client:
                response = await client.post(path, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise StoreError(type(exc).__name__) from None
        if response.status_code >= 300:
            raise StoreError(f"status {response.status_code}")

    async def bump(self, kind: UsageEventKind, tier: str = "", bucket: str = "") -> None:
        """Fire and forget. Whatever happens, the caller carries on."""
        try:
            await self._post(
                "/rpc/bump_usage",
                {
                    "p_day": today().isoformat(),
                    "p_kind": str(kind),
                    "p_tier": tier,
                    "p_bucket": bucket,
                },
            )
        except Exception as exc:
            # The exception's class name only: its message could quote the request.
            log.warning("metrics bump failed: %s", type(exc).__name__)

    async def insert_lead(self, lead: LeadIn) -> None:
        """Unlike a count, a lead is the person's own action: a failure is reported."""
        await self._post(
            "/leads",
            {
                "created_day": today().isoformat(),
                "name": lead.name,
                "email": lead.email,
                "organization": lead.organization,
                "role": lead.role,
                "message": lead.message,
            },
            prefer="return=minimal",
        )

    async def usage(self) -> list[UsageRow]:
        try:
            async with self._client() as client:
                response = await client.get(
                    "/usage_daily", params={"select": "day,kind,tier,bucket,count"}
                )
        except httpx.HTTPError as exc:
            raise StoreError(type(exc).__name__) from None
        if response.status_code >= 300:
            raise StoreError(f"status {response.status_code}")
        rows = response.json()
        if not isinstance(rows, list):
            raise StoreError("unexpected shape")
        try:
            return self._rows(rows)
        except (TypeError, ValueError):
            raise StoreError("unexpected shape") from None

    @staticmethod
    def _rows(rows: list[Any]) -> list[UsageRow]:
        return [
            UsageRow(
                day=date.fromisoformat(str(row.get("day"))),
                kind=str(row.get("kind", "")),
                tier=str(row.get("tier", "")),
                bucket=str(row.get("bucket", "")),
                count=int(row.get("count", 0)),
            )
            for row in rows
            if isinstance(row, dict)
        ]


_override: Store | None = None


def set_store(store: Store | None) -> None:
    """For tests: put a store with a mock transport in place, or None to go back."""
    global _override
    _override = store
    _configured.cache_clear()


@lru_cache(maxsize=1)
def _configured() -> Store:
    settings = get_settings()
    if not settings.store_configured:
        return NullStore()
    return PostgrestStore(url=settings.supabase_url, key=settings.supabase_service_key)


def get_store() -> Store:
    return _override if _override is not None else _configured()
