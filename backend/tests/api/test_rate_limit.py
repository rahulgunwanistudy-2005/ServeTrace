"""The token bucket from bible §16, and the two routes it guards."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.rate_limit import TokenBucketLimiter, client_key, get_limiter
from app.config import get_settings
from app.main import create_app


class FakeClock:
    """A clock the test moves on purpose, so refill is asserted and not slept through."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def limiter(
    capacity: float = 3, refill_per_s: float = 0.5, **kwargs: object
) -> tuple[TokenBucketLimiter, FakeClock]:
    clock = FakeClock()
    return (
        TokenBucketLimiter(capacity=capacity, refill_per_s=refill_per_s, clock=clock, **kwargs),  # type: ignore[arg-type]
        clock,
    )


def test_a_client_may_spend_its_burst_at_once() -> None:
    bucket, _ = limiter(capacity=3)
    assert [bucket.retry_after("a") for _ in range(3)] == [None, None, None]


def test_the_request_after_the_burst_is_refused_with_a_wait_that_makes_sense() -> None:
    bucket, _ = limiter(capacity=3, refill_per_s=0.5)
    for _ in range(3):
        bucket.retry_after("a")

    wait = bucket.retry_after("a")

    assert wait is not None
    assert wait == pytest.approx(2.0)  # half a token per second


def test_tokens_come_back_as_time_passes() -> None:
    bucket, clock = limiter(capacity=3, refill_per_s=0.5)
    for _ in range(3):
        bucket.retry_after("a")
    assert bucket.retry_after("a") is not None

    clock.advance(2.0)

    assert bucket.retry_after("a") is None


def test_refill_stops_at_the_burst_size() -> None:
    """An idle week must not buy a week's worth of requests in one second."""
    bucket, clock = limiter(capacity=3, refill_per_s=0.5)
    bucket.retry_after("a")
    clock.advance(86_400)

    assert [bucket.retry_after("a") for _ in range(4)] == [None, None, None, pytest.approx(2.0)]


def test_one_client_running_out_does_not_affect_another() -> None:
    bucket, _ = limiter(capacity=2)
    for _ in range(2):
        bucket.retry_after("a")

    assert bucket.retry_after("a") is not None
    assert bucket.retry_after("b") is None


def test_a_limit_of_zero_turns_the_whole_thing_off() -> None:
    bucket, _ = limiter(capacity=0, refill_per_s=0)
    assert bucket.enabled is False
    assert all(bucket.retry_after("a") is None for _ in range(50))


def test_the_bucket_map_stays_bounded() -> None:
    bucket, _ = limiter(capacity=1, max_buckets=10)
    for i in range(500):
        bucket.retry_after(f"client-{i}")

    assert len(bucket._buckets) <= 10


def test_a_spray_of_fresh_addresses_cannot_reset_a_limit() -> None:
    """The client at zero tokens is the last one forgotten.

    Evicting the least recently used would do the opposite: a refused client stops making
    requests, so it becomes the oldest entry, and a hundred junk addresses would hand it a
    fresh bucket. That is worse than having no limiter at all, because it looks like one.
    """
    bucket, _ = limiter(capacity=4, max_buckets=5)
    for _ in range(4):
        bucket.retry_after("heavy")
    assert bucket.retry_after("heavy") is not None

    for i in range(500):
        bucket.retry_after(f"noise-{i}")

    assert bucket.retry_after("heavy") is not None
    assert len(bucket._buckets) <= 5


class FakeRequest:
    def __init__(self, peer: str | None, forwarded: str | None = None) -> None:
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}
        self.client = type("C", (), {"host": peer})() if peer else None


def test_a_forwarded_header_is_ignored_when_no_proxy_is_trusted() -> None:
    """Otherwise a client picks its own identity and the limit means nothing."""
    request = FakeRequest(peer="203.0.113.7", forwarded="1.2.3.4")
    assert client_key(request, trusted_hops=0) == "203.0.113.7"  # type: ignore[arg-type]


def test_one_trusted_proxy_means_the_entry_that_proxy_added() -> None:
    request = FakeRequest(peer="10.0.0.1", forwarded="9.9.9.9, 203.0.113.7")
    assert client_key(request, trusted_hops=1) == "203.0.113.7"  # type: ignore[arg-type]


def test_a_header_shorter_than_the_trusted_hops_falls_back_to_the_peer() -> None:
    request = FakeRequest(peer="10.0.0.1", forwarded="203.0.113.7")
    assert client_key(request, trusted_hops=2) == "10.0.0.1"  # type: ignore[arg-type]


def test_a_request_with_no_peer_at_all_still_gets_a_key() -> None:
    assert client_key(FakeRequest(peer=None), trusted_hops=0) == "unknown"  # type: ignore[arg-type]


@pytest.fixture
def tight_limit(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("RATE_LIMIT_BURST", "2")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "6")
    get_settings.cache_clear()
    get_limiter.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()
    get_limiter.cache_clear()


def test_the_geocode_route_refuses_a_flood_in_the_usual_envelope(tight_limit: TestClient) -> None:
    body = {"address": "100 East Fordham Road, Bronx, NY 10468"}
    assert tight_limit.post("/api/geocode", json=body).status_code == 200
    assert tight_limit.post("/api/geocode", json=body).status_code == 200

    response = tight_limit.post("/api/geocode", json=body)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert response.headers["retry-after"] == "10"  # six a minute, so ten seconds a token


def test_the_message_says_what_to_do_and_names_nothing(tight_limit: TestClient) -> None:
    body = {"address": "100 East Fordham Road, Bronx, NY 10468"}
    for _ in range(3):
        response = tight_limit.post("/api/geocode", json=body)

    message = response.json()["error"]["message"]
    assert "wait" in message.lower()
    assert "Fordham" not in message


def test_the_budget_is_shared_across_the_routes_that_cost_money(tight_limit: TestClient) -> None:
    """Both routes spend one upstream call, so they spend one budget."""
    body = {"address": "100 East Fordham Road, Bronx, NY 10468"}
    tight_limit.post("/api/geocode", json=body)
    tight_limit.post("/api/geocode", json=body)

    refused = tight_limit.post("/api/extract", files={"file": ("a.pdf", b"%PDF-1.4", "x/pdf")})

    assert refused.status_code == 429


def test_health_is_never_rate_limited(tight_limit: TestClient) -> None:
    """A liveness probe that can be throttled takes the deployment down with it."""
    statuses = [tight_limit.get("/api/health").status_code for _ in range(20)]
    assert statuses == [200] * 20
