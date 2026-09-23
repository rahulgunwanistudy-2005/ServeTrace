"""Score the extractor against the synthetic corpus' ground truth. Bible §12, S2 §9.

    python -m fixtures.generator --n 200 --seed 7          # writes fixtures/out with PDFs
    cd backend && PYTHONPATH=.. LLM_PROVIDER=gemini GEMINI_API_KEY=... \\
        uv run python ../eval/extraction_eval.py --corpus ../fixtures/out --out ../eval/results

This one *does* call a provider: it is the only script in the repo that needs a key, and
it is never part of the test suite. Clean and scanned variants are scored separately,
because scans are what users actually upload and the two numbers are not the same number.

The labels come from `fixtures/generator`, which wrote the affidavit and then rendered it.
The extractor is being measured against the document's own truth, not against itself.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.api.errors import UpstreamError
from app.config import get_settings
from app.domain.models import AffidavitDraft
from app.extraction.vision import extract_affidavit
from app.geo.distance import haversine_km
from app.geo.geocode import geocode

ADDRESS_TOLERANCE_KM = 0.05
"""S2 §9: an address counts as right if it resolves within 50 m of the true one."""

CONCURRENCY = 4

STRING_FIELDS = (
    "index_number",
    "court",
    "plaintiff",
    "defendant_name",
    "server_name",
    "server_license",
    "agency_license",
    "method",
)
ADDRESS_FIELDS = ("served_address", "mailing_address")
DATE_FIELDS = ("mailing_date", "proof_filed_date")
DESCRIPTION_FIELDS = ("sex", "age_min", "age_max", "height_in_min", "height_in_max")

_PUNCTUATION = re.compile(r"[^a-z0-9 ]+")
_SPACES = re.compile(r"\s+")


def normalize(value: object) -> str:
    return _SPACES.sub(" ", _PUNCTUATION.sub(" ", str(value or "").lower())).strip()


@dataclass(frozen=True, slots=True)
class Scored:
    case_id: str
    variant: str
    fields: dict[str, bool]
    error: str | None = None


async def _address_matches(predicted: str | None, truth: str | None) -> bool:
    if not predicted or not truth:
        return predicted == truth
    if normalize(predicted) == normalize(truth):
        return True
    try:
        here, there = await geocode(predicted), await geocode(truth)
    except UpstreamError:
        # An address the lookup cannot resolve is scored as a miss, not as a crashed run.
        return False
    if here is None or there is None:
        return False
    return haversine_km(here.location, there.location) <= ADDRESS_TOLERANCE_KM


async def score(draft: AffidavitDraft, truth: dict[str, Any]) -> dict[str, bool]:
    fields: dict[str, bool] = {
        name: normalize(getattr(draft, name)) == normalize(truth.get(name))
        for name in STRING_FIELDS
    }

    claimed = str(truth["served_at"])[:16]
    fields["served_at"] = (
        draft.served_at is not None and draft.served_at.isoformat()[:16] == claimed
    )

    for name in ADDRESS_FIELDS:
        fields[name] = await _address_matches(getattr(draft, name), truth.get(name))

    for name in DATE_FIELDS:
        fields[name] = normalize(getattr(draft, name)) == normalize(truth.get(name))

    fields["attempts_count"] = len(draft.attempts) == len(truth.get("attempts", []))

    expected = truth.get("recipient_description") or {}
    got = draft.recipient_description
    fields["recipient_description"] = bool(expected) == bool(got) and all(
        (getattr(got, part, None) if got else None) == expected.get(part)
        for part in DESCRIPTION_FIELDS
    )
    return fields


async def score_file(case_id: str, variant: str, pdf: Path, truth: dict[str, Any]) -> Scored:
    try:
        result = await extract_affidavit(pdf.read_bytes())
    except Exception as exc:  # a failed extraction is a result, not a crashed run
        return Scored(case_id=case_id, variant=variant, fields={}, error=type(exc).__name__)
    return Scored(case_id=case_id, variant=variant, fields=await score(result.draft, truth))


def _targets(corpus: Path, limit: int | None) -> list[tuple[str, str, Path, dict[str, Any]]]:
    targets: list[tuple[str, str, Path, dict[str, Any]]] = []
    for case_dir in sorted((corpus / "cases").iterdir()):
        affidavit = case_dir / "affidavit.json"
        if not affidavit.is_file():
            continue
        truth = json.loads(affidavit.read_text(encoding="utf-8"))
        for variant, name in (("clean", "affidavit.pdf"), ("scanned", "affidavit_scanned.pdf")):
            pdf = case_dir / name
            if pdf.is_file():
                targets.append((case_dir.name, variant, pdf, truth))
    return targets[:limit] if limit else targets


def summarise(results: list[Scored]) -> dict[str, Any]:
    by_variant: dict[str, list[Scored]] = defaultdict(list)
    for item in results:
        by_variant[item.variant].append(item)

    report: dict[str, Any] = {}
    for variant, items in sorted(by_variant.items()):
        scored = [item for item in items if item.error is None]
        totals: dict[str, list[bool]] = defaultdict(list)
        for item in scored:
            for name, correct in item.fields.items():
                totals[name].append(correct)
        per_field = {
            name: round(sum(values) / len(values), 4) for name, values in sorted(totals.items())
        }
        report[variant] = {
            "n_documents": len(items),
            "n_extracted": len(scored),
            "n_failed": len(items) - len(scored),
            "per_field_accuracy": per_field,
            "mean_field_accuracy": (
                round(sum(per_field.values()) / len(per_field), 4) if per_field else 0.0
            ),
        }
    return report


async def run(corpus: Path, out: Path, limit: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    if settings.llm_provider == "none":
        raise SystemExit(
            "LLM_PROVIDER is 'none', so there is nothing to evaluate. Set LLM_PROVIDER "
            "and the matching API key, then run this again."
        )

    targets = _targets(corpus, limit)
    if not targets:
        raise SystemExit(f"no rendered affidavits under {corpus}. Run the fixture generator first.")

    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(args: tuple[str, str, Path, dict[str, Any]]) -> Scored:
        async with gate:
            return await score_file(*args)

    results = await asyncio.gather(*(one(target) for target in targets))
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": settings.llm_provider,
        "model": (
            settings.gemini_model if settings.llm_provider == "gemini" else settings.anthropic_model
        ),
        "corpus": str(corpus),
        "address_tolerance_km": ADDRESS_TOLERANCE_KM,
        "variants": summarise(list(results)),
        "failures": [
            {"case_id": item.case_id, "variant": item.variant, "error": item.error}
            for item in results
            if item.error
        ],
    }

    out.mkdir(parents=True, exist_ok=True)
    (out / "extraction.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(prog="extraction_eval", description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("fixtures/out"))
    parser.add_argument("--out", type=Path, default=Path("eval/results"))
    parser.add_argument("--limit", type=int, default=None, help="score only the first N documents")
    args = parser.parse_args()

    report = asyncio.run(run(args.corpus, args.out, args.limit))
    for variant, figures in report["variants"].items():
        print(f"{variant}: {figures['n_extracted']}/{figures['n_documents']} documents")
        print(f"  mean per-field accuracy: {figures['mean_field_accuracy']:.3f}")
        for name, value in figures["per_field_accuracy"].items():
            print(f"    {name:<24} {value:.3f}")


if __name__ == "__main__":
    main()
