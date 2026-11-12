# Changelog

All notable changes to ServeTrace. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the app version follows
[Semantic Versioning](https://semver.org/). The engine and its thresholds carry their own
version stamps (`ENGINE_VERSION`, `PARAMS_VERSION`): a change listed here is not a change
to how a verdict is reached unless it says so.

## [1.1.0] — 2026-11-12

### Added

- Photos as evidence. Camera-roll photos are read on the device for their time and place
  only; pixels are never read and nothing is uploaded. A photo without a time zone is
  treated as possibly an hour off.
- Whole court files. A PDF, JPEG, PNG or HEIC file of up to 25 pages is sorted into
  summons, affidavit of service and judgment pages, and one file can hold several
  affidavits. The judgment entry date is offered as a draft to confirm.
- Where each field came from. Every field read off a page carries the quote and the page
  it came from, and is outlined on the page when the file has a text layer.
- Flagged-first review. Fields the reader was unsure of are shown first, with the quote
  beside them; every field is still confirmed by the person before anything is compared.
- Advocate attorney edition. A folder of affidavits is read one at a time in the browser,
  confirmed, and compared as a batch: impossible back-to-back services per server, how
  often each New York timing and diligence rule flags, out of the affidavits it applies
  to, and a rollup by process-serving agency. Exports as CSV and as a PDF report.
- A contact form for attorneys and legal-aid organisations, kept only with consent.
- Day-level usage counts (checks, packets, batches), with demos counted apart.
- Methodology: photo-only, time-uncertainty, page-classification and batch rule-rate
  evaluations, published from the eval run; a "Known limitations" section.
- This changelog, at `/changelog`, and the app version in the footer and on every PDF.
- Locale plumbing for a future second language (English is the only locale).

### Changed

- Uncertain time never strengthens a conflict. A fix whose time is uncertain is given the
  most favourable reading, and a conflict that rests only on times with an assumed zone is
  capped at moderate. Verdicts on exact data are unchanged (thresholds `2026.09-v1`).
- The single-affidavit upload endpoint was replaced by the whole-file reader.
- The privacy page describes the one small store and exactly what it can hold.

### Security

- Deployments that allow real court papers must opt in (`LLM_REAL_DATA_ALLOWED`); by
  default every upload screen says the deployment is for demos and synthetic data.
- The store holds no case data: no names from affidavits, addresses, coordinates, IP
  addresses, user agents, or times finer than a day. A store failure never fails a check.
- The contact form has a honeypot and its own rate limit; the reader endpoint has one too.

## [1.0.0] — 2026-09-27

### Added

- Defendant check for New York City Civil Court consumer credit cases: upload the
  affidavit of service, confirm what was read, bring location history (Google Timeline,
  card or bank statement, or typed in), and see whether it conflicts with the sworn time
  and place.
- A deterministic space-time engine (visit and prism tests) with conservative, published
  thresholds, plus a description check against the household and the New York timing
  and diligence rules for CPLR 308(2) and 308(4).
- Evidence packet and draft supporting affidavit as PDFs, with a CPLR 317 deadline clock.
- Advocate mode: a spreadsheet of service records ranked by impossible travel.
- Methodology page with the evaluation on 500 synthetic cases, and a privacy page.
- Demo mode with bundled synthetic cases that needs no network.

