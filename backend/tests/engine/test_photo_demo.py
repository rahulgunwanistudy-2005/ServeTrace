"""Bible §11 DoD for v1.1: a person with no Timeline, only photos.

The fixes are the answer keys the vitest parser tests hold the browser parser to
(`fixtures/**/expected.json`), so this is the engine's half of an end-to-end statement:
these photos, read as the browser reads them, give this verdict.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.domain.models import AnalyzeRequest, ClaimTier, LocationFix
from app.engine.verdict import analyze
from eval.corpus import claim_answer

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
MARIA = FIXTURES / "demo_cases" / "maria_contradicted"


def photo_fixes(path: Path) -> list[LocationFix]:
    fixes = []
    for answer in json.loads(path.read_text()).values():
        if "skip" in answer:
            continue
        fixes.append(
            LocationFix.model_validate(
                {
                    "t": answer["t"],
                    "loc": {"lat": answer["lat"], "lng": answer["lng"]},
                    "accuracy_m": answer["accuracy_m"],
                    "kind": "photo",
                    "source": "photo",
                    "label": "Photo taken here",
                    "time_uncertainty_s": answer["time_uncertainty_s"],
                    "tz_assumed": answer["tz_assumed"],
                }
            )
        )
    return fixes


def maria(fixes: list[LocationFix]) -> AnalyzeRequest:
    affidavit = json.loads((MARIA / "affidavit.json").read_text())
    affidavit["user_confirmed"] = True
    return AnalyzeRequest.model_validate(
        {"affidavit": affidavit, "fixes": [], "household": []}
    ).model_copy(update={"fixes": fixes})


def test_maria_with_only_her_photos_is_not_left_with_no_data() -> None:
    analysis = analyze(maria(photo_fixes(MARIA / "photos" / "expected.json")))
    tier, severity = claim_answer(analysis)
    assert tier == ClaimTier.CONTRADICTED.value
    assert severity == "strong"


def test_maria_photos_with_their_zone_stripped_are_never_strong() -> None:
    """An hour's allowance either way covers 10 km of Manhattan traffic, so these honestly
    say less. Whatever they say, it is not a strong conflict."""
    analysis = analyze(maria(photo_fixes(MARIA / "photos_no_zone" / "expected.json")))
    tier, severity = claim_answer(analysis)
    assert tier != ClaimTier.NO_DATA.value
    assert severity != "strong"
    assert any(f.code == "F-TIME" for f in analysis.findings)


def test_a_zone_assumed_photo_130_km_away_is_a_moderate_conflict_not_a_strong_one() -> None:
    far = [
        f
        for f in photo_fixes(FIXTURES / "photos" / "expected.json")
        if abs(f.loc.lat - 39.9526) < 1e-3
    ]
    assert far and all(f.tz_assumed for f in far)
    tier, severity = claim_answer(analyze(maria(far)))
    assert tier == ClaimTier.CONTRADICTED.value
    assert severity == "moderate"
