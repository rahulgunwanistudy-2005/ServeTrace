"""Assembling one case verdict out of many claims. Bible §11.1.6."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.config import ENGINE_VERSION
from app.domain.models import (
    AnalyzeRequest,
    ClaimTier,
    ServiceAttempt,
    ServiceMethod,
    Severity,
)
from app.engine.params import PARAMS_VERSION
from app.engine.verdict import analyze, claims_of, sort_findings
from tests.engine.conftest import CLAIM_AT, DOOR, affidavit, away, fix, member, ny, visit


def request(fixes=None, household=None, **affidavit_fields) -> AnalyzeRequest:
    return AnalyzeRequest(
        affidavit=affidavit(**affidavit_fields),
        fixes=fixes or [],
        household=household or [],
    )


AT_WORK = visit(CLAIM_AT - timedelta(hours=4), 480, away(14.0))
AT_HOME = visit(CLAIM_AT - timedelta(hours=1), 180, DOOR)


def attempt(when, location=DOOR) -> ServiceAttempt:
    return ServiceAttempt(
        at=when,
        address="2100 WHITE PLAINS ROAD, Bronx, NY 10462",
        location=location,
        outcome="not_home",
    )


# --- Claims ------------------------------------------------------------------------------


def test_the_service_and_every_attempt_are_claims() -> None:
    aff = affidavit(
        method=ServiceMethod.AFFIX_AND_MAIL,
        attempts=[attempt(ny(10, 30, day=5)), attempt(ny(11, 0, day=9))],
    )
    assert [ref for ref, _, _ in claims_of(aff)] == ["served_at", "attempt[0]", "attempt[1]"]


def test_a_claim_with_no_coordinates_is_reported_not_refused() -> None:
    """GeoSearch cannot resolve every address, and the paperwork rules still apply."""
    analysis = analyze(request(fixes=[AT_WORK], served_location=None))
    assert analysis.verdicts == []
    assert [f.code for f in analysis.findings if f.code == "F-NOGEO"] == ["F-NOGEO"]
    assert analysis.overall is ClaimTier.NO_DATA


# --- Overall ------------------------------------------------------------------------------


def test_a_contradicted_service_claim_makes_the_case_contradicted() -> None:
    assert analyze(request(fixes=[AT_WORK])).overall is ClaimTier.CONTRADICTED


def test_a_consistent_service_claim_is_reported_honestly() -> None:
    """Bible §6: showing this is a feature, not a failure to find something."""
    assert analyze(request(fixes=[AT_HOME])).overall is ClaimTier.CONSISTENT


def test_no_fixes_at_all_is_no_data_not_a_verdict() -> None:
    assert analyze(request()).overall is ClaimTier.NO_DATA


def test_a_consistent_service_claim_survives_a_contradicted_attempt() -> None:
    """The deviation from a literal §11.1.6, and the reason for it.

    The user was demonstrably at their own door when the papers are said to have arrived.
    Headlining "your location data conflicts with the affidavit" because they were at work
    during an attempt three weeks earlier would contradict what bible §6 says that headline
    means. The attempt is still reported, strongly.
    """
    earlier = CLAIM_AT - timedelta(days=21)
    analysis = analyze(
        request(
            method=ServiceMethod.AFFIX_AND_MAIL,
            attempts=[attempt(earlier)],
            fixes=[AT_HOME, visit(earlier - timedelta(hours=2), 240, away(14.0))],
        )
    )
    assert analysis.overall is ClaimTier.CONSISTENT
    codes = {f.code for f in analysis.findings}
    assert {"F-VISIT", "R-D2"} <= codes


def test_an_unsettled_service_claim_does_not_bury_a_contradicted_attempt() -> None:
    """The other half of that decision. "We have no data for that time" as a headline,
    with a strong conflict hidden below it, would be its own kind of dishonest."""
    earlier = CLAIM_AT - timedelta(days=21)
    analysis = analyze(
        request(
            method=ServiceMethod.AFFIX_AND_MAIL,
            attempts=[attempt(earlier)],
            fixes=[visit(earlier - timedelta(hours=2), 240, away(14.0))],
        )
    )
    assert analysis.overall is ClaimTier.CONTRADICTED


# --- Findings -----------------------------------------------------------------------------


def test_findings_are_sorted_strongest_first() -> None:
    analysis = analyze(
        request(
            fixes=[AT_WORK],
            mailing_date=CLAIM_AT.date() + timedelta(days=40),
            recipient_description={"sex": "male", "age_min": 70, "age_max": 80},
            household=[member("Me", sex="female", age=34, is_defendant=True)],
        )
    )
    order = [f.severity for f in analysis.findings]
    assert order == sorted(order, key=lambda s: {"strong": 0, "moderate": 1, "info": 2}[s.value])
    assert {"F-VISIT", "R-T2", "F-DESC"} <= {f.code for f in analysis.findings}


def test_sorting_is_stable_inside_a_severity_band() -> None:
    """So the rule registry's own order is the order of the report."""
    from app.domain.models import Finding

    band = [
        Finding(code="A", severity=Severity.MODERATE, title="a", detail=""),
        Finding(code="B", severity=Severity.MODERATE, title="b", detail=""),
        Finding(code="C", severity=Severity.STRONG, title="c", detail=""),
    ]
    assert [f.code for f in sort_findings(band)] == ["C", "A", "B"]


def test_an_attempt_contributes_its_conflict_but_not_its_noise() -> None:
    """Three attempts with nothing recorded near them would otherwise add three
    "no data for that time" notes to a report about the service."""
    earlier = [CLAIM_AT - timedelta(days=d) for d in (7, 14, 21)]
    analysis = analyze(
        request(
            method=ServiceMethod.AFFIX_AND_MAIL,
            attempts=[attempt(w) for w in earlier],
            fixes=[AT_HOME],
        )
    )
    assert [f.code for f in analysis.findings].count("F-NODATA") == 0


# --- Stamps and deadlines -------------------------------------------------------------------


def test_every_analysis_carries_the_versions_it_can_be_traced_back_to() -> None:
    analysis = analyze(request(fixes=[AT_HOME]))
    assert (analysis.params_version, analysis.engine_version) == (PARAMS_VERSION, ENGINE_VERSION)
    assert analysis.generated_at.tzinfo is not None


def test_the_deadline_clock_comes_through_the_analysis() -> None:
    body = AnalyzeRequest(
        affidavit=affidavit(),
        fixes=[AT_HOME],
        knowledge_date=date(2026, 3, 1),
        judgment_entry_date=date(2025, 1, 15),
    )
    deadlines = analyze(body).deadlines
    assert deadlines.cplr_317_deadline == date(2027, 3, 1)
    assert deadlines.cplr_317_outer_limit == date(2030, 1, 15)


def test_the_affidavit_is_echoed_back_unchanged() -> None:
    """The result page, the packet and the draft affidavit are all built from these fields,
    so the analysis has to carry exactly what it was given."""
    body = request(fixes=[AT_HOME])
    assert analyze(body).affidavit == body.affidavit


# --- Determinism ------------------------------------------------------------------------------


def test_the_same_request_twice_gives_the_same_answer() -> None:
    body = request(fixes=[AT_WORK, fix(CLAIM_AT - timedelta(minutes=20), away(9.0))])
    first, second = analyze(body), analyze(body)
    assert first.model_dump(exclude={"generated_at"}) == second.model_dump(exclude={"generated_at"})


@pytest.mark.parametrize("method", list(ServiceMethod))
def test_every_method_produces_an_analysis(method: ServiceMethod) -> None:
    analysis = analyze(request(method=method, fixes=[AT_HOME]))
    assert analysis.overall in set(ClaimTier)
