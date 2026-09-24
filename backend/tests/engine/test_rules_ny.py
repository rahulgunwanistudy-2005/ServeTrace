"""Bible §11.3, rule by rule, plus the promise that every legal statement carries its L-id."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain.models import ClaimTier, ClaimVerdict, ServiceAttempt, ServiceMethod, Severity
from app.engine import copy
from app.engine.params import PARAMS
from app.engine.rules_ny import (
    MAIL_WINDOW_DAYS,
    PROOF_FILING_DAYS,
    RULES,
    check_rules,
)
from tests.engine.conftest import CLAIM_AT, DOOR, affidavit, ny

SERVED_DATE = CLAIM_AT.date()


def rules(method=ServiceMethod.SUBSTITUTE, verdicts=None, **overrides) -> dict[str, object]:
    findings = check_rules(affidavit(method=method, **overrides), verdicts or [], PARAMS)
    return {f.code: f for f in findings}


def attempt(when, outcome: str = "not_home") -> ServiceAttempt:
    return ServiceAttempt(
        at=when, address="2100 WHITE PLAINS ROAD, Bronx, NY 10462", location=DOOR, outcome=outcome
    )


def attempt_verdict(index: int, tier: ClaimTier) -> ClaimVerdict:
    return ClaimVerdict(
        claim_ref=f"attempt[{index}]", claimed_at=CLAIM_AT, claimed_location=DOOR, tier=tier
    )


# --- R-T1: the mailing is missing ---------------------------------------------------------


@pytest.mark.parametrize("method", [ServiceMethod.SUBSTITUTE, ServiceMethod.AFFIX_AND_MAIL])
def test_r_t1_fires_when_no_mailing_date_is_given(method: ServiceMethod) -> None:
    finding = rules(method, mailing_date=None)["R-T1"]
    assert finding.severity is Severity.MODERATE
    assert finding.legal_ref == ("L3" if method is ServiceMethod.AFFIX_AND_MAIL else "L2")


def test_r_t1_does_not_apply_to_personal_delivery() -> None:
    """L1 is handing the papers over. There is no mailing to be missing."""
    assert "R-T1" not in rules(ServiceMethod.PERSONAL, mailing_date=None)


# --- R-T2: the mailing is too far from the delivery ---------------------------------------


@pytest.mark.parametrize("days", [MAIL_WINDOW_DAYS + 1, 34, 60])
def test_r_t2_fires_past_the_statutory_window(days: int) -> None:
    finding = rules(mailing_date=SERVED_DATE + timedelta(days=days))["R-T2"]
    assert finding.severity is Severity.STRONG
    assert finding.numbers == {"days": days, "limit_days": MAIL_WINDOW_DAYS}


@pytest.mark.parametrize("days", [0, 1, MAIL_WINDOW_DAYS])
def test_r_t2_stays_quiet_inside_it(days: int) -> None:
    assert "R-T2" not in rules(mailing_date=SERVED_DATE + timedelta(days=days))


def test_r_t2_counts_a_mailing_before_the_delivery_too() -> None:
    """Bible §11.3 says the absolute difference, and a copy posted five weeks early is
    just as far outside the window as one posted five weeks late."""
    assert "R-T2" in rules(mailing_date=SERVED_DATE - timedelta(days=35))


# --- R-T3: proof of service filed late ----------------------------------------------------


def test_r_t3_counts_from_the_later_of_delivery_and_mailing() -> None:
    mailing = SERVED_DATE + timedelta(days=10)
    finding = rules(
        mailing_date=mailing, proof_filed_date=mailing + timedelta(days=PROOF_FILING_DAYS + 1)
    )["R-T3"]
    assert finding.severity is Severity.MODERATE
    assert finding.numbers["days"] == PROOF_FILING_DAYS + 1


def test_r_t3_stays_quiet_on_the_boundary() -> None:
    mailing = SERVED_DATE + timedelta(days=10)
    assert "R-T3" not in rules(
        mailing_date=mailing, proof_filed_date=mailing + timedelta(days=PROOF_FILING_DAYS)
    )


def test_r_t3_needs_a_filing_date_to_say_anything() -> None:
    assert "R-T3" not in rules(proof_filed_date=None)


def test_r_t3_does_not_apply_to_personal_delivery() -> None:
    """Bible §11.3 scopes it to 308(2) and 308(4), and bible §5 gives no authority for a
    filing deadline on personal delivery. The corpus seeds some anyway; obeying §5 and
    staying quiet is the right answer, and the eval counts those separately."""
    assert "R-T3" not in rules(
        ServiceMethod.PERSONAL,
        mailing_date=None,
        proof_filed_date=SERVED_DATE + timedelta(days=45),
    )


# --- R-D1: due diligence before affix-and-mail --------------------------------------------

DILIGENT = [
    attempt(ny(7, 40, day=4)),
    attempt(ny(13, 15, day=7)),
    attempt(ny(20, 5, day=10)),
]
"""Three attempts, three different days, morning / afternoon / evening. L4's pattern."""


def test_r_d1_stays_quiet_on_a_diligent_pattern() -> None:
    assert "R-D1" not in rules(ServiceMethod.AFFIX_AND_MAIL, attempts=DILIGENT)


def test_r_d1_fires_on_too_few_attempts() -> None:
    finding = rules(ServiceMethod.AFFIX_AND_MAIL, attempts=DILIGENT[:2])["R-D1"]
    assert finding.severity is Severity.MODERATE
    assert finding.legal_ref == "L4"
    assert finding.numbers["attempts"] == 2


def test_r_d1_fires_when_every_attempt_is_on_one_day() -> None:
    same_day = [attempt(ny(7, 40, day=4)), attempt(ny(13, 15, day=4)), attempt(ny(20, 5, day=4))]
    assert finding_reasons(rules(ServiceMethod.AFFIX_AND_MAIL, attempts=same_day)["R-D1"])[1] == 1


def test_r_d1_fires_when_every_attempt_is_inside_office_hours() -> None:
    # 4, 11 and 18 June 2025 are all Wednesdays.
    office = [attempt(ny(10, 0, day=4)), attempt(ny(11, 0, day=11)), attempt(ny(16, 0, day=18))]
    finding = rules(ServiceMethod.AFFIX_AND_MAIL, attempts=office)["R-D1"]
    assert finding.numbers["attempts"] == 3 and finding.numbers["distinct_days"] == 3


def test_a_weekend_attempt_breaks_the_office_hours_pattern() -> None:
    """14 June 2025 is a Saturday, so this set is not "only ever in a working week"."""
    mixed = [attempt(ny(10, 0, day=4)), attempt(ny(11, 0, day=11)), attempt(ny(11, 0, day=14))]
    assert "R-D1" not in rules(ServiceMethod.AFFIX_AND_MAIL, attempts=mixed)


def test_r_d1_says_no_attempts_at_all_rather_than_zero() -> None:
    finding = rules(ServiceMethod.AFFIX_AND_MAIL, attempts=[])["R-D1"]
    assert "no earlier attempts" in finding.detail


def test_r_d1_does_not_apply_to_the_other_methods() -> None:
    for method in (ServiceMethod.PERSONAL, ServiceMethod.SUBSTITUTE):
        assert "R-D1" not in rules(method, attempts=[])


def finding_reasons(finding) -> tuple[int, int]:
    return int(finding.numbers["attempts"]), int(finding.numbers["distinct_days"])


# --- R-D2: the attempts themselves are contradicted ---------------------------------------


def test_r_d2_fires_when_an_attempt_verdict_is_contradicted() -> None:
    verdicts = [
        attempt_verdict(0, ClaimTier.CONTRADICTED),
        attempt_verdict(1, ClaimTier.CONSISTENT),
    ]
    finding = rules(ServiceMethod.AFFIX_AND_MAIL, verdicts=verdicts, attempts=DILIGENT)["R-D2"]
    assert finding.severity is Severity.STRONG
    assert finding.legal_ref == "L3"
    assert finding.numbers["attempts_contradicted"] == 1


def test_r_d2_ignores_the_service_claim_itself() -> None:
    main = ClaimVerdict(
        claim_ref="served_at",
        claimed_at=CLAIM_AT,
        claimed_location=DOOR,
        tier=ClaimTier.CONTRADICTED,
    )
    assert "R-D2" not in rules(ServiceMethod.AFFIX_AND_MAIL, verdicts=[main], attempts=DILIGENT)


# --- R-M1 ----------------------------------------------------------------------------------


def test_r_m1_reports_an_unknown_method_without_alarming_anyone() -> None:
    finding = rules(ServiceMethod.UNKNOWN)["R-M1"]
    assert finding.severity is Severity.INFO
    assert finding.legal_ref is None


def test_r_m1_stays_quiet_when_the_method_is_known() -> None:
    assert "R-M1" not in rules(ServiceMethod.SUBSTITUTE)


# --- Promises the whole module has to keep -------------------------------------------------


def test_every_rule_that_states_law_carries_its_l_id() -> None:
    """Bible §18.6: no legal statement outside §5, and each one says which row it came from."""
    stated = rules(
        ServiceMethod.AFFIX_AND_MAIL,
        verdicts=[attempt_verdict(0, ClaimTier.CONTRADICTED)],
        attempts=DILIGENT[:1],
        mailing_date=SERVED_DATE + timedelta(days=40),
        proof_filed_date=SERVED_DATE + timedelta(days=90),
    )
    assert {"R-T2", "R-T3", "R-D1", "R-D2"} <= set(stated)
    assert all(f.legal_ref in ("L1", "L2", "L3", "L4") for f in stated.values())


def test_the_registry_is_ordered_strongest_first() -> None:
    """A stable sort by severity later keeps this order inside each band, so it is the
    order of the report and worth asserting."""
    assert [rule.__name__ for rule in RULES][:2] == [
        "r_t2_mailing_too_far",
        "r_d2_attempts_contradicted",
    ]


def test_the_served_date_is_read_in_new_york_time() -> None:
    """Just before midnight in New York is already tomorrow in UTC. A rule that counted
    days in UTC would be a day out for every evening service."""
    late = ny(23, 30, day=30, month=6)
    finding = rules(served_at=late, mailing_date=date(2025, 7, 21))["R-T2"]
    assert finding.numbers["days"] == 21


def test_copy_never_states_a_fact_the_bible_does_not() -> None:
    """A smoke test on the wording itself: the two day counts are statute, so they must be
    the ones §5 gives, and no other number may appear as a deadline."""
    _, detail = copy.mailing_too_late(34, MAIL_WINDOW_DAYS)
    assert "20 days" in detail
    _, detail = copy.proof_filed_late(30, PROOF_FILING_DAYS)
    assert "20 days" in detail


class TestLicenceRules:
    """R-L1..R-L3 against the City's register. Bible §5 L7.

    The numbers come out of the committed register at test time rather than being pinned,
    so a refresh cannot silently turn these into tests of a stale snapshot.
    """

    @staticmethod
    def _findings(**overrides: object) -> list[object]:
        return [
            f for f in check_rules(affidavit(**overrides), [], PARAMS) if f.code.startswith("R-L")
        ]

    @staticmethod
    def _earliest_expired() -> str | None:
        import json

        from app.licences.registry import CACHE_PATH

        rows = [
            r
            for r in json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if r["status"].strip().lower() == "expired"
            and r["category"] == "individual"
            and r.get("expires")
        ]
        rows.sort(key=lambda r: r["expires"])
        return str(rows[0]["number"]) if rows else None

    @staticmethod
    def _real(status: str, category: str = "individual") -> str | None:
        import json

        from app.licences.registry import CACHE_PATH

        for row in json.loads(CACHE_PATH.read_text(encoding="utf-8")):
            if row["status"].strip().lower() == status and row["category"] == category:
                return str(row["number"])
        return None

    def test_an_affidavit_with_no_licence_number_raises_nothing(self) -> None:
        """The demo fixtures are this case, and it is the common one on a real affidavit
        that simply did not print the number. Silence, not a finding."""
        assert self._findings(server_license=None, agency_license=None) == []

    def test_a_number_that_is_not_in_the_register_raises_r_l1(self) -> None:
        found = self._findings(server_license="9999999")
        assert [f.code for f in found] == ["R-L1"]
        assert found[0].severity is Severity.MODERATE
        assert found[0].legal_ref == "L7"

    def test_both_numbers_are_checked_independently(self) -> None:
        """An affidavit carries two, and the register can object to both. This is the
        reason the licence rules return a list where every other rule returns one."""
        found = self._findings(server_license="9999999", agency_license="9999998")
        assert [f.code for f in found] == ["R-L1", "R-L1"]
        assert "server" in found[0].title and "agency" in found[1].title

    def test_a_licence_that_had_expired_before_the_service_raises_r_l2(self) -> None:
        from app.licences.registry import LicenceCategory, look_up

        number = self._earliest_expired()
        assert number is not None
        licence = look_up(number, LicenceCategory.INDIVIDUAL)
        assert licence is not None and licence.expires is not None
        # The earliest-expiring licence in the register, so "two years later" is still a
        # date in the past and the affidavit is not sworn to a service in the future.
        served = ny(19, 42, 12, 6, licence.expires.year + 2)
        found = self._findings(server_license=number, served_at=served)
        assert [f.code for f in found] == ["R-L2"]
        assert found[0].legal_ref == "L7"
        # The machine-readable field, not the sentence: the prose belongs to `copy` and
        # has to stay free to change.
        assert found[0].numbers["expired"] == licence.expires.isoformat()

    def test_an_agency_number_is_not_accepted_as_a_server_number(self) -> None:
        """Separate registers. A real agency licence quoted as the server's licence is
        still not in the server register, and the engine must say so."""
        agency = self._real("active", category="agency")
        assert agency is not None
        found = self._findings(server_license=agency, agency_license=None)
        assert [f.code for f in found] == ["R-L1"]

    def test_the_licence_findings_never_reach_the_sworn_document(self) -> None:
        """Bible §15 and the S7 rule that a code with no paragraph produces no paragraph.
        A register snapshot is not something a person should attest to."""
        from app.documents.affidavit import EXCLUDED_CODES

        assert {"R-L1", "R-L2", "R-L3"} <= EXCLUDED_CODES
