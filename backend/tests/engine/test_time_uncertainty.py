"""Bible §11.1.7 (v1.1): uncertain time never strengthens a contradiction.

The property tests prove the shape; these pin the cases a person will actually meet — a
camera-roll photo across town, with and without the time zone its clock was set to.
"""

from __future__ import annotations

from datetime import timedelta

from app.domain.models import ClaimTier, FixKind, LocationFix, Severity
from app.engine.feasibility import evaluate_claim
from app.engine.params import PARAMS
from tests.engine.conftest import CLAIM_AT, DOOR, away


def photo(minutes: float, km: float, *, assumed: bool = False) -> LocationFix:
    return LocationFix(
        t=CLAIM_AT + timedelta(minutes=minutes),
        loc=away(km, 90.0),
        accuracy_m=100.0,
        kind=FixKind.PHOTO,
        source="photo",
        label="Photo taken here",
        time_uncertainty_s=3600 if assumed else 0,
        tz_assumed=assumed,
    )


def conflict_severity(fixes: list[LocationFix]) -> Severity | None:
    _, findings = evaluate_claim("served_at", CLAIM_AT, DOOR, fixes, PARAMS)
    severities = [f.severity for f in findings if f.code in ("F-VISIT", "F-PRISM")]
    if Severity.STRONG in severities:
        return Severity.STRONG
    return Severity.MODERATE if Severity.MODERATE in severities else None


def test_an_exact_photo_ten_km_away_four_minutes_before_is_a_strong_conflict() -> None:
    verdict, _ = evaluate_claim("served_at", CLAIM_AT, DOOR, [photo(-4, 10.5)], PARAMS)
    assert verdict.tier is ClaimTier.CONTRADICTED
    assert conflict_severity([photo(-4, 10.5)]) is Severity.STRONG


def test_the_same_photo_with_an_assumed_zone_is_capped_at_moderate() -> None:
    fixes = [photo(-4, 10.5, assumed=True), photo(5, 10.5, assumed=True)]
    verdict, findings = evaluate_claim("served_at", CLAIM_AT, DOOR, fixes, PARAMS)
    # An hour of slack on 10 km is still over 40 km/h only if the gap is short enough;
    # either way it may never be STRONG.
    assert conflict_severity(fixes) is not Severity.STRONG
    assert any(f.code == "F-TIME" for f in findings)
    assert verdict.tier in (ClaimTier.CONTRADICTED, ClaimTier.INCONCLUSIVE)


def test_an_assumed_zone_photo_cannot_hide_an_exact_impossible_point() -> None:
    fixes = [photo(-4, 10.5, assumed=True), photo(3, 10.5)]
    assert conflict_severity(fixes) is Severity.STRONG


def test_slack_is_spent_in_the_affidavits_favour() -> None:
    """Thirty km twenty minutes out is 90 km/h exact; with an hour either way it is 22."""
    assert conflict_severity([photo(-20, 30.0)]) is Severity.STRONG
    assert conflict_severity([photo(-20, 30.0, assumed=True)]) is None


def test_an_assumed_zone_photo_at_the_door_an_hour_off_still_supports_the_claim() -> None:
    near_door = photo(50, 0.05, assumed=True)
    verdict, findings = evaluate_claim("served_at", CLAIM_AT, DOOR, [near_door], PARAMS)
    assert verdict.tier is ClaimTier.CONSISTENT
    assert any(f.code == "F-TIME" for f in findings)


def test_an_exact_fix_says_nothing_about_estimated_times() -> None:
    _, findings = evaluate_claim("served_at", CLAIM_AT, DOOR, [photo(-4, 10.5)], PARAMS)
    assert not any(f.code == "F-TIME" for f in findings)


def test_a_quoted_gap_is_the_real_gap_and_the_slack_is_named_separately() -> None:
    """The finding's minutes are true of the record; the hour allowed is its own number."""
    fixes = [photo(-2, 200.0, assumed=True)]
    _, findings = evaluate_claim("served_at", CLAIM_AT, DOOR, fixes, PARAMS)
    prism = next(f for f in findings if f.code == "F-PRISM")
    assert prism.numbers["minutes"] == 2.0
    assert prism.numbers["slack_minutes"] == 60.0
    assert prism.severity is Severity.MODERATE
