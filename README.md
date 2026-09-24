# ServeTrace

**They swore they served you. Your phone says otherwise.**

More than 70% of debt collection suits end in a default judgment. Many of those defendants
were never actually served — the papers went in a bin and the affidavit was sworn anyway,
a practice with its own name in New York: *sewer service*. The first the person hears of it
is a frozen bank account. ServeTrace helps someone in that position prove it: upload the
affidavit of service and your own location history, and see whether your data conflicts
with the sworn claim. It checks the affidavit against the CPLR service rules, then produces
an evidence packet and a draft supporting affidavit for a motion to vacate.

A second mode, **Advocate mode**, takes many service records from one process server and
finds sequences nobody could have travelled — two services miles apart, minutes apart. That
is the velocity check fraud engineers run on card transactions, applied to affidavits of
service. As far as we can tell, nobody had pointed it here.

> **Not legal advice.** Everything generated is labelled DRAFT and points the reader at the
> NYC Civil Court Help Center or a legal aid organisation. See [`docs/DISCLOSURE.md`](docs/DISCLOSURE.md).

Scope, the legal model and the engineering rules live in [`CLAUDE.md`](CLAUDE.md). Read it
before changing anything — in particular §5, which is the only place legal facts may come
from, and §6, which governs what the product is allowed to say.

## What it actually does

Three steps and one verdict.

1. **Your court papers.** Upload the affidavit of service. The fields are extracted and
   shown back as an editable card; anything the extractor was unsure of is amber and shows
   the words it was read from. You confirm the details are yours before anything is
   analysed.
2. **Where you were.** Google Timeline export (Android or iOS), a card or bank statement,
   or typed in by hand. **The file is read in your browser and never uploaded.** Only the
   few hours around each sworn moment are sent for analysis, and the screen says how many
   points that is out of how many it read.
3. **The result.** One headline, the map, and the numbers behind it — *"At 7:42 PM your
   phone was 10.6 km from that address"* — plus the findings, the CPLR 317 deadline clock,
   and two downloads.

It says four things and never a fifth. Your data **conflicts** with the affidavit, is
**consistent** with it, **doesn't settle it**, or **isn't there** for that time. It never
says anyone lied. A judge decides what happened.

## Architecture

```
Browser — SvelteKit, static                   Server — FastAPI, stateless, no database
┌──────────────────────────────────┐         ┌──────────────────────────────────────────┐
│ Wizard · MapLibre · IndexedDB    │         │ /api/extract    text layer → LLM → valid. │
│                                  │ affidavit│ /api/geocode    NYC GeoSearch + cache     │
│ Web Worker: location ingest      │ ───────► │ /api/analyze    the engine:               │
│   Timeline (Android/iOS)         │         │    feasibility · description · NY rules   │
│   card CSV · manual              │ windowed │    → verdict                              │
│   → LocationFix[]                │  fixes   │ /api/advocate/analyze                     │
│   window(±3h of each claim) ─────│ ───────► │ /api/documents/{packet,affidavit}         │
│                                  │         │                                           │
│ Full history NEVER leaves device │ ◄─────── │ No DB. No persistence. PII-free logs.     │
└──────────────────────────────────┘         └──────────────────────────────────────────┘
                     one Docker image: FastAPI serves the built bundle at /
```

Four decisions worth stating, because the rest follows from them:

- **The server keeps nothing.** No database, no accounts, no session. Case state lives in
  the browser, and only if you ask for it. There is nothing to breach and nothing to
  subpoena.
- **An LLM is used in exactly one place** — reading fields off an uploaded affidavit. The
  engine, the thresholds, the rules, the verdict and both documents are deterministic
  Python. No language model writes any part of a legal document or decides any verdict.
  `LLM_PROVIDER=none` is fully supported: the app falls back to a manual entry form.
- **The engine exists once, in Python.** The browser never reimplements a threshold. What
  the map draws and what the packet prints come from the same answer.
- **Types are generated, not copied.** Backend OpenAPI → `openapi-typescript` →
  `frontend/src/lib/api/schema.d.ts`.

More in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Running it

Two commands, or one image.

```bash
cd backend && uv sync --all-extras && uv run uvicorn app.main:app --reload
```

```bash
cd frontend && npm install && npm run dev
```

Vite proxies `/api` to `localhost:8000`. `http://localhost:8000/api/health` returns the
engine and params versions and the configured provider.

### As it deploys

```bash
docker build -t servetrace . && docker run --rm -p 8000:8000 servetrace
```

One container: FastAPI serves the built SvelteKit bundle at `/`.

### Configuration

Copy `.env.example` to `.env`. `backend/app/config.py` is the only module that reads the
environment. Every setting has a working default, and **the app is fully usable with no API
key at all**.

## Evaluation

```bash
python eval/run_eval.py
```

Generates the corpus if it is missing, scores the engine, the NY rules, advocate mode and
the robustness sweep, writes `eval/results/`, draws the figure, and rewrites the numbers
the Methodology page reads. About 40 seconds. Run it twice and the output is identical,
the PNG included.

**Headline: 0 false contradictions across 500 cases**, and the claimed moment read
correctly in 500 of 500. Ground-truth labels are decided by construction — the generator
records where it *put* the person — and never by calling the engine. That independence is
what makes the numbers mean anything.

[`eval/REPORT.md`](eval/REPORT.md) has the confusion matrix, precision and recall at both
severities, the per-rule table, the robustness sweep, and a written account of every case
the engine and the labels disagree on, with the reason each one is not an error.

The extractor has its own eval, which needs a provider and a key, and **has not been run**:

```bash
cd backend && PYTHONPATH=.. LLM_PROVIDER=gemini GEMINI_API_KEY=... \
    uv run python ../eval/extraction_eval.py --corpus ../fixtures/out --out ../eval/results
```

## Fixtures

The corpus is a pure function of its seed: the same seed produces byte-identical JSON, and
a test asserts it.

```bash
cd backend
uv run python -m fixtures.generator --n 500 --seed 7            # the corpus (gitignored)
uv run python -m fixtures.generator --n 500 --seed 7 --no-pdfs  # much faster
uv run python -m fixtures.generator --demo                      # the 3 demo cases (committed)
```

`fixtures/addresses_nyc.json` is committed, and rebuilding it is the only step that touches
the network. Two committed artefacts derive from it and neither needs the network:

```bash
cd backend
PYTHONPATH=.. uv run python -m fixtures.generator.build_geocache
PYTHONPATH=.. uv run python -m fixtures.generator.build_demo_extractions
```

## Documents

Two PDFs, rendered by WeasyPrint from Jinja2 templates filled with fields the user
confirmed. No LLM touches either (bible §15).

| route | what comes back |
|---|---|
| `POST /api/documents/packet` | the **Evidence Packet**: verdict, every sworn moment, the map as it was on screen, the findings with the provision each encodes, the records the check ran over, the thresholds it ran under, and a SHA-256 of both inputs |
| `POST /api/documents/affidavit` | the **Draft Supporting Affidavit**, to attach to the court's own Order to Show Cause form — numbered paragraphs built only from confirmed fields and findings, with a blank signature and notary block |

Committed samples of both are in [`docs/samples/`](docs/samples/). Identical input renders
identical bytes: the documents take their timestamp from the analysis rather than a clock,
so a packet can be regenerated and compared.

## Privacy and security

- **Your location file never leaves your device.** It is parsed by a Web Worker, and only
  fixes within ±3 hours of a sworn moment are sent. The screen tells you how many.
- **The server stores nothing.** Uploads are processed in memory and dropped.
- **Logs carry a request id, a route, a status and a latency, and nothing else.** Not a
  name, not an address, not a coordinate, not a line of document text.
  `tests/api/test_log_privacy.py` drives a full case through every route, captures the log
  stream and fails if any of that case's names, addresses or coordinates appear in it.
- Strict Content-Security-Policy (script hashes generated at build time, so the policy
  cannot drift from the bundle), `nosniff`, `no-referrer`, frame denial, HSTS behind TLS,
  and a `default-src 'none'; sandbox` policy on the API.
- Per-IP token-bucket rate limiting on the routes that cost money. Upload, fix-count and
  row-count ceilings on everything else.
- Everything in this repository is **synthetic**. Real NYC street addresses appear as
  geography and nothing else; every person, case, index number and document is invented.

## Quality gates

Every session ends with all of these green.

```bash
cd backend && uv run ruff check . ../fixtures ../eval && uv run ruff format --check . ../fixtures ../eval && uv run mypy app ../fixtures ../eval && uv run pytest
```

```bash
cd frontend && npm run check && npm run typecheck && npm run build && npx vitest run
```

### macOS note

WeasyPrint needs the Homebrew pango stack on its library path. Without it `import
weasyprint` fails with a cffi traceback that mentions none of this, and the PDF tests fail
loudly with this fix in the message — they do not skip.

```bash
brew install pango cairo gdk-pixbuf libffi
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```

Homebrew installs to `/opt/homebrew/lib` on Apple Silicon, which is not on macOS's default
dyld search path, so the libraries are present and invisible. The Docker image installs
them where Debian's linker already looks.

## Deploying

[`render.yaml`](render.yaml) is a Render blueprint for one web service built from the
`Dockerfile`, with a health check on `/api/health`. Two things are worth knowing:

- **`RATE_LIMIT_TRUSTED_HOPS=1`.** Render terminates TLS and proxies to the container, so
  every request arrives from the proxy. Without this the rate limiter sees one client for
  the whole internet and the first busy minute locks everybody out together.
- **Cold start.** On Render's free plan an idle service is suspended and the first request
  wakes it, which takes the better part of a minute. Open the URL two minutes before
  showing it to anyone.

## Limitations

Said here rather than left to be discovered.

- Location history shows where your **phone** was. It is not proof of where you were, and
  a judge decides what happened. Every result card says so.
- If the phone was off, out of battery or not recording, there is nothing to check and the
  product says that instead of guessing.
- A consistent result does not mean the service was proper. It means this particular check
  does not help you.
- New York City Civil Court consumer credit cases only, and only service on a person under
  CPLR 308(1), 308(2) and 308(4). The rules live in one module so other states can be added.
- The extraction eval has not been run, so there are no published extraction numbers.
- Nothing here predicts whether you will win, and nothing here is legal advice.

## Disclosure

Full version in [`docs/DISCLOSURE.md`](docs/DISCLOSURE.md); sources in
[`docs/SOURCES.md`](docs/SOURCES.md).

- **AI in the product:** one place — reading fields off an uploaded affidavit, via Gemini
  or Anthropic. Optional; the app works fully without it. Everything else is deterministic.
- **AI in building it:** written with Claude Code, in planned sessions recorded in
  [`tasks/todo.md`](tasks/todo.md), with mistakes and their rules in
  [`tasks/lessons.md`](tasks/lessons.md).
- **Libraries:** FastAPI, Pydantic, pdfplumber, pypdfium2, httpx, Jinja2, WeasyPrint,
  openpyxl, Pillow · SvelteKit, Svelte 5, Tailwind, MapLibre GL, PapaParse.
- **External services:** NYC Planning Labs GeoSearch (geocoding, free, no key),
  OpenFreeMap (basemap tiles), NYC DCWP's published process-server licence register.
- **Data:** entirely synthetic. Real NYC street addresses as geography only.

## License

MIT — see [`LICENSE`](LICENSE).
