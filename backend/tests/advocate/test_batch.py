"""The attorney-edition batch: rule rates, agency rollup, ranking, exports, report.

Build prompt §6.5. The fixture (`fixtures/advocate_batch/`) is 60 synthetic affidavits with
patterns injected on purpose and an answer key written by the generator, never by the code
under test. Regenerate it with

    cd backend && PYTHONPATH=.. uv run python -m fixtures.generator.advocate_batch

and regenerate the report snapshot, reading the diff, with

    cd backend && PYTHONPATH=.. uv run python -m tests.advocate.test_batch
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.advocate.batch import (
    UNKNOWN_AGENCY,
    agency_of,
    analyze_batch,
    rates,
    rule_flags,
)
from app.documents.advocate_report import report_context
from app.domain.models import (
    Affidavit,
    AffidavitRuleFlag,
    BatchReport,
    BatchReportRequest,
    ServiceMethod,
)
from app.engine.params import PARAMS

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "advocate_batch"
GOLDEN = Path(__file__).resolve().parent / "golden" / "batch_report.json"
FIXED = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)


def load() -> list[Affidavit]:
    rows = json.loads((FIXTURE / "affidavits.json").read_text(encoding="utf-8"))
    return [Affidavit.model_validate(row) for row in rows]


def expected() -> dict[str, Any]:
    return json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def report() -> BatchReport:
    return analyze_batch(load(), PARAMS).model_copy(update={"generated_at": FIXED})


# --- agency normalisation ---------------------------------------------------------------


def _with(**changes: Any) -> Affidavit:
    return load()[0].model_copy(update=changes)


def test_the_agency_licence_is_the_key_when_printed() -> None:
    a = _with(agency_license="0012345-DCA", agency_name="Rapid Legal Services, Inc.")
    b = _with(agency_license="12345", agency_name="RAPID LEGAL SVC")
    assert agency_of(a)[0] == agency_of(b)[0] == "lic:12345"
    assert agency_of(a)[1] == "Rapid Legal Services, Inc."


def test_names_typed_differently_are_one_agency() -> None:
    a = _with(agency_license=None, agency_name="Rapid Legal Services, Inc.")
    b = _with(agency_license=None, agency_name="RAPID LEGAL SERVICES INC")
    assert agency_of(a)[0] == agency_of(b)[0] == "name:RAPID LEGAL SERVICES"


def test_an_affidavit_naming_no_agency_is_unknown() -> None:
    assert agency_of(_with(agency_license=None, agency_name=None))[0] == UNKNOWN_AGENCY


# --- rule-rate math ---------------------------------------------------------------------


def test_a_rate_is_flagged_out_of_applicable_not_out_of_everything() -> None:
    flags = [
        AffidavitRuleFlag(
            index=i, case_ref=None, server_id="s", agency_key="a", rule_code=code, flagged=hit
        )
        for i, (code, hit) in enumerate(
            [("R-T1", True), ("R-T1", False), ("R-T1", False), ("R-T1", True), ("R-M1", False)]
        )
    ]
    (t1, m1) = rates(flags)
    assert (t1.rule_code, t1.flagged, t1.applicable, t1.rate) == ("R-T1", 2, 4, 0.5)
    assert (m1.flagged, m1.applicable, m1.rate) == (0, 1, 0.0)


def test_a_personal_service_is_not_in_the_mailing_denominators() -> None:
    personal = _with(method=ServiceMethod.PERSONAL, mailing_date=None)
    codes = {flag.rule_code for flag in rule_flags(0, personal, PARAMS)}
    assert codes == {"R-M1"}


def test_r_t2_needs_a_mailing_date_to_apply() -> None:
    missing = _with(method=ServiceMethod.SUBSTITUTE, mailing_date=None)
    flags = {f.rule_code: f.flagged for f in rule_flags(0, missing, PARAMS)}
    assert flags["R-T1"] is True
    assert "R-T2" not in flags


def test_r_d2_is_never_a_batch_rule(report: BatchReport) -> None:
    """It needs a defendant's location data, which a batch does not have."""
    assert all(flag.rule_code != "R-D2" for flag in report.flags)
    assert all(rate.rule_code != "R-D2" for rate in report.rule_rates)


def test_rules_that_applied_to_nothing_are_left_out() -> None:
    assert rates([]) == []


# --- the fixture, end to end ------------------------------------------------------------


def test_every_injected_impossible_pair_is_found(report: BatchReport) -> None:
    by_server = {s.server_id: len(s.impossible_pairs) for s in report.servers}
    for server, n in expected()["impossible_pairs"].items():
        assert by_server[server] == n
    assert sum(by_server.values()) == sum(expected()["impossible_pairs"].values())


def test_every_injected_rule_flag_is_found_and_nothing_else(report: BatchReport) -> None:
    for code, indexes in expected()["flagged"].items():
        assert sorted(f.index for f in report.flags if f.rule_code == code and f.flagged) == sorted(
            indexes
        ), code
    flagged_codes = {f.rule_code for f in report.flags if f.flagged}
    assert flagged_codes == set(expected()["flagged"])


def test_the_repeated_description_is_found_once(report: BatchReport) -> None:
    want = expected()["repeated_description"]
    found = [(s.server_id, d) for s in report.servers for d in s.repeated_descriptions]
    assert found == [(want["server"], (want["text"], want["addresses"]))]


def test_the_clean_agency_has_nothing(report: BatchReport) -> None:
    clean = next(a for a in report.agencies if a.agency_display == expected()["clean_agency"])
    assert clean.impossible_pairs == 0
    assert clean.repeated_descriptions == []
    assert all(rate.flagged == 0 for rate in clean.rule_rates)
    assert clean.risk_rank == len(report.agencies)


def test_agencies_rank_by_pairs_then_rates(report: BatchReport) -> None:
    order = [a.agency_display for a in report.agencies]
    assert order == [
        "Kestrel Legal Support Services Inc.",
        "Ironvale Attorney Service Corp.",
        "Halloway & Finch Process Servers LLC",
    ]
    assert [a.risk_rank for a in report.agencies] == [1, 2, 3]
    assert all(a.n_affidavits == 20 and len(a.servers) == 2 for a in report.agencies)


def test_an_r_t2_rate_outranks_repeated_descriptions() -> None:
    """Build prompt §6.3: pairs, then the R-T2 rate, then repeated descriptions."""
    affidavits = load()
    late = [
        a.model_copy(
            update={
                "agency_name": "Late Mail Co",
                "method": ServiceMethod.SUBSTITUTE,
                "mailing_date": a.served_at.date().replace(day=1).replace(year=2026),
            }
        )
        for a in affidavits[40:43]
    ]
    result = analyze_batch(affidavits + late, PARAMS)
    ranked = [a.agency_display for a in result.agencies]
    assert ranked.index("Late Mail Co") < ranked.index("Ironvale Attorney Service Corp.")
    assert ranked[0] == "Kestrel Legal Support Services Inc."


def test_unconfirmed_affidavits_are_listed_and_never_counted() -> None:
    affidavits = load()
    affidavits[3] = affidavits[3].model_copy(update={"user_confirmed": False})
    result = analyze_batch(affidavits, PARAMS)
    assert [(r.index, r.code) for r in result.rejected] == [(3, "unconfirmed")]
    assert all(flag.index != 3 for flag in result.flags)
    assert sum(a.n_affidavits for a in result.agencies) == 59


# --- routes, exports and the report ---------------------------------------------------------


def _payload() -> list[dict[str, Any]]:
    return [json.loads(a.model_dump_json()) for a in load()]


def test_the_batch_route_returns_the_report(client: TestClient) -> None:
    response = client.post("/api/advocate/batch", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["n_affidavits"] == 60
    assert body["app_version"] and body["engine_version"] and body["params_version"]
    assert len(body["agencies"]) == 3


@pytest.mark.parametrize("kind", ["pairs", "flags", "agencies"])
def test_every_csv_export_reads_back(client: TestClient, report: BatchReport, kind: str) -> None:
    response = client.post(
        f"/api/advocate/batch/export.csv?kind={kind}", json=json.loads(report.model_dump_json())
    )
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    if kind == "pairs":
        assert len(rows) == 1 + 2
    elif kind == "flags":
        assert len(rows) == 1 + len(report.flags)
        assert sum(r[5] == "yes" for r in rows[1:]) == 9  # 4 x R-T1, 5 x R-D1
    else:
        assert [r[2] for r in rows[1:]] == [a.agency_display for a in report.agencies]
        assert rows[1][AGENCY_T1] == "4/15"


AGENCY_T1 = 8


def test_an_unknown_export_is_refused(client: TestClient, report: BatchReport) -> None:
    response = client.post(
        "/api/advocate/batch/export.csv?kind=everything",
        json=json.loads(report.model_dump_json()),
    )
    assert response.status_code == 400


def snapshot(report: BatchReport) -> dict[str, Any]:
    return report_context(BatchReportRequest(report=report, unconfirmed=2, failed=1))


def test_the_report_reads_as_it_did(report: BatchReport) -> None:
    """Every sentence and number of the report, pinned (`tasks/lessons.md`)."""
    assert json.loads(json.dumps(snapshot(report), sort_keys=True, default=str)) == json.loads(
        GOLDEN.read_text(encoding="utf-8")
    )


def test_the_report_footer_is_the_required_sentence(report: BatchReport) -> None:
    assert snapshot(report)["disclaimer"] == (
        "Analysis of documents supplied by the user. Data conflicts are not findings of misconduct."
    )


def test_the_report_renders_to_pdf(needs_pdf: None, report: BatchReport) -> None:
    from app.documents.advocate_report import build_report

    pdf = build_report(BatchReportRequest(report=report))
    assert pdf.startswith(b"%PDF")


def regenerate() -> None:  # pragma: no cover - a maintenance command, not a test
    data = analyze_batch(load(), PARAMS).model_copy(update={"generated_at": FIXED})
    GOLDEN.parent.mkdir(exist_ok=True)
    GOLDEN.write_text(json.dumps(snapshot(data), indent=1, sort_keys=True, default=str) + "\n")
    print(f"wrote {GOLDEN}")


if __name__ == "__main__":  # pragma: no cover
    regenerate()
