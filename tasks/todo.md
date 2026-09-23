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
