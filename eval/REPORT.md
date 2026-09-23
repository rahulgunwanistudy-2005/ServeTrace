# Evaluation

Three evals live here. The **engine** and **advocate** evals have been run and their
numbers are below; both come out of one command. The **extraction** eval is written and
has not been run, for want of an API key.

## The engine

```bash
cd backend && PYTHONPATH=.. uv run python ../eval/run_eval.py \
    --corpus ../fixtures/out --out ../eval/results
```

Scored against the 200-case synthetic corpus in `fixtures/out/`. The generator decides
each label **by construction** — it records where it placed the person — and never by
calling the engine. Scoring an engine against labels the engine produced would measure
nothing, and that independence is the only reason these numbers are worth publishing.

Full output lands in `eval/results/engine.json`. The subset the Methodology page shows is
written to `frontend/src/lib/eval/published.json`, and a test in the backend suite fails
if that file goes stale.

### The number that matters

**0 false contradictions.** Across 200 cases, the engine told nobody their data conflicted
with an affidavit when the generator had placed them at the door. Telling someone their
own records contradict a sworn statement when they do not is the one failure that could
hurt a user in court, so it leads, and it has to be zero.

### Accuracy

Two figures, because they answer two questions.

| | |
|---|---|
| **Claimed moment read correctly** | **100.0%** (200 / 200) |
| Whole-case answer | 98.0% (196 / 200) |

The generator labels one thing: where it put the person at the *claimed service time*. So
the like-for-like comparison is the engine's verdict on that claim, and it is right on
every case in the corpus.

`overall` answers a second, product-level question — it also folds in the prior attempts a
308(4) affidavit swears to, which the generator does not label. All four disagreements are
that, and only that: in each one the engine read the claimed moment correctly and then
reported a contradicted *earlier attempt*. Reported separately rather than blended in,
because averaging them together would hide which number moved.

### Confusion matrix — the claimed moment

Rows are what the generator built, columns what the engine answered.

| built as \ answered | contradicted | consistent | no data | inconclusive |
|---|---|---|---|---|
| **contradicted** | **80** | 0 | 0 | 0 |
| **consistent** | 0 | **83** | 0 | 0 |
| **no data** | 0 | 0 | **30** | 0 |
| **inconclusive** | 0 | 0 | 0 | **7** |

### The awkward cases, counted separately

These are where a threshold is either honest or it is not, so they are not averaged away.

| edge case | n | claimed moment |
|---|---|---|
| The November DST fold, where the stated time means two moments | 5 | 100% |
| A single point just inside the match radius | 4 | 100% |
| A single point just outside it, but an easy walk away | 7 | 100% |
| A claim falling moments outside a recorded stay | 4 | 100% |

The third row is the one that moved the engine. Bible §11.1.3 guards sub-minute gaps with
an infinite required speed whenever the fix is outside the match radius, and taken
literally that called a phone 450 m from a door at the claimed minute a STRONG
contradiction — a two-minute walk, and the width of a geocoding error. The generator had
independently labelled that case `INCONCLUSIVE`, and it was right. The guard is now a
floor on elapsed time rather than a jump to infinity: affidavit times are written to the
minute and phone timestamps are rounded to it, so a gap under a minute is not a
measurement, and a distance divided by rounding noise is not a speed. See
`backend/app/engine/feasibility.py`.

### The paperwork rules

Every rule the generator deliberately seeded, where that rule applies, is caught.

| rule | seeded | caught | missed | also found elsewhere | seeded outside the rule's scope |
|---|---|---|---|---|---|
| R-T1 mailing missing | 28 | 28 | 0 | 0 | 0 |
| R-T2 mailing > 20 days from delivery | 24 | 24 | 0 | 0 | 0 |
| R-T3 proof filed > 20 days late | 32 | 32 | 0 | 0 | 6 |
| R-D1 thin due diligence | 17 | 17 | 0 | 0 | 0 |
| R-D2 an attempt itself contradicted | 0 | 0 | 0 | 31 | 0 |

Two columns need their meaning stated rather than assumed.

*Also found elsewhere* is not an error. The generator seeds *some* violations on purpose;
others fall out of the dates it happens to draw, and the engine is right to report those
too. R-D2 is never seeded at all — it depends on the user's location data rather than on
the affidavit — so all 31 are genuine findings about attempts the corpus' own location
histories conflict with.

*Seeded outside the rule's scope* is a disagreement between the generator and the bible,
resolved in the bible's favour. The generator will put a late proof-of-service date on a
308(1) affidavit; bible §11.3 scopes R-T3 to 308(2) and 308(4), and bible §5 gives no
authority for a filing deadline on personal delivery at all. Counting those six as misses
would penalise the engine for obeying §5, so they are counted and named instead of
quietly dropped.

### The description check

104 of 105 descriptions matching nobody in the household were flagged, with **0
households wrongly told that nobody matched**. A false mismatch would be an accusation
about a member of the user's own family, so that zero matters more than the 104.

51 cases were not scored: they are 308(4), where the papers were taped to a door and
nobody accepted anything, so there is nobody to compare against and a mismatch would mean
nothing.

The single miss is the engine being right and the label being loose. In `case_0076` the
affidavit describes a female aged 52–62, 6'1"–6'5". The generator built that description
by shifting the defendant's own details and labelled the case "does not match", but the
household it also generated contains a partner: female, 55, 6'2". Somebody in that
household plainly does match, and saying otherwise would have been a false accusation.

### Runtime

| | |
|---|---|
| Median case | 0.14 ms |
| p95 | 0.8 ms |
| 5,000 fixes × 4 claims | **4 ms** against a 200 ms budget |

Fixes are sorted and indexed once per request and bisected per claim, so an affidavit with
three prior attempts asks four questions of one export rather than four passes over it.
Asserted by `backend/tests/engine/test_performance.py`, which prints the real figures.

## Advocate mode

A different question, a different corpus, and a different failure to be afraid of. The
defendant engine asks whether one person's phone can be reconciled with one sworn claim.
Batch mode asks whether a *process server's own filings* can be reconciled with each
other, which needs no location history from anybody: two services sworn eleven kilometres
apart three minutes apart are in conflict whatever either defendant was doing.

`fixtures/generator/advocate.py` builds five servers' filings — 400 each — and rewrites
some of two servers' records into sequences nobody could have travelled, writing down
exactly which. It decides that from where it *placed* the records and never by calling the
engine, the same independence the case corpus rests on.

### The number that matters

**No server the generator built as ordinary is named: 0 of 3.**

This is batch mode's version of the no-false-accusation gate, and it is the inverse of a
recall number. A sequence the engine misses costs an advocate one line of evidence. A
sequence it reports wrongly goes into a filing or a DCWP complaint under that advocate's
name, and costs them their credibility with whoever reads it. Precision leads; recall
follows.

### Impossible sequences

| | |
|---|---|
| Filings scored | 2,000 |
| Process servers | 5 |
| Planted sequences found | **12 of 12** (recall 100%) |
| Sequences reported that were not planted | **0** (precision 100%) |
| Ordinary servers named | **0 of 3** |
| Reused descriptions | 16 of 16 doors found |

Both flagged servers rank above all three ordinary ones, which is what an advocate
actually reads: the order of the table, not the numbers in it.

A caveat worth stating plainly. 100% precision over 2,000 filings of synthetic ordinary
work is a statement about *this* corpus, whose ordinary days are 14 to 48 minutes apart
within one borough. A real agency's records will contain same-minute duplicate filings,
mis-keyed dates and two servers sharing a licence number, and each of those can look like
an impossible sequence. That is why the ingest returns every unusable row with a reason
instead of dropping it, and why the report never says anything stronger than that two
filings cannot both be right.

### Runtime

| | |
|---|---|
| 2,000 filings | 15 ms |
| 50,000 filings × 25 servers | **247 ms** against a 3 s budget |
| 25,000 → 50,000 filings | 1.98× the time |

That last row is the one that matters. A wall-clock budget passes on a fast laptop even
for an implementation that compares every filing with every other; the ratio is what
asserts the complexity is sort-plus-one-pass. Both are asserted by
`backend/tests/advocate/test_performance.py`, which prints the real figures.

## Extraction — written, not yet run

`eval/extraction_eval.py` scores the extractor field by field against the corpus' ground
truth: exact match for names and licence numbers, minute precision for the claimed time,
and 50 m of geographic tolerance for addresses, so an address counts as right when the
extractor found the right building rather than the generator's punctuation. Clean and
scanned variants are reported separately, and a document the extractor could not read at
all is counted as a failure rather than dropped from the denominator.

**It has not been run.** This machine has no `GEMINI_API_KEY` or `ANTHROPIC_API_KEY`, and
the script refuses to invent numbers with `LLM_PROVIDER=none`. Its arithmetic is covered by
`backend/tests/eval/test_extraction_eval.py`, which runs offline. To produce the figures:

```bash
python -m fixtures.generator --n 200 --seed 7
cd backend && PYTHONPATH=.. LLM_PROVIDER=gemini GEMINI_API_KEY=... \
    uv run python ../eval/extraction_eval.py --corpus ../fixtures/out --out ../eval/results
```

Results land in `eval/results/extraction.json` and belong on the Methodology page exactly
as they come out.

## Still to measure

- **Extraction**, above, once a key exists.
- **A robustness sweep** over GPS jitter and sampling gaps, per S8.

## Honesty

Whatever these numbers are, they go on the Methodology page as they come out, including
the cases the engine gets wrong and the ones it declines to call. The page reads a
generated file rather than hand-typed figures, so it cannot quietly fall out of step with
this report.
