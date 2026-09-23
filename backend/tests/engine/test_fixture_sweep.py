"""The acceptance gate: the engine against 200 cases it has never seen labels for.

The labels come from `fixtures/generator`, which records where it *put* the person and
never asks the engine. That independence is the whole value of this file — a golden
snapshot can only tell us the engine has not changed, and this can tell us it is right.

The gate that matters is the first one. Everything else in here is reporting.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.run_eval import (
    PUBLISHED,
    TIERS,
    build_report,
    format_report,
    published_figures,
    score_corpus,
)

CORPUS = Path(__file__).resolve().parents[3] / "fixtures" / "out"


@pytest.fixture(scope="module")
def report():
    if not (CORPUS / "cases").is_dir():
        pytest.skip("corpus not generated; run `python -m fixtures.generator`")
    return build_report(score_corpus(CORPUS))


def test_no_false_accusations(report, capsys) -> None:
    """Zero cases the generator built as CONSISTENT where the engine contradicts strongly.

    This is the number the whole product rests on. Telling someone their own data conflicts
    with a sworn affidavit when it does not is the one failure that could hurt them in
    court, and no accuracy figure anywhere else buys it back.
    """
    with capsys.disabled():
        print("\n" + format_report(report) + "\n")
    assert report.false_accusations == 0, report.false_accusation_cases


def test_the_corpus_is_the_one_the_generator_was_asked_for(report) -> None:
    """A gate over five cases would pass for the wrong reason."""
    assert report.n_cases == 200


def test_every_claim_verdict_agrees_with_where_the_generator_put_the_person(report) -> None:
    """The like-for-like comparison: the generator labels the claimed service moment, so
    that is what the engine's verdict on that claim is scored against."""
    assert report.claim_accuracy == 1.0


def test_the_only_case_level_disagreements_are_about_prior_attempts(report) -> None:
    """`overall` also answers for the attempts a 308(4) affidavit swears to, which the
    generator does not label. Every disagreement must be one of those, and none may be a
    claim the engine read wrongly."""
    for row in report.disagreements:
        assert row["claim_tier"] == row["true_tier"], row
        assert row["overall_tier"] == "contradicted", row


def test_edge_cases_are_scored_separately_and_all_pass(report) -> None:
    """DST folds, a fix inside the radius, a walkable distance outside it, visit
    boundaries. These are where a threshold is either honest or it is not."""
    assert set(report.by_edge_kind) == {
        "dst_fold",
        "radius_inside",
        "radius_outside_walkable",
        "visit_boundary",
    }
    for name, row in report.by_edge_kind.items():
        assert row["claim_accuracy"] == 1.0, name


def test_every_rule_the_generator_seeded_in_scope_is_caught(report) -> None:
    for code, row in report.rule_recall.items():
        assert row["missed"] == 0, (code, row)


def test_the_description_check_never_flags_a_household_that_matches(report) -> None:
    """A false mismatch would be an accusation about a member of the user's own family."""
    assert report.description["false_flags"] == 0


def test_the_figures_on_the_methodology_page_are_the_figures_this_run_produced(report) -> None:
    """Bible §2 and §14.7: the published numbers are whatever the eval says, as it says
    them. The page reads a generated file, and this is what stops that file going stale
    while the engine moves under it.

        cd backend && PYTHONPATH=.. uv run python ../eval/run_eval.py \
            --corpus ../fixtures/out --out ../eval/results
    """
    assert PUBLISHED.is_file(), f"{PUBLISHED} is missing; re-run the eval"
    committed = json.loads(PUBLISHED.read_text())
    fresh = published_figures(report)

    # Latency is the one figure that is a measurement of a machine rather than a decision
    # of the engine's, so it is checked for shape and sanity and not for equality. Pinning
    # it would make this test fail on a busy laptop, and a test people learn to ignore is
    # worse than no test.
    assert committed.pop("latency_ms").keys() == fresh.pop("latency_ms").keys()
    assert committed == fresh
    assert report.latency_ms["p95"] < 200.0


def test_the_matrices_account_for_every_case(report) -> None:
    for matrix in (report.claim_matrix, report.overall_matrix):
        assert sum(matrix[t][p] for t in TIERS for p in TIERS) == report.n_cases
