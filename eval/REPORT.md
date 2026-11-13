# Evaluation

**Run 2026-11-12 · ServeTrace 1.1.0 · thresholds `2026.09-v1` · engine 0.2.0.**

Eight evals live here. The **engine**, the **rules**, **advocate mode**, the
**robustness sweep** and, new in 1.1, the **photo-only sweep**, the **time-uncertainty
invariants**, the **attorney batch** and the **no-reader layout pass** all run from one
command and their numbers are below. Field-by-field **extraction** needs a paid model call
per document, so it runs on its own, and its caveats are stated beside its numbers.

```bash
python eval/run_eval.py
```

It generates the corpus if it is not there, scores everything, rewrites
`eval/results/*.json`, draws `eval/results/robustness.png`, and rewrites
`frontend/src/lib/eval/published.json` — which is what the Methodology page reads, so the
published figures cannot drift from the run that produced them. A backend test fails if
they do. About a minute on a laptop. It exits non-zero if any gate fails: a false
contradiction, a false STRONG contradiction from photos, a broken time-uncertainty
invariant, or a batch rule rate that disagrees with the independent count.

Run it twice and the numbers are identical, including the PNG byte for byte; this was
checked for 1.1 by running it twice and comparing `published.json` and every results file.
The only figures that move are the ones that time a machine (per-case latency, advocate
runtime). Nothing is sampled at report time; every random choice is seeded.

## Changes since 1.0

Nothing in 1.0's figures moved: the engine's verdicts on exact data are unchanged, and
every number in the sections after this one is what 1.0 published. What 1.1 adds:

### Photos only

Every one of the 500 cases, run again as if its owner had only a few camera-roll photos
from around the claimed time: 865 photos, 335 with no time zone, and 104 of those taken on
a clock an hour off New York (so the time the engine gets is wrong by an hour and marked as
assumed). Labels are the generator's, untouched.

| | |
|---|---|
| False STRONG contradictions (gate) | **0** |
| False MODERATE contradictions | 0 |
| STRONG resting only on assumed-zone photos | 0 |
| Cases with nothing near the claimed time | 196 of 500 |

Fewer records honestly means fewer answers: of the 200 truly contradicted cases, 23 are
still caught from photos alone, 176 become INCONCLUSIVE or NO_DATA, and 1 comes back
CONSISTENT — a photo taken at the door with a clock an hour off, whose widened time covers
the claim. That is a missed conflict, and the direction this product is built to err in. None of the 212 truly consistent cases
became a conflict of any strength.

### Time uncertainty

Bible §11.1.7's three promises, checked on every corpus case at seed 11 (`eval/uncertainty.py`):

| Invariant | Trials | Violations |
|---|---:|---:|
| Raising a fix's time uncertainty never strengthens the conflict | 1,500 | **0** |
| A conflict resting only on assumed-zone fixes is never STRONG | 500 | **0** |
| An exact photo at the door at the claimed time is CONSISTENT | 500 | **0** |

200 of the 500 cases were STRONG before every fix was marked zone-assumed; none stayed
STRONG after. The same three are also property tests over generated geometry
(`tests/engine/test_properties.py`).

### Attorney batch

60 synthetic affidavits from three agencies with problems planted on purpose, scored
against the generator's answer key (`eval/batch_eval.py`):

| Rule | Flagged | Planted | Precision | Recall |
|---|---:|---:|---:|---:|
| R-T1 missing mailing | 4 | 4 | 100% | 100% |
| R-D1 thin diligence | 5 | 5 | 100% | 100% |
| R-T2, R-T3, R-M1 | 0 | 0 | — | — |

Impossible back-to-back services: 2 of 2 found, none extra. The repeated description was
found at its three addresses. The clean agency had no flags and ranked last. Every rate's
denominator (affidavits the rule *applies* to) was recomputed independently from the raw
JSON and bible §11.3's table, and its numerator from the answer key: **0 of 5 rates
disagreed**. R-T2 and R-T3 at 0 flagged are honest zeros: the fixture plants no late
mailing or filing.

### Court files, with no reader

225 synthetic documents in nine layouts (`fixtures/out/layouts`), run through page
classification, affidavit grouping and judgment-date reading with `LLM_PROVIDER=none`:

| Layout | Text layer | Pages sorted right | Affidavits found right |
|---|---|---:|---:|
| L1–L3, L5 | yes | 100% | 100% |
| L4, L6, L7, L7-heic | no | 100% | 100% |
| L8 (summons + affidavits + judgment) | yes | 100% | 100% |

On L8 the judgment entry date was read right in 100% of files and never invented. Read the
image-only rows with care: with no reader, every image page is offered as a candidate
affidavit page by design, and these layouts hold only affidavit pages, so 100% there says
the fallback lost nothing, not that images were classified.

### Court files, with the reader (a small paid sample)

Run 2026-11-13 with `gemini-3.8-flash`, **two documents per layout, 18 in all**, chosen by
`--per-layout 2` (the first two files of each layout in sorted order, not hand-picked):

```bash
python eval/layout_eval.py --per-layout 2 --name layouts_paid
```

| Layout | Docs | Every field right | Pages sorted right | Affidavits found right | Quote boxed on the page |
|---|---:|---:|---:|---:|---:|
| L1–L3, L5 (text layer) | 8 | 16 of 16 fields, all docs | 100% | 100% | 100% (L2: 96.4%) |
| L4 handwritten, L6, L7, L7-heic (images) | 8 | 16 of 16 fields, all docs | 100% | 100% | n/a, no text layer |
| L8 court file | 2 | 16 of 16 fields, all docs | 100% | 100% | 100% |

The judgment entry date on L8 was right in both files and never invented elsewhere. No
document failed and the reader never failed. Here the image pages *were* classified by the
model, so unlike the no-reader pass above, 100% does mean the images were sorted.

**Read this as "it works on every layout", not as an accuracy rate.** Eighteen synthetic
documents cannot measure a rate: one error would have moved a layout by 50 points, and a
perfect score on 2 documents is compatible with a true error rate well above 10%. The
sample was kept small on purpose, to keep the bill to a few cents. A real figure needs
the full 225-document corpus (`python eval/layout_eval.py` with no `--per-layout`), and
real court papers would need more than synthetic ones.

On image-only pages every field is shown amber for the person to check, because no text
layer exists to locate the quote in and confidence is therefore capped at 0.6
(bible §12). That is the design working, not a weakness of the reader.

### Upload to review, in the app

Three documents from the corpus above went through `/check` in the browser, against the
dev server with the Gemini reader on, on 2026-11-14:

| Document | Pages | Upload → review card | Fields shown amber |
|---|---:|---:|---:|
| Handwritten affidavit (L4, PDF of a scan) | 1 | 23.3 s | 18 of 18 (image only) |
| Phone photo (L7, HEIC) | 1 | 11.6 s | 18 of 18 (image only) |
| Whole court file (L8: summons, affidavit, judgment) | 6 | 10.6 s | 5 of 18 (fields absent from the affidavit) |

In the court file the reader sorted all six pages, found the one affidavit on pages 4–5,
and filled in the judgment entry date for the person to confirm. Each document leaves well
over a minute and a half of a 2-minute budget for a person to read and confirm the card.
How long that human review takes was **not** measured here: the browser was driven by a
script, so its confirm click took no time. The dev build logs
`[review-timer] … s to confirm` for that, and timing a real person is the next step.

## The engine

Scored against a **500-case** synthetic corpus. The generator decides each label **by
construction** — it records where it *placed* the person — and never by calling the
engine. Scoring an engine against labels the engine produced would measure nothing, and
that independence is the only reason these numbers are worth publishing.

### The number that matters

**0 false contradictions.** Across 500 cases the engine told nobody their data conflicted
with an affidavit when the generator had placed them at the door. Telling someone their own
records contradict a sworn statement when they do not is the one failure that could hurt a
user in court, so it leads, and it has to be zero.

### Accuracy

Two figures, because they answer two questions.

| | |
|---|---|
| **Claimed moment read correctly** | **100.0%** (500 / 500) |
| Whole-case answer | 96.6% (483 / 500) |

The generator labels one thing: where it put the person at the *claimed service time*. So
the like-for-like comparison is the engine's verdict on that claim, and it is right on
every case in the corpus.

`overall` answers a second, product-level question — it also folds in the prior attempts a
308(4) affidavit swears to, which the generator does not label. All 17 disagreements are
that, and only that: in each one the engine read the claimed moment correctly and then
reported a contradicted *earlier attempt*. Reported separately rather than blended in,
because averaging them together would hide which number moved.

### CONTRADICTED, scored as a classifier

The engine reports a conflict at one of two severities, so it is really two classifiers
and they are scored as two. 200 of the 500 cases were built contradicted.

| operating point | precision | recall | TP | FP | FN |
|---|---|---|---|---|---|
| **STRONG only** | **100.0%** | **100.0%** | 200 | 0 | 0 |
| STRONG + MODERATE | 100.0% | 100.0% | 200 | 0 | 0 |

Read precision first. It is the share of the people this tells "your data conflicts" who
really were elsewhere, and a document filed in court rests on the STRONG row.

### Confusion matrix — the claimed moment

Rows are what the generator built, columns what the engine answered.

| built as \ answered | contradicted | consistent | no data | inconclusive |
|---|---|---|---|---|
| **contradicted** | **200** | 0 | 0 | 0 |
| **consistent** | 0 | **212** | 0 | 0 |
| **no data** | 0 | 0 | **75** | 0 |
| **inconclusive** | 0 | 0 | 0 | **13** |

### By case kind, and the edge cases counted separately

| kind | n | claimed moment | whole case |
|---|---|---|---|
| consistent | 175 | 100% | 100% |
| contradicted | 200 | 100% | 100% |
| no data | 75 | 100% | 81% |
| edge | 50 | 100% | 94% |
| — DST fold | 17 | 100% | 100% |
| — fix inside the radius | 7 | 100% | 100% |
| — walkable distance outside it | 13 | 100% | 77% |
| — visit boundary | 13 | 100% | 100% |

The edge buckets are where a threshold is either honest or it is not: a local time that
happens twice on the night the clocks go back, a fix just inside the match radius, a fix
just outside it but close enough to walk, and a recorded stay that starts or ends on the
claimed minute. The claimed moment is read correctly in all 50.

## The NY rules

Timing and diligence defects are seeded into affidavits by the generator, and the engine
has to find them without being told which ones are there.

| rule | seeded | caught | missed | also found elsewhere | seeded outside the rule's scope |
|---|---|---|---|---|---|
| R-T1 — no mailing shown | 54 | 54 | 0 | 0 | 0 |
| R-T2 — mailing more than 20 days from service | 55 | 55 | 0 | 0 | 0 |
| R-T3 — proof filed late | 62 | 62 | 0 | 0 | 16 |
| R-D1 — thin due diligence | 43 | 43 | 0 | 0 | 0 |
| R-D2 — a prior attempt contradicted | 0 | 0 | 0 | 103 | 0 |

**Nothing seeded in scope was missed.** Two columns need reading carefully rather than
skipping.

*Also found elsewhere* is not an error. R-D2 fires when the user's own data contradicts a
prior attempt, which is a property of the location history and not something the generator
plants in the affidavit, so every one of those 103 is the engine doing its job on data
nobody labelled for it.

*Seeded outside the rule's scope* names 16 cases the generator gave a late proof-of-service
date on a **308(1)** affidavit. Bible §11.3 scopes R-T3 to 308(2) and 308(4), and bible §5
gives no authority for a filing deadline on personal delivery at all. Counting them as
misses would penalise the engine for obeying the legal model; dropping them silently would
be the other kind of lie. They are named.

## The description check

Where the affidavit says the papers were handed to somebody, the engine compares that
person's description to the household the user described.

**242 of 244** mismatches caught. **0 of 115** false flags — no household that matched was
ever told it did not, which matters more than the recall figure, because a false mismatch
is an accusation about a member of the user's own family. 141 cases were not scored: papers
taped to a door were handed to nobody, so there is nothing to compare.

## Advocate mode

A different question over a different corpus: 2,000 filings from 5 synthetic process
servers, some of whose sequences were built so that nobody could have travelled them.

| | |
|---|---|
| **Ordinary servers wrongly named** | **0 of 3** |
| Impossible sequences found that were planted | 100% (12 / 12) |
| Planted sequences found | 100% |
| Reused descriptions | 16 / 16 doors |
| Runtime | 2,000 filings in ~20 ms |

Precision leads and recall follows. A sequence this misses costs an advocate one line of
evidence; a sequence it reports wrongly costs them their credibility with whoever reads the
report. The design target is 50,000 filings in under three seconds, and the measured rate
clears it by two orders of magnitude.

## Robustness — what happens when the data is bad

Every figure above is measured on clean synthetic data, where a fix is exactly where the
generator put the person. Real phone history is not like that. So the same 500 cases are
re-scored with the data deliberately spoiled.

**The labels do not move with the noise, and that is the point.** Ground truth is a
statement about where the generator *placed the person*. Jitter is the phone mis-measuring
that position, not the person walking; dropping fixes is the phone not looking, not the
person leaving. The person is where they always were, so the original label stays true and
a verdict that flips is a real error the noise induced.

![CONTRADICTED under measurement noise](results/robustness.png)

### GPS jitter, error not reported

Every point displaced by a circular Gaussian, and `accuracy_m` left lying about it — the
adversarial reading, a phone that under-reports its own error.

| sigma | precision | recall | verdicts changed | false contradictions |
|---|---|---|---|---|
| 20 m | 100.0% | 100.0% | 0 | 0 |
| 50 m | 100.0% | 100.0% | 0 | 0 |
| 100 m | 100.0% | 100.0% | 3 | 0 |
| 150 m | 100.0% | 100.0% | 27 | 0 |
| 200 m | 100.0% | 100.0% | 67 | 0 |
| 300 m | 99.5% | 100.0% | 121 | 1 |

Flat to 200 m, which already exceeds typical urban GPS error. It only gives anything up at
300 m — where the noise is as wide as the engine's entire match radius, so the error is the
same size as the thing being measured.

### GPS jitter, error reported

The same displacements, with `accuracy_m` raised to match, which is what a real export
contains. Bible §11.1 widens the match radius by exactly that figure.

| sigma | precision | recall | verdicts changed | false contradictions |
|---|---|---|---|---|
| 100 m | 100.0% | 100.0% | 3 | 0 |
| 200 m | 100.0% | 100.0% | 20 | 0 |
| 300 m | **100.0%** | **100.0%** | 38 | **0** |

Every figure holds, all the way out. The pair of tables is the useful part: run alone the
first would overstate the risk and the second would hide it. Together they say the engine
depends on the phone declaring its uncertainty — and that when it does, this degrades to
nothing at all.

**This pair is also what found a real bug**, which is the best argument for having built
the sweep. On the first run, reporting the accuracy changed *nothing* — both columns showed
18 false contradictions at 300 m. That should have been impossible if the radius were doing
any work, and it was not: `_required_speed` short-circuited to zero inside the radius and
priced the full distance one metre outside it, so a fix accurate to 500 m was consistent at
799 m from the door and a moderate contradiction at 801 m. Two metres of GPS noise deciding
whether a sworn statement was contradicted. Pricing only the distance beyond what the data
can resolve is continuous, changes nothing on the clean corpus — all 500 cases score
identically either way — and is what turned the middle table flat.

### Sampling gaps

The record thinned until consecutive points are at least this far apart. Recorded stays are
intervals rather than samples, so only journey points and transactions are thinned.

| gap | precision | recall | false contradictions |
|---|---|---|---|
| 2 min | 100.0% | 100.0% | 0 |
| 10 min | 100.0% | 100.0% | 0 |
| 15 min | 100.0% | 98.0% | 0 |
| 20 min | 100.0% | 98.0% | 0 |
| 30 min | 100.0% | 94.5% | 0 |

Precision never moves and recall falls, which is the right shape and the only honest one.
Thinning destroys information, so some real conflicts stop being provable — and the engine
answers "we don't have data for that time" instead of guessing. Nobody is ever wrongly told
their data conflicts.

## Speed

| | |
|---|---|
| Per case, median | 0.14 ms |
| Per case, p95 | 0.71 ms |
| Per case, max | 1.4 ms |
| 2,000 advocate filings | ~20 ms |

Whole-corpus, whole-sweep: about 10 seconds for 500 cases scored 22 times over.

## Extraction — gemini-3.8-flash, 66 documents

`eval/extraction_eval.py` scores the affidavit extractor per field against the generator's
own truth, clean PDFs and scanned ones separately. Run on 2026-09-28 against a 60-case
corpus rendered with PDFs (`python -m fixtures.generator --n 60 --seed 7`), of which 6 also
have a scanned variant with no text layer, so the model reads them as images. Results:
`eval/results/extraction.json`.

| | Documents read | Per-field accuracy | Service date and time |
|---|---|---|---|
| Clean PDF | 60 of 60 | 100% | 100% |
| Scanned | 6 of 6 | 100% | 100% |

Every field scored: index number, court, both parties, server, both licences, method,
service date and time, both addresses, mailing and filing dates, the number of prior
attempts and the recipient's description.

**How it got here, because two of the three runs taught something.**

- **The first run lost 3 of 60 to timeouts.** The model was thinking before answering, and
  one affidavit spent 8,250 thought tokens and 31 s, past the 30 s deadline in bible §12.
  With thinking off the same call returned the same fields in 3.5 s. Thinking is now off
  (`providers/gemini.py`, pinned by `tests/extraction/test_gemini_provider.py`), and the
  whole run takes under two minutes instead of four and a half.
- **Mailing address then scored 91.7% clean and 83.3% scanned, and the extractor was
  right every time.** All six misses were affidavits the generator had built without a
  mailing paragraph, to exercise R-T1, while still writing a mailing address into the
  label. The model answered "none" off a page that prints none. The label is fixed in
  `fixtures/generator/affidavit.py` and held by a test in `tests/fixtures`; the PDFs are
  byte-identical and the engine, advocate and robustness evals are unchanged.

**What to read into this, and what not to.**

- **Small.** 66 documents, 6 of them scanned. Enough to show the pipeline reads this form
  reliably on a real model; not enough to promise 100% on anything.
- **Synthetic documents.** One form layout, generated. A real process server's affidavit
  is messier, and the scans here are simulated rather than photographed.
- **A miss is caught downstream.** Every field is shown to the person with its source quote
  before anything is compared, and on a scan every field is marked for checking. The
  product also works with no model at all: `LLM_PROVIDER=none` returns an empty draft and
  the UI shows the manual entry form, which is the path every demo case and every test uses.
