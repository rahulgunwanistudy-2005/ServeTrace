"""Score extraction per affidavit layout (v1.1). Bible §12; build prompt §4.4.

    cd backend && PYTHONPATH=.. uv run python -m fixtures.generator.layouts --per-layout 25
    cd backend && PYTHONPATH=.. uv run python ../eval/layout_eval.py   # no key: deterministic
    cd backend && PYTHONPATH=.. LLM_PROVIDER=gemini GEMINI_API_KEY=... \\
        uv run python ../eval/layout_eval.py                                   # every field

Two kinds of number come out of this, and they are reported apart:

- **Deterministic** — page classification on text-layer pages, the grouping of pages into
  affidavits, and the judgment entry date read off a text layer. These need no model and
  are the same on every run.
- **Model-dependent** — per-field accuracy, and classification of image-only pages. These
  need a provider key and are reported as "not run" without one, never as zero.

Targets (§4.4, reported honestly whether met or missed): `served_at` to the minute and
`served_address` ≥ 95% on L1-L3 and ≥ 85% on L4-L7; page classification ≥ 95% on L8.
Labels come from the generator (`truth.json`), never from the reader.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.extraction.vision import extract_document
from eval.extraction_eval import normalize, score

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "fixtures" / "out" / "layouts"
CONCURRENCY = 4

TARGETS: dict[str, float] = {
    **{layout: 0.95 for layout in ("L1", "L2", "L3")},
    **{layout: 0.85 for layout in ("L4", "L5", "L6", "L7", "L7-heic")},
}


@dataclass(slots=True)
class Scored:
    layout: str
    case_id: str
    text_layer: bool
    pages_right: int = 0
    pages_total: int = 0
    text_pages_right: int = 0
    text_pages_total: int = 0
    grouping_right: bool = False
    judgment_expected: str | None = None
    judgment_read: str | None = None
    fields: dict[str, bool] = field(default_factory=dict)
    boxes: tuple[int, int] = (0, 0)
    """(fields with a quote, of those with a box). Text-layer documents only."""
    error: str | None = None


def targets(corpus: Path) -> list[tuple[str, Path, dict[str, Any]]]:
    found: list[tuple[str, Path, dict[str, Any]]] = []
    for truth_path in sorted(corpus.glob("L*/*/truth.json")):
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        for name in truth["files"]:
            variant = truth["layout"] + ("-heic" if name.endswith(".heic") else "")
            found.append((variant, truth_path.parent / name, truth))
    return found


async def score_one(variant: str, path: Path, truth: dict[str, Any], provider: str) -> Scored:
    scored = Scored(layout=variant, case_id=truth["case_id"], text_layer=truth["text_layer"])
    try:
        result = await extract_document(path.read_bytes(), previews=False)
    except Exception as exc:  # a failed read is a result, not a crashed run
        scored.error = type(exc).__name__
        return scored

    expected_types: list[str] = truth["page_types"]
    got = [t.value for t in result.page_types]
    scored.pages_total = len(expected_types)
    scored.pages_right = sum(a == b for a, b in zip(got, expected_types, strict=False))
    if truth["text_layer"]:
        scored.text_pages_total = scored.pages_total
        scored.text_pages_right = scored.pages_right
    scored.grouping_right = [a.pages for a in result.affidavits] == truth["affidavit_pages"]
    scored.judgment_expected = truth["judgment_entry_date"]
    scored.judgment_read = (
        result.judgment_entry_date.isoformat() if result.judgment_entry_date else None
    )

    if provider != "none" and result.affidavits:
        draft = result.affidavits[0].draft
        scored.fields = await score(draft, truth["affidavit"])
        scored.fields["agency_name"] = normalize(draft.agency_name) == normalize(
            truth["affidavit"].get("agency_name")
        )
        if truth["text_layer"]:
            quoted = [e for e in draft.evidence.values() if e.quote]
            scored.boxes = (len(quoted), sum(1 for e in quoted if e.bbox))
    return scored


def _rate(right: int, total: int) -> float | None:
    return round(right / total, 4) if total else None


def summarise(results: list[Scored], provider: str) -> dict[str, Any]:
    by_layout: dict[str, list[Scored]] = defaultdict(list)
    for item in results:
        by_layout[item.layout].append(item)

    report: dict[str, Any] = {}
    for layout, items in sorted(by_layout.items()):
        ok = [i for i in items if i.error is None]
        entry: dict[str, Any] = {
            "n_documents": len(items),
            "n_failed": len(items) - len(ok),
            "page_classification": _rate(
                sum(i.pages_right for i in ok), sum(i.pages_total for i in ok)
            ),
            "affidavit_grouping": _rate(sum(i.grouping_right for i in ok), len(ok)),
        }
        with_judgment = [i for i in ok if i.layout == "L8"]
        if with_judgment:
            entry["judgment_entry_date"] = _rate(
                sum(i.judgment_read == i.judgment_expected for i in with_judgment),
                len(with_judgment),
            )
            entry["judgment_false_dates"] = sum(
                1 for i in with_judgment if i.judgment_read and not i.judgment_expected
            )
        if provider == "none":
            entry["fields"] = "not run: no provider configured"
        else:
            totals: dict[str, list[bool]] = defaultdict(list)
            for item in ok:
                for name, correct in item.fields.items():
                    totals[name].append(correct)
            entry["per_field_accuracy"] = {
                name: round(sum(v) / len(v), 4) for name, v in sorted(totals.items())
            }
            target = TARGETS.get(layout)
            if target is not None:
                for name in ("served_at", "served_address"):
                    value = entry["per_field_accuracy"].get(name)
                    entry[f"{name}_meets_target"] = value is not None and value >= target
            quoted = sum(i.boxes[0] for i in ok)
            entry["evidence_boxed"] = _rate(sum(i.boxes[1] for i in ok), quoted)
        report[layout] = entry
    return report


async def run(corpus: Path, out: Path, limit: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    found = targets(corpus)[:limit] if limit else targets(corpus)
    if not found:
        raise SystemExit(f"no layouts under {corpus}. Run fixtures.generator.layouts first.")
    gate = asyncio.Semaphore(CONCURRENCY)

    async def one(args: tuple[str, Path, dict[str, Any]]) -> Scored:
        async with gate:
            return await score_one(*args, provider=settings.llm_provider)

    results = list(await asyncio.gather(*(one(t) for t in found)))
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": settings.llm_provider,
        "corpus": str(corpus),
        "targets": TARGETS,
        "layouts": summarise(results, settings.llm_provider),
        "failures": [
            {"layout": i.layout, "case_id": i.case_id, "error": i.error} for i in results if i.error
        ],
        "misclassified": [
            {"layout": i.layout, "case_id": i.case_id}
            for i in results
            if i.error is None and i.pages_right != i.pages_total
        ],
        "judgment_misses": [
            {"case_id": i.case_id, "expected": i.judgment_expected, "read": i.judgment_read}
            for i in results
            if i.layout == "L8" and i.judgment_read != i.judgment_expected
        ],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "layouts.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(prog="layout_eval", description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--out", type=Path, default=ROOT / "eval" / "results")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    report = asyncio.run(run(args.corpus, args.out, args.limit))
    print(f"provider: {report['provider']}")
    for layout, figures in report["layouts"].items():
        shown = {k: v for k, v in figures.items() if k != "per_field_accuracy"}
        print(f"{layout:<8} {json.dumps(shown)}")
        for name, value in figures.get("per_field_accuracy", {}).items():
            print(f"           {name:<24} {value:.3f}")


if __name__ == "__main__":
    main()
