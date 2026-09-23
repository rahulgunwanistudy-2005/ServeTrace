"""Builders for the document tests, and the one guard that keeps the PDF gate honest.

The engine's own builders are reused rather than copied (`tests/engine/conftest.py`):
a document test that invented its own affidavit would be testing a shape the engine never
produces, and the whole point of these two modules is that they render *the engine's*
output.

The `needs_pdf` guard lives in `tests/conftest.py`, beside the no-network guard, because
the API suite needs it too.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.domain.models import (
    AffiantStatement,
    AnalyzeRequest,
    CaseAnalysis,
    LocationFix,
)
from app.engine.verdict import analyze
from tests.engine.conftest import CLAIM_AT, DOOR, affidavit, away, fix, member, visit

DEMO_CASES = Path(__file__).resolve().parents[3] / "fixtures" / "demo_cases"
CASE_IDS = ("james_consistent", "lin_affix_mail_diligence", "maria_contradicted")

PINNED_AT = datetime(2026, 9, 23, 15, 10, tzinfo=UTC)
"""One fixed generation time, so every rendered byte in this suite is reproducible.

Bible §15 asks for a generation timestamp; S6 asks for deterministic output given
identical input. Both hold because the documents read `CaseAnalysis.generated_at` rather
than a clock, and this is the value the tests pin it to.
"""

KNEW_ON = date(2026, 3, 14)
ENTERED_ON = date(2025, 8, 1)


def pin(analysis: CaseAnalysis) -> CaseAnalysis:
    return analysis.model_copy(update={"generated_at": PINNED_AT})


def demo_request(case_id: str) -> AnalyzeRequest:
    case = DEMO_CASES / case_id
    fields = json.loads((case / "affidavit.json").read_text())
    fields["user_confirmed"] = True
    return AnalyzeRequest.model_validate(
        {
            "affidavit": fields,
            "fixes": json.loads((case / "fixes.json").read_text()),
            "household": json.loads((case / "household.json").read_text()),
            "knowledge_date": KNEW_ON.isoformat(),
            "judgment_entry_date": ENTERED_ON.isoformat(),
        }
    )


def demo_analysis(case_id: str) -> CaseAnalysis:
    return pin(analyze(demo_request(case_id)))


def demo_fixes(case_id: str) -> list[LocationFix]:
    return demo_request(case_id).fixes


def built(
    fixes: list[LocationFix] | None = None,
    household: list[Any] | None = None,
    knowledge_date: date | None = KNEW_ON,
    judgment_entry_date: date | None = ENTERED_ON,
    **overrides: Any,
) -> CaseAnalysis:
    """An analysis of a made-up case, for the rules that no demo case happens to trip."""
    return pin(
        analyze(
            AnalyzeRequest(
                affidavit=affidavit(**overrides),
                fixes=fixes if fixes is not None else [AT_WORK],
                household=household or [],
                knowledge_date=knowledge_date,
                judgment_entry_date=judgment_entry_date,
            )
        )
    )


AT_WORK = visit(CLAIM_AT - timedelta(hours=4), 480, away(14.0))
"""A twelve-hour stay 14 km away that covers the claimed moment: a STRONG F-VISIT."""

AT_HOME = visit(CLAIM_AT - timedelta(hours=1), 180, DOOR)
"""A stay at the sworn address across the claimed moment: CONSISTENT."""

PASSING_BY = fix(CLAIM_AT - timedelta(minutes=20), away(30.0))
"""One point, 30 km out, twenty minutes before: an F-PRISM with a speed to quote."""


def statement(**overrides: Any) -> AffiantStatement:
    fields: dict[str, Any] = {
        "name": "A. Defendant",
        "residence_address": "2100 WHITE PLAINS ROAD, Bronx, NY 10462",
        "states_not_served": True,
        "states_not_my_address": False,
        "states_no_notice_in_time": True,
        "defense_summary": None,
    }
    fields.update(overrides)
    return AffiantStatement.model_validate(fields)


__all__ = [
    "AT_HOME",
    "AT_WORK",
    "CASE_IDS",
    "CLAIM_AT",
    "DOOR",
    "ENTERED_ON",
    "KNEW_ON",
    "PASSING_BY",
    "PINNED_AT",
    "affidavit",
    "away",
    "built",
    "demo_analysis",
    "demo_fixes",
    "demo_request",
    "fix",
    "member",
    "pin",
    "statement",
    "visit",
]
