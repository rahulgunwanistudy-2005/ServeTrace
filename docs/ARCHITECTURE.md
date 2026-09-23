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

## The engine

Everything in `backend/app/engine/` is pure: no I/O, no wall clock, no FastAPI. One
request in, one `CaseAnalysis` out, and the same input always gives the same answer.

```
AnalyzeRequest ─► verdict.analyze
                    │
                    ├─ build_index(fixes)          one sorted index, shared by every claim
                    │
                    ├─ for each claim (served_at, attempt[0..n]):
                    │     feasibility.evaluate_prepared
                    │        ├─ interpretations()   1 instant, or 2 on the DST fold
                    │        ├─ near evidence at T? ───────────────► CONSISTENT
                    │        ├─ a stay covering T, too far away? ──► CONTRADICTED (strong)
                    │        ├─ prism: speed from the nearest fix each side
                    │        │     > 80 km/h ─► strong · > 40 km/h ─► moderate
                    │        └─ nothing in the window ─────────────► NO_DATA
                    │
                    ├─ rules_ny.check_rules        R-T1, R-T2, R-T3, R-D1, R-D2, R-M1
                    ├─ description.check_description
                    └─ deadlines.compute_deadlines  CPLR 317
```

**Copy lives in one module.** `engine/copy.py` holds every sentence the engine can put in
front of a user. A rule decides *whether* it fires and hands its numbers to a template
there. Nothing else under `engine/` contains a user-facing string, which is what makes
"no legal statement outside bible §5" a thing you can check by reading one file. Every
finding that states law carries the L-id it came from.

**Statute is not a threshold.** The 20-day windows in `rules_ny.py` are named constants in
that module, not entries in `params.py`. Twenty days is twenty days because CPLR 308 says
so; moving it would not tune the engine, it would make the engine wrong. What does live in
`params.py` are the judgement calls — the match radius, the speeds, the description
tolerances — and each is stamped on every verdict as `PARAMS_VERSION`.

**Three places where the code is deliberately more conservative than a literal reading of
bible §11**, all in the same direction, all so the product never accuses anyone on
ambiguous data:

1. *Evidence at the claimed time wins over everything.* §11.1.5 says a `CONSISTENT`
   reading overrides a MODERATE contradiction and is silent on a STRONG one, while §11.1
   separately requires that a fix exactly at the claimed point at the claimed time always
   yields `CONSISTENT`. One rule satisfies both: a fix inside the match radius within the
   consistency window settles the claim. The competing finding is still reported, and a
   third finding says plainly that the user's own data disagrees with itself.
2. *Sub-minute gaps floor the elapsed time instead of jumping to infinity.* The literal
   guard called a phone 450 m from a door at the claimed minute a STRONG contradiction.
   Affidavit times are written to the minute and phone timestamps are rounded to it, so a
   gap under a minute is not a measurement and a distance divided by rounding noise is not
   a speed. The corpus' own edge case at that distance is independently labelled
   `INCONCLUSIVE`, and it is right.
3. *A consistent service claim is never overridden by a contradicted attempt.* §11.1.6
   reads "strongest CONTRADICTED across claims", but §6 defines CONTRADICTED as being far
   from *the claimed service point at the claimed time*. A 308(4) affidavit carries
   attempts on other days, and someone demonstrably home at 7 PM was very likely at work
   during a 10:30 AM attempt three weeks earlier. The attempt still produces its own STRONG
   finding and R-D2; it just does not rewrite the headline. Where the service claim is
   *unsettled*, a contradicted attempt does set the case verdict — burying a strong
   conflict under "we have no data for that time" would be its own dishonesty.

**Ambiguous clocks are evaluated twice.** On the night the clocks go back, a stated local
time names two instants an hour apart, and the affidavit only ever said "1:30 AM". Both
readings are evaluated and the weaker one is kept; when they disagree, the user is told the
choice was made.

**Performance.** 5,000 fixes across four claims analyse in about 4 ms against a 200 ms
budget. Fixes are sorted and indexed once per request and bisected per claim, so an
affidavit with three prior attempts asks four questions of one export rather than making
four passes over it. Interval fixes are bounded on the right and scanned on the left,
because a ten-hour stay can start long before a six-hour window and still cover it.

## Advocate mode

The same physics as the claim engine, pointed at a different question and carrying a
different weight of evidence.

```
XLSX / CSV ─► advocate/ingest.py ─► ServiceRecord[]  +  RejectedRow[]
                                          │
                                          ▼
                              advocate/patterns.py  (bible §11.4)
                                          │
                        ServerReport[] ranked by risk ─► advocate/report.py ─► CSV
```

The defendant flow asks whether one person's phone can be reconciled with one sworn claim.
Batch mode asks whether a process server's **own filings** can be reconciled with each
other, which needs no location history from anybody: two services sworn eleven kilometres
apart three minutes apart are in conflict whatever either defendant was doing that day.
That makes it a different kind of evidence, and the copy says so rather than leaving the
reader to infer it — one contradicted service is a dispute between two accounts, and six
impossible sequences inside one account is a pattern.

Four decisions.

**The elapsed-time floor is imported, not restated.** `patterns.py` prices a step between
two filings with `engine/feasibility.MIN_ELAPSED_S`. Two filings at the same instant would
otherwise divide by zero, and infinity is not JSON; more importantly, an advocate and a
defendant looking at the same two points must be told the same speed.

**A rejected row is part of the answer.** Every row that cannot be parsed comes back as a
`RejectedRow` with the row number the spreadsheet shows and the column at fault — never the
cell's contents, for the same reason the logs redact (bible §16). An advocate is assembling
something they will put their name to, and a parser that silently discards eleven rows
hands them a report whose denominator is wrong.

**Throughput counts completed services, not doors knocked on.** A `not_home` is the
evidence of diligence that 308(4) asks for, so counting attempts would give the server who
documents six fruitless visits a worse number than the one who claims six services. The
rolling-hour window is half-open for the same reason the other thresholds are generous:
the reading that flags less is the one that accuses less.

**`AdvocateAnalysis` carries the filings and the mapping back.** A `ServerReport` holds
only the pairs that do not fit, and a map of those alone would imply that four flagged
steps were the server's entire output — the cluster of ordinary doors is what makes the
outlier mean something. Records are capped and the cut falls *between* servers, so any
server the map can open it can draw completely. The column mapping rides along for the
reason `params_version` does: a number is reproducible only beside what produced it.

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

`/api/analyze` is behind the same bucket. It costs no upstream quota, but it does cost CPU,
and one unauthenticated client should not be able to spend all of it.

One thing this boundary does **not** cover: the result map pans to the user's own points,
so the tile host can infer roughly where those points are from which tiles are requested.
No location data is sent, but the inference is real, and the privacy page says so.

## Maps

`lib/map/AdvocateMap.svelte` and, from session 7, `ResultMap.svelte` both draw with
MapLibre over OpenFreeMap's `liberty` style, with `preserveDrawingBuffer` on so a canvas
can be captured for a document (bible §15).

Two things about that pairing are not obvious and both cost real time to find.

**MapLibre parses style colours itself and does not understand `oklch`.** The whole
palette in `app.css` is OKLCH, so a layer painted straight from a token is rejected and
never drawn. `lib/map/color.ts` resolves a token by filling one canvas pixel with it and
reading the sRGB bytes back, which gets the browser's own conversion — including its gamut
clamping — rather than a second implementation that could disagree with the page.

**A worker failure is scoped to the source, not to the layer that caused it.** A symbol
layer with no `text-font` asks for MapLibre's default `Open Sans Regular`, which
OpenFreeMap does not serve; the glyph request 404s, the worker errors the whole *tile*, and
every layer sharing that source renders nothing. When a source with valid data draws
nothing, `map.style.sourceCaches[id]._tiles` is the place to look — the tiles read
`state: "errored"`.

## The visual system

`frontend/src/app.css` is the whole of it. Colours are semantic tokens — `bg-surface`,
`text-muted`, `border-contradicted` — defined once as CSS custom properties and redefined
in one block under `prefers-color-scheme: dark`. Components never name a raw colour, so
dark mode is one edit rather than a `dark:` variant on every element, and the rule that a
`CONSISTENT` verdict is never rendered in the colour of a conflict lives in
`lib/ui/tone.ts` where a test can hold us to it.

Two consequences worth stating, because both were bugs first:

- **No colour utilities in `app.html`.** A `bg-white` on `<body>` beats a base-layer rule
  and pins the whole app to one scheme regardless of the reader's setting.
- **No class names built by interpolation.** Tailwind scans source text, so `` `border-${tone}` ``
  is a class it never generates. Tones are looked up in a map with every name written out.
