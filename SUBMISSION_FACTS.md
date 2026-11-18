# Submission facts — ServeTrace 1.1.1

Measured 2026-11-19 (IST). Every number below was produced by the command beside it, run
in this session. Test sets are synthetic with generator-set ground truth.

## 1. Verified numbers

| # | Deck claim | Measured | Command | |
|---|---|---|---|---|
| 1 | 0 false contradictions across 500 cases | 0 of 500 | `cd backend && uv run python ../eval/run_eval.py` (clean clone of `main`) | ✅ |
| 2 | 100% (200 of 200) | 200 of 200 truly contradicted cases flagged STRONG, precision 100% (0 false positives). Also: the claimed moment read right in 500 of 500. | same | ✅ |
| 3 | 0 false contradictions at 300 m, accuracy reported | 0 (σ = 300 m jitter, `accuracy_m` reported). Without accuracy reported: 1 at 300 m. | same | ✅ |
| 4 | 0 STRONG on assumed-zone photos, across 865 photos | 0; 865 photos, 335 with no time zone | same | ✅ |
| 5 | 66 of 66 affidavits, every field right (live model) | 66 of 66 (60 clean, 6 scanned), gemini-3.8-flash, recorded run 2026-09-27 19:49 UTC (`eval/results/extraction.json`). Not re-run. | `eval/extraction_eval.py` (paid) | ✅ recorded |
| 6 | Engine p95 < 1 ms | 0.85–0.89 ms over 3 runs (1.7 ms with the test suite running alongside) | same | ✅ |
| 7 | Advocate: 12 of 12 | 12 of 12 planted impossible sequences found, 0 extra, in 2,000 filings from 5 servers | same | ✅ |
| 8 | Advocate: 0 of 3 | 0 of the 3 ordinary (unplanted) servers named | same | ✅ |
| 9 | ~20 ms for 2,000 filings | 15.1–16.2 ms over 3 runs (24 ms under load) | same | ✅ |
| 10 | 980+ automated tests | 1,219: 843 backend (pytest) + 376 frontend (vitest) | `uv run pytest`; `npx vitest run` | ⚠️ |
| 11 | 8 evaluations, one command | 8, one command, after a fix: from a clean checkout the court-file layout eval was silently skipped (commit `60895c7`). 2 min 32 s from empty. | same | ✅ (fixed) |
| 12 | 14 commits since the hackathon | 36 since 2026-09-28 00:00 IST (first commit after v1.0.0); 25 since v1.1 work began 2026-11-12 | `git log --oneline --since="2026-09-28 00:00" \| wc -l` | ⚠️ |
| 13 | Lighthouse accessibility 100 on every main page | 100 on `/`, `/check`, `/demo`, `/attorneys`, `/advocate`, `/methodology` (live site, Lighthouse 12.8.2, mobile profile) | `npx lighthouse <url> --only-categories=accessibility` | ✅ |

### Deck edits needed

Slide numbers aren't in the repo, so slides are named as in the brief.

- **Momentum slide:** "980+ automated tests" → "1,219 automated tests".
- **Momentum slide:** "14 commits since the hackathon" → "36 commits since the hackathon".
- Optional, **Advocate slide:** "~20 ms for 2,000 filings" → "~16 ms for 2,000 filings".

## 2. One-line answers

- Tests: 1,219 (843 backend, 376 frontend), all passing.
- Evaluations: 8 from one command (plus the paid extraction eval and the paid 18-document layout sample, run separately).
- Commits since the hackathon: 36.
- Releases: 3, namely 1.0.0 (2026-09-27), 1.1.0 (2026-11-12) and 1.1.1 (2026-11-19).
- Warm load, browser `loadEventEnd` from India to Render Oregon: `/` 0.9–2.3 s across 5 fresh desktop loads (1.07 s in the smoke run), 1.18 s iPhone; other pages 0.38–0.90 s. Cold start: about 22 s.
- Keep-warm: the workflow is registered and active, but no scheduled run had fired 75 min after the push (0 runs), and it could not be triggered from here. ❓ Not yet verified.
- Lighthouse accessibility: 100 on all 6 main pages.

## 3. Real usage (Supabase store, read-only, counts only)

| | Real | Demo |
|---|---:|---:|
| Checks completed, all time | 0 | 17 |
| Checks, last 7 days | 0 | 17 |
| Evidence packets downloaded | 0 | 15 |
| Attorney batch runs | 0 | 8 |
| Contact-form leads (consented) | 0 | n/a |

The store has counted since it went live on 2026-11-16. v1.0 had no counters, so "since
the v1.0 deploy" cannot be answered. Every demo row is from this session's smoke runs.

## 4. Production audit

| Item | Result | Evidence |
|---|---|---|
| Real-data reading | ✅ `LLM_PROVIDER=gemini` on the live service; real uploads accepted (the demo-only notice and `LLM_REAL_DATA_ALLOWED` were removed in 1.1.1, so the stale value still on Render is ignored). Every upload screen names Gemini. | `/api/health`; `backend/app/config.py:20` |
| Gemini spend cap | ❓ Not visible from here; it lives in the Google Cloud console. The deck's "spend capped" is only true if you set one. | `docs/DEPLOY.md` §2 |
| Rate limits | ✅ Per client IP: `/api/extract` 60/min, burst 6; other paid routes 30/min, burst 10; contact form 5/hour. Behind Render, `RATE_LIMIT_TRUSTED_HOPS=1`. | `render.yaml:45-63`; `backend/app/config.py:42-65` |
| Copy agrees: /privacy, README, deck | ⚠️ /privacy and the upload screens match. Two README lines below the new top are stale: "switching on real court papers" (Deploying) and "has not been run" (Evaluation, extraction). | `README.md` |
| `LLM_PROVIDER=none` fallback | ✅ in code and tests: an empty draft, then the manual form. The 225-document layout eval runs with no reader. ❓ Not exercised end-to-end on the live site, because that would mean switching production off the reader. | `tests/extraction/test_vision.py:126`; `eval/run_eval.py` `run_layouts` |
| Location file stays on device | ✅ Parsed in a Web Worker; only fixes within ±3 h of a claim are kept and sent. | `frontend/src/lib/ingest/client.ts:26`, `worker.ts:31-47`, `pipeline.ts:93-100`, `window.ts:47-63`; photos `check/LocationStep.svelte:79-82`; request `case/store.svelte.ts:105-113` |
| Store holds counts and leads only | ✅ Counts carry day, kind, tier and bucket only. A lead needs `consent: true`. | `backend/app/metrics/store.py:121-150`; `backend/app/domain/models.py:579-600` |
| Secrets in git history | ✅ gitleaks 8.30.1, 44 commits: 1 hit, a false positive (an empty `SUPABASE_SERVICE_KEY=` in `.env.example` matched across a line break). `.env` never committed. No key-shaped strings in `git log -p`. | `gitleaks detect --source . --redact` |
| `.env.example` | ✅ Every setting a deploy needs, with no secret values. | `.env.example` |
| Repo public, LICENSE | ✅ Public, MIT. | `gh repo view` |
| Render plan | ⚠️ Free plan, in a workspace with about 20 other free web services. They share 750 free instance-hours a month. | Render API |

## 5. Links

- Live: https://servetrace.onrender.com
- Demo: https://servetrace.onrender.com/demo
- For attorneys: https://servetrace.onrender.com/attorneys
- Repo: https://github.com/rahulgunwanistudy-2005/ServeTrace
- Release tag: https://github.com/rahulgunwanistudy-2005/ServeTrace/releases/tag/v1.1.1
- Devpost: https://lexhack-2026.devpost.com/

## 6. Manual to-dos for Rahul

1. **UptimeRobot (or similar):** add a 5-minute HTTP monitor on `https://servetrace.onrender.com/api/health`. The GitHub keep-warm is only a fallback; its schedule drifts.
2. **Render hours.** Always-on ServeTrace uses about 720–744 of the workspace's 750 free hours a month, and those hours are shared with about 20 other free services. If they run out, Render suspends every free service, ServeTrace included, until the 1st. Check Billing → free usage before relying on keep-warm. The workflow stops itself after 2026-11-30 (`KEEPWARM_UNTIL`). To stay warm past that safely, move ServeTrace to a paid instance (your call).
3. **`VIDEO_URL_TBD`** in `README.md`: replace it with the video link.
4. **Gemini spend cap:** confirm a budget and cap exist on the Google project before the deck says "spend capped".
5. **Deck:** apply the edits in §1.
6. **README stale lines** (below the new top, left untouched as briefed): the "has not been run" extraction note and "switching on real court papers". Say if you want them corrected.
7. **Keep-warm:** GitHub → Actions → keepwarm → Run workflow, and check it goes green. It never ran during this session. (`gh` here is logged in as `rahul-software-dev`, which can only read the repo.)

## 7. What changed this session

- `60895c7` Eval: a clean checkout generates the layout corpus instead of skipping it; timings re-measured
- `daae174` Keep-warm workflow: `/api/health` every 10 min until 2026-11-30
- `a8238d9` README: reviewer-first top with measured results
- `a22f0b3` Fix: the attorney sample batch now ships in the image, plus a test
- `aee2995` `scripts/smoke_live.py`: live browser smoke test and the three clips
- `b205db0` 1.1.1 changelog, test count, runbook step (tagged `v1.1.1`, deployed, smoke green)
- `2bb50f5`, `2d16a45` and this commit: `SUBMISSION_FACTS.md`, post-deploy smoke report, notes
