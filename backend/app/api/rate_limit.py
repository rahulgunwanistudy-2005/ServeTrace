"""In-memory token buckets, one per client. Bible §16.

The two routes this guards are the only ones that cost money or an upstream quota per
call, so the point is not to stop a determined attacker — a stateless server with no
database cannot — but to stop one client from spending the deployment's budget by
accident or by loop.

Two decisions worth stating:

- **Monotonic clock.** Wall-clock time can step backwards (NTP, a suspended container),
  which with a naive implementation either hands out free requests or locks a client out
  until the clock catches up.
- **Bounded map, evicted by how close a client is to its limit.** An unbounded dict keyed
  by client address is a memory leak the moment anyone sprays source addresses at it. The
  obvious bound — drop the least recently used — is wrong here: a client that has just
  been refused stops making requests, so it is *precisely* the least recently used, and a
  hundred junk addresses would clear its bucket. Forgetting a client with a full bucket
  costs nothing, because recreating it gives the same full bucket back. So when the map is
  full, what is dropped is whoever has the most tokens left, and the client at zero tokens
  is the last one forgotten.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from fastapi import Request

from app.api.errors import RateLimitedError
from app.config import get_settings

MAX_BUCKETS: Final = 10_000
"""Roughly a megabyte of buckets. Past this, the least-limited clients are forgotten."""

EVICT_FRACTION: Final = 0.1
"""Evict in batches, so the scan that ranks buckets is paid once per thousand requests
rather than once per request while the map is full."""


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated: float


class TokenBucketLimiter:
    """`capacity` requests may be made at once; they refill at `refill_per_s`."""

    def __init__(
        self,
        capacity: float,
        refill_per_s: float,
        max_buckets: int = MAX_BUCKETS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.capacity = capacity
        self.refill_per_s = refill_per_s
        self.max_buckets = max_buckets
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}

    @property
    def enabled(self) -> bool:
        return self.capacity > 0 and self.refill_per_s > 0

    def retry_after(self, key: str) -> float | None:
        """Spend one token for `key`. Returns None when allowed, else the seconds to wait."""
        if not self.enabled:
            return None

        now = self._clock()
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=self.capacity, updated=now)
            self._buckets[key] = bucket
            self._evict(now)
        else:
            bucket.tokens = self._tokens_at(bucket, now)
            bucket.updated = now

        if bucket.tokens < 1.0:
            return (1.0 - bucket.tokens) / self.refill_per_s

        bucket.tokens -= 1.0
        return None

    def _tokens_at(self, bucket: _Bucket, now: float) -> float:
        elapsed = max(0.0, now - bucket.updated)
        return min(self.capacity, bucket.tokens + elapsed * self.refill_per_s)

    def _evict(self, now: float) -> None:
        if len(self._buckets) <= self.max_buckets:
            return
        over = len(self._buckets) - self.max_buckets
        batch = max(over, int(self.max_buckets * EVICT_FRACTION), 1)
        ranked = sorted(self._buckets.items(), key=lambda item: -self._tokens_at(item[1], now))
        for key, _ in ranked[:batch]:
            del self._buckets[key]

    def reset(self) -> None:
        self._buckets.clear()


def client_key(request: Request, trusted_hops: int) -> str:
    """Identify the client, without letting the client choose its own identity.

    `X-Forwarded-For` is attacker-controlled up to the point where a proxy you trust
    appended to it, so the only honest reading is by position from the right: with
    `trusted_hops = 1` the entry the single trusted proxy added is the client. The
    default is 0 — trust nothing, use the peer address — because a deployment sitting
    directly on the internet that trusted this header would let one client wear as many
    identities as it liked. Render terminates TLS in front of the app, so it needs 1.
    """
    if trusted_hops > 0:
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= trusted_hops:
            return parts[-trusted_hops]
    client = request.client
    return client.host if client else "unknown"


@lru_cache(maxsize=1)
def get_limiter() -> TokenBucketLimiter:
    settings = get_settings()
    return TokenBucketLimiter(
        capacity=float(settings.rate_limit_burst),
        refill_per_s=settings.rate_limit_per_minute / 60.0,
    )


async def enforce_rate_limit(request: Request) -> None:
    """Dependency for the routes that cost something per call.

    One budget per client covers both routes together. Splitting it per route would let a
    client spend twice as much for the same reason, and the reason is the cost, not the
    path.
    """
    limiter = get_limiter()
    wait = limiter.retry_after(client_key(request, get_settings().rate_limit_trusted_hops))
    if wait is None:
        return
    raise RateLimitedError(
        "That is more requests than we allow in a short time. Please wait a few seconds "
        "and try again.",
        headers={"retry-after": str(max(1, round(wait)))},
    )
