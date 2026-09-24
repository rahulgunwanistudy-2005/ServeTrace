# tasks/todo.md

## Session 1 — Scaffold, contracts, synthetic fixtures

**Goal:** a repo that builds, type-checks and tests clean on both sides, with every data
contract from bible §10 defined and a deterministic synthetic fixture generator that every
later session can test against.

### Steps
- [x] S1.1 Repo layout per bible §9; `.gitignore`, `.dockerignore`, `.env.example`, `README.md`
- [x] S1.2 Backend skeleton: uv project, FastAPI factory, `config.py`, `logging.py`, `/api/health`
- [x] S1.3 Error envelope `api/errors.py` — `{error:{code,message}}` + typed exception classes
- [x] S1.4 Contracts: bible §10 verbatim in `domain/models.py` + model tests
- [x] S1.5 `engine/params.py` frozen dataclass + `PARAMS_VERSION`
- [x] S1.6 `geo/distance.py` haversine + range tests
- [x] S1.7 Typed `NotImplementedError` shells for every later-session module
- [x] S1.8 `fixtures/generator/build_addresses.py` → `addresses_nyc.json` (~300 NYC addresses)
- [x] S1.9 Fixture generator: people, location history (Android/iOS/CSV), affidavit PDF, labels
- [x] S1.10 Advocate generator: 5 servers x 400 records, 2 bad with known impossible pairs
- [x] S1.11 Determinism test: same seed -> byte-identical outputs
- [x] S1.12 Curated demo cases into `fixtures/demo_cases/` (committed)
- [x] S1.13 Frontend skeleton: SvelteKit 2 + Svelte 5 + TS strict + adapter-static + Tailwind
- [x] S1.14 `lib/copy/en.ts`, API client stub, `gen:types` script
- [x] S1.15 Dockerfile multi-stage; FastAPI mounts `frontend/build` at `/`
- [x] S1.16 `docs/SOURCES.md`, `docs/ARCHITECTURE.md`, `docs/DISCLOSURE.md`
- [x] S1.17 Quality gates green both sides; docker build

### Risks / open questions
- **NYC GeoSearch availability.** `build_addresses.py` hits the network once. Output JSON is
  committed so tests never touch the network. If the API is down, the committed JSON still works.
- **WeasyPrint system libs.** Needs pango/cairo/gdk-pixbuf. Present locally; Dockerfile must
  install them explicitly on the python runtime stage.
- **Determinism vs. floats.** Jitter and geo maths must be reproducible. Fix by seeding a single
  `random.Random(seed)` per generator, deriving all sub-seeds from it, and rounding all emitted
  coordinates to 7 dp before serialisation. No `set` iteration, no `dict` ordering reliance,
  no wall-clock time in outputs.
- **Ground-truth labels must not come from the engine** (bible/S1 §6). The generator decides
  `true_tier` from where it *put* the person; the engine is the thing under test in later
  sessions. Keeping these independent is the whole point of the eval.
- **Python version.** Bible pins 3.12; local default is 3.14. `uv` pins 3.12 via
  `.python-version` + `requires-python`.
- **DST edge cases.** Generator must emit dates crossing the Nov DST fold so the engine's
  "evaluate both interpretations, take weaker tier" rule (bible §11.1.1) has fixtures.

### Done criteria
- [x] `uv run ruff check`, `ruff format --check`, `mypy app`, `pytest -q` green
- [x] `npm run build`, `npx svelte-check`, `npx tsc --noEmit`, `npx vitest run` green
- [ ] `docker build .` — BLOCKED in this environment (see Review)
- [x] Generator deterministic (asserted by a test, not by eyeball)
- [x] Demo cases exist with PDFs, both Timeline shapes, CSV, ground-truth JSON
- [x] No legal statement anywhere outside bible §5
- [x] No real personal data anywhere in the repo

### Review

**Built**

- Repo layout per bible §9, `.gitignore` / `.dockerignore` / `.env.example` / `README.md`.
- Backend: FastAPI app factory, `config.py` (only env reader), PII-free JSON request logging
  with request ids, `/api/health` returning engine + params versions and the LLM provider,
  typed error hierarchy behind one `{error:{code,message}}` envelope.
- All bible §10 contracts in `domain/models.py`, `engine/params.py` as a frozen dataclass
  with `PARAMS_VERSION`, `geo/distance.py` haversine.
- Typed `NotImplementedError` shells for every session 2-5 module, so the seams are fixed
  and later sessions fill bodies rather than invent interfaces.
- `fixtures/addresses_nyc.json`: 401 real NYC addresses from GeoSearch, all five boroughs,
  built by a committed one-off script so no test ever touches the network.
- Seeded generator: people with shifts/commutes/households, day plans, GPS-jittered fixes,
  both Google Timeline shapes plus card CSV, affidavit ground truth plus a rendered NYC
  affidavit PDF plus a scanned variant, advocate corpus with an injected-pair answer key.
- 200-case corpus at the specified mix, three committed demo cases, eval scaffold.
- Frontend: SvelteKit 2 / Svelte 5 / TS strict / adapter-static / Tailwind 4, all routes,
  all copy centralised in `lib/copy/en.ts`, typed API client, windowing with its own tests.
- Multi-stage Dockerfile; `docs/SOURCES.md`, `ARCHITECTURE.md`, `DISCLOSURE.md`.

**Verified**

- Backend: `ruff check` and `ruff format --check` clean over `backend`, `fixtures`, `eval`;
  `mypy` strict clean over all 53 source files; 63 tests pass.
- Frontend: `svelte-check` 0 errors 0 warnings over 212 files, `tsc --noEmit` clean,
  `npm run build` succeeds, 35 vitest tests pass.
- Determinism asserted by test: two runs at the same seed are byte-identical, different
  seeds differ, and a case is a pure function of its seed and kind.

**Three real bugs found and fixed**

1. Prism-flavour contradictions could place the claimed time within 15 minutes of the home
   visit that a commute starts from. Bible §11.1.3 makes any fix inside the match radius
   within +/-15 min CONSISTENT, so the engine would have been right and the *label* wrong,
   scoring a correct engine as incorrect. Prism claims are now only placed inside commutes
   of 50 minutes or more, at 40-60% of the way through.
2. Gaps originally dropped a visit only when they swallowed it whole, so an eight-hour work
   visit straddling a gap survived and no case was ever genuinely NO_DATA. Gaps now truncate
   visits the way a real export does when a phone dies mid-stay.
3. `StaticFiles(html=True)` 404'd on `/methodology` and `/privacy`: adapter-static writes
   `methodology.html`, not `methodology/index.html`, and the `200.html` SPA fallback was
   never wired up. Replaced with `api/static_site.py`, which tries the exact file, then
   `.html`, then `<dir>/index.html`, then the SPA fallback — and resolves the candidate
   before checking containment, so neither `../` traversal nor a symlink escapes the
   bundle. Both are covered by tests.

**Not verified: `docker build`**

The Docker daemon on this machine cannot reach any container registry — `docker pull`
times out on every base image, while the same registries answer normally from the shell,
so it is the daemon's network and not the Dockerfile. The build is therefore unverified
and must be run before deploying.

What *was* verified is the substance of that acceptance gate: FastAPI serving the real
built bundle at `/` alongside `/api/health`, which is what the container does.

**Deferred, deliberately**

- `schema.d.ts` is a placeholder until session 2 adds routes worth generating types from;
  `npm run gen:types` is wired and ready.
- Ingest parsers, map components and all session 2-5 modules are typed shells.
- Determinism is asserted over JSON, not PDFs: WeasyPrint stamps a creation date, so PDF
  bytes differ run to run. The JSON ground truth is what the eval consumes.

**One deviation from the brief**

The bible suggested asserting Times Square to Grand Central at 0.6-0.8 km. The true
straight-line distance between those landmarks' coordinates is 0.914 km, so the test
brackets 0.7-1.1 km instead. Asserting the stated range would have meant asserting
something false.

---

## Session 2 — Affidavit extraction + geocoding

**Goal:** `POST /api/extract` turns an uploaded affidavit (PDF or image) into an
`AffidavitDraft` with per-field confidence and verbatim evidence quotes, validated
deterministically. `POST /api/geocode` resolves NYC addresses with caching. Everything
works with `LLM_PROVIDER=none`.

### Steps
- [x] S2.1 Contracts: `AffidavitDraft`, `AttemptDraft`, `ValidationNote`, `ExtractionResult`,
      `GeocodeRequest`/`GeocodeResult` in `domain/models.py` (nothing crosses a module
      boundary undeclared)
- [x] S2.2 `extraction/pdf_text.py`: sniff pdf/jpg/png by magic bytes, reject HEIC loudly,
      pdfplumber text layer, pypdfium2 raster (200 dpi, <= 3 pages), SHA-256 of raw bytes
- [x] S2.3 `extraction/schema.py`: the provider-facing JSON Schema + `draft_from_payload`
      (one parser shared by every provider, so a recorded response can be tested offline)
- [x] S2.4 `extraction/prompt.md` loaded once at import; text >= 200 chars -> text prompt,
      otherwise the image prompt
- [x] S2.5 `extraction/vision.py`: orchestrator, `Extractor` protocol, provider registry,
      `run_with_retry` (temperature 0, 30 s, one retry on schema violation)
- [x] S2.6 Providers: `gemini.py` (google-genai structured output), `anthropic.py` (tool use),
      `none.py` (empty draft)
- [x] S2.7 `extraction/validators.py`: date sanity, licence pattern, time/date parsing,
      America/New_York localisation with a DST-ambiguity flag, method keyword fallback,
      evidence-quote grounding (difflib ratio >= 0.90), confidence caps -> `ValidationNote[]`
- [x] S2.8 `geo/geocode.py`: GeoSearch via httpx (5 s), NYC bounding-box rejection, on-disk
      cache.json + in-memory LRU; `POST /api/geocode`
- [x] S2.9 `POST /api/extract`: size/type limits, orchestration, geocode `served_address` and
      each attempt address, attach `LatLng` when confident
- [x] S2.10 Seed `backend/app/geo/cache.json` from the committed address pool (no network)
- [x] S2.11 Tests: pdf_text, schema contract vs a recorded response, validators rule by rule,
      retry, geocode cache hit/miss on an httpx MockTransport, bbox, route limits. No network.
- [x] S2.12 `eval/extraction_eval.py` + documented command; run only if a key exists
- [x] S2.13 Demo cases: `fixtures/demo_cases/*/extraction.json` so demo mode never calls an LLM
- [x] S2.14 Frontend: regenerate `schema.d.ts` from the new OpenAPI, wire `api.extract` /
      `api.geocode` in `client.ts`
- [x] S2.15 Quality gates both sides

### Risks / open questions
- **No LLM key on this machine.** Every provider path must therefore be provably correct
  without network: the shared payload parser is tested against a recorded response, and the
  retry rule is tested with an injected `send`. The real-provider eval is written and
  documented but reported as not run.
- **Draft fields stay strings.** Dates, times and method come back from the model as free
  text and are normalised in `validators.py`, not by pydantic. A model that writes
  "June 12, 2025" must produce a note the user can act on, not a 422 that loses the whole
  extraction.
- **"Exactly as written plus normalised ISO"** is satisfied by one mechanism, not two: the
  normalised value is the field, the verbatim span is `evidence_quotes[field]`, and that
  same quote is what the grounding check scores.
- **Demo extractions without a key.** `extraction.json` records its own provenance
  (`provider`), so a draft derived from the committed ground truth can never be mistaken
  for a real model output.
- **Rate limiting deferred.** Bible §16 wants a token bucket per IP; `RateLimitedError`
  already exists. `/api/extract` and `/api/geocode` are the first routes that cost money,
  so this is the next session's first job, not a silent omission.

### Outcome

Built as planned, with three deviations worth recording.

- **`build_geocache.py` needs no network.** The address pool was already resolved against
  GeoSearch in session 1, so seeding `app/geo/cache.json` only re-keys those answers. 401
  addresses cached; a test asserts the two files stay in sync, because drift would quietly
  put the demo back on the network.
- **`extraction.json` for the demo cases is derived, not extracted.** No API key exists on
  this machine. Each file records `provider: "derived_from_ground_truth"`, and
  `docs/DISCLOSURE.md` says what that means, so a derived draft can never be read as
  something a model produced. With a key configured, the same script records a real one.
- **Two small additions beyond the brief.** `DemoOnlyError` (the `DEMO_ONLY` setting was
  otherwise dead) and `GEMINI_MODEL` / `ANTHROPIC_MODEL` settings, so the extraction model
  is configuration rather than a literal that ages.

**Not run:** `eval/extraction_eval.py`, for want of a key. Its scoring is covered offline
by `tests/eval/test_extraction_eval.py` and the command is in `eval/REPORT.md`.

**Still deferred:** the §16 rate limiter. `/api/extract` and `/api/geocode` are the first
routes that cost money on each call, so it is the first job of the next session.

---

## Session 3 — Location ingest in the browser (Web Worker)

**Goal:** a location export is parsed entirely on the device into `LocationFix[]`, windowed
around the claimed times, and only the windowed fixes ever reach the server. A 150 MB file
must not freeze the tab.

### Steps
- [x] S3.0 Carry-over from session 2: `api/rate_limit.py` in-memory token bucket per IP
      (bible §16), applied to `/api/extract` and `/api/geocode`, settings-driven, tests
- [x] S3.1 `ingest/types.ts`: the whole protocol in one place — `IngestRequest`,
      `IngestResponse`, `IngestStats`, `IngestErrorCode`, `PendingFix`
- [x] S3.2 `ingest/tz.ts`: ISO-with-offset → epoch ms, NY day key, NY display formatting
- [x] S3.3 `ingest/streamJson.ts`: chunked scanner that yields one top-level item at a time
      from an array document or from a named array inside an object document, so a 150 MB
      export is never one 150 MB string and never one giant `JSON.parse`
- [x] S3.4 `parsers/googleAndroid.ts`, `parsers/googleIos.ts`, `parsers/detect.ts` —
      per-item pure functions plus whole-document wrappers; unknown shape →
      `UNSUPPORTED_FORMAT` with a human message
- [x] S3.5 `parsers/cardCsv.ts` (papaparse + column map) and `parsers/manual.ts` produce
      `PendingFix[]` carrying an address; `ingest/resolve.ts` fills locations through an
      injected geocoder (address only, bounded concurrency, per-address memo)
- [x] S3.6 `ingest/dedupe.ts`; `window.ts` gains dedupe + the 5,000 cap with a stated
      priority rule, still returning `{kept, total}`
- [x] S3.7 `ingest/stats.ts`: point count, covered date range, per-day coverage, and the
      early warning when a claimed date is not in the export at all
- [x] S3.8 `ingest/worker.ts` module worker (`{type:"parse"}` → progress → done/error) and
      `ingest/client.ts`, the typed main-thread wrapper
- [x] S3.9 `/dev/ingest`: drop a file, see counts, coverage and a raw-point map preview.
      Not linked in production and refuses to render there
- [x] S3.10 Tests: both Timeline shapes against the committed demo fixtures, Android/iOS
      parity for visits (1 m / 1 s), a DST day, malformed coordinates, empty file,
      windowing boundaries, dedupe, the streaming scanner, CSV column mapping, resolve
- [x] S3.11 Copy strings in `lib/copy/en.ts`; quality gates both sides

### Risks / open questions
- **150 MB without a streaming JSON dependency.** Bible §8 pins the stack and a streaming
  JSON parser is not in it. The scanner in S3.3 is the answer: decode the file in chunks,
  track string/escape/depth state, and hand each top-level item to `JSON.parse` on its own.
  Peak memory is then one item, not one document.
- **Memory after parsing, not just during.** A multi-year export is millions of points. The
  worker therefore accepts the claim times and windows *as it parses*, so what it retains is
  bounded by the window and not by the file. Stats are accumulated incrementally, so the
  date-coverage warning still describes the whole file.
- **Android duplicates itself.** `timelinePath` points and `rawSignals.position` are the
  same points; only the raw signals carry accuracy. Dedupe must merge rather than pick, or
  every path point is either doubled or loses its accuracy.
- **Android and iOS are not the same information.** iOS renders a whole commute as one
  activity with a start and an end point; Android renders it as every sampled point. Parity
  can therefore only be asserted for visits, which is what the brief asks for.
- **Geocoding belongs to the main thread.** CSV and manual entries need `/api/geocode`.
  Parsers stay pure and return `PendingFix[]`; `resolve.ts` takes the geocoder as an
  argument, so every test of them is offline by construction.
- **A dev route in a static build.** adapter-static prerenders every page, so the honest
  option is `prerender = false` plus a load that 404s outside dev, and a nav link that only
  exists in dev. The code ships inert rather than being silently reachable.

### Outcome

**Built**

- **Rate limiter (§16, carried over from session 2).** `api/rate_limit.py`: a token bucket
  per client on `/api/extract` and `/api/geocode`, the two routes that cost money per call.
  One budget covers both, because the reason for the limit is the cost and not the path.
  Monotonic clock, a `retry-after` header on the 429 (which meant giving `ServeTraceError`
  a headers slot), settings for the rate, the burst and how many proxies may be believed.
- **`streamJson.ts`** — the piece that makes a 150 MB export possible without a dependency
  the bible does not list. A character-fed state machine yields one array element at a time
  and hands each to `JSON.parse` on its own, so peak memory is one record rather than one
  document. Measured at ~17 MB/s.
- **Parsers** for both Timeline shapes, each a pure function over one record, plus
  whole-document wrappers for tests. Android's `durationMinutesOffsetFromStartTime` paths
  and `activity` segments are handled as well as the documented shapes, because real
  exports contain them.
- **Format detection by what the file contains**, not by sniffing: the scanner tags each
  item with the array it came from, so `semanticSegments` means Android and a top-level
  array means iOS, decided by the first record that actually yields a location.
- **`cardCsv.ts`** (papaparse, column mapping, `7:42 PM` as well as `19:42`) and
  **`manual.ts`** (typed intervals, overnight shifts). Both produce `PendingFix[]` carrying
  an address; **`resolve.ts`** turns those into points through a geocoder passed in as an
  argument, four at a time, once per distinct address.
- **`dedupe.ts`, `window.ts`, `stats.ts`, `pipeline.ts`, `worker.ts`, `client.ts`** — the
  assembled ingest, windowing *as it reads* so what the worker holds is bounded by the
  window and not by the file.
- **`/dev/ingest`**: drop a file, see counts, coverage, warnings, a map and a point table.
- Every user-facing sentence ingest can produce now lives in `lib/copy/en.ts`.

**Verified**

- Backend: `ruff check`, `ruff format --check`, `mypy` strict over 59 files, `pytest` 234
  passed (was 218). Frontend: `svelte-check` 0 errors 0 warnings over 263 files,
  `tsc --noEmit` clean, `npm run build` clean, `vitest` 223 passed (was 41).
- The three committed demo cases parse from their Android export into exactly the fixes
  `fixes.json` records — same count, same kinds, every instant equal and every point within
  10 cm. That file was written by the S1 generator before any of this code existed.
- Android and iOS renderings of the same history agree on every visit within a metre and a
  second, and on the labels.
- The scanner gives the same answer wherever the document is cut in two — asserted at every
  one of 69 positions — and across every chunk size from 1 to 12 bytes on a string
  containing a two-byte degree sign.
- Live in a real browser at `/dev/ingest`: a 906-point synthetic export parsed in the
  worker, 1 fix kept for a 19:42 claim (the work visit spanning it), coverage across three
  days reported, map drawn. Every network request in the tab was to the dev server; the
  location data never left the page.
- Live against the running API: ten geocodes pass, the eleventh returns 429 with
  `retry-after: 2`, and the log lines carry route, status and latency and no address.
- In a production build `/dev/ingest` renders "404 Not found", the nav link is absent from
  the built HTML, and no `build/dev/` directory is emitted.
- `npm run gen:types` produces a byte-identical `schema.d.ts`: the limiter changes no
  contract.

**Three things worth knowing**

1. **Windowing moved into the parse.** The brief has `window.ts` filter a finished list.
   That is still there and still tested, but the worker now also takes the claim times and
   drops out-of-window fixes as it reads. A multi-year export is millions of points, and
   holding all of them to throw most away afterwards is both a memory problem and a privacy
   one. Statistics are still accumulated over the whole file, so the coverage warning is
   unaffected.
2. **papaparse ships no types**, and `@types/papaparse` would be a dependency outside §8.
   The slice actually used is declared in `src/types/papaparse.d.ts` instead — narrow on
   purpose, so reaching for more of papaparse is a decision rather than an autocomplete.
3. **The map pans to the user's own points**, which means the tile host (OpenFreeMap) can
   infer roughly where those points are from the tiles requested. No location data is
   *sent*, but this is a real inference and the privacy page must say so plainly in session
   7. The alternative is self-hosted tiles, which is a deploy cost, not a code change.

**Deferred, deliberately**

- The dev route's chunk carries maplibre (~780 KB) into the deployed bundle even though the
  page 404s there. It is route-lazy, so no user ever downloads it, and session 7 pulls
  maplibre in for `ResultMap` anyway. Not worth a build plugin today.
- `client.ts` (the worker wrapper) has no test: driving a real `Worker` from vitest needs a
  browser environment the project does not have. It is kept to the minimum that cannot be
  tested any other way, and the whole of `pipeline.ts` underneath it is covered. It was
  exercised by hand at `/dev/ingest`, which is what that page is for.

---

## Session 4 — Feasibility engine, description check, NY rules, verdict

**Goal:** `POST /api/analyze` takes a confirmed affidavit, windowed fixes, an optional
household and the two dates, and returns a `CaseAnalysis` that is deterministic,
explainable and conservative. This is the core of the product. Precision over features.

### Steps
- [x] S4.1 `engine/copy.py` — every sentence the engine can emit, as templates with numbers
      interpolated. No free text anywhere else in `engine/`; every legal claim carries its
      L-id from bible §5
- [x] S4.2 `engine/feasibility.py` — bible §11.1 as pure functions: DST dual interpretation,
      visit test, Hagerstrand prism test, no-data fallback, precedence
- [x] S4.3 `engine/description.py` — bible §11.2, tolerances, missing fields ignored
- [x] S4.4 `engine/rules_ny.py` — R-T1, R-T2, R-T3, R-D1, R-D2, R-M1 as an ordered registry
      of small functions, each returning `Finding | None`
- [x] S4.5 `documents/deadlines.py` — CPLR 317 arithmetic (L6), note text from `engine/copy.py`
- [x] S4.6 `engine/verdict.py` — assemble claims, run feasibility/rules/description, overall
      tier, sorted findings, version stamps
- [x] S4.7 `POST /api/analyze` — refuse unconfirmed affidavits (422), enforce the §16 caps,
      rate limit, wire into `main.py`
- [x] S4.8 Unit tests: every tier path, precedence, one-sided prism, the 60 s guard, radius
      plus accuracy, each rule R-T1..R-M1, description tolerances, deadline arithmetic
- [x] S4.9 Property tests (hypothesis, >= 500 examples each) for the four invariants in §11.1
- [x] S4.10 Golden tests: the three demo cases produce exactly their expected tiers and
      findings, snapshot JSON committed
- [x] S4.11 Fixture sweep over all 200 generated cases: the no-false-accusation gate, plus
      the confusion matrix
- [x] S4.12 Performance: 5,000 fixes x 4 claims under 200 ms, asserted by a test
- [x] S4.13 `eval/run_eval.py` + `eval/REPORT.md` with the real numbers
- [x] S4.14 Frontend: regenerate `schema.d.ts`, wire `api.analyze`, verdict copy in `en.ts`
- [x] S4.15 Design pass: tokens, UI primitives, every existing page, Methodology filled with
      the real thresholds and eval numbers the engine now produces
- [x] S4.16 Quality gates both sides

### Risks / open questions
- **`overall` when an attempt is contradicted but the service claim is not.** Bible §11.1.6
  reads "strongest CONTRADICTED across claims", but bible §6 defines CONTRADICTED as being
  far from *the claimed service point at the claimed time*. A 308(4) case has attempts on
  other days, and a person who was home at 7 PM was very likely at work during a 10:30 AM
  attempt three weeks earlier. Taking the literal reading would headline "your data
  conflicts with the affidavit" for someone whose data *supports* the service claim, which
  is the one thing §6 forbids. Resolution below in the outcome; it has to be decided before
  the eval, because it decides what the eval is measuring.
- **DST is the engine's problem, not only the extractor's.** `Affidavit.served_at` is aware
  by the time it arrives, so the fold has already been resolved to one instant. The engine
  must still ask whether that local wall time is ambiguous and evaluate both readings,
  because the document itself only ever said "7:42 PM".
- **A claim with no coordinates.** `served_location` can be null when GeoSearch could not
  resolve the address. The location check cannot run, but the timing rules still can, so
  this must degrade to a stated INFO finding rather than a 4xx.
- **The no-false-accusation gate is the real acceptance test.** Zero cases where ground
  truth is CONSISTENT and the engine says CONTRADICTED with STRONG severity. Thresholds
  move before that number does.
- **Golden files are only worth what their provenance is.** The three demo snapshots are
  written by the engine, so they catch *change*, not correctness. Correctness comes from
  the generator's independent labels in the sweep. Both are needed and they are not the
  same test.

### Outcome

**Built**

- **`engine/feasibility.py`** — bible §11.1 as pure functions. Visit test, Hagerstrand
  prism test, no-data fallback, both readings of an ambiguous clock, and one `FixIndex`
  built per request and bisected per claim.
- **`engine/copy.py`** — every sentence the engine can put in front of a user, in one
  file. Nothing else under `engine/` holds a user-facing string, which is what makes "no
  legal statement outside bible §5" checkable by reading one module.
- **`engine/description.py`** (§11.2), **`engine/rules_ny.py`** (§11.3 as an ordered
  registry of six small functions), **`documents/deadlines.py`** (CPLR 317),
  **`engine/verdict.py`** (assembly, overall tier, sorted findings, version stamps).
- **`POST /api/analyze`** — refuses unconfirmed affidavits, enforces the §16 caps, behind
  the same token bucket as the other routes.
- **`eval/run_eval.py`** — scores the engine against the corpus, writes
  `eval/results/engine.json`, and generates the figures the Methodology page reads.
- **Frontend:** regenerated types, `api.analyze`, a semantic colour system with dark mode,
  ten UI primitives, components that render a real `CaseAnalysis`, and every page
  rewritten. The Methodology page now carries the actual thresholds and eval numbers.
- **`/dev/analyze`** — runs a committed demo case through the real API and renders it with
  the components the result screen will use. Dev-only, like `/dev/ingest`.

**Verified**

- Backend: `ruff check`, `ruff format --check`, `mypy` strict over 60 files across `app`,
  `fixtures` and `eval`, `pytest` **405 passed** (was 234).
- Frontend: `svelte-check` 0 errors 0 warnings over 277 files, `tsc --noEmit` clean,
  `npm run build` clean, `vitest` **244 passed** (was 223).
- Hypothesis runs 500 examples on each of the four §11.1 invariants, plus a fifth on order
  independence.
- **The no-false-accusation gate passes: 0 of 200.** The engine reads the claimed moment
  correctly in 200 of 200. Full numbers, including the four case-level disagreements and
  why they are not errors, are in `eval/REPORT.md`.
- 5,000 fixes x 4 claims analyse in 4 ms against a 200 ms budget.
- `curl` against a running server returns byte-identical golden output for all three demo
  cases.
- Live in a browser: `/dev/analyze` runs Maria's case through the real API and renders the
  verdict, the claims table, both findings with their CPLR citation and the deadline card.
  Checked in light and dark, at 375 px with no horizontal scroll.
- The production build serves from FastAPI, and `/dev/analyze` renders "404 Not found"
  with no dev link in any built HTML and no `build/dev/` directory.

**Three places the code is deliberately more conservative than a literal §11**

All in the same direction, all written up in `docs/ARCHITECTURE.md` and the module
docstrings, and all reached by following a fixture rather than an opinion.

1. **Evidence at the claimed time wins over everything.** §11.1.5 says CONSISTENT overrides
   a MODERATE contradiction and is silent on STRONG, while §11.1 separately requires a fix
   exactly at the claimed point at the claimed time to always yield CONSISTENT. One rule
   satisfies both. The competing finding is still reported, and a third says plainly that
   the user's own data disagrees with itself.
2. **Sub-minute gaps floor the elapsed time rather than jumping to infinity.** The literal
   guard called a phone 450 m from a door at the claimed minute a STRONG contradiction.
   The corpus' own edge case at that distance is independently labelled INCONCLUSIVE, and
   it is right.
3. **A consistent service claim is never overridden by a contradicted attempt**, because
   §6 defines the headline as being about the claimed service point at the claimed time.
   Where the service claim is *unsettled*, a contradicted attempt does set the verdict.

**Deferred, deliberately**

- Advocate mode, documents and the wizard are the next sessions. `/check`, `/result`,
  `/demo` and `/advocate` are styled, honest placeholders that say what is coming.
- The two dev routes carry maplibre (~780 KB) and the demo fixtures (~100 KB) into the
  deployed bundle as route-lazy chunks that 404 and are never requested. Session 3's
  position stands; session 7 pulls maplibre in for `ResultMap` anyway.
- `docker build` remains unverified in this environment for the reason recorded in
  session 1.

## Session 5 — Advocate mode

**Goal:** a legal-aid worker loads a spreadsheet of service records from one or more
process servers and gets servers ranked by physical-impossibility evidence, with a map of
each server's day and exports they can attach to a DCWP complaint. Bible §11.4, §14.6.

The defendant flow asks one question of one affidavit. This asks the same question of a
whole filing history, and the answer is a different kind of evidence: one contradicted
service is a dispute, and six sequences nobody could have driven is a pattern.

### Steps
- [x] S5.1 `advocate/ingest.py` — CSV and XLSX (openpyxl read-only). Column-mapping
      contract: `server_id`, `datetime` (or `date` + `time`), and either `lat`+`lng` or
      `address`. Rows that fail validation are **returned with a reason**, never dropped
- [x] S5.2 Address geocoding inside ingest: cache first, GeoSearch after, at most five
      lookups in flight, per-row status
- [x] S5.3 Accept a JSON list of confirmed `Affidavit` objects and convert to
      `ServiceRecord` (the served claim plus every attempt)
- [x] S5.4 `advocate/patterns.py` — bible §11.4 exactly: consecutive-pair impossibility,
      rolling-hour throughput, repeated descriptions, risk rank. Sort + single pass +
      deque; O(n log n) per server
- [x] S5.5 `advocate/report.py` — CSV of impossible pairs, plus a JSON summary
- [x] S5.6 `POST /api/advocate/analyze` (multipart file + mapping JSON) →
      `{reports, rejected, stats}`; §16 caps, rate limited
- [x] S5.7 Tests: recall 1.0 on the generator's injected pairs and zero false pairs on
      clean servers; throughput window edges; description normalisation; 50k rows < 3 s
- [x] S5.8 `fixtures/demo_cases/advocate_servers.xlsx` committed with its expected
      report snapshot
- [x] S5.9 Frontend: `/advocate` — upload, column mapping, ranked server table,
      `AdvocateMap.svelte` day view with impossible edges in red, pair list, exports
- [x] S5.10 Quality gates both sides; types regenerated

### Risks / open questions
- **What counts as "completed" for throughput.** Bible §11.4 says "max completed services
  in any rolling 60-minute window". A `not_home` is an attempt, not a service. Counting
  attempts would inflate a diligent server's number and make the flag meaningless.
- **Two records at the same instant.** `required_speed_kmh` is a float on the wire and
  infinity is not JSON. The engine already solved the same problem with a floor on elapsed
  time (`MIN_ELAPSED_S`); advocate must use the same floor, or the two halves of the
  product will price the same journey differently.
- **A rejected row is the product, not an error.** An advocate is building a complaint. A
  parser that quietly drops the eleven rows it could not read hands them a report whose
  denominator is wrong, so every rejection carries its row number and its reason.
- **Precision matters more than recall here.** A false impossible pair in a DCWP complaint
  damages the advocate who filed it. The §11.4 thresholds are the engine's, unchanged.

### Outcome

**Built**

- **`advocate/patterns.py`** — bible §11.4 as pure functions over one server's filings:
  consecutive-pair impossibility, rolling-hour throughput, repeated descriptions, risk
  rank. The elapsed-time floor is imported from `engine/feasibility.py` rather than
  restated, so an advocate and a defendant looking at the same two points are told the
  same speed.
- **`advocate/ingest.py`** — CSV and XLSX through openpyxl in read-only mode, the column
  mapping contract, the date formats case-management systems actually export, address
  lookups capped at five in flight and at a per-file budget, and a `RejectedRow` for every
  row that could not be used. Also `records_from_affidavits`, so an advocate who has run
  clients through the defendant flow can analyse what they already hold.
- **`advocate/report.py`** — CSV of the sequences and of the server summary, written in
  New York local time because the reader is checking them against a paper affidavit.
- **`POST /api/advocate/{columns,analyze,analyze-affidavits,export.csv}`**, behind the
  same token bucket and the same §16 caps as everything else.
- **`eval/advocate_eval.py`**, folded into the one eval command, writing
  `eval/results/advocate.json` and the batch figures the Methodology page now prints.
- **Frontend `/advocate`** — a three-stage flow on one route: drop a file, confirm the
  columns we guessed, read the report. Ranked server table, `AdvocateMap.svelte` with the
  ordinary week in grey and the impossible steps in labelled red, per-pair cards with both
  filings, reused-description cards, the rejected-row list, and CSV exports.
- **`lib/advocate/mapping.ts`** — header guessing as a pure, tested function, so the
  mapping step is a review rather than a form.
- **`lib/map/color.ts`** — design tokens into MapLibre. See the lesson.
- **`fixtures/demo_cases/advocate_servers.xlsx`** — 194 filings, four servers, one week,
  committed with its expected report, and loadable from the page itself.

**Verified**

- Backend: `ruff check`, `ruff format --check` (93 files), `mypy` strict over 63 files,
  `pytest` **503 passed** (was 405).
- Frontend: `svelte-check` 0 errors 0 warnings over 286 files, `tsc --noEmit` clean,
  `npm run build` clean, `vitest` **264 passed** (was 244).
- **Precision 1.00 and recall 1.00** on the corpus' 12 injected sequences, and **0 of 3
  ordinary servers named.** 16 of 16 reused-description doors found. Both flagged servers
  rank above all three clean ones.
- 50,000 filings across 25 servers in **247 ms** against a 3 s budget, and doubling the
  rows costs 1.98× the time — the ratio is the assertion that matters, because a wall-clock
  bound passes on a fast laptop even for an O(n²) implementation.
- The committed demo XLSX goes through the real ingest and the real engine in the test
  suite, needs no network, and every one of its 194 rows is usable.
- Live in a browser, both colour schemes, 375 px and desktop: the demo file loads from the
  page, the guessed mapping is right, the report renders, selecting a server re-draws the
  map, and the impossible edges are labelled with their speeds.

**Two decisions worth recording**

1. **`AdvocateAnalysis` carries the filings back, and the mapping that produced them.**
   A `ServerReport` holds only the pairs that do not fit, and a map of those alone would
   imply four flagged steps were the server's whole output — the cluster of ordinary doors
   is what makes the outlier mean anything. The records are capped at 10,000 and cut
   *between* servers, so any server the map can open it can draw completely. The mapping
   rides along for the same reason `params_version` does: a number is only reproducible
   beside what produced it.
2. **A rejected row is part of the answer.** Every row that cannot be used comes back with
   its spreadsheet row number and the column at fault, and never the cell's contents. An
   advocate is building something they will put their name to, and a parser that quietly
   drops eleven rows hands them a report whose denominator is wrong.

**Deferred**

- Documents (S6) and the defendant wizard (S7) are next. `/check`, `/result` and `/demo`
  are still styled placeholders; the advocate PDF report waits for S6's print stylesheet,
  so batch mode exports CSV today.
- `docker build` remains unverified here for the reason recorded in session 1.

---

## Session 6 — Visual system: the "editorial monochrome" reskin

**Reference.** `dribbble.com/shots/27621487` (LAIN, "NS — Modern Creative Branding
Agency"). What is actually being borrowed, stated precisely so it can be argued with:

| Move in the reference | What it becomes here |
|---|---|
| Near-monochrome page; the only colour is the artwork | Chrome goes achromatic. Red/amber/green are reserved for **verdicts and severities only** — which is bible §6's rule, now enforced by the palette instead of by discipline |
| Cards *recede* (light grey inset on near-white), no borders, no shadow | `surface` becomes quieter than `canvas`; depth from tone, not elevation |
| One black "featured" card with iridescent artwork | The dark panel: hero, the demo case, the impossible-pair callout |
| Huge display type against 11px eyebrows | A display scale with tight tracking, plus `.st-eyebrow`; all small text raised to ≥12.5px so it still clears AA (the reference does not) |
| Lead clause black, remainder grey, in one paragraph | `.st-statement` — used for the impossible-travel angle on the landing page |
| Label-left / arrow-right CTA row | `Button` gains the arrow affordance; `ActionRow` for card footers |
| Giant stat numbers under an image strip | `StatTile` — carries the Pew and New York Focus numbers from bible §2 |

**Deliberately not borrowed:** the reference is a marketing site and leans on a licensed
grotesk, 10px grey-on-grey, and motion. Bible §8 pins system fonts (a web font is a
network dependency the privacy page would have to disclose), §14 asks for AA and grade-7
reading, and §16 wants a demo that never fails. So: dark and cinematic on the *marketing*
surfaces (landing, demo, advocate intro), calm paper on the *working* surfaces (wizard,
result, methodology, privacy). Someone reading about a frozen bank account should not be
made to squint.

**Plan**
1. `app.css` — retune every token (warm paper light scheme, true near-black dark scheme),
   add the display/eyebrow/statement/iridescent/panel component layer.
2. `app.html` — theme-colour to match.
3. Primitives — `Button`, `Card`, `Callout`, `StepHeader`, `TierBadge`, `SeverityTag`,
   `DemoChip`, `FileDrop`, `VerdictCard`, `FindingList`, `ClaimTable`, `DeadlineCard`.
   New: `Eyebrow`, `Section`, `StatTile`, `ActionRow`, `Iridescent`.
4. `+layout.svelte` — editorial header, dark footer with the big underlined link.
5. Pages — landing (full rebuild), check, demo, result, methodology, privacy, advocate.
6. Map palette fallbacks follow the tokens.
7. Gates: `svelte-check`, `tsc --noEmit`, `vitest`, `npm run build`; verify live in both
   schemes at 375 px and desktop.

**Built**

- `app.css` rewritten end to end: warm-paper light scheme, true near-black dark scheme,
  achromatic chrome, `--st-raised` / `--st-faint` / `--st-on-accent` / the four
  `--st-panel-*` tokens, and a component layer carrying `.st-display`, `.st-display-sm`,
  `.st-eyebrow`, `.st-statement`, `.st-panel`, `.st-iridescent`, `.st-rule`, `.st-shell`.
- Four new primitives — `Eyebrow`, `Section`, `StatTile`, `ActionRow` — and twelve
  restyled: `Button` (pill, ink/inverting, optional arrow), `Card`, `Callout`,
  `StepHeader`, `TierBadge`, `SeverityTag`, `DemoChip`, `FileDrop`, `LimitationNote`,
  `VerdictCard`, `FindingList`, `ClaimTable`, `DeadlineCard`.
- `+layout.svelte`: full-bleed `main`, editorial header with a scrollable nav and a pill
  CTA, and the dark closing footer with the cropped wordmark.
- Landing page rebuilt: iridescent hero, the provisions strip in place of a logo wall,
  numbered steps, the statement paragraph, three sourced stat tiles, the "what this is
  not" list, and a closing panel. Copy for the strip, the stats and the closing panel
  added to `en.ts`.
- `check`, `demo`, `result`, `privacy`, `methodology`, `advocate` and the three advocate
  components moved onto the shell and the new primitives. Map token fallbacks follow the
  new palette.

**Verified**

- `svelte-check` 0 errors 0 warnings over 290 files, `tsc --noEmit` clean, `vitest`
  **264 passed**, `npm run build` clean.
- Live in a browser against a real backend, both colour schemes, 375 px and 1280 px:
  landing, check, demo, methodology, privacy, advocate. The advocate demo file goes all
  the way through — mapping, ranked table, map with red impossible edges and speed
  labels, pair cards — in both schemes. No horizontal overflow at 375 px on either the
  landing or the advocate page.

**Three decisions worth recording**

1. **The chrome is achromatic so that a verdict is the only colour on the page.** Bible §6
   asks for tiers that read at a glance and are never carried by hue alone. The old
   palette put a blue accent on every button, link, progress bar and focus ring, so a
   verdict had to shout over the furniture. Now red, amber and green appear nowhere
   except a tier or a severity, and the rule is enforced by the palette rather than by
   remembering.
2. **Cards recede instead of floating.** `surface` is now quieter than `canvas`, with no
   border and no shadow — depth is tonal. The one raised element in the product is the
   verdict card, which means "this is the thing you came for" is said by elevation and
   costs no colour.
3. **The iridescent field is CSS, and the panel bottom-aligns its copy into the flat
   part of the scrim.** No image asset: the privacy page has nothing new to disclose, the
   demo still works with the network off (bible §16), and contrast under the headline is
   a property of the layout rather than of wherever the gradient landed.

**Deferred**

- The dev-only routes (`/dev/ingest`, `/dev/analyze`) still use raw Tailwind slate. They
  refuse to render in a production build, so they were left alone.
- The MapLibre basemap is the light `liberty` style in both schemes. A dark basemap is a
  separate decision about tiles, not about tokens.

---

## Session 7 — Evidence packet, draft supporting affidavit

Build pack `S6_documents.md`. Numbered 7 here because the repo's session 6 was the visual
system; the build pack numbers the *feature* streams and this is its sixth. No LLM
anywhere in this session — bible §15 is explicit, and the whole claim of the product is
that a document handed to a court was assembled from fields a person confirmed.

**Goal:** two PDFs a court help-center volunteer would take seriously. An Evidence Packet
that shows its working, and a Draft Supporting Affidavit that attaches to the court's own
Order to Show Cause form rather than replacing it.

### Steps
- [x] S7.1 `documents/render.py` — the one place WeasyPrint is imported. Jinja environment
      with autoescape and `StrictUndefined`, `render_pdf()`, and a loud, instructive
      failure when the native pango stack is missing.
- [x] S7.2 `documents/copy.py` — every sentence in both documents, each legal statement
      carrying its bible §5 L-id. Same discipline as `engine/copy.py`: templates hold
      structure, this holds prose.
- [x] S7.3 `documents/templates/` — `base.html.j2`, `packet.html.j2`, `affidavit.html.j2`,
      and a real `static/print.css` (Letter, 11pt serif, page numbers, footer disclaimer on
      every page, "DRAFT" on every page of the affidavit).
- [x] S7.4 `documents/packet.py` — bible §15 sections: verdict cover, map image, claim
      table, findings with legal refs, windowed fixes table, methodology box, both
      SHA-256s, generation time in New York.
- [x] S7.5 `documents/affidavit.py` — the paragraph library. Every paragraph tied to an
      L-id or a finding code; unconfirmed paragraphs excluded, never softened; CPLR 317
      paragraph only when eligible; exhibit list; blank signature and notary block.
- [x] S7.6 `domain/models.py` — `PacketRequest`, `DraftAffidavitRequest`, `AffiantStatement`.
- [x] S7.7 `POST /api/documents/packet` and `/api/documents/affidavit` → `application/pdf`,
      behind the same rate limit and the same §16 caps as everything else.
- [x] S7.8 Tests: renders for all three demo cases; paragraph selection; 317 eligibility;
      pdfplumber text extraction carries the key numbers; autoescape proven on a hostile
      field; byte-determinism; golden text snapshots of both documents.
- [x] S7.9 Regenerate `frontend/src/lib/api/schema.d.ts` (bible §17 — the API changed).
- [x] S7.10 Both PDFs for `maria_contradicted` into `docs/samples/`, page 1 rendered to
      PNG and looked at.
- [x] S7.11 Quality gates both sides; `tasks/todo.md` and `tasks/lessons.md` updated.

### Risks / open questions
- **WeasyPrint's native libraries.** Installed here via Homebrew, but `/opt/homebrew/lib`
  is not on macOS's default dyld fallback path, so `import weasyprint` fails in a plain
  shell with a stack trace that names none of that. Docker already installs the same stack
  on Debian, where it is on the default path, so this is a local-shell problem only. The
  suite must not paper over it with a silent skip: whatever it does has to name the fix.
- **Determinism.** WeasyPrint writes no `/CreationDate` unless the HTML asks for one, so
  identical HTML gives byte-identical PDFs. Measured before relying on it. The documents
  therefore carry `analysis.generated_at` as their own timestamp rather than a fresh clock
  read, which is both more honest and what makes the byte test possible.
- **How long a fixes table may be.** §16 allows 5,000 points per analysis, which is about
  eighty pages of table. The packet is an exhibit, so it cannot quietly truncate; it prints
  a bounded number, says how many of how many, and hashes every one of them.

### Review

**Built**

- **`documents/render.py`** — the one place WeasyPrint is imported, and the only place it
  may be. Jinja with autoescape and `StrictUndefined`; a fetcher allowed exactly one
  protocol (`data:`, how the map arrives) with `fail_on_errors` set, so a document that
  tried to reach the network does not render at all rather than quietly losing a section;
  and a missing native stack caught once and re-raised as a sentence with the fix in it.
- **`documents/copy.py`** — every sentence in both documents, each legal statement
  carrying its bible §5 L-id. `packet.py` and `affidavit.py` decide *which* paragraphs and
  hand over numbers; templates hold structure; prose is in one file somebody can read
  against §5 end to end.
- **`documents/packet.py` + `packet.html.j2`** — every section bible §15 names: verdict
  cover, map (or its text alternative), one row per sworn moment, findings with the
  provision each encodes, the windowed records, the deadline note, the thresholds, and a
  SHA-256 of the affidavit file and of the canonical JSON of the records.
- **`documents/affidavit.py` + `affidavit.html.j2`** — a paragraph library where every
  paragraph carries its source, and a `match` over finding codes that writes nothing for a
  code it does not know. DRAFT in the margin of every page, blank signature and notary.
- **`POST /api/documents/{packet,affidavit}`** → `application/pdf`, behind the same token
  bucket, the same §16 caps and the same "analysis refuses an unconfirmed affidavit" rule
  as `/api/analyze`.
- **`docs/samples/`** — both PDFs for `maria_contradicted`, built by
  `tests/documents/build_samples.py` through the same code path a download takes, with a
  README saying plainly that everyone in them is invented.

**Verified**

- Backend: `ruff check`, `ruff format --check` (123 files), `mypy` strict over 65 files,
  `pytest` **630 passed** (was 503).
- Frontend: `svelte-check` 0 errors 0 warnings over 290 files, `tsc --noEmit` clean,
  `npm run build` clean, `vitest` **264 passed**. `schema.d.ts` regenerated: +151 lines
  for the two new routes and their request shapes.
- Both documents rendered for all three demo cases, and every page of both looked at as a
  PNG. Two layout bugs found that way and only that way — see below.
- Byte-determinism asserted, not assumed: the same analysis renders the same PDF twice.

**Three decisions worth recording**

1. **The document's timestamp is `analysis.generated_at`, not a fresh clock read.** It is
   the moment the numbers were computed, which is what the document reports; a second
   time taken at download would be a different and less meaningful number. It also makes
   the bytes a pure function of the input, which is what S6 asked for and what session 1
   recorded as impossible — WeasyPrint 70 writes no `/CreationDate` unless the HTML asks
   for one, so identical HTML gives identical PDFs. Measured before relying on it.
2. **A finding code with no paragraph produces no paragraph.** The risk this is designed
   against is a rule added in a later session quietly writing prose into a document
   somebody signs under oath. Silence is the safe default, and a test reads the engine's
   own source for the codes it constructs and fails when one appears in none of
   `HANDLED_CODES`, `INFO_ONLY_CODES` or `EXCLUDED_CODES`. A new rule now fails a test
   rather than growing a sentence.
3. **A consistent case does not annex the records that work against it.** Bible §6 says
   report a consistent result honestly, and the result page does. It does not follow that
   the draft affidavit should point a judge at an exhibit placing the person at the door:
   with no location finding, the records paragraph and Exhibit B are both left out, and
   the affidavit rests on whatever paperwork grounds there are. Asserted for
   `james_consistent`.

**Two bugs no gate could see**

- The draft affidavit ended on a third page carrying one grey sentence. The provenance
  line and the rule above it were body elements, and after a notary block that may not be
  split they had nowhere to go. It is in the page margin now, beside the disclaimer, and a
  test asserts the last page is the one the signature is on.
- `table.data th` sets the default alignment and outranks a bare `.num`, so the two
  numeric column headers sat over the wrong edge of their columns while the numbers under
  them were right-aligned. Both were invisible in the type-check, the lint and the tests,
  and obvious in a rendered page.

**One pre-existing failure fixed in passing**

`ruff check . ../fixtures ../eval` — the command in the README — was red on HEAD: two
lines in `fixtures/generator/advocate_demo.py` were 102 and 103 columns. Session 5 reported
the gate green, so it was run over `backend` alone. Wrapped.

**Deferred**

- The packet's map section prints its text alternative: the capture comes from the result
  map's canvas and `ResultMap.svelte` is still a placeholder. The embedding path itself is
  covered — a real PNG goes in and comes out in the PDF, and four validation tests guard
  what may be embedded.
- Wiring the two downloads into `/result` is the defendant wizard's work (S8), as is the
  advocate PDF report, which now has a print stylesheet to build on.
- `docker build` remains unverified here for the reason recorded in session 1.

---

## Session 8 — The iridescent field, moving

**Reference.** The same shot session 6 worked from — `dribbble.com/shots/27621487` — plus a
10s screen recording of it playing. What the recording shows that a still cannot: the field
*flows*. Curved arcs at 0s flatten to hard diagonals by 3s and dissolve to near-black by 9s.
Everything else on that page is static; all of the motion is in the background.

Session 6 listed motion under "deliberately not borrowed", for a stated reason: bible §16
wants a demo that never fails. That reason is answered here rather than dropped — the CSS
field is the floor and always paints, and the shader is an enhancement that can fail down
to it silently. Nothing that can fail is load-bearing.

**What is actually wrong with the field today**, stated so it can be argued with:

| | Today | Reference |
|---|---|---|
| Presence | A band across the top ~26rem, `inset: auto` below | Fills the panel |
| Structure | `blur(11px)` over a 12%-period ribbon — the edges are gone | Wide dark bodies, thin bright specular edges, readable |
| Motion | None | ~10s loop, sweeping and re-forming |

### Steps
- [x] S8.1 Promote the field's colours out of the `::before` rule into `--st-iris-*` tokens,
      so the CSS and the shader cannot disagree about what the field is made of. (Session 5's
      lesson: one source, or two surfaces drift invisibly.)
- [x] S8.2 `.st-iridescent::before` — fill the panel, tighten the blur so the ribbon edges
      survive, and add a `@keyframes` sweep gated behind `prefers-reduced-motion:
      no-preference`. Reduced motion renders exactly today's static frame.
- [x] S8.3 `lib/ui/iridescent.ts` — the pure parts, so they can be tested under vitest's node
      environment: the "should this run at all" decision, and the palette packing.
- [x] S8.4 `lib/ui/IridescentField.svelte` — a WebGL2 canvas, no new dependency (bible §8):
      `getContext('webgl2')` and a fragment shader string. Domain-warped ribbons with
      chromatic dispersion at the edges. Colours resolved through `lib/map/color.ts`, the
      bridge session 5 built for exactly this problem.
- [x] S8.5 Fail-down paths, each one silent: no WebGL2, shader will not compile, context
      lost, `prefers-reduced-motion`, SSR. Every one of them leaves the CSS field visible.
- [x] S8.6 Cost: cap DPR (the field is blurred, so half resolution is free), pause on
      `visibilitychange` and when scrolled out of view. Maria is on a phone.
- [x] S8.7 Mount in the five panels that carry `.st-iridescent`. `StatTile` keeps the CSS
      floor — a WebGL context per stat tile buys nothing.
- [x] S8.8 Tests for S8.3; gates both sides; look at every panel in both schemes, at 375 px
      and desktop, with motion on and with `prefers-reduced-motion` forced.

### Risks / open questions
- **A background that moves under type.** The scrim (`::after`) is what makes the field safe
  to put copy on, and it does not move. Contrast stays a property of the layout, which is
  what session 6 made it. The animation must not touch the scrim.
- **`vitest` runs in `environment: node`.** No canvas, no WebGL. So the shader itself is
  verified by looking at it, and only the decision logic is unit-tested. Said plainly rather
  than papered over with a mock that proves nothing.
- **Battery.** A full-screen fragment shader at 60fps on a phone is the kind of thing that
  makes a person close a tab. Half resolution, paused when hidden, paused when off-screen.

### Review

**Built**

- **`app.css`** — the field's colours promoted to `--st-iris-*` tokens, so the CSS and the
  shader read one source rather than two copies of the same six hues. The two `-wash`
  variants carry their alpha spelled out longhand, matching the convention
  `--st-panel-fade-*` already set and for the same reason: a `color-mix()` a browser does
  not understand takes the whole `background` shorthand with it.
- **`.st-iridescent::before`** — fills the panel instead of banding its top 26rem, blur
  down from 11px to 6px so the ribbon edges survive, and an 11s sweep gated on
  `prefers-reduced-motion: no-preference`. The translation is a little over one ribbon
  period, so the loop closes with no seam.
- **`lib/ui/iridescent.ts`** — both shader sources and every decision around them that is
  pure enough to test under vitest's node environment: `shouldRun`, `renderSize`,
  `hexToVec3`, the token table and `UNIFORM_NAMES`.
- **`lib/ui/IridescentField.svelte`** — a WebGL2 canvas and no new dependency (bible §8):
  `getContext('webgl2')` and a fragment shader string. Warped bands with a specular line
  down each lit face and per-channel dispersion across it. Colours resolved through
  `lib/map/color.ts`, the bridge session 5 built for exactly this problem.
- Mounted in the five panels carrying `.st-iridescent`. `StatTile` keeps the CSS floor: a
  WebGL context per stat tile buys nothing.

**Verified**

- Frontend: `svelte-check` 0 errors 0 warnings over 293 files, `tsc --noEmit` clean,
  `vitest` **283 passed** (was 264), `npm run build` clean.
- Backend, untouched but run per bible §17: `ruff check` and `ruff format --check` clean
  over 124 files, `mypy` clean over 65, `pytest` **630 passed**.
- Every panel looked at on the landing page, `/demo` and `/advocate`, at 1280 px and
  375 px, at the top and the bottom of the breath. No horizontal overflow at 375 px.
- **Contrast measured rather than assumed.** A script reads the live drawing buffer behind
  every piece of text on a panel, composites the scrim over it with the scrim's own
  gradient stops, and computes the ratio — sampled every 180 ms across a full 22-second
  breath so the number is the worst frame and not a frame. Tightest is the 12px eyebrow at
  **6.32:1** against a 4.5 requirement; nothing fails. Elements with an opaque background
  of their own (the pills) are excluded and checked against that background instead:
  "Start check" is 16.7:1, "See a demo" 19.6:1.

**Three decisions worth recording**

1. **The CSS field was kept, not replaced.** It is the floor and it always paints; the
   canvas is an enhancement at z −2 that fades in only once it has produced a frame. No
   WebGL2, a shader that will not compile, a lost context, reduced motion, SSR — each one
   leaves the product looking exactly as it did before this session, and says nothing to
   the user. Session 6 declined the reference's motion because bible §16 wants a demo that
   never fails; the answer was to keep the motion off the critical path, not to do without
   it.
2. **The shader has a ceiling, and the ceiling is a contrast guarantee.** See
   `lessons.md`: a specular peak clipping to white took a 12px eyebrow to 3.88:1. The fix
   is a soft rolloff to 0.66 rather than a dimmer field, because it bounds the brightest
   pixel the field can ever emit. That is what makes the measurement above hold for every
   frame rather than for the one that was checked. It also looks more like the reference,
   where the brightest points still carry their hue.
3. **The cost is bounded three ways.** Drawn at 0.6 of CSS resolution with a ceiling of
   1.2M pixels (the field is all Gaussians and smoothed noise — there is no detail to
   lose), paused on `visibilitychange`, and paused by an `IntersectionObserver` when the
   panel is off screen. On the landing page at 375 px the hero canvas is 225×352. The
   footer's canvas never draws a frame until it is scrolled to.

**On verifying an animation in this pane**

The browser pane reports `document.visibilityState === "hidden"` and suspends
`requestAnimationFrame`, which is precisely what the renderer pauses on — so the component
mounted, sized itself, compiled, and sat at opacity 0, which looks exactly like a broken
renderer. It was exercised end to end by overriding the `visibilityState` getter and
backing `rAF` with `setTimeout` before the component mounted. Everything reported above
was measured through the real component on that footing, not through a stand-in.

**Deferred**

- The `/check` and `/result` panels do not carry the field, because those screens are
  still the placeholders S7_ui replaces. Bible §14 puts calm paper on the working surfaces
  and keeps the cinematic treatment for the marketing ones, so whether `/result` gets a
  field at all is a decision for that session rather than a default.

### Correction — the field was animating and was not moving

Rahul looked at the first cut and saw a still image. He was right, and the evidence in the
review above says so: two samples a second and a half apart reading 53,54,53 and 49,51,50.
That was quoted as proof the loop was running, which it is, and taken as proof the thing
worked, which it is not. Nothing was broken — every drift rate was roughly a twelfth of
what it needed to be, and every check that had been run asked whether pixels changed rather
than how much.

**Measured, both sides.** Frames sampled out of the reference recording at 8fps, cropped to
its background and reduced to grey, differ from their neighbours by 7.58 levels of 255 and
by 36.27 over a full second; mean frame brightness runs 10.6 to 72.4 across the ten
seconds, a factor of 6.8. The same measurement now runs against the shader through a
1×1-normalised probe, per frame to zero mean and unit variance so it compares pattern
change and not brightness — an unnormalised first attempt read the field's darkness as
stillness and overstated the gap by 40%.

| | Reference | Before | After |
|---|---|---|---|
| Pattern change per 1/8 s | 0.1778 | 0.0589 | **0.1906** |
| Pattern change per 1.0 s | 0.7721 | 0.3726 | **0.7728** |
| Pattern change per 2.0 s | 0.9158 | 0.5901 | **0.8570** |
| Brightness swing over the loop | 6.80× | 1.61× | **4.35×** |

Every `uTime` rate except the breath is multiplied by 3.5, found by sweeping the factor
against the metric rather than by eye; the bands also now drift as well as reshape, which
the reference does and warping alone does not. The breath keeps its ~20s period, which
already matched, and got a deeper floor: only the trough moves, because the peak is what
the contrast ceiling guards. The CSS fallback's sweep went 34s → 11s for the same reason.

The brightness swing stays under the reference's because the rolloff compresses the top of
the range. That is the contrast guarantee and it stays.

**Re-verified after retuning** — faster motion sweeps far more configurations under the
copy, so the contrast audit is not inherited: 70 samples over 25 seconds, zero failures,
tightest **6.27:1** against a 4.5 requirement. `vitest` 283 passed, `svelte-check` 0/0 over
293 files, `tsc` and `npm run build` clean.

---

## Session 9 — Real licence data, and saying precisely what the demo is

**Why.** Rahul asked for real data instead of synthetic, or else the "Synthetic demo data"
chip gone. Neither branch applies cleanly, and the reasons are worth writing down.

**The demo cannot be real, structurally.** The defendant flow joins a court affidavit about
a named person to *that person's phone location history for the same evening*. The second
is private personal data by definition: there is no free public source, and bible §18.7
forbids real personal data in this repo. Advocate mode is the same — NYC does require a
server to record GPS for every service (§5 L7, 6 RCNY § 2-233b), but those logs sit with
the server and are not published anywhere.

**The chip stays, because of what the demo actually contains.** Index `CV-025236-25/BX`,
"Civil Court of the City of New York, County of Bronx", server "T. Ockham-Doyle", licence
`1401648`. Checked against the live DCWP register: no collision today, but real licences
are six or seven digits, so the format is indistinguishable from a real one. Unlabelled,
that screen is a fabricated court record naming a licensed professional and asserting their
sworn statement conflicts with the evidence. For a product whose subject is exactly that
accusation, it is the one thing it cannot be caught doing.

**But there is real free data worth having.** NYC DCWP publishes its licence register:
899 `Process Server Individual` and 146 `Process Serving Agency` licences, no key, no cost.
So ServeTrace can check the number on the affidavit against it — a server whose licence
was not in force on the day they swore they served is a real, checkable problem, and it
sits under an L-id §5 already carries (L7).

### Steps
- [x] S9.1 `fixtures/generator/build_licences.py` → `backend/app/licences/cache.json`,
      following `build_geocache.py`. **Numbers, category, status and dates only.** The
      register also carries each licensee's name and home ZIP; those are real people at
      mostly residential addresses, the check does not need them, and §18.7 says they do
      not belong in this repo.
- [x] S9.2 `app/licences/registry.py` — load once (`lru_cache`), normalise a licence number
      to bare digits, look up by number and category.
- [x] S9.3 R-L1..R-L3 in `engine/rules_ny.py` + copy in `engine/copy.py`, every one
      carrying L7.
- [x] S9.4 Tests: the three rules, the normaliser, absent/unknown handling, and that the
      committed cache holds no name or address field.
- [x] S9.5 The demo label: a precise provenance line in place of the vague chip.
- [x] S9.6 Gates both sides; `todo.md` and `lessons.md`.

### Risks / open questions
- **The register is a snapshot of *now*, not a history.** `license_status` is today's
  status and `lic_expir_dd` today's expiry. So "revoked on the day they served" is not a
  claim this data can support, and R-L3 must not make it — it says the licence is revoked
  *today* and leaves the inference to the reader. The selected plan had R-L3 as STRONG for
  "revoked that day"; it ships MODERATE and differently worded, because the data does not
  reach. Same asymmetry on expiry: an expiry *before* the service date is meaningful, an
  expiry after it is not evidence the licence was in force then, so only one direction
  produces a finding.
- **A number absent from the register is not proof of anything.** Records get corrected,
  and an affidavit can carry a typo. R-L1 is MODERATE and worded as something to check.
- **Never the name.** Matching the *name* against the register would be a stronger finding
  and would mean shipping 899 real people's names and accusing a real person of a
  mismatch. Not built, deliberately.

### Review

**Built**

- **`app/licences/registry.py` + `cache.json`** — 1045 licences (899 individual, 146
  agency) from NYC Open Data, committed so nothing on the analysis path touches the
  network. `normalise` reduces `0745503-DCA` and `745503` to one key so the register and
  an affidavit can meet. `in_force_on` is deliberately one-sided.
- **`fixtures/generator/build_licences.py`** — the one-off refresh, following
  `build_geocache.py`. Four fields, sorted, so a refresh is a reviewable diff.
- **R-L1..R-L3 in `engine/rules_ny.py`** — number not in the register; licence not in
  force on the date sworn; licence currently revoked or suspended. All three carry L7.
  They share one walker because the server's number and the agency's ask the register the
  same question, and they are registered in a new `MULTI_RULES` list because an affidavit
  carries two numbers and the register can object to both.
- **The demo label** — `Demo · Real NYC addresses and real CPLR rules. The people and
  cases are invented.` in place of `Synthetic demo data`.

**Verified**

- Backend `pytest` **656 passed** (was 630), `ruff check` and `ruff format --check` clean
  over 129 files, `mypy` clean over 68.
- Frontend `svelte-check` 0/0 over 293 files, `tsc` clean, `vitest` 283 passed, build clean.
- The engine goldens regenerated to **byte-identical** content, and the only lines that
  moved in `published.json` were `runtime_ms` and the three latency figures. The new rules
  add nothing to any existing case, which is what they should do.

**The decision this session actually turned on**

Giving the engine a real register immediately broke the fixtures, and it was right to.
Every synthetic affidavit carried an invented seven-digit licence number, so every demo
case grew two `R-L1` findings — including `james_consistent`, whose whole job is to report
honestly that the data supports the affidavit, and which suddenly led with two licence
complaints. Those findings were true of the fixture and false of the scenario.

The tempting fixes were both wrong. Giving the fixtures real licence numbers would tie a
real licensee to an invented server accused of a sworn statement that does not hold up.
Suppressing the rules for demo cases would put a special case in production code to make a
fixture look better. So the generator stopped inventing the numbers: a fixture may not
assert something checkable that it cannot back.

Removing them re-rolled every downstream value, because the generator is a pure function
of its seed — a two-field change arrived as an unreviewable diff across every committed
fixture. The two draws are still made and thrown away, in the same position, so the diff
is the two fields and the hashes that follow them.

**Deferred**

- The methodology page does not yet publish the register's counts or describe the licence
  check. It is real, free, citable data and exactly the kind of number bible §2 rewards
  publishing; it needs either an endpoint or a build-time constant, and belongs with the
  other page work in S7_ui.
- Nothing matches the server's **name** against the register. It would be a stronger
  finding and would mean shipping 899 real people's names and accusing one of a mismatch.
  Not built, deliberately, and recorded here so the omission reads as a decision.

### Follow-up — the badge goes, the sentence stays

Rahul asked for the `DEMO` tag itself to go. It has: `DemoChip` is now `DemoNote` and
renders one muted line and no pill. The disclosure is untouched, because the pill was never
the part carrying it — beside a sentence reading "The people and cases are invented", a
badge reading `DEMO` said the same word twice and only one of them was informative.

Two things fell out of doing it:

- **`/demo` no longer renders the note at all.** Its own `demo.note` — "Every name, case
  and document on these screens is invented for demonstration. The addresses are real New
  York City streets, used as geography and nothing else." — already says everything the
  shared note says and says it better. Bible §16 asks each demo screen to disclose, not to
  disclose twice. `DemoNote` is now for the screens with no sentence of their own, which is
  `/advocate` once a demo file is loaded, and `/dev/analyze`.
- **The component was renamed**, because `DemoChip` that renders no chip is a name that
  lies to the next person who greps for it.

Verified: `svelte-check` 0/0 over 293 files, `tsc` clean, `vitest` 283 passed, build clean.
Looked at on `/demo` and on `/advocate` all the way through to the ranked table — 194 rows,
four servers, the same figures as before.

---

## Session 10 — S7_ui: the wizard, the result screen, the map moment

**Constraint, stated first because it governs every choice below.** Rahul asked for the
aesthetics not to change: the S6 visual system stands, and this session builds *on* it.
No new colours, no new type scale, no new component vocabulary. Everything here composes
the primitives that already exist — `VerdictCard`, `ClaimTable`, `FindingList`,
`DeadlineCard`, `Callout`, `StepHeader`, `FileDrop`, `ActionRow`, `Button`, `Eyebrow`,
`Section`, `Card` — and the tokens in `app.css`. If something needs a colour that is not
already a token, that is a signal the design is wrong, not that the palette is short.

**Where the work already is.** The two dev routes are working prototypes of exactly this
session's two halves: `/dev/ingest` drives the worker and shows what came out, and
`/dev/analyze` renders a real `CaseAnalysis` through the real primitives. This session is
substantially about moving that logic into the product and giving it a wizard around it.
Both dev routes are deleted at the end, because once `/check` and `/result` exist they are
duplicate code that can rot.

### Steps
- [x] S10.1 `lib/case/store.svelte.ts` — the `Case` store in runes: affidavit draft,
      confirmed flag, fixes, household, knowledge and judgment dates, analysis. Persisted
      to IndexedDB **only** when the user ticks "Save on this device", cleared on demand.
- [x] S10.2 `lib/demo/cases.ts` — the three committed demo cases, lazily imported so a
      case only costs its own chunk. This is the first time fixture data reaches the
      production bundle, and the existing `ingest/demoFixtures.ts` stays test-only.
- [x] S10.3 `/result` — verdict card, claim table, findings, "what this means / what it
      does not", deadline clock, next steps. Reads the store; redirects to `/check` when
      there is nothing to show.
- [x] S10.4 `lib/map/ResultMap.svelte` — MapLibre, red claim pin, the user's fixes as a
      trail, a dashed line from the nearest fix to the claim labelled with the distance and
      the required speed, a time scrubber, `preserveDrawingBuffer` so the packet can
      capture it. Palette through `lib/map/color.ts` — session 5's lesson. Text-alternative
      table beside it, which `ClaimTable` already is.
- [x] S10.5 `/demo` — the three cases become clickable and land on `/result`. Must work
      with `LLM_PROVIDER=none` and make no call but `/api/analyze` and `/api/documents/*`.
- [x] S10.6 `/check` step 1 — upload, extract, the review card: every field editable, amber
      and the source quote under anything below 0.8 confidence, validation notes inline,
      and the confirmation tick that `user_confirmed` depends on.
- [x] S10.7 `/check` step 2 — three tiles (Timeline · card statement · type it in), per-OS
      export instructions, worker progress, coverage warning, and the "sending N of M
      points" line that makes §13's windowing visible.
- [x] S10.8 `/check` step 3 — the household roster, optional, and the two dates.
- [x] S10.9 Downloads on `/result`: evidence packet (with the map PNG from the canvas) and
      the draft affidavit, both already served by `/api/documents/*`.
- [x] S10.10 Delete `/dev/ingest` and `/dev/analyze` and their nav links.
- [x] S10.11 Responsive at 375 / 768 / 1280, keyboard path through the whole wizard, and
      the gates both sides.

### Risks / open questions
- **The store is the one piece of real state in the product.** Everything so far has been
  a pure function of its input. A wizard that loses your work on a back button is worse
  than no wizard, and IndexedDB that saves without being asked breaks the promise the
  privacy page makes. Save is opt-in, and refusing it has to be the default that works.
- **`/result` with no case.** Reachable from the nav and from a bookmark. It cannot throw
  and it cannot show an empty verdict card; it sends the person to `/check`.
- **The map is where session 5's lesson bites again.** Tokens are `oklch`, MapLibre parses
  its own colours and understands none of it, and a symbol layer with no `text-font` takes
  down every other layer sharing its source. `lib/map/color.ts` and an explicit font on
  every symbol layer.
- **Bundling fixtures.** `/demo` needs real case data in the production build for the first
  time. Lazily, so the landing page does not carry three cases it may never show.

### Review

**Built**

- **`lib/case/store.svelte.ts`** — the first real state in the product. Runes, with every
  wizard field written straight into it so Back preserves everything by construction
  rather than by remembering to. IndexedDB is gated on one flag that defaults to off.
- **`lib/demo/cases.ts`** — the three committed cases, lazily imported so each is its own
  chunk and the landing page carries none of them.
- **`/result`** — verdict card, map, claim table, findings, "what this means / what it does
  not", deadline clock, next steps, both downloads. Composed entirely from S6 primitives.
- **`lib/map/ResultMap.svelte`** — the map moment. Red claim pin, the person's trail, a
  dashed line between them labelled with the distance and the required speed, a ±15-to-90
  minute scrubber, and the canvas the evidence packet embeds.
- **`/check`** — three steps on one route. Upload → extract → an editable review card with
  amber and the source quote under anything below 0.8 → the tick that `user_confirmed`
  depends on; then three location doors; then the optional roster.
- **`lib/ui/TextField.svelte`, `CheckBox.svelte`, `AffiantForm.svelte`** — field styling
  extracted from `ColumnMapper` rather than invented, so the wizard cannot drift from the
  advocate side of the product.
- **`/demo`** — the three cases are now buttons that load a case and land on `/result`,
  where the engine runs for real.
- **`/dev/ingest` and `/dev/analyze` deleted**, with their nav links.

**Verified**

- Frontend: `svelte-check` 0/0 over 295 files, `tsc` clean, `vitest` **294 passed** (was
  283), build clean. Backend, untouched: `ruff` clean over 129, `mypy` clean over 68,
  `pytest` **656 passed**.
- The whole wizard walked end to end against a live backend: papers → geocode → typed
  location → roster → verdict, and separately all three demo cases.
- Evidence packet downloaded with the map embedded — 866 KB against 77 KB without it,
  which is how the embedding was confirmed rather than assumed. Draft affidavit downloaded
  carrying exactly the ticks that were made and omitting the paragraph for the one that
  was not.
- 375 px: no horizontal scroll, nothing overflowing outside the two deliberate scrollers,
  every input labelled.

**Three bugs worth recording**

1. **The affidavit time was read in the browser's timezone.** `new Date('2025-06-12T19:42')`
   is browser-local, and on this machine — set to IST — a service typed as 19:42 reached
   the engine as 10:12 AM. Nine and a half hours, in the one number the whole verdict turns
   on, and it would have been silently wrong for every user outside New York while looking
   perfectly plausible. `lib/ingest/tz.ts` has had `nyLocalToInstant` since session 3; the
   wizard now uses it, and so does the manual location entry, which had the same bug.
2. **The map filtered out the very stay that proves the case.** A `VISIT` is an interval,
   and the window test measured from its start — so a recorded stay from 8:00 AM to 8:00 PM
   was eleven hours from a 7:42 PM claim and fell outside ±90 minutes. The scrubber read
   "0 of 1" on the demo case built to be contradicted. Distance is measured to the interval
   now, which is what the engine's own visit test does.
3. **A `map.on('error')` handler was deleting every successful capture.** MapLibre fires
   `error` for any survivable thing — one missing tile, one glyph range — so the packet
   printed its text alternative every time. Removed, and the capture became a pull rather
   than a push: the packet asks the map for its canvas at the moment it is built, so it
   cannot depend on an event having fired earlier and cannot hand over a frame from before
   the person moved the scrubber.

**Deferred**

- **The map capture is downscaled to 1400 px** before it is sent, because the raw canvas is
  the viewport times the device pixel ratio and the server refuses anything over 3 MB. At
  1280 px it was 1.5 MB; on a 2560 px display the untouched capture would have crossed the
  limit and failed on exactly the screens most likely to be showing this to a court.
- The `/check` upload path is exercised through the manual and demo routes; a real PDF
  through `POST /api/extract` needs `LLM_PROVIDER` configured, which this machine does not
  have. The route handles `provider === 'none'` by saying so and showing the manual form.
- `docs/screens/` for the Devpost gallery, and a Lighthouse run. The structural half of
  §14's accessibility ask is checked — labels, no overflow, keyboard-reachable controls.
