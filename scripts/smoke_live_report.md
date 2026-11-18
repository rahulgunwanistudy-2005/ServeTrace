# Live smoke test

Run 2026-11-18 21:45 UTC against https://servetrace.onrender.com with `scripts/smoke_live.py`.
Desktop is 1440x900; phone is Playwright's emulated iPhone 13 (390x844, touch, mobile
user agent) in Chromium. Load time is the browser's navigation `loadEventEnd`.

## Pages

| Viewport | Page | Status | Load | Console errors | Horizontal overflow | Result |
|---|---|---:|---:|---:|---:|---|
| desktop | `/` | 200 | 1792 ms | 0 | 0 px | pass |
| desktop | `/check` | 200 | 396 ms | 0 | 0 px | pass |
| desktop | `/demo` | 200 | 412 ms | 0 | 0 px | pass |
| desktop | `/attorneys` | 200 | 416 ms | 0 | 0 px | pass |
| desktop | `/advocate` | 200 | 687 ms | 0 | 0 px | pass |
| desktop | `/methodology` | 200 | 368 ms | 0 | 0 px | pass |
| desktop | `/privacy` | 200 | 390 ms | 0 | 0 px | pass |
| desktop | `/changelog` | 200 | 391 ms | 0 | 0 px | pass |
| iphone | `/` | 200 | 2266 ms | 0 | 0 px | pass |
| iphone | `/check` | 200 | 380 ms | 0 | 0 px | pass |
| iphone | `/demo` | 200 | 387 ms | 0 | 0 px | pass |
| iphone | `/attorneys` | 200 | 372 ms | 0 | 0 px | pass |
| iphone | `/advocate` | 200 | 703 ms | 0 | 0 px | pass |
| iphone | `/methodology` | 200 | 582 ms | 0 | 0 px | pass |
| iphone | `/privacy` | 200 | 611 ms | 0 | 0 px | pass |
| iphone | `/changelog` | 200 | 385 ms | 0 | 0 px | pass |

## Flows

| Flow | Result | Time | Detail |
|---|---|---:|---|
| desktop: /demo case to verdict + packet | pass | 7.1 s | verdict 'conflicts'; packet 38,458 bytes |
| desktop: attorney sample batch to report | pass | 9.9 s | Compare 60 confirmed affidavits; Download the report (PDF) 35,620 bytes; Sequences (CSV) 568 bytes |
| desktop: photo import on /check | pass | 4.0 s | 3 photos read · 3 with a location · 3 near the claimed time. |
| desktop: contact form refuses, never submits | pass | 1.8 s | name and email filled, consent not ticked: Send stays disabled, no request to /api/leads |
| iphone: /demo case to verdict + packet | pass | 6.9 s | verdict 'conflicts'; packet 38,453 bytes |

Screenshots are in `scripts/smoke_out/` (gitignored).
