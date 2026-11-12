"""The time-uncertainty invariants, swept over the whole corpus at a fixed seed.

Bible §11.1.7 makes three promises about a fix whose time is not exact (a photo with no
time zone, say). `tests/engine/test_properties.py` checks them on generated geometry with
Hypothesis; this sweep checks the same three on every case in the synthetic corpus, which
is what real-looking records look like, and publishes the counts:

1. **Raising a fix's uncertainty never raises severity.** For each case, a few fixes picked
   by a seeded generator get their `time_uncertainty_s` raised by a seeded amount, and the
   conflict on the service claim must be no stronger than before.
2. **A conflict resting only on assumed-zone fixes is never STRONG.** Every fix in the case
   is marked `tz_assumed`, and the service claim must not come back STRONG.
3. **An exact photo at the door at the claimed time is CONSISTENT**, whatever else the case
   holds. One is added, and the service claim must come back CONSISTENT.

A violation is a bug in the engine, not a number to explain, so the count must be zero and
each one is named. The same seed gives the same trials; nothing here reads a clock.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from app.domain.models import AnalyzeRequest, FixKind, LocationFix
from app.engine.verdict import analyze
from eval.corpus import case_dirs, claim_answer, load_case

SEED: Final = 11
RAISES_PER_CASE: Final = 3
MAX_RAISE_S: Final = 7200
MAX_UNCERTAINTY_S: Final = 86_400


def adversity(request: AnalyzeRequest) -> int:
    """0 no conflict on the service claim, 1 MODERATE, 2 STRONG."""
    tier, severity = claim_answer(analyze(request))
    if tier != "contradicted":
        return 0
    return {"strong": 2, "moderate": 1}.get(severity or "", 0)


def _with_fixes(request: AnalyzeRequest, fixes: list[LocationFix]) -> AnalyzeRequest:
    return request.model_copy(update={"fixes": fixes})


@dataclass
class Invariant:
    trials: int = 0
    violations: int = 0
    cases: list[str] = field(default_factory=list)

    def check(self, ok: bool, case_id: str) -> None:
        self.trials += 1
        if not ok:
            self.violations += 1
            if case_id not in self.cases:
                self.cases.append(case_id)


@dataclass
class UncertaintyReport:
    seed: int = SEED
    n_cases: int = 0
    raising: Invariant = field(default_factory=Invariant)
    assumed_only: Invariant = field(default_factory=Invariant)
    exact_photo: Invariant = field(default_factory=Invariant)
    strong_before_assumed: int = 0
    """Cases STRONG with their real time zones; each must drop to MODERATE or below."""

    @property
    def violations(self) -> int:
        return self.raising.violations + self.assumed_only.violations + self.exact_photo.violations


def run(corpus: Path, seed: int = SEED) -> UncertaintyReport:
    report = UncertaintyReport(seed=seed)
    for case_dir in case_dirs(corpus):
        request, _ = load_case(case_dir)
        rng = random.Random(f"{seed}:{case_dir.name}")
        case_id = case_dir.name
        report.n_cases += 1
        before = adversity(request)

        fixes = list(request.fixes)
        for _ in range(RAISES_PER_CASE if fixes else 0):
            index = rng.randrange(len(fixes))
            raised = list(fixes)
            raised[index] = fixes[index].model_copy(
                update={
                    "time_uncertainty_s": min(
                        fixes[index].time_uncertainty_s + rng.randint(1, MAX_RAISE_S),
                        MAX_UNCERTAINTY_S,
                    )
                }
            )
            report.raising.check(adversity(_with_fixes(request, raised)) <= before, case_id)

        if fixes:
            report.strong_before_assumed += int(before == 2)
            assumed = [f.model_copy(update={"tz_assumed": True}) for f in fixes]
            report.assumed_only.check(adversity(_with_fixes(request, assumed)) < 2, case_id)

        door = request.affidavit.served_location
        if door is not None:
            photo = LocationFix(
                t=request.affidavit.served_at,
                loc=door,
                kind=FixKind.PHOTO,
                source="photo",
                label="Photo taken here",
            )
            tier, _ = claim_answer(analyze(_with_fixes(request, [*fixes, photo])))
            report.exact_photo.check(tier == "consistent", case_id)
    return report


def _invariant(item: Invariant) -> dict[str, Any]:
    return {"trials": item.trials, "violations": item.violations}


def published_figures(report: UncertaintyReport) -> dict[str, Any]:
    return {
        "seed": report.seed,
        "n_cases": report.n_cases,
        "raising_never_strengthens": _invariant(report.raising),
        "assumed_only_never_strong": _invariant(report.assumed_only),
        "exact_photo_consistent": _invariant(report.exact_photo),
        "strong_before_assumed": report.strong_before_assumed,
        "violations": report.violations,
    }


def as_json(report: UncertaintyReport) -> dict[str, Any]:
    return {
        **published_figures(report),
        "violation_cases": {
            "raising": report.raising.cases,
            "assumed_only": report.assumed_only.cases,
            "exact_photo": report.exact_photo.cases,
        },
    }


def format_report(report: UncertaintyReport) -> str:
    def line(name: str, item: Invariant) -> str:
        named = f"  {item.cases}" if item.cases else ""
        return f"  {name:<44} {item.violations} of {item.trials} trials{named}"

    return "\n".join(
        [
            f"Time-uncertainty invariants (v1.1), seed {report.seed}, {report.n_cases} cases",
            line("raising uncertainty strengthened a conflict", report.raising),
            line("assumed-zone-only conflict came back STRONG", report.assumed_only)
            + f"  ({report.strong_before_assumed} were STRONG before)",
            line("exact photo at the door was not CONSISTENT", report.exact_photo),
            f"  violations: {report.violations}   <- gate, must be 0",
        ]
    )
