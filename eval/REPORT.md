# Evaluation

Four evals live here. The **engine**, the **rules**, **advocate mode** and the
**robustness sweep** all run from one command and their numbers are below. The
**extraction** eval is written and has not been run, for want of an API key — said plainly
here rather than left as a gap for a reader to discover.

```bash
python eval/run_eval.py
```

It generates the corpus if it is not there, scores everything, rewrites
`eval/results/*.json`, draws `eval/results/robustness.png`, and rewrites
`frontend/src/lib/eval/published.json` — which is what the Methodology page reads, so the
published figures cannot drift from the run that produced them. A backend test fails if
they do. About 40 seconds on a laptop, most of it the first-time corpus build.

Run it twice and the numbers are identical, including the PNG byte for byte. Nothing here
is sampled at report time.

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

## Extraction — not run

`eval/extraction_eval.py` scores the affidavit extractor per field, clean PDFs and scanned
ones separately, with each field's evidence quote checked against the document's own text
layer. It needs a provider and an API key, and this machine has neither, so **there are no
extraction numbers here and none are published**. The harness is committed and the command
is in the README.

The product does not depend on it: `LLM_PROVIDER=none` returns an empty draft and the UI
shows the manual entry form, which is the path every demo case and every test uses.
