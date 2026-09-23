"""Space-time feasibility for one claim. Bible §11.1.

Pure functions, no I/O, no wall clock. Given a claimed time, a claimed point and the
user's location fixes, decide whether the data conflicts with the claim, supports it, or
says nothing — and say why in numbers a person can check.

Three tests, in order of how directly they speak:

1. **The visit test.** An export that says "you were at this place from 08:00 to 20:00"
   is a stronger statement than a scatter of points, because the phone stayed put long
   enough to be sure. If such an interval covers the claimed time and sits far from the
   claimed address, that is the clearest conflict there is.
2. **The space-time prism** (Hägerstrand). Between a fix before the claim and a fix after
   it, the claimed point is only reachable at some speed. If that speed is absurd, the
   claim and the data cannot both be true.
3. **Nothing in the window** — say so, plainly. `NO_DATA` is an answer, not a failure.

Two decisions that are not in the bible's wording and that both go the same way, towards
never accusing anyone on ambiguous data:

- **Evidence at the claimed time wins over everything.** Bible §11.1.5 says a `CONSISTENT`
  reading overrides a MODERATE contradiction. It is silent on a STRONG one, but bible §11.1
  also requires that a fix exactly at the claimed point at exactly the claimed time always
  yields `CONSISTENT`. Both are satisfied by one rule: a fix inside the match radius within
  the consistency window settles the claim as `CONSISTENT`, whatever else the data says.
  The competing finding is still reported, and a third finding says plainly that the user's
  own data disagrees with itself. Nothing is hidden and nobody is accused on it.
- **Both readings of an ambiguous clock are evaluated**, and the weaker one is kept. The
  affidavit only ever said "7:42 PM"; on the night the clocks go back that names two
  moments an hour apart, and the engine has no way to know which the server meant.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.models import (
    ClaimTier,
    ClaimVerdict,
    Finding,
    FixKind,
    LatLng,
    LocationFix,
    Severity,
)
from app.engine import copy
from app.engine.params import EngineParams
from app.geo.distance import haversine_km

INTERVAL_KINDS = (FixKind.VISIT, FixKind.MANUAL)
"""Bible §11.1.2: only these two carry an interval the visit test may rely on."""

MIN_ELAPSED_S = 60.0
"""The shortest gap a required speed may be computed over.

Bible §11.1.3 guards sub-minute gaps with an infinite speed whenever the fix is outside
the match radius. Taken literally that calls a phone 450 metres from a door at the claimed
minute a STRONG contradiction, which is a two-minute walk and the width of a geocoding
error — and the corpus' own edge case at that distance is labelled INCONCLUSIVE by the
generator, independently and correctly.

So the guard here is a floor on the elapsed time rather than a jump to infinity. The
justification is the data: affidavit times are written to the minute and phone timestamps
are rounded to it, so a gap under a minute is not a measurement, and a distance divided by
rounding noise is not a speed. Flooring is strictly more conservative than the literal
rule, which is the direction bible §11 says to err, and it keeps the severity a continuous
function of distance instead of a cliff at the radius."""


# --- How strongly a reading goes against the affidavit ----------------------------------
#
# Used for two things: choosing the weaker of two readings of an ambiguous clock, and
# combining claims into one case verdict. Ordered so that `min()` is always the
# conservative choice.

_RANK: dict[tuple[ClaimTier, Severity | None], int] = {
    (ClaimTier.CONTRADICTED, Severity.STRONG): 4,
    (ClaimTier.CONTRADICTED, Severity.MODERATE): 3,
    (ClaimTier.INCONCLUSIVE, None): 2,
    (ClaimTier.NO_DATA, None): 1,
    (ClaimTier.CONSISTENT, None): 0,
}


def conflict_rank(tier: ClaimTier, severity: Severity | None = None) -> int:
    """How adverse a reading is to the affidavit. Higher means a stronger conflict."""
    return _RANK.get((tier, severity), _RANK[(ClaimTier.INCONCLUSIVE, None)])


@dataclass(frozen=True, slots=True)
class _Reading:
    """One evaluation of one claim at one instant."""

    tier: ClaimTier
    severity: Severity | None
    findings: list[Finding]
    nearest_fix_km: float | None
    """How far the claimed point was from the fix closest in time to the claim."""
    required_speed_kmh: float | None
    fixes_used: list[LocationFix]

    @property
    def rank(self) -> int:
        return conflict_rank(self.tier, self.severity)


@dataclass(frozen=True, slots=True)
class _Anchor:
    """A fix reduced to the single moment and point that constrains the claim.

    A long visit either side of the claimed time constrains it from its near end, not from
    wherever the interval happens to start, so the anchor time is the interval clamped to
    the claim. That is the tight reading, and the tight reading is the honest one.
    """

    at: datetime
    fix: LocationFix
    km: float
    radius_km: float

    @property
    def within_radius(self) -> bool:
        return self.km <= self.radius_km


@dataclass(slots=True)
class FixIndex:
    """Fixes arranged so a claim only touches what is near it in time.

    Built once per request and shared by every claim in it. An affidavit with three prior
    attempts asks four questions of the same export, and sorting it four times would make
    the whole analysis linear in the file for no reason.
    """

    points: list[LocationFix] = field(default_factory=list)
    point_times: list[datetime] = field(default_factory=list)
    intervals: list[LocationFix] = field(default_factory=list)
    interval_starts: list[datetime] = field(default_factory=list)


def _span(fix: LocationFix) -> tuple[datetime, datetime]:
    """An interval fix, normalised. Bad data with `t_end` before `t` is not a reason to
    crash, and swapping the ends is the only reading that means anything."""
    if fix.t_end is None:
        return fix.t, fix.t
    return (fix.t, fix.t_end) if fix.t_end >= fix.t else (fix.t_end, fix.t)


def build_index(fixes: list[LocationFix]) -> FixIndex:
    index = FixIndex()
    for fix in sorted(fixes, key=lambda f: (f.t, f.t_end or f.t)):
        if fix.t_end is None:
            index.points.append(fix)
            index.point_times.append(fix.t)
        else:
            index.intervals.append(fix)
            index.interval_starts.append(_span(fix)[0])
    return index


def _in_window(index: FixIndex, at: datetime, window: timedelta) -> list[LocationFix]:
    """Every fix whose own span overlaps [at - window, at + window]."""
    low, high = at - window, at + window
    lo = bisect_left(index.point_times, low)
    hi = bisect_right(index.point_times, high)
    found = list(index.points[lo:hi])
    # Intervals are a small minority of any export, and one of them can start long before
    # the window and still cover it, so they are bounded on the right and scanned on the left.
    for fix in index.intervals[: bisect_right(index.interval_starts, high)]:
        if _span(fix)[1] >= low:
            found.append(fix)
    return found


def _radius_km(fix: LocationFix, params: EngineParams) -> float:
    """Bible §11: the match radius, widened by the fix's own stated accuracy."""
    return params.match_radius_km + (fix.accuracy_m or 0.0) / 1000.0


def _anchor(fix: LocationFix, at: datetime, point: LatLng, params: EngineParams) -> _Anchor:
    start, end = _span(fix)
    return _Anchor(
        at=min(max(at, start), end),
        fix=fix,
        km=haversine_km(fix.loc, point),
        radius_km=_radius_km(fix, params),
    )


def _covers(fix: LocationFix, at: datetime, params: EngineParams) -> bool:
    """Bible §11.1.2: a visit covers T when t - tolerance <= T <= t_end + tolerance."""
    if fix.t_end is None or fix.kind not in INTERVAL_KINDS:
        return False
    start, end = _span(fix)
    tolerance = timedelta(minutes=params.visit_tolerance_min)
    return start - tolerance <= at <= end + tolerance


def interpretations(claimed_at: datetime, tz: ZoneInfo) -> list[datetime]:
    """Every instant the affidavit's wall-clock time could mean. Bible §11.1.1.

    On the night the clocks go back, the same local time names two moments an hour apart,
    and the affidavit said only the local time. Both are returned, oldest first.
    """
    local_at = claimed_at.astimezone(tz)
    naive = local_at.replace(tzinfo=None)
    earlier = naive.replace(fold=0, tzinfo=tz)
    later = naive.replace(fold=1, tzinfo=tz)
    if earlier.utcoffset() == later.utcoffset():
        return [claimed_at.astimezone(UTC)]
    return sorted({earlier.astimezone(UTC), later.astimezone(UTC)})


def evaluate_claim(
    claim_ref: str,
    claimed_at: datetime,
    claimed_location: LatLng,
    fixes: list[LocationFix],
    params: EngineParams,
) -> tuple[ClaimVerdict, list[Finding]]:
    """Visit test, then Hagerstrand prism test, then the no-data fallback.

    The pure entry point: hand it a list and it answers. A caller with several claims over
    the same export should build one `FixIndex` and use `evaluate_prepared` instead.
    """
    return evaluate_prepared(claim_ref, claimed_at, claimed_location, build_index(fixes), params)


def evaluate_prepared(
    claim_ref: str,
    claimed_at: datetime,
    claimed_location: LatLng,
    index: FixIndex,
    params: EngineParams,
) -> tuple[ClaimVerdict, list[Finding]]:
    """`evaluate_claim` against an index prepared once for the whole request."""
    tz = ZoneInfo(params.tz)
    readings = [
        _evaluate_instant(claim_ref, at, claimed_location, index, params)
        for at in interpretations(claimed_at, tz)
    ]
    kept = min(readings, key=lambda r: r.rank)
    findings = list(kept.findings)

    if len(readings) > 1 and len({r.rank for r in readings}) > 1:
        # The choice of reading changed the answer, so the user is told it was made.
        title, detail = copy.ambiguous_clock(claim_ref, claimed_at.astimezone(tz))
        findings.append(
            Finding(
                code="F-CLOCK",
                severity=Severity.INFO,
                title=title,
                detail=detail,
                numbers={"claim": claim_ref, "readings": float(len(readings))},
            )
        )

    verdict = ClaimVerdict(
        claim_ref=claim_ref,
        claimed_at=claimed_at,
        claimed_location=claimed_location,
        tier=kept.tier,
        nearest_fix_km=kept.nearest_fix_km,
        required_speed_kmh=kept.required_speed_kmh,
        fixes_used=kept.fixes_used,
    )
    return verdict, findings


def _evaluate_instant(
    claim_ref: str, at: datetime, point: LatLng, index: FixIndex, params: EngineParams
) -> _Reading:
    window = timedelta(hours=params.search_window_h)
    near_window = timedelta(minutes=params.consistent_window_min)
    in_window = _in_window(index, at, window)

    if not in_window:
        title, detail = copy.no_data(claim_ref, at, params.search_window_h)
        return _Reading(
            tier=ClaimTier.NO_DATA,
            severity=None,
            findings=[
                Finding(
                    code="F-NODATA",
                    severity=Severity.INFO,
                    title=title,
                    detail=detail,
                    numbers={"claim": claim_ref, "window_hours": float(params.search_window_h)},
                )
            ],
            nearest_fix_km=None,
            required_speed_kmh=None,
            fixes_used=[],
        )

    anchors = [_anchor(fix, at, point, params) for fix in in_window]
    # "Nearest" is nearest *in time*, reported as a distance: the answer to "where was my
    # phone at 7:42 PM", which is the number the result headline is built from. The
    # smallest distance anywhere in the six-hour window would be a different and much
    # more flattering question — going home two hours later does not put you at the door
    # when the papers were said to arrive.
    closest_in_time = min(anchors, key=lambda a: (abs(a.at - at), a.km))
    nearest_km = round(closest_in_time.km, 3)

    near = _best_near(anchors, at, near_window)
    conflict = _covering_conflict(anchors, at, claim_ref, params) or _prism(
        anchors, at, claim_ref, params
    )

    if near is not None:
        return _consistent(claim_ref, at, near, conflict, nearest_km, params)
    if conflict is not None:
        return _Reading(
            tier=ClaimTier.CONTRADICTED,
            severity=conflict.severity,
            findings=[conflict.finding],
            nearest_fix_km=nearest_km,
            required_speed_kmh=conflict.speed_kmh,
            fixes_used=conflict.fixes,
        )
    return _Reading(
        tier=ClaimTier.INCONCLUSIVE,
        severity=None,
        findings=[],
        nearest_fix_km=nearest_km,
        required_speed_kmh=None,
        fixes_used=[a.fix for a in _prism_sides(anchors, at)],
    )


@dataclass(frozen=True, slots=True)
class _Conflict:
    severity: Severity
    finding: Finding
    fixes: list[LocationFix]
    speed_kmh: float | None


def _best_near(anchors: list[_Anchor], at: datetime, near_window: timedelta) -> _Anchor | None:
    """The closest fix that puts the phone at the claimed point around the claimed time."""
    candidates = [a for a in anchors if a.within_radius and abs(a.at - at) <= near_window]
    return min(candidates, key=lambda a: a.km) if candidates else None


def _required_speed(anchor: _Anchor, at: datetime) -> float:
    """km/h needed to be at the claimed point at the claimed time.

    A fix inside its own stated accuracy of the claimed point *is* at the claimed point,
    so there is no journey to price and the answer is zero. That has to be a special case
    rather than a small number, or a transaction with 500 m of accuracy would price its
    own uncertainty as a 48 km/h dash.
    """
    if anchor.within_radius:
        return 0.0
    seconds = max(abs((at - anchor.at).total_seconds()), MIN_ELAPSED_S)
    return anchor.km / (seconds / 3600.0)


def _covering_conflict(
    anchors: list[_Anchor], at: datetime, claim_ref: str, params: EngineParams
) -> _Conflict | None:
    """Bible §11.1.2, as a speed question like every other.

    A stay that covers the claimed time leaves no time to be anywhere else, so its anchor
    sits at the claim itself and the elapsed floor decides what distance that makes
    impossible. What still makes this the *visit* test is the conclusion, not the
    arithmetic: a recorded stay is stronger evidence than a point passed through, so a
    conflicting stay is STRONG where the same required speed from a single point would be
    MODERATE. Bible §11.1.5 gives the visit test precedence, and this is what that
    precedence is worth.

    Among several covering stays the nearest one is used: the reading least adverse to the
    affidavit, and the only one that cannot be lowered by a fix moving further away.
    """
    covering = [a for a in anchors if _covers(a.fix, at, params)]
    if not covering:
        return None
    best = min(covering, key=lambda a: a.km)
    if _required_speed(best, at) <= params.v_moderate_kmh:
        return None
    start, end = _span(best.fix)
    title, detail = copy.visit_conflict(claim_ref, at, best.km, start, end)
    return _Conflict(
        severity=Severity.STRONG,
        finding=Finding(
            code="F-VISIT",
            severity=Severity.STRONG,
            title=title,
            detail=detail,
            numbers={"claim": claim_ref, "distance_km": round(best.km, 3)},
        ),
        fixes=[best.fix],
        speed_kmh=None,
    )


def _prism_sides(anchors: list[_Anchor], at: datetime) -> list[_Anchor]:
    """The nearest anchor before the claim and the nearest after it. Bible §11.1.3.

    Two fixes can share a timestamp; a phone reporting two places at the same second is
    noise, not evidence, so the tie goes to whichever is *closest* to the claimed point.
    That is the reading least adverse to the affidavit, and because `min` over distances
    only ever rises when a fix moves away, it keeps the engine monotone.
    """
    before = [a for a in anchors if a.at <= at]
    after = [a for a in anchors if a.at >= at]
    sides: list[_Anchor] = []
    if before:
        sides.append(max(before, key=lambda a: (a.at, -a.km)))
    if after:
        nearest_after = min(after, key=lambda a: (a.at, a.km))
        if not sides or nearest_after.fix is not sides[0].fix:
            sides.append(nearest_after)
    return sides


def _prism(
    anchors: list[_Anchor], at: datetime, claim_ref: str, params: EngineParams
) -> _Conflict | None:
    sides = _prism_sides(anchors, at)
    if not sides:
        return None

    fastest, anchor = max(((_required_speed(a, at), a) for a in sides), key=lambda pair: pair[0])
    if fastest <= params.v_moderate_kmh:
        return None

    severity = Severity.STRONG if fastest > params.v_strong_kmh else Severity.MODERATE
    seconds = abs((at - anchor.at).total_seconds())
    numbers: dict[str, float | str] = {"claim": claim_ref, "distance_km": round(anchor.km, 3)}

    if seconds < MIN_ELAPSED_S:
        # The speed that set the severity came off the floor, not off the clock, so it is
        # not quoted back: a number the data cannot support does not belong in a sentence
        # a judge might read.
        title, detail = copy.simultaneous_conflict(claim_ref, at, anchor.km, anchor.at)
        speed_kmh = None
    else:
        title, detail = copy.prism_conflict(
            claim_ref, at, fastest, anchor.km, seconds / 60.0, anchor.at
        )
        numbers["minutes"] = round(seconds / 60.0, 1)
        numbers["required_speed_kmh"] = round(fastest, 1)
        speed_kmh = round(fastest, 1)

    return _Conflict(
        severity=severity,
        finding=Finding(
            code="F-PRISM", severity=severity, title=title, detail=detail, numbers=numbers
        ),
        fixes=[a.fix for a in sides],
        speed_kmh=speed_kmh,
    )


def _consistent(
    claim_ref: str,
    at: datetime,
    near: _Anchor,
    conflict: _Conflict | None,
    nearest_km: float,
    params: EngineParams,
) -> _Reading:
    """Evidence at the claimed time settles it, and any competing finding is still shown."""
    if _covers(near.fix, at, params):
        start, end = _span(near.fix)
        title, detail = copy.visit_match(claim_ref, at, near.km, start, end)
    else:
        title, detail = copy.near_claim(claim_ref, at, near.km, near.at)

    findings = [
        Finding(
            code="F-NEAR",
            severity=Severity.INFO,
            title=title,
            detail=detail,
            numbers={"claim": claim_ref, "distance_km": round(near.km, 3)},
        )
    ]
    fixes = [near.fix]
    if conflict is not None:
        findings.append(conflict.finding)
        title, detail = copy.data_disagrees(claim_ref, at)
        findings.append(
            Finding(
                code="F-CONFLICT",
                severity=Severity.INFO,
                title=title,
                detail=detail,
                numbers={"claim": claim_ref},
            )
        )
        fixes.extend(f for f in conflict.fixes if f is not near.fix)

    return _Reading(
        tier=ClaimTier.CONSISTENT,
        severity=None,
        findings=findings,
        nearest_fix_km=nearest_km,
        required_speed_kmh=None,
        fixes_used=fixes,
    )
