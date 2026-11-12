"""The v1.1 scorers' own arithmetic: the attorney batch and the time-uncertainty sweep.

As with `test_run_eval.py`, the point is that the code which counts is itself checked, on
cases where the right count is obvious, so a change cannot quietly change what a published
"100%" means.
"""

from __future__ import annotations

import json

from app.advocate.batch import analyze_batch
from app.domain.models import Affidavit
from app.engine.params import PARAMS
from eval.batch_eval import FIXTURE, independent_applicable, score
from eval.uncertainty import Invariant


def _fixture() -> tuple[list[dict], dict]:  # type: ignore[type-arg]
    rows = json.loads((FIXTURE / "affidavits.json").read_text(encoding="utf-8"))
    truth = json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))
    return rows, truth


def test_the_batch_scores_perfectly_against_its_own_answer_key() -> None:
    rows, truth = _fixture()
    report = analyze_batch([Affidavit.model_validate(r) for r in rows], PARAMS)
    result = score(rows, truth, report)
    assert result.all_flags_right
    assert result.rates_wrong == []
    assert (result.pairs.precision, result.pairs.recall) == (1.0, 1.0)
    assert result.repeated_description_found
    assert result.clean_agency_clean and result.clean_agency_last


def test_a_wrong_flag_costs_precision_and_a_wrong_rate_is_named() -> None:
    rows, truth = _fixture()
    report = analyze_batch([Affidavit.model_validate(r) for r in rows], PARAMS)
    flipped = next(f for f in report.flags if f.rule_code == "R-T1" and not f.flagged)
    flipped.flagged = True
    for rate in report.rule_rates:
        if rate.rule_code == "R-T1":
            rate.flagged += 1
    result = score(rows, truth, report)
    assert result.rules["R-T1"].precision == 0.8
    assert result.rules["R-T1"].recall == 1.0
    assert [w["rule"] for w in result.rates_wrong] == ["R-T1"]


def test_applicability_reads_the_table_not_the_engine() -> None:
    assert independent_applicable({"method": "308_1"}) == ["R-M1"]
    assert independent_applicable({"method": "308_2"}) == ["R-T1", "R-M1"]
    assert independent_applicable(
        {"method": "308_4", "mailing_date": "2025-01-02", "proof_filed_date": "2025-01-09"}
    ) == ["R-T1", "R-T2", "R-T3", "R-D1", "R-M1"]


def test_an_invariant_names_each_failing_case_once() -> None:
    item = Invariant()
    for ok, case in [(True, "a"), (False, "b"), (False, "b"), (False, "c")]:
        item.check(ok, case)
    assert (item.trials, item.violations, item.cases) == (4, 3, ["b", "c"])
