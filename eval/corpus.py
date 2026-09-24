"""Reading the corpus, and the one question every scorer in this package asks of it.

Both `run_eval` and `robustness` load cases and then want the same thing back: what did
the engine say about the *service claim*, and how strongly. Keeping that in one place is
partly about the import cycle it otherwise creates, and mostly about the fact that two
copies of "which findings count as a conflict" is two copies that can disagree — and the
number they feed is the one the whole eval is gated on.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.domain.models import AnalyzeRequest, CaseAnalysis, ClaimTier, Severity
from app.engine.verdict import MAIN_CLAIM

CONFLICT_CODES = ("F-VISIT", "F-PRISM")
"""The two findings that say the location data conflicts with a sworn moment.

`F-CONFLICT` is excluded deliberately: it records that consistent evidence *also* exists
alongside a conflict (bible §11.1.5), so counting it would double one case."""


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


def case_dirs(corpus: Path) -> list[Path]:
    cases = sorted(d for d in (corpus / "cases").iterdir() if d.is_dir())
    if not cases:
        raise SystemExit(f"no cases under {corpus / 'cases'}. Run `python -m fixtures.generator`.")
    return cases


def claim_answer(analysis: CaseAnalysis) -> tuple[str, str | None]:
    """The engine's verdict on the service claim, and the severity behind it.

    Scoped to the service claim on purpose. A 308(4) affidavit swears to prior attempts,
    and one of those can carry its own STRONG finding while the service claim itself is
    consistent — so a severity read off the whole finding list would answer a question
    about a different moment than the one the generator labelled.
    """
    main = next((v for v in analysis.verdicts if v.claim_ref == MAIN_CLAIM), None)
    tier = main.tier.value if main is not None else ClaimTier.NO_DATA.value
    conflicts = [
        f.severity
        for f in analysis.findings
        if f.code in CONFLICT_CODES and f.numbers.get("claim") == MAIN_CLAIM
    ]
    if Severity.STRONG in conflicts:
        return tier, Severity.STRONG.value
    if Severity.MODERATE in conflicts:
        return tier, Severity.MODERATE.value
    return tier, None
