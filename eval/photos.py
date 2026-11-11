"""The photo-only sweep: every corpus case, as if its owner had only their camera roll.

v1.1 lets a person with no Timeline bring photos instead, and a photo is a much thinner
record than an export: a handful of points, some with a clock whose time zone the camera
never wrote down. This sweep asks whether the engine stays honest on records like that.

**How a photo-only case is built.** From each case's own fixes — which the generator put
where it put the person — a few moments in the ±3 h window are picked and turned into
photos: the place the person really was at that moment, with GPS-grade jitter. About
four in ten lose their time zone, and of those a third were taken with the camera clock
set an hour off New York, so the time the engine is given is *wrong by an hour* and
marked as assumed. That last group is the adversarial one; it is exactly what bible
§11.1.7's cap exists for.

**Labels are untouched.** Where the person was at the claimed moment does not depend on
how many photos they took, so the generator's `true_tier` stands. Nothing here asks the
engine anything until scoring (lessons.md, 2026-09-23).

**What is gated.** False STRONG contradictions on cases built CONSISTENT: must be zero,
as on the full corpus. MODERATE false contradictions and the share of cases that become
NO_DATA are reported, not gated — fewer records honestly means fewer answers.

    python eval/run_eval.py   # runs this too
"""

from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any

from app.domain.models import AnalyzeRequest, FixKind, LatLng, LocationFix
from app.engine.verdict import analyze
from eval.corpus import case_dirs, claim_answer, load_case

WINDOW = timedelta(hours=3)
ZONE_LOST_SHARE = 0.4
CLOCK_OFF_SHARE = 1 / 3
PHOTO_JITTER_M = 25.0
ASSUMED_UNCERTAINTY_S = 3600


def _jitter(loc: LatLng, rng: random.Random, metres: float) -> LatLng:
    bearing = rng.uniform(0, 2 * math.pi)
    distance = abs(rng.gauss(0, metres))
    dlat = distance * math.cos(bearing) / 111_320
    dlng = distance * math.sin(bearing) / (111_320 * math.cos(math.radians(loc.lat)))
    return LatLng(lat=round(loc.lat + dlat, 7), lng=round(loc.lng + dlng, 7))


def photo_request(request: AnalyzeRequest, case_id: str) -> tuple[AnalyzeRequest, dict[str, int]]:
    """The same case, with its fixes replaced by a few photos. Deterministic per case id."""
    rng = random.Random(f"photos:{case_id}")
    claim = request.affidavit.served_at
    nearby = [
        f for f in request.fixes if (f.t_end or f.t) >= claim - WINDOW and f.t <= claim + WINDOW
    ]
    n = rng.randint(0, 4)
    photos: list[LocationFix] = []
    counts = Counter[str]()
    for _ in range(n if nearby else 0):
        source = rng.choice(nearby)
        if source.t_end is not None:
            span = (source.t_end - source.t).total_seconds()
            moment = source.t + timedelta(seconds=rng.uniform(0, max(span, 0)))
        else:
            moment = source.t
        lost_zone = rng.random() < ZONE_LOST_SHARE
        clock_off = lost_zone and rng.random() < CLOCK_OFF_SHARE
        shift = timedelta(hours=rng.choice((-1, 1))) if clock_off else timedelta(0)
        photos.append(
            LocationFix(
                t=moment + shift,
                loc=_jitter(source.loc, rng, PHOTO_JITTER_M),
                accuracy_m=round(rng.uniform(5, 65), 1),
                kind=FixKind.PHOTO,
                source="photo",
                label="Photo taken here",
                time_uncertainty_s=ASSUMED_UNCERTAINTY_S if lost_zone else 0,
                tz_assumed=lost_zone,
            )
        )
        counts["photos"] += 1
        counts["zone_lost"] += int(lost_zone)
        counts["clock_off"] += int(clock_off)
    return request.model_copy(update={"fixes": photos}), dict(counts)


@dataclass
class PhotoReport:
    n_cases: int = 0
    n_photos: int = 0
    zone_lost: int = 0
    clock_off: int = 0
    false_strong: int = 0
    false_strong_cases: list[str] = field(default_factory=list)
    false_moderate: int = 0
    no_data: int = 0
    strong_from_assumed_only: int = 0
    matrix: dict[str, dict[str, int]] = field(default_factory=dict)


def run(corpus: Path) -> PhotoReport:
    report = PhotoReport()
    matrix: dict[str, Counter[str]] = {}
    for case_dir in case_dirs(corpus):
        request, truth = load_case(case_dir)
        photo, counts = photo_request(request, case_dir.name)
        analysis = analyze(photo)
        tier, severity = claim_answer(analysis)
        true_tier = str(truth["true_tier"])

        report.n_cases += 1
        report.n_photos += counts.get("photos", 0)
        report.zone_lost += counts.get("zone_lost", 0)
        report.clock_off += counts.get("clock_off", 0)
        matrix.setdefault(true_tier, Counter())[tier] += 1
        if tier == "no_data":
            report.no_data += 1
        if true_tier == "consistent" and tier == "contradicted":
            if severity == "strong":
                report.false_strong += 1
                report.false_strong_cases.append(case_dir.name)
            else:
                report.false_moderate += 1
        if severity == "strong" and photo.fixes and all(f.tz_assumed for f in photo.fixes):
            report.strong_from_assumed_only += 1
    report.matrix = {t: dict(sorted(c.items())) for t, c in sorted(matrix.items())}
    return report


def published_figures(report: PhotoReport) -> dict[str, Any]:
    return {
        "n_cases": report.n_cases,
        "n_photos": report.n_photos,
        "zone_lost": report.zone_lost,
        "clock_off": report.clock_off,
        "false_strong": report.false_strong,
        "false_moderate": report.false_moderate,
        "no_data": report.no_data,
        "strong_from_assumed_only": report.strong_from_assumed_only,
    }


def format_report(report: PhotoReport) -> str:
    lines = [
        "Photo-only sweep (v1.1)",
        f"  cases {report.n_cases}, photos {report.n_photos} "
        f"({report.zone_lost} with no time zone, {report.clock_off} of those an hour off)",
        f"  false STRONG contradictions: {report.false_strong}   <- gate, must be 0",
        f"  false MODERATE contradictions: {report.false_moderate}",
        f"  STRONG resting only on assumed-zone photos: {report.strong_from_assumed_only}",
        f"  no data at the claimed time: {report.no_data} of {report.n_cases}",
        "  true tier -> engine tier:",
    ]
    for true_tier, row in report.matrix.items():
        lines.append(f"    {true_tier:<13} {row}")
    return "\n".join(lines)
