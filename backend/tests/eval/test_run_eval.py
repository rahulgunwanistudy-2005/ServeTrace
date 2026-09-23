"""The eval's own arithmetic.

Published numbers are only as trustworthy as the code that counts them, and this is the
code that decides what goes on the Methodology page. It is scored here on hand-written
rows rather than on the corpus, so a change in the engine cannot quietly change what
"accuracy" means.
"""

from __future__ import annotations

from app.domain.models import ServiceMethod
from eval.run_eval import CaseResult, build_report, format_report


def row(
    case_id: str = "case_x",
    *,
    true_tier: str = "contradicted",
    claim_tier: str | None = None,
    overall_tier: str | None = None,
    false_accusation: bool = False,
    kind: str = "contradicted",
    edge_kind: str | None = None,
    seeded: tuple[str, ...] = (),
    found: tuple[str, ...] = (),
    method: ServiceMethod = ServiceMethod.SUBSTITUTE,
    description_expected_match: bool = True,
    description_flagged: bool = False,
    description_scored: bool = True,
) -> CaseResult:
    return CaseResult(
        case_id=case_id,
        kind=kind,
        edge_kind=edge_kind,
        true_tier=true_tier,
        claim_tier=claim_tier or true_tier,
        overall_tier=overall_tier or claim_tier or true_tier,
        false_accusation=false_accusation,
        nearest_fix_km=1.0,
        required_speed_kmh=None,
        seeded_rule_codes=list(seeded),
        found_rule_codes=list(found),
        description_expected_match=description_expected_match,
        description_flagged=description_flagged,
        description_scored=description_scored,
        method=method,
        latency_ms=1.0,
    )


def test_accuracy_counts_agreement_with_the_generators_label() -> None:
    report = build_report([row(), row(true_tier="consistent", claim_tier="inconclusive")])
    assert report.claim_accuracy == 0.5


def test_claim_and_overall_accuracy_are_counted_separately() -> None:
    """They answer different questions, and blending them would hide which one moved."""
    report = build_report(
        [
            row(claim_tier="contradicted", overall_tier="contradicted"),
            row(true_tier="no_data", claim_tier="no_data", overall_tier="contradicted"),
        ]
    )
    assert (report.claim_accuracy, report.overall_accuracy) == (1.0, 0.5)


def test_the_matrix_accounts_for_every_case() -> None:
    rows = [row(), row(true_tier="consistent"), row(true_tier="consistent", claim_tier="no_data")]
    report = build_report(rows)
    assert report.claim_matrix["consistent"]["consistent"] == 1
    assert report.claim_matrix["consistent"]["no_data"] == 1
    assert sum(sum(r.values()) for r in report.claim_matrix.values()) == 3


def test_false_accusations_are_named_not_just_counted() -> None:
    report = build_report([row("case_bad", false_accusation=True), row("case_ok")])
    assert report.false_accusations == 1
    assert report.false_accusation_cases == ["case_bad"]


def test_a_rule_seeded_outside_its_own_scope_is_not_counted_as_a_miss() -> None:
    """Bible §11.3 scopes R-T3 to 308(2) and 308(4). The generator seeds it on personal
    service too, and the engine is right to stay quiet there."""
    report = build_report([row(seeded=("R-T3",), method=ServiceMethod.PERSONAL)])
    assert report.rule_recall["R-T3"] == {
        "seeded": 0,
        "found": 0,
        "missed": 0,
        "extra": 0,
        "out_of_scope": 1,
    }


def test_a_rule_seeded_in_scope_and_missed_is_counted_as_a_miss() -> None:
    report = build_report([row(seeded=("R-T3",), method=ServiceMethod.SUBSTITUTE)])
    assert report.rule_recall["R-T3"]["missed"] == 1


def test_a_rule_found_without_being_seeded_is_reported_but_not_as_an_error() -> None:
    """The generator seeds *some* violations on purpose; others fall out of the dates it
    happens to draw, and reporting those is the engine working."""
    report = build_report([row(found=("R-T1",))])
    assert report.rule_recall["R-T1"] == {
        "seeded": 0,
        "found": 0,
        "missed": 0,
        "extra": 1,
        "out_of_scope": 0,
    }


def test_the_description_score_separates_misses_from_false_flags() -> None:
    rows = [
        row(description_expected_match=False, description_flagged=True),
        row(description_expected_match=False, description_flagged=False),
        row(description_expected_match=True, description_flagged=True),
    ]
    scores = build_report(rows).description
    assert (scores["mismatches_caught"], scores["mismatches_total"]) == (1, 2)
    assert scores["false_flags"] == 1
    assert scores["recall"] == 0.5


def test_cases_the_check_does_not_run_on_are_excluded_from_its_denominator() -> None:
    rows = [
        row(description_scored=False),
        row(description_expected_match=False, description_flagged=True),
    ]
    scores = build_report(rows).description
    assert scores["n_scored"] == 1 and scores["n_skipped_by_method"] == 1


def test_edge_kinds_are_grouped_on_their_own() -> None:
    rows = [row(kind="edge", edge_kind="dst_fold", true_tier="consistent"), row()]
    report = build_report(rows)
    assert set(report.by_edge_kind) == {"dst_fold"}
    assert report.by_edge_kind["dst_fold"]["n"] == 1


def test_disagreements_list_every_case_either_number_got_wrong() -> None:
    rows = [
        row(),
        row("case_y", true_tier="no_data", claim_tier="no_data", overall_tier="contradicted"),
    ]
    assert [d["case_id"] for d in build_report(rows).disagreements] == ["case_y"]


def test_the_printed_report_leads_with_the_number_that_matters() -> None:
    text = format_report(build_report([row(false_accusation=True)]))
    headline = next(line for line in text.splitlines() if line.strip())
    assert "FALSE CONTRADICTIONS" in text
    assert text.index("FALSE CONTRADICTIONS") < text.index("accuracy")
    assert headline.startswith("ServeTrace")
