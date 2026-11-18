# Live smoke test

Run 2026-11-18 21:50 UTC against https://servetrace.onrender.com with `scripts/smoke_live.py`.
Desktop is 1440x900; phone is Playwright's emulated iPhone 13 (390x844, touch, mobile
user agent) in Chromium. Load time is the browser's navigation `loadEventEnd`.

## Pages

| Viewport | Page | Status | Load | Console errors | Horizontal overflow | Result |
|---|---|---:|---:|---:|---:|---|
| desktop | `/` | 200 | 2098 ms | 0 | 0 px | pass |
| desktop | `/check` | 200 | 409 ms | 0 | 0 px | pass |
| desktop | `/demo` | 200 | 413 ms | 0 | 0 px | pass |
| desktop | `/attorneys` | 200 | 420 ms | 0 | 0 px | pass |
| desktop | `/advocate` | 200 | 726 ms | 0 | 0 px | pass |
| desktop | `/methodology` | 200 | 421 ms | 0 | 0 px | pass |
| desktop | `/privacy` | 200 | 401 ms | 0 | 0 px | pass |
| desktop | `/changelog` | 200 | 407 ms | 0 | 0 px | pass |
| iphone | `/` | 200 | 1208 ms | 0 | 0 px | pass |
| iphone | `/check` | 200 | 923 ms | 0 | 0 px | pass |
| iphone | `/demo` | 200 | 371 ms | 0 | 0 px | pass |
| iphone | `/attorneys` | 200 | 387 ms | 0 | 0 px | pass |
| iphone | `/advocate` | 200 | 700 ms | 0 | 0 px | pass |
| iphone | `/methodology` | 200 | 397 ms | 0 | 0 px | pass |
| iphone | `/privacy` | 200 | 385 ms | 0 | 0 px | pass |
| iphone | `/changelog` | 200 | 387 ms | 0 | 0 px | pass |

## Flows

| Flow | Result | Time | Detail |
|---|---|---:|---|
| desktop: /demo case to verdict + packet | pass | 18.0 s | verdict 'conflicts'; packet 38,458 bytes |
| desktop: attorney sample batch to report | pass | 14.5 s | Compare 60 confirmed affidavits; Download the report (PDF) 472,792 bytes; Sequences (CSV) 568 bytes |
| desktop: photo import on /check | pass | 3.9 s | 3 photos read · 3 with a location · 3 near the claimed time. |
| desktop: contact form refuses, never submits | pass | 1.8 s | name and email filled, consent not ticked: Send stays disabled, no request to /api/leads |
| iphone: /demo case to verdict + packet | pass | 7.2 s | verdict 'conflicts'; packet 38,455 bytes |
| record a_demo_map_verdict | pass | 27.7 s | verdict 'conflicts'; packet 508,649 bytes |
| record b_photo_import | pass | 11.3 s | 3 photos read · 3 with a location · 3 near the claimed time. |
| record c_attorney_batch_report | pass | 24.8 s | Compare 60 confirmed affidavits; Download the report (PDF) 621,844 bytes; Sequences (CSV) 568 bytes |

## Clips

- `scripts/smoke_out/video/a_demo_map_verdict.webm`
- `scripts/smoke_out/video/b_photo_import.webm`
- `scripts/smoke_out/video/c_attorney_batch_report.webm`

Screenshots are in `scripts/smoke_out/` (gitignored).
