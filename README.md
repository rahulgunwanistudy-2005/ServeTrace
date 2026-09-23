# ServeTrace

**They swore they served you. Your phone says otherwise.**

More than 70% of debt collection suits end in a default judgment. Many of those defendants
were never actually served — the papers were thrown away and the affidavit was sworn
anyway. ServeTrace helps someone in that position prove it: upload the affidavit of
service and your own location history, and see whether your data conflicts with the sworn
claim.

A second mode, **Advocate mode**, takes many service records from one process server and
finds sequences nobody could have travelled — two services miles apart, minutes apart. It
is the velocity check fraud engineers run on card transactions, applied to affidavits of
service.

Scope, law and engineering rules live in [`CLAUDE.md`](CLAUDE.md). Read it before changing
anything.

> Not legal advice. See [`docs/DISCLOSURE.md`](docs/DISCLOSURE.md).

## Layout

```
backend/     FastAPI, Pydantic contracts, deterministic engine, document rendering
frontend/    SvelteKit static bundle, location ingest, MapLibre
fixtures/    Seeded synthetic corpus generator, committed demo cases, NYC address pool
eval/        Scores the engine against the corpus' ground truth
docs/        Sources, architecture, disclosure
tasks/       Session plan and lessons
```

## Running it

### Backend

```bash
cd backend && uv sync --all-extras
uv run uvicorn app.main:app --reload
```

`http://localhost:8000/api/health` returns the engine and params versions, and the
configured LLM provider.

### Frontend

```bash
cd frontend && npm install
npm run dev
```

Vite proxies `/api` to `localhost:8000`.

### Everything, as it deploys

```bash
docker build -t servetrace .
docker run --rm -p 8000:8000 servetrace
```

One container: FastAPI serves the built SvelteKit bundle at `/`.

## Configuration

Copy `.env.example` to `.env`. `config.py` is the only module that reads the environment.

The app is fully usable with `LLM_PROVIDER=none` — extraction falls back to a manual entry
form and nothing else changes.

## Fixtures

The corpus is a pure function of its seed: the same seed produces byte-identical JSON, and
a test asserts it.

```bash
cd backend
# 200 cases + advocate records -> fixtures/out/ (gitignored)
uv run python -m fixtures.generator --n 200 --seed 7

# much faster, skips PDF rendering
uv run python -m fixtures.generator --n 200 --seed 7 --no-pdfs

# the three curated demo cases -> fixtures/demo_cases/ (committed)
uv run python -m fixtures.generator --demo
```

Ground-truth labels are decided by construction — the generator records where it *put* the
person — and never by calling the engine. That independence is what makes the eval mean
anything.

`fixtures/addresses_nyc.json` is committed. Rebuilding it is the only step that touches the
network:

```bash
uv run python -m fixtures.generator.build_addresses
```

Two committed artefacts are derived from it, and neither needs the network:

```bash
cd backend
# address pool -> backend/app/geo/cache.json, so demo addresses resolve from disk
PYTHONPATH=.. uv run python -m fixtures.generator.build_geocache

# demo cases -> fixtures/demo_cases/<case>/extraction.json, so demo mode needs no LLM
PYTHONPATH=.. uv run python -m fixtures.generator.build_demo_extractions
```

Without a provider configured, the second one derives each draft from the case's own
committed affidavit and records `provider: "derived_from_ground_truth"` in the file. With
`LLM_PROVIDER` set it runs the real extractor and records that instead. Tests assert both
files stay in step with what they were derived from.

## Evaluation

```bash
cd backend
# the engine, against the corpus' independent ground truth
PYTHONPATH=.. uv run python ../eval/run_eval.py --corpus ../fixtures/out --out ../eval/results

# the extractor, per field, clean and scanned separately. Needs a provider and a key.
PYTHONPATH=.. LLM_PROVIDER=gemini GEMINI_API_KEY=... \
    uv run python ../eval/extraction_eval.py --corpus ../fixtures/out --out ../eval/results
```

The engine eval also rewrites `frontend/src/lib/eval/published.json`, which is what the
Methodology page reads — so the published figures cannot drift from the run that produced
them, and a test fails if they do.

Current headline: **0 false contradictions across 200 cases**, and the claimed moment read
correctly in 200 of 200. See [`eval/REPORT.md`](eval/REPORT.md) for the confusion matrix,
the edge cases, the per-rule numbers and the four case-level disagreements with the reason
each one is not an error.

### macOS note

WeasyPrint needs the Homebrew pango stack on its library path, so PDF rendering needs:

```bash
brew install pango gdk-pixbuf libffi
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```

`--no-pdfs` avoids this entirely. The Docker image installs the libraries properly.

## Quality gates

Every session ends with all of these green.

```bash
cd backend
uv run ruff check . ../fixtures ../eval
uv run ruff format --check . ../fixtures ../eval
uv run mypy app ../fixtures ../eval
uv run pytest
```

```bash
cd frontend && npm run check && npm run typecheck && npm run build && npx vitest run
```

## Development-only routes

Two pages exist to exercise a slice end to end by hand. Both refuse to render outside
`npm run dev` and neither appears in a production build.

| route | what it does |
|---|---|
| `/dev/ingest` | drop a location export, see what the worker parsed, windowed and kept |
| `/dev/analyze` | run a committed demo case through the real `POST /api/analyze` |
