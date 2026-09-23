# Disclosure

What ServeTrace is, what it is not, and where AI is involved. This page exists so a judge,
a legal aid worker or a user can tell exactly what they are looking at.

## What this does

ServeTrace compares a process server's sworn affidavit of service against the user's own
location history, checks the affidavit against New York's service rules, and produces an
evidence packet and a draft supporting affidavit for a motion to vacate a default judgment.

## What this is not

- **Not legal advice.** Everything generated is labelled DRAFT and directs the user to the
  NYC Civil Court Help Center or a legal aid organisation.
- **Not an accusation.** ServeTrace never states that anyone lied or committed fraud. It
  states that data conflicts. A judge decides what happened.
- **Not a prediction.** There is no "you will win" score and no outcome modelling.
- **Not a filing service.** It does not e-file, email anyone, or submit complaints on the
  user's behalf.
- **Not general-purpose.** It covers New York City Civil Court consumer credit actions and
  service on natural persons under CPLR 308(1), 308(2) and 308(4). Nothing else.

## Where AI is used

In exactly one place: reading the fields out of an uploaded affidavit PDF or photo.

Everything downstream is deterministic Python — the feasibility engine, the thresholds,
the timing rules, the verdict, and every generated document. No language model writes any
part of a legal document, and no language model decides any verdict.

The user confirms every extracted field before analysis runs; the backend refuses to
analyse an affidavit that has not been confirmed. Fields the extractor was unsure about are
flagged with the verbatim quote they came from, so the user is correcting a reading rather
than trusting one.

The product is fully usable with `LLM_PROVIDER=none`: the extraction step is replaced by a
manual entry form and nothing else changes.

## What the location check can and cannot show

Location history shows where a phone was, not where a person was. A phone left at home, a
phone that lost signal, and a phone whose owner was standing next to it look the same in an
export. Thresholds are deliberately generous towards the affidavit — a 300 m match radius
and an 80 km/h "impossible" speed for door-to-door NYC travel — so that a contradiction is
reported only when the user's own data leaves no reasonable room for the sworn account.

A `CONSISTENT` result is shown as plainly as a `CONTRADICTED` one. If the data backs the
server up, the product says so.

## Data handling

No accounts, no database, no persistence. Location files are parsed in the browser and the
full history never leaves the device; only the few hours around each claimed time are
transmitted, and the interface says how many points that is before sending. Uploads are
processed in memory. Logs record the request, not the person.

## Synthetic data

Every fixture, demo case, name, index number, licence number and affidavit in this
repository is invented. Street addresses come from NYC Planning Labs GeoSearch and are used
purely as geography; no address is associated with any real person. Demo screens carry a
"Synthetic demo data" chip.

The demo cases ship with their extraction already computed, in
`fixtures/demo_cases/<case>/extraction.json`, so a demonstration never calls a language
model or a network. Each of those files records how it was produced in its `provider`
field. `derived_from_ground_truth` means the draft was built from the case's own committed
affidavit, quoted from the rendered document and run through the same deterministic
validators as a real upload — it is what a perfect extraction of that document looks like,
not something a model said. A provider name there means a real model produced it.
