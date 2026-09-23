"""New York timing and due-diligence rules R-T1..R-M1. Bible §11.3.

Every finding this module emits carries the L-id from bible §5 that it encodes.
No legal statement may originate here that is not in that table.

The day counts below are **statute**, not thresholds, which is why they live here as named
constants rather than in `engine/params.py`. Twenty days is twenty days because CPLR 308
says so; moving it would not tune the engine, it would make the engine wrong. The one
number that is not statute is the due-diligence pattern, and bible §5 L4 is explicit that
courts *commonly expect* it — so R-D1 is a flag for review and says so in as many words.

Each rule is a small function of the same context, registered in an ordered list. Adding
a rule means writing one function and appending it; there is no dispatch to get wrong, and
the order of the report is the order of this list.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final
from zoneinfo import ZoneInfo

from app.domain.models import (
    Affidavit,
    ClaimTier,
    ClaimVerdict,
    Finding,
    ServiceMethod,
    Severity,
)
from app.engine import copy
from app.engine.params import EngineParams

MAIL_WINDOW_DAYS: Final = 20
"""L2 / L3: delivery (or affixing) and mailing must be within 20 days of each other."""

PROOF_FILING_DAYS: Final = 20
"""L2 / L3: proof of service is filed within 20 days of the later of the two."""

DILIGENCE_MIN_ATTEMPTS: Final = 3
DILIGENCE_MIN_DAYS: Final = 2
"""L4: the practitioner standard courts commonly expect. Never stated as statute."""

OFFICE_HOURS: Final = (9, 17)
"""L4: attempts only ever made inside a working day are the pattern courts look at."""

MAILING_METHODS: Final = (ServiceMethod.SUBSTITUTE, ServiceMethod.AFFIX_AND_MAIL)


@dataclass(frozen=True, slots=True)
class RuleContext:
    affidavit: Affidavit
    verdicts: list[ClaimVerdict]
    tz: ZoneInfo

    @property
    def method(self) -> ServiceMethod:
        return self.affidavit.method

    @property
    def served_date(self) -> date:
        """The claimed delivery or affixing, as a New York calendar date. Bible §11.1.1."""
        return self.affidavit.served_at.astimezone(self.tz).date()

    def local(self, when: datetime) -> datetime:
        return when.astimezone(self.tz)


def _legal_ref(method: ServiceMethod) -> str:
    """L2 governs 308(2); L3 governs 308(4). Both say the same thing about the mailing."""
    return "L3" if method is ServiceMethod.AFFIX_AND_MAIL else "L2"


def r_t1_mailing_missing(ctx: RuleContext) -> Finding | None:
    """The affidavit does not show the mailing that 308(2) and 308(4) both require."""
    if ctx.method not in MAILING_METHODS or ctx.affidavit.mailing_date is not None:
        return None
    title, detail = copy.missing_mailing(ctx.method.value)
    return Finding(
        code="R-T1",
        severity=Severity.MODERATE,
        title=title,
        detail=detail,
        legal_ref=_legal_ref(ctx.method),
    )


def r_t2_mailing_too_far(ctx: RuleContext) -> Finding | None:
    """Delivery and mailing more than 20 days apart, in either direction."""
    mailing = ctx.affidavit.mailing_date
    if ctx.method not in MAILING_METHODS or mailing is None:
        return None
    days = abs((mailing - ctx.served_date).days)
    if days <= MAIL_WINDOW_DAYS:
        return None
    title, detail = copy.mailing_too_late(days, MAIL_WINDOW_DAYS)
    return Finding(
        code="R-T2",
        severity=Severity.STRONG,
        title=title,
        detail=detail,
        numbers={"days": float(days), "limit_days": float(MAIL_WINDOW_DAYS)},
        legal_ref=_legal_ref(ctx.method),
    )


def r_t3_proof_filed_late(ctx: RuleContext) -> Finding | None:
    """Proof of service filed more than 20 days after the later of delivery and mailing."""
    filed = ctx.affidavit.proof_filed_date
    if ctx.method not in MAILING_METHODS or filed is None:
        return None
    mailing = ctx.affidavit.mailing_date
    later = max(ctx.served_date, mailing) if mailing is not None else ctx.served_date
    days = (filed - later).days
    if days <= PROOF_FILING_DAYS:
        return None
    title, detail = copy.proof_filed_late(days, PROOF_FILING_DAYS)
    return Finding(
        code="R-T3",
        severity=Severity.MODERATE,
        title=title,
        detail=detail,
        numbers={"days": float(days), "limit_days": float(PROOF_FILING_DAYS)},
        legal_ref=_legal_ref(ctx.method),
    )


def r_d1_thin_diligence(ctx: RuleContext) -> Finding | None:
    """L4: three attempts, two different days, different times of day. A flag, not a verdict."""
    if ctx.method is not ServiceMethod.AFFIX_AND_MAIL:
        return None

    attempts = ctx.affidavit.attempts
    locals_ = [ctx.local(a.at) for a in attempts]
    days = {when.date() for when in locals_}
    reasons: list[str] = []

    if len(attempts) < DILIGENCE_MIN_ATTEMPTS:
        reasons.append(copy.diligence_too_few(len(attempts)))
    if attempts and len(days) < DILIGENCE_MIN_DAYS:
        reasons.append(copy.diligence_one_day(len(days)))
    if attempts and all(
        when.weekday() < 5 and OFFICE_HOURS[0] <= when.hour < OFFICE_HOURS[1] for when in locals_
    ):
        reasons.append(copy.diligence_office_hours())

    if not reasons:
        return None
    title, detail = copy.thin_diligence(reasons)
    return Finding(
        code="R-D1",
        severity=Severity.MODERATE,
        title=title,
        detail=detail,
        numbers={"attempts": float(len(attempts)), "distinct_days": float(len(days))},
        legal_ref="L4",
    )


def r_d2_attempts_contradicted(ctx: RuleContext) -> Finding | None:
    """The attempts are what justifies affix-and-mail, so a conflict there goes to the root."""
    if ctx.method is not ServiceMethod.AFFIX_AND_MAIL:
        return None
    contradicted = [
        v
        for v in ctx.verdicts
        if v.claim_ref.startswith("attempt[") and v.tier is ClaimTier.CONTRADICTED
    ]
    if not contradicted:
        return None
    title, detail = copy.contradicted_attempts(len(contradicted))
    return Finding(
        code="R-D2",
        severity=Severity.STRONG,
        title=title,
        detail=detail,
        numbers={"attempts_contradicted": float(len(contradicted))},
        legal_ref="L3",
    )


def r_m1_method_unknown(ctx: RuleContext) -> Finding | None:
    """Every timing rule above depends on which kind of service this was, so say so."""
    if ctx.method is not ServiceMethod.UNKNOWN:
        return None
    title, detail = copy.method_unknown()
    return Finding(code="R-M1", severity=Severity.INFO, title=title, detail=detail)


RULES: Final[tuple[Callable[[RuleContext], Finding | None], ...]] = (
    r_t2_mailing_too_far,
    r_d2_attempts_contradicted,
    r_t1_mailing_missing,
    r_t3_proof_filed_late,
    r_d1_thin_diligence,
    r_m1_method_unknown,
)
"""Ordered strongest first, so a stable sort by severity leaves this order inside each band."""


def check_rules(
    affidavit: Affidavit, verdicts: list[ClaimVerdict], params: EngineParams
) -> list[Finding]:
    ctx = RuleContext(affidavit=affidavit, verdicts=verdicts, tz=ZoneInfo(params.tz))
    return [finding for rule in RULES if (finding := rule(ctx)) is not None]
