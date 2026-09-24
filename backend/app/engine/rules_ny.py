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
from app.licences.registry import LicenceCategory, Standing, in_force_on, look_up

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


LICENCE_KINDS: Final[tuple[tuple[str, LicenceCategory, str], ...]] = (
    ("server", LicenceCategory.INDIVIDUAL, "server_license"),
    ("agency", LicenceCategory.AGENCY, "agency_license"),
)
"""The two numbers an affidavit carries, and the register each is checked against."""


def _licence_findings(ctx: RuleContext, wanted: frozenset[Standing]) -> list[Finding]:
    """Both licence numbers, checked against the register. Bible §5 L7.

    One walker for all three rules because the server's number and the agency's number ask
    the register exactly the same question, and the only thing that differs is the word in
    the sentence. `wanted` is what lets each rule take its own subset of the answers.
    """
    out: list[Finding] = []
    for kind, category, field in LICENCE_KINDS:
        number = getattr(ctx.affidavit, field)
        standing = in_force_on(number, category, ctx.served_date)
        if standing not in wanted:
            continue

        if standing is Standing.UNKNOWN_NUMBER:
            title, detail = copy.licence_not_found(kind)
            out.append(
                Finding(
                    code="R-L1",
                    severity=Severity.MODERATE,
                    title=title,
                    detail=detail,
                    legal_ref="L7",
                )
            )
            continue

        licence = look_up(number, category)
        if licence is None:  # pragma: no cover - only UNKNOWN_NUMBER reaches here with None
            continue

        if standing is Standing.EXPIRED and licence.expires is not None:
            reason = copy.licence_expired_on(licence.expires, ctx.served_date)
            title, detail = copy.licence_not_in_force(kind, reason)
            out.append(
                Finding(
                    code="R-L2",
                    severity=Severity.MODERATE,
                    title=title,
                    detail=detail,
                    numbers={"expired": licence.expires.isoformat()},
                    legal_ref="L7",
                )
            )
        elif standing is Standing.NOT_YET_ISSUED and licence.issued is not None:
            reason = copy.licence_issued_after(licence.issued, ctx.served_date)
            title, detail = copy.licence_not_in_force(kind, reason)
            out.append(
                Finding(
                    code="R-L2",
                    severity=Severity.MODERATE,
                    title=title,
                    detail=detail,
                    numbers={"issued": licence.issued.isoformat()},
                    legal_ref="L7",
                )
            )
        elif standing is Standing.REVOKED:
            title, detail = copy.licence_revoked(kind, licence.status)
            out.append(
                Finding(
                    code="R-L3",
                    severity=Severity.MODERATE,
                    title=title,
                    detail=detail,
                    numbers={"status": licence.status},
                    legal_ref="L7",
                )
            )
    return out


def r_l1_licence_unknown(ctx: RuleContext) -> list[Finding]:
    """L7: the number on the affidavit is not in the City's register at all."""
    return _licence_findings(ctx, frozenset({Standing.UNKNOWN_NUMBER}))


def r_l2_licence_not_in_force(ctx: RuleContext) -> list[Finding]:
    """L7: the register places the licence outside the date the service is sworn to.

    One-sided, and `registry.in_force_on` explains why: the register is a snapshot of now,
    so it can show a licence had already lapsed or had not yet been issued, and can never
    show that one *was* in force on a past date.
    """
    return _licence_findings(ctx, frozenset({Standing.EXPIRED, Standing.NOT_YET_ISSUED}))


def r_l3_licence_revoked(ctx: RuleContext) -> list[Finding]:
    """L7: the licence is revoked or suspended *today*.

    MODERATE and written in the present tense on purpose. The register carries no status
    history, so "revoked when they served you" is a sentence this data cannot support, and
    the finding does not imply it.
    """
    return _licence_findings(ctx, frozenset({Standing.REVOKED}))


RULES: Final[tuple[Callable[[RuleContext], Finding | None], ...]] = (
    r_t2_mailing_too_far,
    r_d2_attempts_contradicted,
    r_t1_mailing_missing,
    r_t3_proof_filed_late,
    r_d1_thin_diligence,
    r_m1_method_unknown,
)
"""Ordered strongest first, so a stable sort by severity leaves this order inside each band."""

MULTI_RULES: Final[tuple[Callable[[RuleContext], list[Finding]], ...]] = (
    r_l1_licence_unknown,
    r_l2_licence_not_in_force,
    r_l3_licence_revoked,
)
"""Rules that can produce more than one finding, because an affidavit carries two licence
numbers and the register can object to both. Kept as a separate list rather than widening
every rule above to return a list: six working rules answer a simpler question and there is
no reason to make them all say so in a more complicated way."""


def check_rules(
    affidavit: Affidavit, verdicts: list[ClaimVerdict], params: EngineParams
) -> list[Finding]:
    ctx = RuleContext(affidavit=affidavit, verdicts=verdicts, tz=ZoneInfo(params.tz))
    findings = [finding for rule in RULES if (finding := rule(ctx)) is not None]
    for multi in MULTI_RULES:
        findings.extend(multi(ctx))
    return findings
