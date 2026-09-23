"""Score the engine against the synthetic corpus' ground truth. Session 6.

The corpus labels come from `fixtures/generator`, which decides them by construction and
never by calling the engine. Keeping the two independent is what makes these numbers worth
publishing on the Methodology page.

    uv run python eval/run_eval.py --corpus fixtures/out --out eval/results
"""

from __future__ import annotations

import argparse
from pathlib import Path


def run(corpus: Path, out: Path) -> None:
    """Analyse every case, compare tiers against ground truth, write the report."""
    raise NotImplementedError("Session 6")


def main() -> None:
    parser = argparse.ArgumentParser(prog="run_eval", description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("fixtures/out"))
    parser.add_argument("--out", type=Path, default=Path("eval/results"))
    args = parser.parse_args()
    run(args.corpus, args.out)


if __name__ == "__main__":
    main()
