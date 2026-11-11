"""Which requests count, and how. Build prompt §8.2.

Events are emitted on the server, after the response, and only for three things: a check
that produced a verdict, an evidence packet that was downloaded, and an advocate batch
that was compared. There is no client-side analytics anywhere in the product.

A demo is counted apart. A request is a demo when the deployment is demo-only, or when
the browser says so with `X-ServeTrace-Demo: 1` — which it does for the bundled cases, the
sample affidavit and the sample batch. That header can be left off by someone who wants to
inflate the real count; the cost of that is a wrong number on a methodology page, and the
alternative (fingerprinting the payload to spot fixtures) would mean reading case data
for a counter, which this store exists not to do.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Final

from fastapi import BackgroundTasks, Request

from app.config import get_settings
from app.domain.models import UsageEventKind, UsageStats, UsageTotals
from app.metrics.store import StoreError, get_store

DEMO_HEADER: Final = "x-servetrace-demo"
DEMO_BUCKET: Final = "demo"
STATS_TTL_S: Final = 300.0


def is_demo(request: Request) -> bool:
    return get_settings().demo_only or request.headers.get(DEMO_HEADER) == "1"


def batch_bucket(n: int) -> str:
    """Batch size, coarsely: enough to know whether attorneys bring ten or a hundred."""
    if n <= 10:
        return "1-10"
    if n <= 50:
        return "11-50"
    return "51+"


def record(
    background: BackgroundTasks,
    request: Request,
    kind: UsageEventKind,
    *,
    tier: str = "",
    bucket: str = "",
) -> None:
    """Count one event, after the response has gone. Never raises, never waits."""
    store = get_store()
    if not store.available:
        return
    background.add_task(store.bump, kind, tier, DEMO_BUCKET if is_demo(request) else bucket)


@dataclass(slots=True)
class _Cached:
    at: float
    stats: UsageStats


_cache: _Cached | None = None


def clear_cache() -> None:
    global _cache
    _cache = None


async def usage_stats() -> UsageStats:
    """Totals by kind, real and demo apart, cached for five minutes in memory."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache.at < STATS_TTL_S:
        return _cache.stats

    store = get_store()
    off = UsageStats(enabled=False, since=None, totals=[])
    if not store.available:
        return off
    try:
        rows = await store.usage()
    except StoreError:
        return off

    real: dict[UsageEventKind, int] = dict.fromkeys(UsageEventKind, 0)
    demo: dict[UsageEventKind, int] = dict.fromkeys(UsageEventKind, 0)
    for row in rows:
        try:
            kind = UsageEventKind(row.kind)
        except ValueError:
            continue
        target = demo if row.bucket == DEMO_BUCKET else real
        target[kind] += row.count
    stats = UsageStats(
        enabled=True,
        since=min((row.day for row in rows), default=None),
        totals=[
            UsageTotals(kind=kind, real=real[kind], demo=demo[kind]) for kind in UsageEventKind
        ],
    )
    _cache = _Cached(at=now, stats=stats)
    return stats
