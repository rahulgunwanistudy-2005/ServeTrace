# Architecture

## Shape

```
Browser (SvelteKit, static)                         Server (FastAPI, stateless)
┌─────────────────────────────────────┐            ┌──────────────────────────────────────┐
│ Wizard UI + MapLibre                │  affidavit │ /api/extract                         │
│                                     │ ─────────► │  pdf text layer → LLM vision → valid.│
│ Web Worker: location ingest         │            │ /api/geocode (NYC GeoSearch + cache) │
│  Timeline.json (Android/iOS), CSV,  │  windowed  │ /api/analyze                         │
│  manual → LocationFix[]             │  fixes     │  engine: feasibility, description,   │
│  window(±3h of each claim) ────────►│ ─────────► │  NY timing rules, verdict            │
│ Full history NEVER leaves device    │            │ /api/advocate/analyze                │
│                                     │            │ /api/documents/packet (WeasyPrint)   │
│ IndexedDB: optional local case save │  ◄──────── │ No DB. No persistence. Redacted logs.│
└─────────────────────────────────────┘            └──────────────────────────────────────┘
```

## Decisions

These are settled. `CLAUDE.md` §7 is the authority; this file explains the consequences.

**Stateless server, no database.** There is no account and nothing to breach. Case state
lives in the browser and in the exported bundle. It also keeps the deployment to a single
Render service with no persistence bill.

**Single deployable.** A multi-stage Docker build compiles the SvelteKit bundle with Node,
then serves it from FastAPI via `StaticFiles`. `app/main.py` mounts the bundle at `/` last,
so `/api/*` always wins over a same-named static path.

**The LLM is used in exactly one place.** Affidavit field extraction, and nothing else.
Every verdict, every rule, every number and every generated document is deterministic
Python. `LLM_PROVIDER=none` is a fully supported mode: the UI falls back to manual entry
and the rest of the product is unchanged. Documents are Jinja2 templates filled from
fields the user has confirmed.

**The engine exists once, in Python.** The frontend never reimplements feasibility,
thresholds or verdict logic. It windows the fixes and posts them; everything else happens
server-side. The one deliberate duplication is the ±3h window constant, because the
browser must apply it *before* anything is transmitted — that is the privacy boundary, and
`src/lib/ingest/window.ts` has its own tests for exactly that reason.

**Types are generated.** `backend` OpenAPI → `openapi-typescript` → `frontend/src/lib/api/schema.d.ts`,
via `npm run gen:types`. Hand-copied types drift.

## Layering

```
routes_*.py   → engine / extraction / advocate / documents   → domain.models
                                                              → geo, engine.params
```

Routes hold no logic; they validate, call one module, and shape the response. The engine
never imports FastAPI. `config.py` is the only module that reads the environment.

## Determinism

`engine/params.py` is a frozen dataclass with a `PARAMS_VERSION`. Every `CaseAnalysis` and
every generated document carries that version plus the engine version, so any verdict a
user downloaded can be traced to the exact thresholds that produced it. Changing a
threshold requires bumping the version.

The fixture generator under `fixtures/generator/` is a pure function of its seed: the same
seed produces byte-identical JSON, which is asserted by a test rather than assumed. Its
ground-truth labels are decided by construction and never by calling the engine, so the
eval measures the engine rather than measuring it against itself.

## Privacy boundary

The full location history is parsed in a Web Worker and never transmitted. Only fixes
within ±3h of a claimed time are posted to `/api/analyze`, and the UI states how many of
how many points that is before sending. Uploads are processed in memory. Logs carry a
request id, route, status and latency, and never a name, an address, a coordinate or
document text.
