"""Score the engine against the synthetic corpus' ground truth.

The corpus labels come from `fixtures/generator`, which decides them by construction and
never by calling the engine. Keeping the two independent is what makes these numbers worth
publishing on the Methodology page.

    cd backend && PYTHONPATH=.. uv run python ../eval/run_eval.py \\
        --corpus ../fixtures/out --out ../eval/results

**Two accuracies are reported, and the difference between them is the point.** The
generator labels one thing: where it put the person at the *claimed service time*. So the
like-for-like comparison is against the engine's verdict on that claim. `overall` is a
second, product-level question — it also folds in the prior attempts a 308(4) affidavit
swears to — and it is reported separately rather than blended in, because scoring it
against a label about a different moment would be measuring the wrong thing quietly.

The number that leads is neither of those. It is the false-contradiction count: cases the
generator built as CONSISTENT where the engine says CONTRADICTED with STRONG severity.
Telling somebody their data conflicts with a sworn affidavit when it does not is the one
failure that could hurt a user in court, so it is reported first and it has to be zero.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.domain.models import AnalyzeRequest, ClaimTier, ServiceMethod, Severity
from app.engine.params import PARAMS, PARAMS_VERSION
from app.engine.verdict import MAIN_CLAIM, analyze
from eval.advocate_eval import format_report as format_advocate
from eval.advocate_eval import published_figures as advocate_published
from eval.advocate_eval import run as run_advocate

TIERS = ("contradicted", "consistent", "no_data", "inconclusive")

DESCRIPTION_METHODS = (ServiceMethod.PERSONAL, ServiceMethod.SUBSTITUTE)
"""Bible §11.2 only defines the description check for these two. Scoring it on the others
would score a check that deliberately does not run."""

MAILING_METHODS = (ServiceMethod.SUBSTITUTE, ServiceMethod.AFFIX_AND_MAIL)

RULE_SCOPE: dict[str, tuple[ServiceMethod, ...]] = {
    "R-T1": MAILING_METHODS,
    "R-T2": MAILING_METHODS,
    "R-T3": MAILING_METHODS,
    "R-D1": (ServiceMethod.AFFIX_AND_MAIL,),
    "R-D2": (ServiceMethod.AFFIX_AND_MAIL,),
    "R-M1": tuple(ServiceMethod),
}
"""Which methods each rule applies to, straight from bible §11.3.

This is here because the generator is slightly more generous than the bible: it will seed
a late proof-of-service date on a 308(1) affidavit, where §11.3 scopes R-T3 to 308(2) and
308(4), and bible §5 gives no authority for a filing deadline on personal delivery at all.
Counting those as misses would penalise the engine for obeying §5. They are counted and
named separately instead, because quietly dropping them would be the other kind of lie."""


@dataclass
class CaseResult:
    case_id: str
    kind: str
    edge_kind: str | None
    true_tier: str
    claim_tier: str
    overall_tier: str
    false_accusation: bool
    nearest_fix_km: float | None
    required_speed_kmh: float | None
    seeded_rule_codes: list[str]
    found_rule_codes: list[str]
    description_expected_match: bool
    description_flagged: bool
    description_scored: bool
    method: ServiceMethod
    latency_ms: float


@dataclass
class Report:
    params_version: str
    n_cases: int
    false_accusations: int = 0
    false_accusation_cases: list[str] = field(default_factory=list)
    claim_accuracy: float = 0.0
    overall_accuracy: float = 0.0
    claim_matrix: dict[str, dict[str, int]] = field(default_factory=dict)
    overall_matrix: dict[str, dict[str, int]] = field(default_factory=dict)
    by_kind: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_edge_kind: dict[str, dict[str, Any]] = field(default_factory=dict)
    rule_recall: dict[str, dict[str, int]] = field(default_factory=dict)
    description: dict[str, Any] = field(default_factory=dict)
    latency_ms: dict[str, float] = field(default_factory=dict)
    disagreements: list[dict[str, Any]] = field(default_factory=list)


def load_case(case_dir: Path) -> tuple[AnalyzeRequest, dict[str, Any]]:
    """Read one case as the API would receive it: an affidavit the user has confirmed."""
    affidavit = json.loads((case_dir / "affidavit.json").read_text())
    affidavit["user_confirmed"] = True
    request = AnalyzeRequest.model_validate(
        {
            "affidavit": affidavit,
            "fixes": json.loads((case_dir / "fixes.json").read_text()),
            "household": json.loads((case_dir / "household.json").read_text()),
        }
    )
    return request, json.loads((case_dir / "ground_truth.json").read_text())


def score_case(case_dir: Path) -> CaseResult:
    request, truth = load_case(case_dir)
    started = time.perf_counter()
    analysis = analyze(request)
    latency_ms = (time.perf_counter() - started) * 1000.0

    main = next((v for v in analysis.verdicts if v.claim_ref == MAIN_CLAIM), None)
    claim_tier = main.tier if main is not None else ClaimTier.NO_DATA
    strong_conflict = any(
        f.severity is Severity.STRONG and f.code in ("F-VISIT", "F-PRISM")
        for f in analysis.findings
    )
    method = request.affidavit.method

    return CaseResult(
        case_id=truth["case_id"],
        kind=truth["kind"],
        edge_kind=truth["edge_kind"],
        true_tier=truth["true_tier"],
        claim_tier=claim_tier.value,
        overall_tier=analysis.overall.value,
        false_accusation=(
            truth["true_tier"] == ClaimTier.CONSISTENT.value
            and claim_tier is ClaimTier.CONTRADICTED
            and strong_conflict
        ),
        nearest_fix_km=main.nearest_fix_km if main else None,
        required_speed_kmh=main.required_speed_kmh if main else None,
        seeded_rule_codes=list(truth["seeded_rule_codes"]),
        found_rule_codes=sorted({f.code for f in analysis.findings if f.code.startswith("R-")}),
        description_expected_match=bool(truth["description_matches_household"]),
        description_flagged=any(f.code == "F-DESC" for f in analysis.findings),
        description_scored=method in DESCRIPTION_METHODS,
        method=method,
        latency_ms=latency_ms,
    )


def _matrix(results: list[CaseResult], predicted: str) -> dict[str, dict[str, int]]:
    counts: Counter[tuple[str, str]] = Counter(
        (r.true_tier, getattr(r, predicted)) for r in results
    )
    return {t: {p: counts[(t, p)] for p in TIERS} for t in TIERS}


def _accuracy(results: list[CaseResult], predicted: str) -> float:
    if not results:
        return 0.0
    hits = sum(1 for r in results if r.true_tier == getattr(r, predicted))
    return round(hits / len(results), 4)


def _group(results: list[CaseResult], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[CaseResult]] = {}
    for result in results:
        groups.setdefault(str(getattr(result, key)), []).append(result)
    return {
        name: {
            "n": len(rows),
            "claim_accuracy": _accuracy(rows, "claim_tier"),
            "overall_accuracy": _accuracy(rows, "overall_tier"),
        }
        for name, rows in sorted(groups.items())
    }


def _rule_recall(results: list[CaseResult]) -> dict[str, dict[str, int]]:
    """Per rule: how many cases were built to trip it, and how many the engine caught.

    `extra` is not an error. The generator seeds *some* violations deliberately; others
    fall out of the dates it happens to draw, and the engine is right to report those too.
    """
    recall: dict[str, dict[str, int]] = {}
    for result in results:
        for code in set(result.seeded_rule_codes) | set(result.found_rule_codes):
            row = recall.setdefault(
                code, {"seeded": 0, "found": 0, "missed": 0, "extra": 0, "out_of_scope": 0}
            )
            seeded = code in result.seeded_rule_codes
            found = code in result.found_rule_codes
            in_scope = result.method in RULE_SCOPE.get(code, tuple(ServiceMethod))
            if seeded and not in_scope:
                row["out_of_scope"] += 1
                continue
            row["seeded"] += int(seeded)
            row["found"] += int(seeded and found)
            row["missed"] += int(seeded and not found)
            row["extra"] += int(found and not seeded)
    return dict(sorted(recall.items()))


def _description_scores(results: list[CaseResult]) -> dict[str, Any]:
    scored = [r for r in results if r.description_scored]
    flagged_when_no_match = sum(
        1 for r in scored if not r.description_expected_match and r.description_flagged
    )
    expect_flag = sum(1 for r in scored if not r.description_expected_match)
    flagged_when_match = sum(
        1 for r in scored if r.description_expected_match and r.description_flagged
    )
    expect_quiet = sum(1 for r in scored if r.description_expected_match)
    return {
        "n_scored": len(scored),
        "n_skipped_by_method": len(results) - len(scored),
        "mismatches_caught": flagged_when_no_match,
        "mismatches_total": expect_flag,
        "false_flags": flagged_when_match,
        "matches_total": expect_quiet,
        "recall": round(flagged_when_no_match / expect_flag, 4) if expect_flag else None,
    }


def build_report(results: list[CaseResult]) -> Report:
    latencies = sorted(r.latency_ms for r in results)
    report = Report(params_version=PARAMS_VERSION, n_cases=len(results))
    report.false_accusation_cases = [r.case_id for r in results if r.false_accusation]
    report.false_accusations = len(report.false_accusation_cases)
    report.claim_accuracy = _accuracy(results, "claim_tier")
    report.overall_accuracy = _accuracy(results, "overall_tier")
    report.claim_matrix = _matrix(results, "claim_tier")
    report.overall_matrix = _matrix(results, "overall_tier")
    report.by_kind = _group(results, "kind")
    report.by_edge_kind = _group([r for r in results if r.edge_kind], "edge_kind")
    report.rule_recall = _rule_recall(results)
    report.description = _description_scores(results)
    report.latency_ms = {
        "median": round(statistics.median(latencies), 2),
        "p95": round(latencies[int(len(latencies) * 0.95)], 2) if latencies else 0.0,
        "max": round(latencies[-1], 2) if latencies else 0.0,
    }
    report.disagreements = [
        {
            "case_id": r.case_id,
            "kind": r.kind,
            "edge_kind": r.edge_kind,
            "true_tier": r.true_tier,
            "claim_tier": r.claim_tier,
            "overall_tier": r.overall_tier,
        }
        for r in results
        if r.true_tier != r.overall_tier or r.true_tier != r.claim_tier
    ]
    return report


def score_corpus(corpus: Path) -> list[CaseResult]:
    cases = sorted(d for d in (corpus / "cases").iterdir() if d.is_dir())
    if not cases:
        raise SystemExit(f"no cases under {corpus / 'cases'}. Run `python -m fixtures.generator`.")
    return [score_case(case) for case in cases]


def format_matrix(matrix: dict[str, dict[str, int]], title: str) -> str:
    header = f"{title:<16}" + "".join(f"{t:>14}" for t in TIERS)
    rows = [
        f"{truth:<16}" + "".join(f"{matrix[truth][pred]:>14}" for pred in TIERS) for truth in TIERS
    ]
    return "\n".join([header, *rows])


def format_report(report: Report) -> str:
    lines = [
        "ServeTrace engine evaluation",
        f"params {report.params_version} · {report.n_cases} synthetic cases",
        "",
        f"FALSE CONTRADICTIONS: {report.false_accusations}"
        + (f"  {report.false_accusation_cases}" if report.false_accusation_cases else ""),
        "",
        f"service-claim accuracy  {report.claim_accuracy:.1%}",
        f"overall-tier accuracy   {report.overall_accuracy:.1%}",
        "",
        format_matrix(report.claim_matrix, "claim truth\\pred"),
        "",
        format_matrix(report.overall_matrix, "case truth\\pred"),
        "",
        "by case kind:",
    ]
    lines += [
        f"  {name:<28} n={row['n']:<4} claim {row['claim_accuracy']:.0%}"
        f"  overall {row['overall_accuracy']:.0%}"
        for name, row in {**report.by_kind, **report.by_edge_kind}.items()
    ]
    lines += ["", "rules (seeded by the generator / caught by the engine):"]
    lines += [
        f"  {code:<6} seeded {row['seeded']:<4} caught {row['found']:<4} "
        f"missed {row['missed']:<4} also found elsewhere {row['extra']:<4} "
        f"seeded outside the rule's scope {row['out_of_scope']}"
        for code, row in report.rule_recall.items()
    ]
    description = report.description
    lines += [
        "",
        f"description check: {description['mismatches_caught']}/{description['mismatches_total']} "
        f"mismatches caught, {description['false_flags']}/{description['matches_total']} "
        f"false flags, {description['n_skipped_by_method']} cases not scored (308(4))",
        "",
        f"latency per case: median {report.latency_ms['median']} ms, "
        f"p95 {report.latency_ms['p95']} ms, max {report.latency_ms['max']} ms",
    ]
    return "\n".join(lines)


def published_figures(report: Report) -> dict[str, Any]:
    """The subset of this report that the Methodology page publishes, plus the thresholds.

    Bible §14.7 requires that page to carry the thresholds and the eval numbers, and bible
    §2 requires the numbers to be honest. Both are served by generating this file rather
    than typing figures into a Svelte component: the page cannot drift from the eval,
    and `tests/engine/test_fixture_sweep.py` fails if the committed copy goes stale.
    """
    return {
        "params_version": report.params_version,
        "engine_params": {
            "match_radius_km": PARAMS.match_radius_km,
            "visit_tolerance_min": PARAMS.visit_tolerance_min,
            "search_window_h": PARAMS.search_window_h,
            "consistent_window_min": PARAMS.consistent_window_min,
            "v_strong_kmh": PARAMS.v_strong_kmh,
            "v_moderate_kmh": PARAMS.v_moderate_kmh,
            "desc_age_tolerance_y": PARAMS.desc_age_tolerance_y,
            "desc_height_tolerance_in": PARAMS.desc_height_tolerance_in,
            "adv_simultaneous_min": PARAMS.adv_simultaneous_min,
            "adv_simultaneous_km": PARAMS.adv_simultaneous_km,
            "adv_max_per_hour": PARAMS.adv_max_per_hour,
        },
        "n_cases": report.n_cases,
        "false_accusations": report.false_accusations,
        "claim_accuracy": report.claim_accuracy,
        "overall_accuracy": report.overall_accuracy,
        "claim_matrix": report.claim_matrix,
        "by_kind": report.by_kind,
        "by_edge_kind": report.by_edge_kind,
        "rule_recall": report.rule_recall,
        "description": report.description,
        "latency_ms": report.latency_ms,
        "n_disagreements": len(report.disagreements),
    }


PUBLISHED = (
    Path(__file__).resolve().parents[1] / "frontend" / "src" / "lib" / "eval" / "published.json"
)


def run(corpus: Path, out: Path, publish: Path | None = PUBLISHED) -> Report:
    """Analyse every case, compare tiers against ground truth, write the report.

    Batch mode is scored in the same pass. It shares the thresholds and the same
    independently-labelled corpus, and the Methodology page prints both sets of numbers,
    so running them apart is how one of them goes stale without anybody noticing.
    """
    results = score_corpus(corpus)
    report = build_report(results)
    out.mkdir(parents=True, exist_ok=True)
    (out / "engine.json").write_text(
        json.dumps(
            {"report": asdict(report), "cases": [asdict(r) for r in results]},
            indent=1,
            sort_keys=True,
        )
        + "\n"
    )

    advocate = run_advocate(corpus, out) if (corpus / "advocate").is_dir() else None

    if publish is not None:
        figures = published_figures(report)
        if advocate is not None:
            figures["advocate"] = advocate_published(advocate)
        publish.parent.mkdir(parents=True, exist_ok=True)
        publish.write_text(json.dumps(figures, indent=1, sort_keys=True) + "\n")

    print(format_report(report))
    if advocate is not None:
        print("\n" + format_advocate(advocate))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(prog="run_eval", description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("fixtures/out"))
    parser.add_argument("--out", type=Path, default=Path("eval/results"))
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="skip rewriting the figures the Methodology page reads",
    )
    args = parser.parse_args()
    report = run(args.corpus, args.out, None if args.no_publish else PUBLISHED)
    if report.false_accusations:
        raise SystemExit("false contradictions found: the no-false-accusation gate failed")


if __name__ == "__main__":
    main()
