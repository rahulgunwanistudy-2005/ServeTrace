"""Bible §11.1, path by path.

These tests assert on tiers, severities and finding *codes*. Never on wording: the
sentences live in `engine/copy.py` and have to stay free to change, which is a lesson this
project has already paid for once.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.domain.models import ClaimTier, FixKind, Severity
from app.engine.feasibility import (
    MIN_ELAPSED_S,
    conflict_rank,
    evaluate_claim,
    interpretations,
)
from app.engine.params import PARAMS, EngineParams
from app.geo.distance import haversine_km
from tests.engine.conftest import CLAIM_AT, DOOR, NY, affidavit, away, fix, ny, visit


def run(fixes: list, at=CLAIM_AT, point=DOOR, params: EngineParams = PARAMS):
    return evaluate_claim("served_at", at, point, fixes, params)


def codes(findings) -> set[str]:
    return {f.code for f in findings}


# --- No data ----------------------------------------------------------------------------


def test_no_fixes_at_all_is_no_data() -> None:
    verdict, findings = run([])
    assert verdict.tier is ClaimTier.NO_DATA
    assert verdict.nearest_fix_km is None
    assert codes(findings) == {"F-NODATA"}


def test_fixes_only_outside_the_window_are_no_data() -> None:
    outside = CLAIM_AT + timedelta(hours=PARAMS.search_window_h, minutes=1)
    verdict, _ = run([fix(outside, away(20.0))])
    assert verdict.tier is ClaimTier.NO_DATA


def test_a_visit_starting_before_the_window_but_covering_the_claim_is_used() -> None:
    """The visit test would be worthless if a ten-hour stay fell out of a six-hour window."""
    long_stay = visit(CLAIM_AT - timedelta(hours=9), 720, away(14.0))
    verdict, findings = run([long_stay])
    assert verdict.tier is ClaimTier.CONTRADICTED
    assert codes(findings) == {"F-VISIT"}


# --- The visit test ---------------------------------------------------------------------


def test_visit_far_from_the_door_covering_the_claim_contradicts_strongly() -> None:
    verdict, findings = run([visit(CLAIM_AT - timedelta(hours=2), 300, away(14.2))])
    assert verdict.tier is ClaimTier.CONTRADICTED
    assert [f.severity for f in findings] == [Severity.STRONG]
    assert findings[0].code == "F-VISIT"
    assert findings[0].numbers["distance_km"] == pytest.approx(14.2, abs=0.05)


def test_visit_at_the_door_covering_the_claim_is_consistent() -> None:
    verdict, findings = run([visit(CLAIM_AT - timedelta(hours=2), 300, away(0.05))])
    assert verdict.tier is ClaimTier.CONSISTENT
    assert codes(findings) == {"F-NEAR"}


@pytest.mark.parametrize("gap_min", [PARAMS.visit_tolerance_min - 1, PARAMS.visit_tolerance_min])
def test_a_stay_ending_just_before_the_claim_still_covers_it(gap_min: int) -> None:
    """Bible §11.1.2: the tolerance reaches forwards out of the end of a stay."""
    stay = visit(CLAIM_AT - timedelta(minutes=60 + gap_min), 60, away(0.05))
    assert run([stay])[0].tier is ClaimTier.CONSISTENT


@pytest.mark.parametrize("gap_min", [PARAMS.visit_tolerance_min - 1, PARAMS.visit_tolerance_min])
def test_a_stay_starting_just_after_the_claim_also_covers_it(gap_min: int) -> None:
    stay = visit(CLAIM_AT + timedelta(minutes=gap_min), 60, away(0.05))
    assert run([stay])[0].tier is ClaimTier.CONSISTENT


def test_a_stay_beyond_the_tolerance_does_not_cover_the_claim() -> None:
    far_stay = visit(
        CLAIM_AT - timedelta(minutes=60 + PARAMS.visit_tolerance_min + 5), 60, away(14.0)
    )
    verdict, findings = run([far_stay])
    assert "F-VISIT" not in codes(findings)
    assert verdict.tier is ClaimTier.CONTRADICTED  # the prism still has something to say


def test_a_stay_450_metres_from_the_door_is_not_a_contradiction() -> None:
    """The distance a geocode can be wrong by is not evidence that anyone was elsewhere."""
    verdict, findings = run([visit(CLAIM_AT - timedelta(hours=1), 180, away(0.45))])
    assert verdict.tier is not ClaimTier.CONTRADICTED
    assert "F-VISIT" not in codes(findings)


def test_the_nearest_covering_stay_decides_when_several_cover_the_claim() -> None:
    """The reading least adverse to the affidavit, so no fix can be cherry-picked."""
    near_ish = visit(CLAIM_AT - timedelta(hours=1), 180, away(3.0))
    far = visit(CLAIM_AT - timedelta(hours=1), 180, away(30.0))
    _, findings = run([far, near_ish])
    assert findings[0].numbers["distance_km"] == pytest.approx(3.0, abs=0.05)


# --- The prism test ---------------------------------------------------------------------


def test_impossible_speed_between_two_points_contradicts_strongly() -> None:
    """The speed quoted is the one the data can *prove*, not the one it suggests.

    A phone 14 km away knows its own position to within the match radius, so the journey
    the record establishes is 14 km less that radius. Quoting the full 14 km would be
    reading the fix as a point when it is a disc, and this number goes into a document a
    judge reads: the defensible figure is the smallest one consistent with the evidence.
    """
    fixes = [
        fix(CLAIM_AT - timedelta(minutes=5), away(14.0)),
        fix(CLAIM_AT + timedelta(minutes=5), away(14.0)),
    ]
    verdict, findings = run(fixes)
    assert verdict.tier is ClaimTier.CONTRADICTED
    assert findings[0].code == "F-PRISM"
    assert findings[0].severity is Severity.STRONG
    provable_km = 14.0 - PARAMS.match_radius_km
    assert verdict.required_speed_kmh == pytest.approx(provable_km / (5 / 60), rel=0.02)
    assert verdict.required_speed_kmh < 14.0 / (5 / 60)


def test_crossing_the_match_radius_does_not_flip_a_verdict_on_one_metre() -> None:
    """The distance half of session 4's lesson: no threshold may cliff at the radius.

    A transaction accurate to 500 m gets a 0.8 km radius. Under the old short circuit a
    fix 799 m from the door cost nothing and one 801 m away cost a 48 km/h dash — two
    metres of GPS noise deciding whether a sworn statement was contradicted. The property
    that forbids that is continuity: a metre of extra distance may only ever buy a metre's
    worth of required speed.
    """
    accurate_to_500m = {"accuracy_m": 500.0, "kind": FixKind.TRANSACTION}
    radius_km = PARAMS.match_radius_km + 0.5

    just_inside = fix(CLAIM_AT, away(radius_km - 0.001), **accurate_to_500m)
    just_outside = fix(CLAIM_AT, away(radius_km + 0.001), **accurate_to_500m)

    inside_verdict, inside_findings = run([just_inside])
    outside_verdict, outside_findings = run([just_outside])

    assert "F-PRISM" not in codes(inside_findings)
    assert "F-PRISM" not in codes(outside_findings)
    assert inside_verdict.tier is not ClaimTier.CONTRADICTED
    assert outside_verdict.tier is not ClaimTier.CONTRADICTED


def test_a_fix_that_admits_its_error_is_not_contradicted_by_that_error() -> None:
    """A cell-tower fix accurate to 1 km, 1.2 km from the door, at the claimed minute.

    Bible §11.1 widens the match radius by the fix's own `accuracy_m` precisely so that a
    phone is not contradicted by noise it declared. The same displacement from a fix
    claiming 10 m of accuracy is a real conflict, and the pair is what shows the field is
    doing work rather than being read and discarded.
    """
    vague = fix(CLAIM_AT, away(1.2), accuracy_m=1000.0, kind=FixKind.TRANSACTION)
    precise = fix(CLAIM_AT, away(1.2), accuracy_m=10.0, kind=FixKind.TRANSACTION)

    assert run([vague])[0].tier is not ClaimTier.CONTRADICTED
    assert run([precise])[0].tier is ClaimTier.CONTRADICTED


def test_a_merely_brisk_speed_contradicts_moderately() -> None:
    """Between the two thresholds: possible in a car, not on foot. Bible §11.1.3."""
    fixes = [fix(CLAIM_AT - timedelta(minutes=30), away(25.0))]
    verdict, findings = run(fixes)
    assert verdict.tier is ClaimTier.CONTRADICTED
    assert findings[0].severity is Severity.MODERATE


def test_a_reachable_distance_is_inconclusive_not_consistent() -> None:
    fixes = [fix(CLAIM_AT - timedelta(hours=2), away(3.0))]
    verdict, findings = run(fixes)
    assert verdict.tier is ClaimTier.INCONCLUSIVE
    assert findings == []


def test_only_a_fix_before_the_claim_still_evaluates_that_side() -> None:
    verdict, _ = run([fix(CLAIM_AT - timedelta(minutes=2), away(20.0))])
    assert verdict.tier is ClaimTier.CONTRADICTED


def test_only_a_fix_after_the_claim_still_evaluates_that_side() -> None:
    verdict, _ = run([fix(CLAIM_AT + timedelta(minutes=2), away(20.0))])
    assert verdict.tier is ClaimTier.CONTRADICTED


def test_a_distant_fix_at_the_same_minute_quotes_no_speed() -> None:
    """The severity comes off the elapsed floor, so no speed the data cannot support is
    printed next to it."""
    verdict, findings = run([fix(CLAIM_AT + timedelta(seconds=20), away(30.0))])
    assert verdict.tier is ClaimTier.CONTRADICTED
    assert findings[0].severity is Severity.STRONG
    assert verdict.required_speed_kmh is None
    assert "required_speed_kmh" not in findings[0].numbers


def test_a_walkable_distance_at_the_same_minute_is_not_a_contradiction() -> None:
    """The corpus' own `radius_outside_walkable` edge case, in one assertion.

    450 m is outside the match radius and inside a two-minute walk. Bible §11.1.3's
    literal infinite-speed guard would call this a STRONG contradiction of a sworn
    statement, which is exactly the accusation this product must never make.
    """
    verdict, findings = run([fix(CLAIM_AT, away(0.45), accuracy_m=25.0)])
    assert verdict.tier is ClaimTier.INCONCLUSIVE
    assert findings == []


def test_the_elapsed_floor_is_what_sets_that_boundary() -> None:
    """A kilometre in the minute the floor allows is 60 km/h: over moderate, under strong."""
    assert pytest.approx(60.0) == 1.0 / (MIN_ELAPSED_S / 3600)
    verdict, findings = run([fix(CLAIM_AT, away(1.0))])
    assert verdict.tier is ClaimTier.CONTRADICTED
    assert findings[0].severity is Severity.MODERATE


# --- Radius, accuracy and the consistency window -----------------------------------------


def test_a_fix_inside_the_match_radius_at_the_claim_is_consistent() -> None:
    verdict, findings = run([fix(CLAIM_AT, away(PARAMS.match_radius_km - 0.01))])
    assert verdict.tier is ClaimTier.CONSISTENT
    assert codes(findings) == {"F-NEAR"}


def test_stated_accuracy_widens_the_radius() -> None:
    """A card transaction is accurate to 500 m and must not be read as a 500 m journey."""
    just_outside = PARAMS.match_radius_km + 0.2
    without = run([fix(CLAIM_AT, away(just_outside))])[0]
    withit = run([fix(CLAIM_AT, away(just_outside), accuracy_m=500.0, kind=FixKind.TRANSACTION)])[0]
    assert without.tier is not ClaimTier.CONSISTENT
    assert withit.tier is ClaimTier.CONSISTENT


def test_evidence_at_the_door_just_outside_the_consistency_window_does_not_count() -> None:
    late = CLAIM_AT + timedelta(minutes=PARAMS.consistent_window_min + 1)
    verdict, _ = run([fix(late, DOOR), fix(CLAIM_AT - timedelta(minutes=3), away(25.0))])
    assert verdict.tier is ClaimTier.CONTRADICTED


def test_evidence_at_the_door_inside_the_window_wins_and_says_so() -> None:
    """Bible §11.1.5, and the §11.1 invariant, resolved the same way: never accuse on data
    that argues with itself, and never hide that it does."""
    inside = CLAIM_AT + timedelta(minutes=PARAMS.consistent_window_min - 1)
    verdict, findings = run([fix(inside, DOOR), fix(CLAIM_AT - timedelta(minutes=3), away(25.0))])
    assert verdict.tier is ClaimTier.CONSISTENT
    assert codes(findings) == {"F-NEAR", "F-PRISM", "F-CONFLICT"}


# --- Daylight saving ---------------------------------------------------------------------

DST_FOLD_NIGHT = ny(1, 30, day=2, month=11)
"""01:30 on 2 November 2025 happens twice in New York."""


def test_the_fold_produces_two_interpretations_an_hour_apart() -> None:
    both = interpretations(DST_FOLD_NIGHT, NY)
    assert len(both) == 2
    assert both[1] - both[0] == timedelta(hours=1)


def test_an_ordinary_time_produces_exactly_one() -> None:
    assert len(interpretations(CLAIM_AT, NY)) == 1


def test_the_weaker_reading_of_an_ambiguous_clock_is_kept() -> None:
    """Home for the first 1:30 AM, twenty kilometres away for the second.

    The fixtures are placed against the UTC instants on purpose. Adding a `timedelta` to a
    zoned datetime moves the wall clock, not the moment, so on this one night of the year
    building a fixture that way silently lands it an hour from where it was meant to be —
    which is the whole reason this rule exists.
    """
    early, late = interpretations(DST_FOLD_NIGHT, NY)
    fixes = [
        visit(early - timedelta(minutes=30), 60, DOOR),
        visit(late - timedelta(minutes=30), 60, away(20.0)),
    ]
    verdict, findings = run(fixes, at=DST_FOLD_NIGHT)
    assert verdict.tier is ClaimTier.CONSISTENT
    assert "F-CLOCK" in codes(findings)


def test_no_clock_finding_when_both_readings_agree() -> None:
    early, late = interpretations(DST_FOLD_NIGHT, NY)
    fixes = [visit(early - timedelta(hours=2), 360, DOOR)]
    verdict, findings = run(fixes, at=DST_FOLD_NIGHT)
    assert verdict.tier is ClaimTier.CONSISTENT
    assert "F-CLOCK" not in codes(findings)
    assert late - early == timedelta(hours=1)


# --- Ordering ----------------------------------------------------------------------------


def test_conflict_rank_orders_readings_from_strongest_conflict_to_weakest() -> None:
    order = [
        conflict_rank(ClaimTier.CONTRADICTED, Severity.STRONG),
        conflict_rank(ClaimTier.CONTRADICTED, Severity.MODERATE),
        conflict_rank(ClaimTier.INCONCLUSIVE),
        conflict_rank(ClaimTier.NO_DATA),
        conflict_rank(ClaimTier.CONSISTENT),
    ]
    assert order == sorted(order, reverse=True)


def test_the_verdict_reports_where_the_phone_was_at_the_claimed_time() -> None:
    """Not the friendliest point in the six-hour window: going home later is not an alibi."""
    fixes = [
        visit(CLAIM_AT - timedelta(hours=2), 240, away(14.0)),
        visit(CLAIM_AT + timedelta(hours=2), 300, DOOR),
    ]
    verdict, _ = run(fixes)
    assert verdict.nearest_fix_km == pytest.approx(14.0, abs=0.05)


def test_an_unresolved_claim_point_is_never_invented() -> None:
    """`evaluate_claim` is only ever called with a point; the caller handles the other case."""
    assert affidavit(served_location=None).served_location is None


def test_distance_uses_the_one_haversine_in_the_codebase() -> None:
    assert haversine_km(DOOR, away(2.5)) == pytest.approx(2.5, abs=0.001)
