"""F-DESC: does anyone in the household match the described recipient? Bible §11.2.

The affidavit describes whoever took the papers. If the user says nobody living at that
address looks anything like that, it is worth a judge's attention — but only worth so
much, because the roster is typed in by the person disputing the service. Hence MODERATE,
always, and never a word about photographs. Bible §3 puts face and photo analysis
permanently out of scope, and this module is the place that would have been tempted.

The comparison is deliberately forgiving:

- **Missing fields are ignored, never counted against anyone.** An affidavit that gives
  only a sex and a household member with no height recorded should not produce a mismatch
  out of two blanks.
- **Every stated field is widened** by the tolerances in `params`, because a description
  written by a stranger at a doorway is an estimate, not a measurement.
- **Weight and hair are not compared at all.** Bible §11.2 names sex, age and height; hair
  changes on a Tuesday and a weight guessed through a half-open door is not evidence.

So a finding here means: every person the user listed differs from the description on a
field the affidavit itself stated, by more than the tolerance.
"""

from __future__ import annotations

from app.domain.models import (
    Affidavit,
    Finding,
    HouseholdMember,
    PersonDescription,
    ServiceMethod,
    Severity,
)
from app.engine import copy
from app.engine.params import EngineParams

COMPARABLE_SEXES = ("male", "female")
"""A description reading "unknown", or a roster row reading "other", states nothing to
compare. Treating either as a mismatch would manufacture findings out of a blank."""


def _within(value: int, low: int | None, high: int | None, tolerance: int) -> bool:
    if low is not None and value < low - tolerance:
        return False
    return not (high is not None and value > high + tolerance)


def matches(described: PersonDescription, member: HouseholdMember, params: EngineParams) -> bool:
    """True when nothing the affidavit stated rules this person out."""
    if (
        described.sex in COMPARABLE_SEXES
        and member.sex in COMPARABLE_SEXES
        and described.sex != member.sex
    ):
        return False
    if member.age is not None and not _within(
        member.age, described.age_min, described.age_max, params.desc_age_tolerance_y
    ):
        return False
    return member.height_in is None or _within(
        member.height_in,
        described.height_in_min,
        described.height_in_max,
        params.desc_height_tolerance_in,
    )


def _states_anything(described: PersonDescription) -> bool:
    """A description block with nothing comparable in it cannot rule anybody out."""
    return (
        described.sex in COMPARABLE_SEXES
        or described.age_min is not None
        or described.age_max is not None
        or described.height_in_min is not None
        or described.height_in_max is not None
    )


def check_description(
    affidavit: Affidavit, household: list[HouseholdMember], params: EngineParams
) -> list[Finding]:
    """Missing fields are ignored, never counted as a mismatch. Photos are never used."""
    described = affidavit.recipient_description
    if described is None or not household or not _states_anything(described):
        return []

    if affidavit.method is ServiceMethod.PERSONAL:
        # L1: the papers were handed to the defendant, so the defendant is who to compare.
        candidates = [m for m in household if m.is_defendant]
        legal_ref = "L1"
    elif affidavit.method is ServiceMethod.SUBSTITUTE:
        # L2: anyone of suitable age and discretion at the address will do, so all of them.
        candidates = list(household)
        legal_ref = "L2"
    else:
        # 308(4) tapes the papers to a door and 'unknown' does not say what happened. In
        # neither case did a person accept anything, so there is nobody to compare against
        # and a mismatch would mean nothing.
        return []

    if not candidates or any(matches(described, m, params) for m in candidates):
        return []

    described_words = copy.describe_recipient(
        described.sex,
        described.age_min,
        described.age_max,
        described.height_in_min,
        described.height_in_max,
    )
    if affidavit.method is ServiceMethod.PERSONAL:
        member = candidates[0]
        title, detail = copy.description_mismatch_personal(
            described_words,
            copy.describe_member(member.label, member.sex, member.age, member.height_in),
        )
    else:
        title, detail = copy.description_mismatch_substitute(described_words, len(candidates))

    return [
        Finding(
            code="F-DESC",
            severity=Severity.MODERATE,
            title=title,
            detail=detail,
            numbers={"described": described_words, "household_size": float(len(candidates))},
            legal_ref=legal_ref,
        )
    ]
