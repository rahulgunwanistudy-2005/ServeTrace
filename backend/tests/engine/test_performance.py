"""The §16 ceiling, analysed inside the S4 budget.

Bible §16 caps one request at 5,000 fixes; the S4 brief asks for four claims analysed
against that in under 200 ms. The point is not speed for its own sake — it is that a
person on a phone taps *Check* once and waits, and a request that takes a second on a
free-tier container is a request that gets tapped twice.

The budget is a ceiling, not a target, so these tests assert the ceiling and print the
real figure. A performance test that fails on a busy laptop teaches people to ignore
failures, which costs more than it saves.
"""

from __future__ import annotations

import time
from datetime import timedelta

from app.domain.models import FixKind, LocationFix, ServiceAttempt, ServiceMethod
from app.engine.feasibility import build_index, evaluate_prepared
from app.engine.params import PARAMS
from app.engine.verdict import analyze
from tests.engine.conftest import CLAIM_AT, DOOR, affidavit, away, fix

BUDGET_MS = 200.0
MAX_FIXES = 5_000

CLAIMS = 4
"""The service plus three prior attempts: the most a 308(4) affidavit usually carries."""


def a_days_worth(n: int) -> list[LocationFix]:
    """`n` fixes spread over a week, so most of them fall outside any one claim's window.

    That is the realistic shape — an export is mostly irrelevant to any given minute — and
    it is what the index exists to skip. Building them all inside the window would measure
    a case that cannot happen under the §13 windowing.
    """
    span = timedelta(days=7).total_seconds()
    fixes: list[LocationFix] = []
    for i in range(n):
        offset = timedelta(seconds=-span / 2 + span * i / n)
        fixes.append(
            fix(
                CLAIM_AT + offset,
                away(0.2 + (i % 400) * 0.05, bearing_deg=(i * 7) % 360),
                kind=FixKind.VISIT if i % 50 == 0 else FixKind.PATH,
                minutes=45.0 if i % 50 == 0 else None,
                accuracy_m=15.0 + (i % 30),
            )
        )
    return fixes


def test_five_thousand_fixes_across_four_claims_fit_the_budget(capsys) -> None:
    fixes = a_days_worth(MAX_FIXES)
    attempts = [
        ServiceAttempt(
            at=CLAIM_AT - timedelta(days=days),
            address="2100 WHITE PLAINS ROAD, Bronx, NY 10462",
            location=DOOR,
            outcome="not_home",
        )
        for days in (2, 5, 9)
    ]
    body = affidavit(method=ServiceMethod.AFFIX_AND_MAIL, attempts=attempts)
    from app.domain.models import AnalyzeRequest

    request = AnalyzeRequest(affidavit=body, fixes=fixes)
    assert len(list(request.affidavit.attempts)) + 1 == CLAIMS

    started = time.perf_counter()
    analysis = analyze(request)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    with capsys.disabled():
        print(f"\n{MAX_FIXES} fixes x {CLAIMS} claims: {elapsed_ms:.1f} ms (budget {BUDGET_MS})\n")
    assert len(analysis.verdicts) == CLAIMS
    assert elapsed_ms < BUDGET_MS


def test_extra_claims_are_nearly_free(capsys) -> None:
    """Four claims over one export must not cost four times one claim.

    This is what the index is actually for. Reading the file is linear and always will be
    — you cannot know what is in a window without looking — but *sorting* it once and
    bisecting per claim is the difference between four passes and one. A regression here
    would pass the budget above and still be the wrong shape, which is how an engine ends
    up too slow two sessions later for reasons nobody can find.
    """
    fixes = a_days_worth(MAX_FIXES)
    index = build_index(fixes)

    def per_claim(n_claims: int) -> float:
        started = time.perf_counter()
        for i in range(n_claims):
            evaluate_prepared(f"attempt[{i}]", CLAIM_AT - timedelta(days=i), DOOR, index, PARAMS)
        return time.perf_counter() - started

    one, four = per_claim(1), per_claim(CLAIMS)
    with capsys.disabled():
        print(f"\n1 claim: {one * 1000:.2f} ms · {CLAIMS} claims: {four * 1000:.2f} ms\n")
    assert four < one * CLAIMS * 1.5


def test_building_the_index_is_the_linear_part_and_is_done_once(capsys) -> None:
    """Stated as a measurement rather than a claim, so the shape is on the record."""
    fixes = a_days_worth(MAX_FIXES)
    started = time.perf_counter()
    index = build_index(fixes)
    build_ms = (time.perf_counter() - started) * 1000.0

    started = time.perf_counter()
    evaluate_prepared("served_at", CLAIM_AT, DOOR, index, PARAMS)
    claim_ms = (time.perf_counter() - started) * 1000.0

    with capsys.disabled():
        print(f"\nindex {MAX_FIXES} fixes: {build_ms:.2f} ms")
        print(f"one claim against it: {claim_ms:.2f} ms\n")
    assert build_ms + claim_ms * CLAIMS < BUDGET_MS
