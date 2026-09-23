# Evaluation

Not yet run. Session 6 fills this in.

## What gets measured

The engine is scored against the synthetic corpus in `fixtures/out/`, whose ground-truth
labels are decided by the generator *by construction* — it records where it placed the
person — and never by calling the engine. Scoring the engine against labels the engine
produced would measure nothing.

Planned figures:

- Confusion matrix over the four tiers: `CONTRADICTED`, `CONSISTENT`, `NO_DATA`,
  `INCONCLUSIVE`.
- **False contradiction rate.** The number that matters most. Telling someone their data
  conflicts with a sworn affidavit when it does not is the one failure that could hurt a
  user in court, so it is reported first and the thresholds are tuned to keep it near zero.
- Accuracy broken out by case kind, with the edge cases reported separately: DST fold,
  a fix exactly at the match radius, a walkable distance outside it, and visit-interval
  boundaries.
- Advocate mode: recall and precision against the injected impossible pairs, which are
  written to the corpus as a known answer key.
- Extraction: per-field accuracy on rendered affidavits, and on the scanned variants
  separately, since those are what users will actually upload.
- Runtime: analysis latency, and advocate throughput on 50,000 rows.

## Extraction eval — written, not yet run

`eval/extraction_eval.py` scores the extractor field by field against the corpus' ground
truth: exact match for names and licence numbers, minute precision for the claimed time,
and 50 m of geographic tolerance for addresses, so an address counts as right when the
extractor found the right building rather than the generator's punctuation. Clean and
scanned variants are reported separately, and a document the extractor could not read at
all is counted as a failure rather than dropped from the denominator.

**It has not been run.** This machine has no `GEMINI_API_KEY` or `ANTHROPIC_API_KEY`, and
the script refuses to invent numbers with `LLM_PROVIDER=none`. Its arithmetic is covered by
`backend/tests/eval/test_extraction_eval.py`, which runs offline. To produce the figures:

```
python -m fixtures.generator --n 200 --seed 7
cd backend && PYTHONPATH=.. LLM_PROVIDER=gemini GEMINI_API_KEY=... \
    uv run python ../eval/extraction_eval.py --corpus ../fixtures/out --out ../eval/results
```

Results land in `eval/results/extraction.json` and belong on the Methodology page exactly
as they come out.

## Honesty

Whatever these numbers are, they go on the Methodology page as they come out, including
the cases the engine gets wrong and the ones it declines to call.
