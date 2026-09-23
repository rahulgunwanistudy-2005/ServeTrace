"""The three demo cases, pinned.

These snapshots catch *change*, not correctness: they were written by the engine, so they
cannot tell us the engine is right. What proves correctness is `test_fixture_sweep.py`,
which scores the engine against labels the generator decided by construction and never by
asking the engine. Both are needed, and they are not the same test.

What a golden file is for is the demo. Bible §2 and §17 both say the demo must never fail
live, and a wording change or a threshold nudge that quietly moves Maria from
CONTRADICTED to INCONCLUSIVE is exactly the kind of thing that only shows up on stage.
Regenerate deliberately:

    cd backend && PYTHONPATH=.. uv run python -m tests.engine.test_golden
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.domain.models import AnalyzeRequest, CaseAnalysis
from app.engine.verdict import analyze

DEMO_CASES = Path(__file__).resolve().parents[3] / "fixtures" / "demo_cases"
GOLDEN = Path(__file__).resolve().parent / "golden"
CASE_IDS = ("james_consistent", "lin_affix_mail_diligence", "maria_contradicted")


def load(case_id: str) -> AnalyzeRequest:
    case = DEMO_CASES / case_id
    affidavit = json.loads((case / "affidavit.json").read_text())
    affidavit["user_confirmed"] = True
    return AnalyzeRequest.model_validate(
        {
            "affidavit": affidavit,
            "fixes": json.loads((case / "fixes.json").read_text()),
            "household": json.loads((case / "household.json").read_text()),
        }
    )


def snapshot(analysis: CaseAnalysis) -> dict[str, Any]:
    """Everything the engine decided, and nothing it was handed.

    `generated_at` is a wall clock and `affidavit` is an echo of the input, so neither
    belongs in a file whose whole job is to change only when a decision changes.
    """
    return analysis.model_dump(mode="json", exclude={"generated_at", "affidavit"})


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_demo_case_matches_its_golden_snapshot(case_id: str) -> None:
    expected = json.loads((GOLDEN / f"{case_id}.json").read_text())
    assert snapshot(analyze(load(case_id))) == expected


@pytest.mark.parametrize(
    ("case_id", "tier"),
    [
        ("james_consistent", "consistent"),
        ("lin_affix_mail_diligence", "contradicted"),
        ("maria_contradicted", "contradicted"),
    ],
)
def test_the_demo_still_tells_the_story_it_was_built_to_tell(case_id: str, tier: str) -> None:
    """Asserted separately from the snapshot, because a regenerated snapshot would happily
    record a demo that had stopped working."""
    assert analyze(load(case_id)).overall.value == tier


def test_marias_headline_number_is_the_distance_her_own_file_records() -> None:
    """Bible §14.5 builds the result headline out of this number, so it is worth pinning
    on its own: it comes from the generator's independent geometry, not from the engine."""
    truth = json.loads((DEMO_CASES / "maria_contradicted" / "ground_truth.json").read_text())
    verdict = analyze(load("maria_contradicted")).verdicts[0]
    assert verdict.nearest_fix_km == pytest.approx(truth["true_distance_km_at_claim"], abs=0.05)


def test_sentences_start_with_a_capital_and_stay_that_way() -> None:
    """`str.capitalize()` lower-cases the rest of the string, which turned "7:42 PM on 12
    June 2025" into "7:42 pm on 12 june 2025" in a generated document. A golden snapshot
    found it; this keeps it found."""
    for case_id in CASE_IDS:
        for finding in analyze(load(case_id)).findings:
            for sentence in finding.detail.split(". "):
                assert sentence[:1] == sentence[:1].upper(), finding.detail
            assert " pm " not in finding.detail and " am " not in finding.detail


def test_lin_trips_exactly_the_rules_that_case_was_built_around() -> None:
    truth = json.loads((DEMO_CASES / "lin_affix_mail_diligence" / "ground_truth.json").read_text())
    found = {f.code for f in analyze(load("lin_affix_mail_diligence")).findings}
    assert set(truth["seeded_rule_codes"]) <= found


def regenerate() -> None:  # pragma: no cover - a maintenance command, not a test
    GOLDEN.mkdir(exist_ok=True)
    for case_id in CASE_IDS:
        path = GOLDEN / f"{case_id}.json"
        path.write_text(
            json.dumps(snapshot(analyze(load(case_id))), indent=1, sort_keys=True) + "\n"
        )
        print(f"wrote {path}")


if __name__ == "__main__":  # pragma: no cover
    regenerate()
