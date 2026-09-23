"""The four invariants in bible §11.1, as properties over generated inputs.

These are the assertions that catch what hand-picked cases never do. Each one is a
statement about the *shape* of the engine rather than about any particular answer:

1. moving a fix away from the claimed point never weakens a contradiction;
2. shifting the whole world by a constant changes nothing;
3. a fix far outside the search window changes nothing;
4. a fix exactly at the claimed point at exactly the claimed time is always CONSISTENT.

Fixes are generated in polar coordinates around the claimed point, so "move it further
away" is one number going up and `haversine_km` is exactly monotone in it. Generating
latitudes instead would make the move only approximately a move, and a property test with
an approximate premise proves nothing.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from app.domain.models import ClaimTier, FixKind, LocationFix, Severity
from app.engine.feasibility import conflict_rank, evaluate_claim, interpretations
from app.engine.params import PARAMS
from app.geo.distance import haversine_km
from tests.engine.conftest import CLAIM_AT, DOOR, NY, away

EXAMPLES = settings(
    max_examples=500,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

WINDOW_S = PARAMS.search_window_h * 3600


@st.composite
def placed_fix(draw: st.DrawFn, *, offset_s: st.SearchStrategy[int] | None = None) -> LocationFix:
    """One fix somewhere in or near the search window, at a drawn bearing and distance."""
    seconds = draw(offset_s or st.integers(min_value=-WINDOW_S - 600, max_value=WINDOW_S + 600))
    km = draw(st.floats(min_value=0.0, max_value=60.0, allow_nan=False, allow_infinity=False))
    bearing = draw(st.floats(min_value=0.0, max_value=359.999, allow_nan=False))
    kind = draw(st.sampled_from(list(FixKind)))
    duration = draw(st.one_of(st.none(), st.integers(min_value=1, max_value=600)))
    accuracy = draw(st.one_of(st.none(), st.floats(min_value=0.0, max_value=500.0)))
    start = CLAIM_AT + timedelta(seconds=seconds)
    return LocationFix(
        t=start,
        t_end=start + timedelta(minutes=duration) if duration is not None else None,
        loc=away(km, bearing),
        accuracy_m=accuracy,
        kind=kind,
        source="generated",
    )


FIXES = st.lists(placed_fix(), min_size=0, max_size=12)


SEVERITY_ORDER = {Severity.STRONG: 0, Severity.MODERATE: 1, Severity.INFO: 2}
"""`Severity` is a `StrEnum`, so comparing two of them compares their spelling. Sorting by
that would put "moderate" before "strong" and quietly weaken every assertion below."""


def fingerprint(fixes: list[LocationFix], at: datetime = CLAIM_AT) -> object:
    """Everything about a verdict that an invariant says must not move.

    Finding *text* carries times and distances and is expected to change under a shift, so
    what is compared is the tier and which findings fired, not their sentences.
    """
    verdict, findings = evaluate_claim("served_at", at, DOOR, fixes, PARAMS)
    return verdict.tier, tuple(sorted((f.code, f.severity.value) for f in findings))


def adversity(fixes: list[LocationFix], at: datetime = CLAIM_AT) -> int:
    """How strongly the engine reads this data against the affidavit."""
    verdict, findings = evaluate_claim("served_at", at, DOOR, fixes, PARAMS)
    if verdict.tier is not ClaimTier.CONTRADICTED:
        return conflict_rank(verdict.tier)
    conflicts = [f for f in findings if f.code in ("F-VISIT", "F-PRISM")]
    strongest = min((f.severity for f in conflicts), key=lambda s: SEVERITY_ORDER[s])
    return conflict_rank(verdict.tier, strongest)


def moved_away(fix: LocationFix, extra_km: float) -> LocationFix:
    """The same fix, further from the claimed point along the same bearing."""
    current = haversine_km(fix.loc, DOOR)
    bearing = _bearing_from_door(fix)
    return fix.model_copy(update={"loc": away(current + extra_km, bearing)})


def _bearing_from_door(fix: LocationFix) -> float:
    import math

    lat1, lat2 = math.radians(DOOR.lat), math.radians(fix.loc.lat)
    dlng = math.radians(fix.loc.lng - DOOR.lng)
    y = math.sin(dlng) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlng)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


# --- Invariant 1 --------------------------------------------------------------------------


@EXAMPLES
@given(
    fixes=st.lists(placed_fix(), min_size=1, max_size=10),
    index=st.integers(min_value=0, max_value=9),
    extra_km=st.floats(min_value=0.01, max_value=40.0, allow_nan=False),
)
def test_moving_a_fix_further_away_never_weakens_the_contradiction(
    fixes: list[LocationFix], index: int, extra_km: float
) -> None:
    index %= len(fixes)
    moved = list(fixes)
    moved[index] = moved_away(fixes[index], extra_km)
    assume(haversine_km(moved[index].loc, DOOR) > haversine_km(fixes[index].loc, DOOR))
    assert adversity(moved) >= adversity(fixes)


# --- Invariant 2 --------------------------------------------------------------------------


@EXAMPLES
@given(fixes=FIXES, shift_minutes=st.integers(min_value=-20_000, max_value=20_000))
def test_shifting_every_timestamp_by_the_same_amount_changes_nothing(
    fixes: list[LocationFix], shift_minutes: int
) -> None:
    shift = timedelta(minutes=shift_minutes)
    shifted_claim = CLAIM_AT + shift
    # A shift that lands the claim on the night the clocks go back genuinely does change
    # the answer, because the affidavit's wall-clock time then names two moments. That is
    # the rule in bible §11.1.1 working, not the invariant failing.
    assume(len(interpretations(shifted_claim, NY)) == 1)

    shifted = [
        f.model_copy(
            update={"t": f.t + shift, "t_end": f.t_end + shift if f.t_end is not None else None}
        )
        for f in fixes
    ]
    assert fingerprint(shifted, shifted_claim) == fingerprint(fixes, CLAIM_AT)


# --- Invariant 3 --------------------------------------------------------------------------


@EXAMPLES
@given(
    fixes=FIXES,
    hours_out=st.integers(min_value=PARAMS.search_window_h + 1, max_value=400),
    before=st.booleans(),
    km=st.floats(min_value=0.0, max_value=200.0, allow_nan=False),
)
def test_a_fix_far_outside_the_window_changes_nothing(
    fixes: list[LocationFix], hours_out: int, before: bool, km: float
) -> None:
    offset = timedelta(hours=hours_out if not before else -hours_out)
    distant = LocationFix(
        t=CLAIM_AT + offset,
        loc=away(km, 42.0),
        kind=FixKind.PATH,
        source="generated",
    )
    assert fingerprint([*fixes, distant]) == fingerprint(fixes)


# --- Invariant 4 --------------------------------------------------------------------------


@EXAMPLES
@given(fixes=FIXES, kind=st.sampled_from(list(FixKind)))
def test_a_fix_at_the_claimed_point_at_the_claimed_time_is_always_consistent(
    fixes: list[LocationFix], kind: FixKind
) -> None:
    """Whatever else the data says. Bible §11.1's own invariant, and the reason evidence at
    the claimed time takes precedence over the visit and prism tests rather than the other
    way round."""
    exact = LocationFix(t=CLAIM_AT, loc=DOOR, kind=kind, source="generated")
    verdict, _ = evaluate_claim("served_at", CLAIM_AT, DOOR, [*fixes, exact], PARAMS)
    assert verdict.tier is ClaimTier.CONSISTENT


# --- Determinism ---------------------------------------------------------------------------


@EXAMPLES
@given(fixes=FIXES, order_seed=st.integers(min_value=0, max_value=10_000))
def test_the_answer_does_not_depend_on_the_order_fixes_arrive_in(
    fixes: list[LocationFix], order_seed: int
) -> None:
    """A verdict that changed with the order of a JSON array would be unreproducible, and
    an unreproducible verdict is not evidence."""
    import random

    shuffled = list(fixes)
    random.Random(order_seed).shuffle(shuffled)
    assert fingerprint(shuffled) == fingerprint(fixes)
