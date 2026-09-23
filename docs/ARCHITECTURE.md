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

## Extraction

One provider-agnostic pipeline, in `backend/app/extraction/`:

```
bytes ─► sniff (magic bytes)  ─► pdfplumber text layer ─► text >= 200 chars ─► text prompt
                              └─► image                └─► otherwise ───────► pypdfium2 raster,
                                                                              <= 3 pages, 200 dpi
                                        │
                                        ▼
                               provider (gemini | anthropic | none)
                                        │  JSON, one shared schema
                                        ▼
                               validators.py  (deterministic)
                                        │
                                        ▼
                          AffidavitDraft + ValidationNote[]
```

`schema.py` holds the one JSON Schema every provider is given and the one parser that
reads every provider's answer, so "what the model may say" and "what we do with it" cannot
drift apart. Every field comes back as `{value, confidence, evidence_quote}`; the quote is
what makes grounding possible, and it doubles as the "exactly as written" form of every
date and time, since the field itself holds the normalised value.

`validators.py` is where every judgement lives: dates and times parsed and localised to
America/New_York with a DST-ambiguity flag, licence numbers checked, method normalised or
inferred from the form's own wording, and each quote scored against the text layer with
`difflib` (0.90). Failing a check never drops a field — it caps that field's confidence and
attaches a note, because a user can correct a field they can see and cannot correct one
that was silently discarded. A document with no text layer has nothing to check a quote
against, so everything read off a scan is capped at 0.6.

`LLM_PROVIDER=none` is a first-class configuration, not a stub: the deterministic half
still runs, so the service method comes off the affidavit's own wording and the user types
the rest.

## Geocoding

`geo/geocode.py` asks NYC GeoSearch and nothing else, sends only the address, and drops any
result outside a five-borough bounding box. `app/geo/cache.json` is committed and derived
from the same address pool the fixtures use, so every demo and fixture address resolves
from disk with no upstream call — that is what makes bible §17's "the demo must never fail"
true rather than hopeful. At runtime, misses are kept in a bounded in-memory LRU; the file
is never written by the server.

## Location ingest

Everything under `frontend/src/lib/ingest/` runs on the user's device, in a Web Worker.

```
File ─► file.stream() ─► streamJson.ts ─► one record at a time ─► parsers/ ─► LocationFix
                          (state machine)                          android/ios
                                                                       │
                                            stats (whole file) ◄───────┤
                                                                       ▼
                                                     window ±3h of each claim  ── dropped
                                                                       │
                                                        dedupe, cap 5,000
                                                                       ▼
                                                            what may be sent
```

**Why a hand-written scanner.** A Timeline export can be hundreds of megabytes. Reading it
into a string and calling `JSON.parse` needs the file, the string and the object graph in
memory at once, and a streaming JSON parser is a dependency bible §8 does not list.
`streamJson.ts` is a character-fed state machine that yields one element of the interesting
array at a time and hands each to `JSON.parse` on its own: peak memory is one record, and
the browser's parser still does the parsing. It runs at roughly 17 MB/s, so a 150 MB export
is about ten seconds in the worker with progress reported throughout. Because it holds all
its state in fields, a chunk boundary anywhere — mid-key, mid-string, mid-number, or
between the two bytes of a degree sign — cannot change the result, and a test asserts that
by cutting the same document at every position.

**Why windowing happens during the parse.** `window.ts` is still the definition of the
privacy boundary and still has its own tests. But the worker is also given the claimed
times, and drops out-of-window fixes as it reads. A multi-year history is millions of
points; collecting them all to discard most afterwards is both a memory problem and an
unnecessary risk. What the worker holds is bounded by the window, not by the file.
Statistics are accumulated over every fix, including the discarded ones, so the user is
still told what their whole export covers.

**Why the parsers are pure.** Nothing in `ingest/` can reach the network. Card statements
and typed-in entries produce a `PendingFix` that carries an address rather than a point;
`resolve.ts` turns those into points using a geocoder handed to it by the caller
(`geocoder.ts`, which posts the address and nothing else). Every parser test is therefore
offline by construction rather than by mocking.

**Shape detection.** The scanner tags each record with the array it came from, so the
format decides itself: records from `semanticSegments` or `rawSignals` are an Android
export, records from a top-level array are an iOS one. An Android export writes every
journey point twice — in `timelinePath` and again in `rawSignals`, where the accuracy
figure is — so duplicates are merged rather than chosen between, and `dedupe.ts` and
`stats.ts` share one key function so the count on screen and the list that is sent cannot
disagree.

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
document text. `/api/extract` and `/api/geocode` are behind a per-client token bucket
(`api/rate_limit.py`), which is the only place the server keeps anything between requests —
a count and a timestamp per address, and nothing that says who anyone is.

One thing this boundary does **not** cover: the result map pans to the user's own points,
so the tile host can infer roughly where those points are from which tiles are requested.
No location data is sent, but the inference is real, and the privacy page says so.
