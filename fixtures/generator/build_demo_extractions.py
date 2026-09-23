"""Cache an extraction for each demo case so demo mode never calls an LLM.

    cd backend && PYTHONPATH=.. uv run python -m fixtures.generator.build_demo_extractions

With a provider configured, the real extractor runs and its answer is recorded. Without
one, the draft is derived from each case's committed `affidavit.json` and its rendered
text layer: the same fields, quoted from the same document, run through the same
deterministic validators. Either way the result is written to
`fixtures/demo_cases/<case>/extraction.json` in the exact shape `POST /api/extract`
returns, and `provider` records which of the two it was, so a derived draft can never be
mistaken for something a model said.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.domain.models import AffidavitDraft, AttemptDraft, ExtractionResult
from app.extraction.pdf_text import extract_text, sha256_of
from app.extraction.validators import validate
from app.extraction.vision import extract_affidavit

from .writer import write_json

DEMO_DIR = Path(__file__).resolve().parents[1] / "demo_cases"

DERIVED = "derived_from_ground_truth"

CONFIDENCE: dict[str, float] = {
    "index_number": 0.96,
    "court": 0.93,
    "plaintiff": 0.95,
    "defendant_name": 0.97,
    "server_name": 0.94,
    "server_license": 0.93,
    "agency_license": 0.9,
    "method": 0.92,
    "served_date": 0.96,
    "served_time": 0.95,
    "served_address": 0.94,
    "recipient_name": 0.86,
    "recipient_relationship": 0.87,
    "recipient_description": 0.83,
    "mailing_date": 0.9,
    "mailing_address": 0.89,
    "proof_filed_date": 0.85,
}
"""Fixed, so the demo fixtures stay byte-identical between runs. These stand in for a
model's own estimates and are deliberately unremarkable: nothing in the demo turns on a
field being flagged amber that a real extraction would have read confidently."""


def quote_for(text: str, printed: str | None) -> str | None:
    """The verbatim span of `text` that says `printed`.

    Line wrapping and case are allowed to differ, because the form does both: it prints
    the court in capitals and wraps addresses mid-line. The span returned is always the
    document's own characters, never the ones searched for.
    """
    if not printed:
        return None
    pattern = re.compile(r"\s+".join(re.escape(word) for word in printed.split()), re.IGNORECASE)
    found = pattern.search(text)
    return found.group(0) if found else None


def _printed_date(iso: str | None) -> str | None:
    """How the affidavit template prints a date: "June 12, 2025"."""
    if not iso:
        return None
    from datetime import date

    day = date.fromisoformat(iso)
    return f"{day.strftime('%B')} {day.day}, {day.year}"


def _printed_time(hhmm: str) -> str:
    """How the affidavit template prints a time: "7:42 PM"."""
    hour, minute = (int(part) for part in hhmm.split(":"))
    suffix = "AM" if hour < 12 else "PM"
    return f"{hour % 12 or 12}:{minute:02d} {suffix}"


METHOD_PHRASES: dict[str, str] = {
    "308_1": "to said Defendant personally",
    "308_2": "a person of suitable age and discretion",
    "308_4": "By affixing a true copy of each to the door of said premises",
}
"""The wording each method is actually read from, which is what a model would quote."""


def _needle_for(name: str, value: Any, printed: dict[str, str | None]) -> str:
    """What to look for on the page for this field.

    Three fields are not printed as their own value. The court is printed across two
    lines without the words "County of"; the method is printed as the statutory wording
    rather than as "308_2"; the description is printed as a table row without its labels.
    """
    if name == "court":
        return str(value).split(",")[0]
    if name == "method":
        return METHOD_PHRASES.get(str(value), str(value))
    if name == "recipient_description":
        raw = str(value.get("raw_text") or "")
        return " ".join(part.split(": ")[-1] for part in raw.split("  "))
    return printed.get(name) or str(value)


def derive_draft(affidavit: dict[str, Any], text: str) -> AffidavitDraft:
    """Rebuild what a perfect extraction of this document would have produced."""
    served_at = str(affidavit["served_at"])
    served_date, served_clock = served_at[:10], served_at[11:16]

    values: dict[str, Any] = {
        name: affidavit.get(name)
        for name in (
            "index_number",
            "court",
            "plaintiff",
            "defendant_name",
            "server_name",
            "server_license",
            "agency_license",
            "method",
            "served_address",
            "recipient_name",
            "recipient_relationship",
            "mailing_address",
        )
    }
    values["served_date"] = served_date
    values["served_time"] = served_clock
    values["mailing_date"] = affidavit.get("mailing_date")
    values["proof_filed_date"] = affidavit.get("proof_filed_date")
    values["recipient_description"] = affidavit.get("recipient_description")

    printed: dict[str, str | None] = {
        "served_date": _printed_date(served_date),
        "served_time": _printed_time(served_clock),
        "mailing_date": _printed_date(affidavit.get("mailing_date")),
        "proof_filed_date": _printed_date(affidavit.get("proof_filed_date")),
    }

    quotes: dict[str, str] = {}
    confidence: dict[str, float] = {}
    for name, value in values.items():
        if not value:
            continue
        quote = quote_for(text, _needle_for(name, value, printed))
        if quote:
            quotes[name] = quote
        confidence[name] = CONFIDENCE.get(name, 0.8)

    attempts = [
        AttemptDraft(
            at_date=str(attempt["at"])[:10],
            at_time=str(attempt["at"])[11:16],
            address=attempt.get("address"),
            outcome=attempt.get("outcome"),
        )
        for attempt in affidavit.get("attempts", [])
    ]
    for index, attempt in enumerate(affidavit.get("attempts", [])):
        quote = quote_for(text, str(attempt.get("address") or ""))
        if quote:
            quotes[f"attempts[{index}]"] = quote
        confidence[f"attempts[{index}]"] = 0.82

    return AffidavitDraft(
        **values,
        attempts=attempts,
        field_confidence=confidence,
        evidence_quotes=quotes,
    )


async def build_case(case_dir: Path) -> ExtractionResult:
    pdf = (case_dir / "affidavit.pdf").read_bytes()
    if get_settings().llm_provider != "none":
        return await extract_affidavit(pdf)

    layer = extract_text(pdf)
    affidavit = json.loads((case_dir / "affidavit.json").read_text(encoding="utf-8"))
    draft, notes = validate(derive_draft(affidavit, layer.text), layer.text)
    return ExtractionResult(
        draft=draft,
        notes=notes,
        provider=DERIVED,
        source_sha256=sha256_of(pdf),
        n_pages=layer.n_pages,
        has_text_layer=layer.has_text_layer,
        used_vision=False,
    )


async def build(demo_dir: Path = DEMO_DIR) -> list[str]:
    case_ids = json.loads((demo_dir / "index.json").read_text(encoding="utf-8"))["cases"]
    for case_id in case_ids:
        result = await build_case(demo_dir / case_id)
        write_json(demo_dir / case_id / "extraction.json", result)
    return list(case_ids)


if __name__ == "__main__":
    ids = asyncio.run(build())
    print(f"wrote extraction.json for {len(ids)} demo cases: {', '.join(ids)}")
