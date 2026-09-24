"""How the engine degrades when the location data gets worse.

Every other number in this eval is measured on clean synthetic data, where a fix is
exactly where the generator put the person. Real phone history is not like that: an urban
GPS fix carries tens to hundreds of metres of error, and a battery-saving phone can go
twenty minutes without recording anything at all. A verdict that is only right on clean
data is not worth publishing, so this module makes the data worse on purpose and re-scores.

**Why the labels do not move with the noise.** Ground truth here is a statement about
where the generator *placed the person* — and jitter is the phone mis-measuring that
position, not the person walking. Dropping fixes is the phone not looking, not the person
leaving. The person is where they always were, so the original label stays true under both
perturbations, and a verdict that flips is a genuine error the noise induced rather than a
label that went stale. That is what makes scoring against the unperturbed truth correct
here, and it would be wrong for a perturbation that actually moved somebody.

**The jitter sweep is run twice, and the pair is the interesting part.** Bible §11.1
widens the match radius by each fix's own `accuracy_m`, so a phone that admits to 200 m of
error already gets a 200 m cushion. The first pass withholds that: positions move and
`accuracy_m` goes on lying about them, which is the adversarial reading and the one where
the engine has nothing to fall back on. The second pass reports the error honestly, as a
real phone does. Running only the first would overstate the risk; running only the second
would hide it. Run together they say which of the two the engine actually depends on.

Three sweeps:

* **GPS jitter**, sigma 20 m to 300 m. Each fix is displaced by an independent circular
  Gaussian. 300 m is roughly the worst a phone does in a Manhattan street canyon, and it
  is also the engine's own match radius, so the far end of this sweep is the point where
  noise is the same size as the thing being measured.
* **GPS jitter with the error reported**, the same displacements with `accuracy_m` raised
  to match, which is what a phone in a street canyon actually writes into its export.
* **Sampling gaps**, 2 min → 30 min. The stream is thinned until consecutive fixes are at
  least that far apart, which is what a phone in battery saver actually produces. Visits
  are intervals rather than samples, so thinning a visit would be inventing a different
  export; only PATH and TRANSACTION points are thinned.

Seeded throughout, so the sweep is as reproducible as the corpus it perturbs.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.domain.models import AnalyzeRequest, ClaimTier, FixKind, LocationFix, Severity
from app.engine.verdict import analyze
from eval.corpus import case_dirs, claim_answer, load_case

JITTER_SIGMA_M = (0.0, 20.0, 50.0, 100.0, 150.0, 200.0, 300.0)
GAP_MINUTES = (0.0, 2.0, 5.0, 10.0, 15.0, 20.0, 30.0)

THINNABLE = (FixKind.PATH, FixKind.TRANSACTION)
"""A VISIT or a MANUAL entry is an interval, not a sample.

Thinning one would not simulate a phone recording less often; it would delete a stay the
person actually reported, which is a different experiment with a different ground truth."""

SEED = 7

M_PER_DEG_LAT = 111_132.0
"""Metres per degree of latitude. Constant enough over one city to be a constant."""


@dataclass
class Level:
    """One point on one sweep."""

    value: float
    n_cases: int
    false_accusations: int = 0
    false_accusation_cases: list[str] = field(default_factory=list)
    claim_accuracy: float = 0.0
    strong: dict[str, Any] = field(default_factory=dict)
    strong_or_moderate: dict[str, Any] = field(default_factory=dict)
    flipped_from_clean: int = 0
    """Cases whose service-claim tier differs from the same case with no perturbation.

    Accuracy answers "is the engine right"; this answers "did the noise change its mind",
    which is the property a person deciding whether to trust a number actually asks about.
    """


@dataclass
class Sweep:
    name: str
    unit: str
    levels: list[Level] = field(default_factory=list)


@dataclass
class RobustnessReport:
    seed: int
    n_cases: int
    jitter: Sweep = field(default_factory=lambda: Sweep("GPS jitter", "sigma_m"))
    jitter_reported: Sweep = field(
        default_factory=lambda: Sweep("GPS jitter, error reported", "sigma_m")
    )
    gaps: Sweep = field(default_factory=lambda: Sweep("sampling gap", "minutes"))

    @property
    def sweeps(self) -> tuple[Sweep, Sweep, Sweep]:
        return (self.jitter, self.jitter_reported, self.gaps)


def jitter_fix(
    fix: LocationFix, sigma_m: float, rng: random.Random, *, report_accuracy: bool = False
) -> LocationFix:
    """Displace one fix by an independent circular Gaussian of `sigma_m` metres.

    With `report_accuracy` the fix also admits to the error, which is what a phone does:
    `accuracy_m` becomes at least sigma. The engine widens its match radius by exactly
    that (bible §11.1), so the difference between the two calls is the difference between
    a phone that knows it is uncertain and one that does not.
    """
    if sigma_m <= 0:
        return fix
    north_m = rng.gauss(0.0, sigma_m)
    east_m = rng.gauss(0.0, sigma_m)
    lat = fix.loc.lat + north_m / M_PER_DEG_LAT
    # A degree of longitude shortens with latitude. At 40.7°N it is about 84 km.
    m_per_deg_lng = M_PER_DEG_LAT * math.cos(math.radians(fix.loc.lat))
    lng = fix.loc.lng + east_m / m_per_deg_lng
    update: dict[str, Any] = {"loc": fix.loc.model_copy(update={"lat": lat, "lng": lng})}
    if report_accuracy:
        update["accuracy_m"] = max(fix.accuracy_m or 0.0, sigma_m)
    return fix.model_copy(update=update, deep=True)


def thin_fixes(fixes: list[LocationFix], gap_minutes: float) -> list[LocationFix]:
    """Keep intervals; thin samples until consecutive ones are `gap_minutes` apart."""
    if gap_minutes <= 0:
        return list(fixes)
    gap_s = gap_minutes * 60.0
    kept: list[LocationFix] = []
    last_sample_t = None
    for fix in sorted(fixes, key=lambda f: f.t):
        if fix.kind not in THINNABLE:
            kept.append(fix)
            continue
        if last_sample_t is None or (fix.t - last_sample_t).total_seconds() >= gap_s:
            kept.append(fix)
            last_sample_t = fix.t
    return kept


def _claim_answer(request: AnalyzeRequest) -> tuple[str, str | None]:
    return claim_answer(analyze(request))


@dataclass(frozen=True)
class Answer:
    """One case's outcome at one perturbation level."""

    case_id: str
    true_tier: str
    claim_tier: str
    severity: str | None


def _score(answers: list[Answer], baseline: list[str], value: float) -> Level:
    """Score one perturbation level against the *unperturbed* ground truth."""
    contradicted = ClaimTier.CONTRADICTED.value
    truth_positive = sum(1 for a in answers if a.true_tier == contradicted)

    def at(strong_only: bool) -> dict[str, Any]:
        predicted = [
            a
            for a in answers
            if a.claim_tier == contradicted
            and (a.severity == Severity.STRONG.value if strong_only else a.severity is not None)
        ]
        tp = sum(1 for a in predicted if a.true_tier == contradicted)
        return {
            "predicted_positive": len(predicted),
            "true_positives": tp,
            "false_positives": len(predicted) - tp,
            "false_negatives": truth_positive - tp,
            "precision": round(tp / len(predicted), 4) if predicted else None,
            "recall": round(tp / truth_positive, 4) if truth_positive else None,
        }

    level = Level(value=value, n_cases=len(answers))
    level.claim_accuracy = (
        round(sum(1 for a in answers if a.true_tier == a.claim_tier) / len(answers), 4)
        if answers
        else 0.0
    )
    level.strong = at(strong_only=True)
    level.strong_or_moderate = at(strong_only=False)
    level.flipped_from_clean = sum(
        1 for a, clean in zip(answers, baseline, strict=True) if a.claim_tier != clean
    )
    # The gate the whole eval turns on: noise made a consistent person look contradicted,
    # at the severity a court document would actually rest on.
    level.false_accusation_cases = sorted(
        a.case_id
        for a in answers
        if a.true_tier == ClaimTier.CONSISTENT.value
        and a.claim_tier == contradicted
        and a.severity == Severity.STRONG.value
    )
    level.false_accusations = len(level.false_accusation_cases)
    return level


def run(corpus: Path, out: Path, seed: int = SEED) -> RobustnessReport:
    """Perturb every case at every level of both sweeps and re-score."""
    loaded = []
    for case_dir in case_dirs(corpus):
        request, truth = load_case(case_dir)
        loaded.append((str(truth["case_id"]), request, str(truth["true_tier"])))

    baseline = [_claim_answer(request)[0] for _, request, _ in loaded]
    report = RobustnessReport(seed=seed, n_cases=len(loaded))

    for reported, sweep in ((False, report.jitter), (True, report.jitter_reported)):
        for sigma in JITTER_SIGMA_M:
            answers = []
            for index, (case_id, request, true_tier) in enumerate(loaded):
                # One stream per (level, case), so a case's noise does not depend on how
                # many cases preceded it. The seed does not mention which pass this is, on
                # purpose: the two jitter passes displace every fix *identically*, so the
                # only difference between their numbers is whether the phone owned up to
                # the error. Any other difference would be noise pretending to be a result.
                rng = random.Random(f"{seed}:jitter:{sigma}:{index}")
                perturbed = request.model_copy(
                    update={
                        "fixes": [
                            jitter_fix(f, sigma, rng, report_accuracy=reported)
                            for f in request.fixes
                        ]
                    }
                )
                tier, severity = _claim_answer(perturbed)
                answers.append(Answer(case_id, true_tier, tier, severity))
            sweep.levels.append(_score(answers, baseline, sigma))

    for gap in GAP_MINUTES:
        answers = []
        for case_id, request, true_tier in loaded:
            perturbed = request.model_copy(update={"fixes": thin_fixes(request.fixes, gap)})
            tier, severity = _claim_answer(perturbed)
            answers.append(Answer(case_id, true_tier, tier, severity))
        report.gaps.levels.append(_score(answers, baseline, gap))

    out.mkdir(parents=True, exist_ok=True)
    (out / "robustness.json").write_text(
        json.dumps(asdict(report), indent=1, sort_keys=True) + "\n"
    )
    return report


def format_report(report: RobustnessReport) -> str:
    lines = [
        "Robustness — how the verdict holds up as the data gets worse",
        f"{report.n_cases} cases per level, seed {report.seed}",
    ]
    for sweep in report.sweeps:
        lines += [
            "",
            f"{sweep.name} ({sweep.unit}):",
            f"  {'level':>7}  {'STRONG prec':>12} {'STRONG rec':>11}"
            f" {'+MOD prec':>10} {'+MOD rec':>9}  {'flipped':>7}  {'false acc':>9}",
        ]
        for level in sweep.levels:
            lines.append(
                f"  {level.value:>7.0f}  {_pct(level.strong['precision']):>12}"
                f" {_pct(level.strong['recall']):>11}"
                f" {_pct(level.strong_or_moderate['precision']):>10}"
                f" {_pct(level.strong_or_moderate['recall']):>9}"
                f"  {level.flipped_from_clean:>7}  {level.false_accusations:>9}"
            )
    return "\n".join(lines)


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _publish_sweep(sweep: Sweep) -> dict[str, Any]:
    return {
        "name": sweep.name,
        "unit": sweep.unit,
        "levels": [
            {
                "value": level.value,
                "precision": level.strong["precision"],
                "recall": level.strong["recall"],
                "precision_with_moderate": level.strong_or_moderate["precision"],
                "recall_with_moderate": level.strong_or_moderate["recall"],
                "false_accusations": level.false_accusations,
            }
            for level in sweep.levels
        ],
    }


def published_figures(report: RobustnessReport) -> dict[str, Any]:
    """What the Methodology page prints. Enough to draw the curve, and nothing else."""
    return {
        "seed": report.seed,
        "n_cases": report.n_cases,
        "jitter": _publish_sweep(report.jitter),
        "jitter_reported": _publish_sweep(report.jitter_reported),
        "gaps": _publish_sweep(report.gaps),
        "max_false_accusations": max(
            level.false_accusations for sweep in report.sweeps for level in sweep.levels
        ),
        "max_false_accusations_reported": max(
            level.false_accusations
            for sweep in (report.jitter_reported, report.gaps)
            for level in sweep.levels
        ),
    }
