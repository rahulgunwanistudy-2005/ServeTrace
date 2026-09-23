"""Generate the synthetic fixture corpus.

    python -m fixtures.generator --n 200 --seed 7        # -> fixtures/out/   (gitignored)
    python -m fixtures.generator --demo                  # -> fixtures/demo_cases/ (committed)

Everything is a pure function of `--seed`, so the same seed produces byte-identical JSON.
"""

from __future__ import annotations

import argparse
import random
from dataclasses import asdict
from pathlib import Path

from .advocate import generate_advocate
from .advocate import to_csv as advocate_csv
from .affidavit import render_pdf, scanned_variant, sha256_of
from .cases import Case, make_case
from .demo import DEMO_SPECS, build_demo_case
from .timeline import to_android_timeline, to_card_csv, to_ios_timeline
from .writer import write_bytes, write_json, write_text

FIXTURES_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = FIXTURES_DIR / "out"
DEMO_OUT = FIXTURES_DIR / "demo_cases"

# Bible/S1 §6 case mix.
MIX: tuple[tuple[str, float], ...] = (
    ("contradicted", 0.40),
    ("consistent", 0.35),
    ("no_data", 0.15),
    ("edge", 0.10),
)

SCANNED_EVERY = 10
"""Rasterising is slow, so only every tenth case gets a scanned variant."""


def case_kinds(n: int) -> list[str]:
    """Exact quotas, not sampled ones, so a 200-case run always has 80 contradictions."""
    kinds: list[str] = []
    for kind, share in MIX:
        kinds.extend([kind] * round(n * share))
    while len(kinds) < n:
        kinds.append("contradicted")
    return kinds[:n]


def write_case(case: Case, out_dir: Path, *, with_pdf: bool, with_scan: bool, seed: int) -> None:
    rng = random.Random(seed)
    case_dir = out_dir / case.case_id

    affidavit = case.affidavit
    if with_pdf:
        pdf = render_pdf(rng, affidavit)
        write_bytes(case_dir / "affidavit.pdf", pdf)
        affidavit = affidavit.model_copy(update={"source_sha256": sha256_of(pdf)})
        if with_scan:
            write_bytes(case_dir / "affidavit_scanned.pdf", scanned_variant(rng, pdf))

    write_json(case_dir / "affidavit.json", affidavit)
    write_json(case_dir / "ground_truth.json", asdict(case.truth))
    write_json(case_dir / "household.json", list(case.household))
    write_json(case_dir / "fixes.json", case.fixes)
    write_json(case_dir / "timeline_android.json", to_android_timeline(case.fixes))
    write_json(case_dir / "timeline_ios.json", to_ios_timeline(case.fixes))
    write_text(case_dir / "transactions.csv", to_card_csv(rng, case.fixes, case.person))


def generate_corpus(n: int, seed: int, out: Path, *, pdfs: bool) -> dict[str, object]:
    kinds = case_kinds(n)
    counts: dict[str, int] = {}
    tiers: dict[str, int] = {}
    ids: list[str] = []

    for index, kind in enumerate(kinds):
        # A per-case seed keeps every case independent of how many cases precede it.
        case_seed = seed * 1_000_003 + index
        case = make_case(random.Random(case_seed), f"case_{index:04d}", kind)
        write_case(
            case,
            out / "cases",
            with_pdf=pdfs,
            with_scan=pdfs and index % SCANNED_EVERY == 0,
            seed=case_seed ^ 0x5EED,
        )
        counts[kind] = counts.get(kind, 0) + 1
        tiers[case.truth.true_tier] = tiers.get(case.truth.true_tier, 0) + 1
        ids.append(case.case_id)

    records, server_truths = generate_advocate(random.Random(seed * 7919))
    write_text(out / "advocate" / "records.csv", advocate_csv(records))
    write_json(
        out / "advocate" / "ground_truth.json",
        {"servers": [asdict(t) for t in server_truths]},
    )

    manifest = {
        "seed": seed,
        "n_cases": n,
        "case_ids": ids,
        "kind_counts": dict(sorted(counts.items())),
        "true_tier_counts": dict(sorted(tiers.items())),
        "advocate_records": len(records),
        "advocate_servers": [t.server_id for t in server_truths],
        "pdfs_rendered": pdfs,
    }
    write_json(out / "manifest.json", manifest)
    return manifest


def generate_demo(out: Path) -> list[str]:
    ids: list[str] = []
    for index, spec_fn in enumerate(DEMO_SPECS):
        spec = spec_fn()
        case = build_demo_case(spec, seed=4242 + index)
        write_case(case, out, with_pdf=True, with_scan=True, seed=9001 + index)
        ids.append(case.case_id)
    write_json(out / "index.json", {"cases": ids})
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(prog="fixtures.generator", description=__doc__)
    parser.add_argument("--n", type=int, default=200, help="number of cases to generate")
    parser.add_argument("--seed", type=int, default=7, help="master seed")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--demo", action="store_true", help="write the three curated demo cases instead"
    )
    parser.add_argument("--no-pdfs", action="store_true", help="skip PDF rendering (much faster)")
    args = parser.parse_args()

    if args.demo:
        ids = generate_demo(DEMO_OUT)
        print(f"wrote {len(ids)} demo cases to {DEMO_OUT}: {', '.join(ids)}")
        return

    manifest = generate_corpus(args.n, args.seed, args.out, pdfs=not args.no_pdfs)
    print(f"wrote {manifest['n_cases']} cases to {args.out}")
    print(f"  kinds:  {manifest['kind_counts']}")
    print(f"  tiers:  {manifest['true_tier_counts']}")
    print(f"  advocate: {manifest['advocate_records']} records")


if __name__ == "__main__":
    main()
