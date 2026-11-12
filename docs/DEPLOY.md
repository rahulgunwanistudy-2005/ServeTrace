# Deploying ServeTrace 1.1

One Docker image, one Render web service. FastAPI serves the API under `/api` and the built
SvelteKit site at `/`. There is no database for case data; the optional store holds only
day-level counts and contact-form leads.

## 1. Build and run it locally first

```bash
docker build -t servetrace:1.1.0 .
```

```bash
docker run --rm -p 8000:8000 -e LLM_PROVIDER=none servetrace:1.1.0
```

```bash
scripts/smoke.sh http://localhost:8000
```

`scripts/smoke.sh` checks the version, the pages and their security headers, a demo check
(the synthetic Maria case must come back `contradicted`), that the evidence packet renders
as a PDF, that a 20 MB body is refused with a 413, and whether the store is on. It sends
only the bundled synthetic case, marked as a demo.

## 2. Render

`render.yaml` is a blueprint for the service. Create it from the repository in the Render
dashboard (New → Blueprint), then type in the values marked `sync: false`:

| Setting | Value | Notes |
|---|---|---|
| `GEMINI_API_KEY` | from Google AI Studio | Only read when `LLM_PROVIDER=gemini`. Put a spending cap on the Google project. |
| `ANTHROPIC_API_KEY` | optional | Only read when `LLM_PROVIDER=anthropic`. |
| `SUPABASE_URL` | `https://<project>.supabase.co` | Only with the store (step 3). |
| `SUPABASE_SERVICE_KEY` | the project's service-role key | Server-side only. Never put it in the frontend. |

Everything else has a committed value. The ones that matter:

- **`RATE_LIMIT_TRUSTED_HOPS=1`.** Render proxies every request; without this the rate
  limiter sees one client for the whole internet.
- **`LLM_REAL_DATA_ALLOWED=false`.** Every upload screen then says *"This deployment is for
  demos and synthetic data. Do not upload real court papers."* See step 4 before changing it.
- **`METRICS_ENABLED=false`** until step 3 is done.
- **`CORS_ORIGINS` empty.** Site and API share one origin, so nothing needs allowing.

With `LLM_PROVIDER=none` (or a key with no credit) the app is fully usable: the affidavit
is typed in, and the reader failing never fails an upload.

After each deploy:

```bash
scripts/smoke.sh https://<your-service>.onrender.com
```

**Logs.** The app writes one JSON line per request: request id, route, method, status,
latency. The image runs uvicorn with `--no-access-log` because uvicorn's own line carries
the client's IP address, which the privacy page says the logs do not hold. Render's edge
proxy keeps its own HTTP logs outside the container; those are the platform's, governed by
Render's terms, and are not something this app can switch off.

On the free plan an idle service sleeps and the first request takes up to a minute; the
script waits 90 seconds for health. Open the URL a couple of minutes before showing it.

## 3. The store (optional): counts and the contact form

1. Create a Supabase project.
2. In its SQL editor, run `infra/supabase/001_v1_1.sql`. It creates `usage_daily` and
   `leads` with row-level security on and no policies, and a `bump_usage` function only the
   service role may call. The public anon key can read or write nothing.
3. Set `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` and `METRICS_ENABLED=true` on Render.
4. **Before switching it on, replace the deletion-contact placeholder** in
   `frontend/src/lib/copy/en.ts` (`privacy.deletionContact`, currently
   *"[deletion contact address, to be added before launch]"*) with a real address people
   can write to for their lead to be deleted, and redeploy.
5. Check: `curl https://<service>/api/stats` says `"enabled": true`, and submitting the
   `/attorneys` form adds one row to `leads`.

What the store can never receive: names from affidavits, addresses, coordinates, IP
addresses, user agents, or any time finer than a day. A store outage never fails a check;
counts are sent after the response and failures are logged by exception class only.

Deleting a lead on request: `delete from leads where email = '<address>';` in the SQL
editor.

## 4. Real court papers

`LLM_REAL_DATA_ALLOWED=true` removes the demo-data notice and invites real affidavits,
which are sent to the configured reader (Gemini or Claude) for field extraction. Free
model tiers may let the provider use inputs to improve its products. **Turn this on only
after confirming, in the provider's current terms for the plan the key is on, that inputs
are not used for training.** That is a person's check, not something the code can verify.
Nothing else about the product changes: location files are still read only on the device,
and photos are never uploaded.

## 5. Rolling back

Render keeps previous deploys: Events → pick the last good deploy → Rollback. The image
holds no state, so a rollback is complete. If a migration was applied to the store, it is
additive and the previous version simply ignores the tables.

## 6. What a release looks like

1. Bump `APP_VERSION` in `backend/app/config.py` and add the release at the top of
   `CHANGELOG.md` (a test fails if they disagree).
2. If the engine or a threshold changed, bump `ENGINE_VERSION` / `PARAMS_VERSION` and
   re-run `python eval/run_eval.py` (a test fails if the published figures go stale).
3. Run the gates in the README, push, let Render build, run `scripts/smoke.sh`.
