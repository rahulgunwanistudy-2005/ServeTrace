"""Bible §11.4: 50,000 rows in under three seconds.

The number is not arbitrary. An advocate's whole year of filings from one agency is tens
of thousands of rows, and a request that takes a minute is one they will not make twice —
so the bound is really about whether the batch mode gets used at all.

Wall-clock assertions are fragile, so the budget is generous and the test prints what it
measured. What it is really protecting is the complexity: sort plus one pass. An
accidental O(n²) — comparing every filing with every other rather than with the next one —
would miss this by minutes, not milliseconds.
"""

from __future__ import annotations

import random
import time
from datetime import timedelta

from app.advocate.patterns import analyze_servers
from app.domain.models import ServiceRecord
from app.engine.params import PARAMS
from tests.advocate.conftest import DAY_START, km_away

ROWS = 50_000
SERVERS = 25
BUDGET_S = 3.0


def _corpus() -> list[ServiceRecord]:
    """Realistic shape: several servers, a full day each, ordinary gaps between doors."""
    rng = random.Random(11)
    records: list[ServiceRecord] = []
    for server in range(SERVERS):
        when = DAY_START
        for _ in range(ROWS // SERVERS):
            when += timedelta(minutes=rng.randint(9, 40))
            records.append(
                ServiceRecord(
                    server_id=f"SRV-{server:03d}",
                    at=when,
                    loc=km_away(rng.uniform(0.1, 6.0), rng.uniform(0, 360)),
                    address=f"{rng.randint(1, 900)} SYNTHETIC STREET",
                    case_ref=f"CV-{rng.randint(1000, 99999)}-25",
                    outcome=rng.choice(("served", "affixed", "not_home")),
                    recipient_desc=f"{rng.choice('MF')}/{rng.randrange(25, 70, 5)}",
                )
            )
    rng.shuffle(records)
    return records


def test_fifty_thousand_filings_analyse_inside_the_budget(capsys) -> None:
    records = _corpus()

    started = time.perf_counter()
    reports = analyze_servers(records, PARAMS)
    elapsed = time.perf_counter() - started

    with capsys.disabled():
        print(
            f"\n{len(records):,} filings x {len(reports)} servers: {elapsed * 1000:.0f} ms "
            f"(budget {BUDGET_S * 1000:.0f})"
        )

    assert len(reports) == SERVERS
    assert elapsed < BUDGET_S


def test_doubling_the_rows_does_not_square_the_time(capsys) -> None:
    """The property the budget is a proxy for.

    An O(n²) implementation passes a generous wall-clock bound on a fast machine and then
    fails on the one row count that matters. This asserts the shape of the curve instead:
    twice the work should cost near twice the time, and is allowed four times as a very
    loose ceiling on interpreter noise.
    """
    records = _corpus()
    half = records[: len(records) // 2]

    def measure(rows: list[ServiceRecord]) -> float:
        started = time.perf_counter()
        analyze_servers(rows, PARAMS)
        return time.perf_counter() - started

    small = min(measure(half) for _ in range(3))
    large = min(measure(records) for _ in range(3))

    with capsys.disabled():
        print(
            f"\n{len(half):,}: {small * 1000:.0f} ms · {len(records):,}: {large * 1000:.0f} ms "
            f"(ratio {large / small:.2f})"
        )

    assert large < small * 4
