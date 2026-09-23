"""The three curated demo cases. Committed, fixed, and never randomly redrawn.

Bible §17: the demo must never fail. These are built by hand rather than sampled so a
live demonstration shows exactly the same three stories every time.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.models import ClaimTier, HouseholdMember, ServiceMethod

from .addresses import Address, by_borough
from .affidavit import make_affidavit
from .cases import Case, GroundTruth
from .people import Person, Shift
from .timeline import fixes_for_day, plan_day


def _address(fragment: str, borough: str) -> Address:
    """Resolve a pinned demo address, loudly.

    A silent fallback here would quietly relocate a demo case to a different street the
    next time the address pool is rebuilt, and the curated story would stop matching the
    map without anything failing.
    """
    fragment = fragment.upper()
    for candidate in by_borough(borough):
        if fragment in candidate.address.upper():
            return candidate
    raise LookupError(
        f"demo address {fragment!r} is not in the {borough} pool; "
        "pick another from fixtures/addresses_nyc.json or rebuild the pool"
    )


@dataclass(frozen=True, slots=True)
class DemoSpec:
    case_id: str
    person: Person
    method: ServiceMethod
    service_date: date
    service_hour: float
    tier: ClaimTier
    reason: str
    description_matches: bool
    seed_rule_violations: bool


def _maria() -> DemoSpec:
    """Bronx home health aide, at a Manhattan client when service is claimed at her door."""
    person = Person(
        name="Maria Delarmo",
        sex="female",
        age=34,
        height_in=63,
        home=_address("2100 WHITE PLAINS ROAD", "Bronx"),
        work=_address("1400 LEXINGTON AVENUE", "Manhattan"),
        shift=Shift(start_h=8, end_h=20, workdays=(0, 1, 2, 3, 4)),
        commute_speed_kmh=22.0,
        household=(
            HouseholdMember(
                label="Maria Delarmo", sex="female", age=34, height_in=63, is_defendant=True
            ),
            HouseholdMember(label="Daughter", sex="female", age=9, height_in=52),
        ),
    )
    return DemoSpec(
        case_id="maria_contradicted",
        person=person,
        method=ServiceMethod.SUBSTITUTE,
        service_date=date(2025, 6, 12),
        service_hour=19.7,
        tier=ClaimTier.CONTRADICTED,
        reason=(
            "The affidavit claims substituted service at Maria's Bronx door at 7:42 PM. Her "
            "phone puts her at her client's Manhattan address across that whole evening, and "
            "the only other person in the household is a nine-year-old."
        ),
        description_matches=False,
        seed_rule_violations=False,
    )


def _james() -> DemoSpec:
    """The honest case: the data backs the server up, and ServeTrace says so."""
    person = Person(
        name="James Okonkwa",
        sex="male",
        age=41,
        height_in=71,
        home=_address("900 BEDFORD AVENUE", "Brooklyn"),
        work=_address("550 8 AVENUE", "Manhattan"),
        shift=Shift(start_h=9, end_h=17, workdays=(0, 1, 2, 3, 4)),
        commute_speed_kmh=24.0,
        household=(
            HouseholdMember(
                label="James Okonkwa", sex="male", age=41, height_in=71, is_defendant=True
            ),
            HouseholdMember(label="Partner", sex="female", age=39, height_in=65),
        ),
    )
    return DemoSpec(
        case_id="james_consistent",
        person=person,
        method=ServiceMethod.SUBSTITUTE,
        service_date=date(2025, 5, 14),
        service_hour=19.25,
        tier=ClaimTier.CONSISTENT,
        reason=(
            "James was home when the papers were left with his partner, and his partner "
            "matches the description on the affidavit. His own data supports the server's "
            "account, and the product has to say so."
        ),
        description_matches=True,
        seed_rule_violations=False,
    )


def _lin() -> DemoSpec:
    """Affix and mail with thin due diligence: the paperwork is the problem, not the GPS."""
    person = Person(
        name="Lin Quintaro",
        sex="other",
        age=52,
        height_in=66,
        home=_address("104 HILLSIDE AVENUE", "Queens"),
        work=_address("1750 ATLANTIC AVENUE", "Brooklyn"),
        shift=Shift(start_h=14, end_h=22, workdays=(0, 1, 2, 3, 4)),
        commute_speed_kmh=20.0,
        household=(
            HouseholdMember(
                label="Lin Quintaro", sex="other", age=52, height_in=66, is_defendant=True
            ),
        ),
    )
    return DemoSpec(
        case_id="lin_affix_mail_diligence",
        person=person,
        method=ServiceMethod.AFFIX_AND_MAIL,
        service_date=date(2025, 9, 9),
        service_hour=16.5,
        tier=ClaimTier.CONTRADICTED,
        reason=(
            "The papers were taped to Lin's Queens door at 4:30 PM on a shift day, while "
            "Lin's phone was at work in Brooklyn. Both prior attempts fall on the same "
            "weekday inside office hours, which is not the pattern courts expect before "
            "affix-and-mail is allowed."
        ),
        description_matches=False,
        seed_rule_violations=True,
    )


DEMO_SPECS = (_maria, _james, _lin)


def build_demo_case(spec: DemoSpec, seed: int) -> Case:
    rng = random.Random(seed)
    person = spec.person
    claimed_at = person.local(spec.service_date, spec.service_hour)

    affidavit, aff_truth = make_affidavit(
        rng,
        person,
        spec.method,
        claimed_at,
        person.home,
        spec.description_matches,
        spec.seed_rule_violations,
    )
    if spec.case_id == "lin_affix_mail_diligence":
        # The whole point of this case is the thin attempt pattern, so it is pinned rather
        # than left to the dice: two attempts, same weekday, both inside office hours.
        pinned = [
            attempt.model_copy(
                update={"at": claimed_at.replace(hour=hour, minute=minute) - timedelta(days=days)}
            )
            for attempt, (days, hour, minute) in zip(
                affidavit.attempts[:2], ((7, 10, 30), (14, 11, 0)), strict=False
            )
        ]
        affidavit = affidavit.model_copy(update={"attempts": pinned})

    days = sorted({spec.service_date, *(a.at.date() for a in affidavit.attempts)})
    fixes = []
    for day in days:
        fixes.extend(fixes_for_day(rng, person, plan_day(person, day, rng)))
    fixes.sort(key=lambda f: (f.t, f.kind.value, f.loc.lat, f.loc.lng))

    distance = person.commute_km if spec.tier is ClaimTier.CONTRADICTED else 0.0
    return Case(
        case_id=spec.case_id,
        person=person,
        affidavit=affidavit,
        fixes=fixes,
        household=person.household,
        truth=GroundTruth(
            case_id=spec.case_id,
            true_tier=spec.tier.value,
            kind="demo",
            edge_kind=None,
            reason=spec.reason,
            person_name=person.name,
            home_address=person.home.address,
            work_address=person.work.address,
            claimed_address=person.home.address,
            claimed_at=claimed_at.isoformat(),
            method=spec.method.value,
            true_distance_km_at_claim=round(distance, 4),
            description_matches_household=aff_truth.description_matches_household,
            seeded_rule_codes=aff_truth.seeded_rule_codes,
            n_fixes=len(fixes),
            dates_covered=tuple(d.isoformat() for d in days),
        ),
    )
