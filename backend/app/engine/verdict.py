"""Combine claim verdicts and findings into one case verdict. Bible §11.1.6.

Deterministic apart from `generated_at`: the same request always produces the same
verdicts, the same findings in the same order, and the same numbers. That is what makes
the golden snapshots in the test suite worth having.

**How `overall` is decided, and one deliberate deviation.** Bible §11.1.6 reads "strongest
CONTRADICTED across claims, else CONSISTENT if the main claim is consistent". Taken
literally that lets a contradicted *attempt* set the headline. A 308(4) affidavit carries
attempts on other days, and someone who was demonstrably home at 7 PM was very likely at
work during a 10:30 AM attempt three weeks earlier — so the literal reading would headline
"your location data conflicts with the affidavit" for a user whose data *supports* the
service claim. Bible §6 defines CONTRADICTED as being far from **the claimed service point
at the claimed time**, and calls showing a consistent result honestly a feature. So:

1. the service claim contradicted -> CONTRADICTED;
2. the service claim consistent -> CONSISTENT, whatever the attempts say;
3. otherwise a contradicted attempt still sets CONTRADICTED, because burying a strong
   conflict under "we don't have data for that time" would be its own dishonesty;
4. otherwise the service claim's own tier.

Nothing is hidden either way: a contradicted attempt always produces its own STRONG
finding and R-D2, and findings are sorted strongest first.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.config import ENGINE_VERSION
from app.documents.deadlines import compute_deadlines
from app.domain.models import (
    Affidavit,
    AnalyzeRequest,
    CaseAnalysis,
    ClaimTier,
    ClaimVerdict,
    Finding,
    LatLng,
    LocationFix,
    Severity,
)
from app.engine import copy
from app.engine.description import check_description
from app.engine.feasibility import build_index, evaluate_prepared
from app.engine.params import PARAMS, PARAMS_VERSION, EngineParams
from app.engine.rules_ny import check_rules

MAIN_CLAIM = "served_at"

_SEVERITY_ORDER = {Severity.STRONG: 0, Severity.MODERATE: 1, Severity.INFO: 2}


def claims_of(affidavit: Affidavit) -> list[tuple[str, datetime, LatLng | None]]:
    """Every sworn moment in the affidavit that the user's data can speak to."""
    claims: list[tuple[str, datetime, LatLng | None]] = [
        (MAIN_CLAIM, affidavit.served_at, affidavit.served_location)
    ]
    claims.extend(
        (f"attempt[{i}]", attempt.at, attempt.location)
        for i, attempt in enumerate(affidavit.attempts)
    )
    return claims


def _overall(verdicts: list[ClaimVerdict]) -> ClaimTier:
    main = next((v for v in verdicts if v.claim_ref == MAIN_CLAIM), None)
    if main is not None and main.tier in (ClaimTier.CONTRADICTED, ClaimTier.CONSISTENT):
        return main.tier
    if any(v.tier is ClaimTier.CONTRADICTED for v in verdicts):
        return ClaimTier.CONTRADICTED
    return main.tier if main is not None else ClaimTier.NO_DATA


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Strongest first. Stable, so each rule module's own order survives inside a band."""
    return sorted(findings, key=lambda f: _SEVERITY_ORDER[f.severity])


def analyze(request: AnalyzeRequest, params: EngineParams = PARAMS) -> CaseAnalysis:
    affidavit = request.affidavit
    fixes: list[LocationFix] = request.fixes
    verdicts: list[ClaimVerdict] = []
    findings: list[Finding] = []
    # One index for every claim in the request: an affidavit with three prior attempts
    # asks four questions of the same export.
    index = build_index(fixes)

    for claim_ref, claimed_at, location in claims_of(affidavit):
        if location is None:
            # An address GeoSearch could not resolve. The location check cannot run for
            # this claim, but the paperwork rules still can, so this is a stated gap
            # rather than a refusal.
            title, detail = copy.no_coordinates(claim_ref, claimed_at)
            findings.append(
                Finding(
                    code="F-NOGEO",
                    severity=Severity.INFO,
                    title=title,
                    detail=detail,
                    numbers={"claim": claim_ref},
                )
            )
            continue

        verdict, claim_findings = evaluate_prepared(claim_ref, claimed_at, location, index, params)
        verdicts.append(verdict)
        if claim_ref == MAIN_CLAIM:
            findings.extend(claim_findings)
        else:
            # An attempt that produced nothing but "no data for that time" is noise on a
            # report about the service. An attempt the data conflicts with is not, and it
            # carries the numbers R-D2 only counts.
            findings.extend(f for f in claim_findings if f.severity is not Severity.INFO)

    findings.extend(check_rules(affidavit, verdicts, params))
    findings.extend(check_description(affidavit, request.household, params))

    return CaseAnalysis(
        affidavit=affidavit,
        verdicts=verdicts,
        findings=sort_findings(findings),
        overall=_overall(verdicts),
        deadlines=compute_deadlines(request.knowledge_date, request.judgment_entry_date),
        params_version=PARAMS_VERSION,
        engine_version=ENGINE_VERSION,
        generated_at=datetime.now(UTC),
    )
