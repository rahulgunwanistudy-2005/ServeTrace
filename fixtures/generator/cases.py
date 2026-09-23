"""Assemble a whole synthetic case, with its label.

The label is decided *by construction*: the generator places the person somewhere and
records what it did. It never asks the engine. Session 1 of the build pack is explicit
about this, and it is the only thing that makes the eval in `eval/` meaningful — a label
derived from the engine would just measure the engine against itself.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from app.domain.models import (
    Affidavit,
    ClaimTier,
    FixKind,
    HouseholdMember,
    LatLng,
    LocationFix,
    ServiceMethod,
)
from app.engine.params import PARAMS
from app.geo.distance import haversine_km

from .addresses import Address
from .affidavit import make_affidavit
from .people import TZ, Person, make_person
from .timeline import DayTruth, fixes_for_day, plan_day

CaseKind = str
"""One of "contradicted", "consistent", "no_data", "edge"."""

EDGE_KINDS: tuple[str, ...] = (
    "dst_fold",
    "radius_inside",
    "radius_outside_walkable",
    "visit_boundary",
)

DST_FOLD_DAY = date(2025, 11, 2)
"""Local 01:00-02:00 happens twice on this date in America/New_York."""

MIN_CONTRADICTION_KM = 3.0
"""Below this, a "contradiction" would be arguing with GPS noise rather than with the server."""

_MIN_PRISM_COMMUTE_MIN = 50.0
"""A prism-flavour contradiction is only placed inside a commute at least this long, so the
claimed time can sit more than 15 minutes clear of both endpoints."""


@dataclass(frozen=True, slots=True)
class GroundTruth:
    """What the generator built. This is the answer key, not a prediction."""

    case_id: str
    true_tier: str
    kind: CaseKind
    edge_kind: str | None
    reason: str
    person_name: str
    home_address: str
    work_address: str
    claimed_address: str
    claimed_at: str
    method: str
    true_distance_km_at_claim: float
    description_matches_household: bool
    seeded_rule_codes: tuple[str, ...]
    n_fixes: int
    dates_covered: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Case:
    case_id: str
    person: Person
    affidavit: Affidavit
    fixes: list[LocationFix]
    household: tuple[HouseholdMember, ...]
    truth: GroundTruth

    def ground_truth_dict(self) -> dict[str, object]:
        return asdict(self.truth)


def _service_day(rng: random.Random, person: Person, must_work: bool) -> date:
    """A plausible service date in 2025 that matches whether we need the person at work."""
    for _ in range(80):
        day = date(2025, 1, 1) + timedelta(days=rng.randint(0, 330))
        if person.works_on(day) == must_work:
            return day
    return date(2025, 6, 12)


def _mid(rng: random.Random, start: datetime, end: datetime, pad: float = 0.15) -> datetime:
    """A time strictly inside an interval, kept away from both edges."""
    span = (end - start).total_seconds()
    low, high = span * pad, span * (1.0 - pad)
    if high <= low:
        return start + timedelta(seconds=span / 2)
    return (start + timedelta(seconds=rng.uniform(low, high))).replace(second=0, microsecond=0)


def _plausible_service_hour(when: datetime) -> bool:
    """Process servers work daytime and evening; a 03:00 service would be its own red flag."""
    return 6 <= when.hour <= 22


def _pick_person(rng: random.Random, min_commute_km: float) -> Person:
    for _ in range(60):
        person = make_person(rng)
        if person.commute_km >= min_commute_km:
            return person
    return make_person(rng)


def _offset_point(origin: Address, km_east: float) -> tuple[float, float]:
    """A point `km_east` kilometres due east of `origin`, for the radius edge cases."""
    import math

    d_lng = km_east / (111.320 * math.cos(math.radians(origin.lat)))
    return round(origin.lat, 7), round(origin.lng + d_lng, 7)


def _build_edge_case(
    rng: random.Random, case_id: str, edge_kind: str
) -> tuple[Person, datetime, Address, list[LocationFix], ClaimTier, str, tuple[date, ...]]:
    """Edge cases are hand-placed, so their labels are honest about genuine ambiguity."""
    person = _pick_person(rng, MIN_CONTRADICTION_KM)
    home = person.home

    if edge_kind == "dst_fold":
        # 01:30 local occurs twice on the fold date. The person is home for the whole night,
        # so both interpretations agree and the honest label is CONSISTENT.
        day = DST_FOLD_DAY
        claimed_at = datetime(day.year, day.month, day.day, 1, 30, tzinfo=TZ)
        truth = plan_day(person, day, rng)
        fixes = fixes_for_day(rng, person, truth)
        return (
            person,
            claimed_at,
            home,
            fixes,
            ClaimTier.CONSISTENT,
            "Service claimed at 01:30 on the November DST fold, when that local time occurs "
            "twice. The person was home across both interpretations.",
            (day,),
        )

    day = _service_day(rng, person, must_work=False)
    claimed_at = datetime(day.year, day.month, day.day, rng.randint(10, 20), 15, tzinfo=TZ)
    truth = plan_day(person, day, rng)
    fixes = fixes_for_day(rng, person, truth)

    if edge_kind == "visit_boundary":
        # Claimed nine minutes after the home visit ends: inside the ten-minute tolerance.
        last_visit_end = next((f.t_end for f in reversed(fixes) if f.t_end is not None), None)
        if last_visit_end is not None:
            claimed_at = (last_visit_end + timedelta(minutes=9)).replace(second=0, microsecond=0)
        return (
            person,
            claimed_at,
            home,
            fixes,
            ClaimTier.CONSISTENT,
            "Service claimed nine minutes after the home visit ends, inside the "
            f"{PARAMS.visit_tolerance_min}-minute visit tolerance.",
            (day,),
        )

    # The two radius cases keep exactly one fix, placed at a measured offset from the door.
    offset_km = 0.25 if edge_kind == "radius_inside" else 0.45
    lat, lng = _offset_point(home, offset_km)
    single = LocationFix(
        t=claimed_at,
        loc=LatLng(lat=lat, lng=lng),
        accuracy_m=25.0,
        kind=FixKind.PATH,
        source="timeline_android",
        label=None,
    )
    if edge_kind == "radius_inside":
        return (
            person,
            claimed_at,
            home,
            [single],
            ClaimTier.CONSISTENT,
            f"The only fix sits {offset_km} km from the door, inside the "
            f"{PARAMS.match_radius_km} km match radius.",
            (day,),
        )
    return (
        person,
        claimed_at,
        home,
        [single],
        ClaimTier.INCONCLUSIVE,
        f"The only fix sits {offset_km} km from the door: outside the "
        f"{PARAMS.match_radius_km} km radius, but an easy walk, so it neither matches nor "
        "contradicts the claim.",
        (day,),
    )


def make_case(rng: random.Random, case_id: str, kind: CaseKind) -> Case:
    edge_kind: str | None = None
    gaps: tuple[tuple[datetime, datetime], ...] = ()

    if kind == "edge":
        edge_kind = rng.choice(EDGE_KINDS)
        person, claimed_at, claimed_place, fixes, tier, reason, days = _build_edge_case(
            rng, case_id, edge_kind
        )
    else:
        person = _pick_person(
            rng, MIN_CONTRADICTION_KM if kind in ("contradicted", "no_data") else 0.0
        )
        day = _service_day(rng, person, must_work=kind in ("contradicted", "no_data"))
        day_truth = plan_day(person, day, rng)
        claimed_place = person.home
        claimed_at, tier, reason = _claim_for(rng, person, day_truth, kind)
        days = (day,)
        if kind == "no_data":
            window = timedelta(hours=PARAMS.search_window_h, minutes=10)
            gaps = ((claimed_at - window, claimed_at + window),)
        fixes = fixes_for_day(rng, person, day_truth, gaps)

    method = rng.choices(
        (ServiceMethod.SUBSTITUTE, ServiceMethod.AFFIX_AND_MAIL, ServiceMethod.PERSONAL),
        weights=(0.5, 0.3, 0.2),
    )[0]
    description_matches = rng.random() < 0.45
    affidavit, aff_truth = make_affidavit(
        rng,
        person,
        method,
        claimed_at,
        claimed_place,
        description_matches,
        seed_rule_violations=rng.random() < 0.55,
    )

    # Prior attempts sit on earlier days, so those days need history too or every 308(4)
    # attempt would look like NO_DATA for reasons the generator never intended.
    extra_days = sorted({a.at.date() for a in affidavit.attempts} - set(days))
    for extra in extra_days:
        fixes.extend(fixes_for_day(rng, person, plan_day(person, extra, rng), gaps))
    fixes.sort(key=lambda f: (f.t, f.kind.value, f.loc.lat, f.loc.lng))

    all_days = tuple(sorted({*days, *extra_days}))
    distance_km = _true_distance_km(person, claimed_at, claimed_place, kind, edge_kind, fixes)

    return Case(
        case_id=case_id,
        person=person,
        affidavit=affidavit,
        fixes=fixes,
        household=person.household,
        truth=GroundTruth(
            case_id=case_id,
            true_tier=tier.value,
            kind=kind,
            edge_kind=edge_kind,
            reason=reason,
            person_name=person.name,
            home_address=person.home.address,
            work_address=person.work.address,
            claimed_address=claimed_place.address,
            claimed_at=claimed_at.isoformat(),
            method=method.value,
            true_distance_km_at_claim=round(distance_km, 4),
            description_matches_household=aff_truth.description_matches_household,
            seeded_rule_codes=aff_truth.seeded_rule_codes,
            n_fixes=len(fixes),
            dates_covered=tuple(d.isoformat() for d in all_days),
        ),
    )


def _claim_for(
    rng: random.Random, person: Person, day_truth: DayTruth, kind: CaseKind
) -> tuple[datetime, ClaimTier, str]:
    """Choose when service is claimed, and say plainly where the person really was."""
    home_stays = [s for s in day_truth.stays if s.kind == "home"]
    work_stays = [s for s in day_truth.stays if s.kind == "work"]

    if kind == "consistent":
        for stay in sorted(home_stays, key=lambda s: s.start, reverse=True):
            when = _mid(rng, stay.start, stay.end)
            if _plausible_service_hour(when):
                return (
                    when,
                    ClaimTier.CONSISTENT,
                    "The person was at the claimed address when service is claimed.",
                )
        stay = home_stays[0]
        return (
            _mid(rng, stay.start, stay.end),
            ClaimTier.CONSISTENT,
            "The person was at the claimed address when service is claimed.",
        )

    if kind == "no_data":
        stay = work_stays[0] if work_stays else home_stays[0]
        return (
            _mid(rng, stay.start, stay.end),
            ClaimTier.NO_DATA,
            "The phone recorded nothing for the whole window around the claimed time.",
        )

    # Contradicted, in one of two flavours: caught by the visit test, or by the prism test.
    #
    # Prism flavour needs the claimed time to sit well inside a *long* commute. Bible
    # §11.1.3 makes any fix within the match radius within +/-15 min of the claim
    # CONSISTENT, and a commute begins at the person's own front door, which is the
    # claimed address. Place the claim too near the start of a short commute and the
    # engine would rightly call it consistent while this label said contradicted, which
    # would score a correct engine as wrong.
    long_commutes = [
        travel
        for travel in day_truth.travels
        if (travel[3] - travel[2]).total_seconds() >= _MIN_PRISM_COMMUTE_MIN * 60
    ]
    if long_commutes and rng.random() < 0.4:
        _, _, start, end = long_commutes[rng.randrange(len(long_commutes))]
        when = _mid(rng, start, end, pad=0.4)
        return (
            when,
            ClaimTier.CONTRADICTED,
            "The person was mid-commute, minutes from path fixes far from the claimed "
            "address, so reaching the door would have taken an impossible speed.",
        )
    stay = work_stays[0] if work_stays else home_stays[-1]
    when = _mid(rng, stay.start, stay.end)
    return (
        when,
        ClaimTier.CONTRADICTED,
        f"The person was at work, {person.commute_km:.1f} km from the claimed address, "
        "inside a recorded visit that covers the claimed time.",
    )


def _true_distance_km(
    person: Person,
    claimed_at: datetime,
    claimed_place: Address,
    kind: CaseKind,
    edge_kind: str | None,
    fixes: list[LocationFix],
) -> float:
    """How far the person really was from the door. Geometry the generator constructed."""
    if edge_kind in ("radius_inside", "radius_outside_walkable") and fixes:
        return haversine_km(fixes[0].loc, claimed_place.latlng)
    if kind == "contradicted":
        return person.commute_km
    return 0.0
