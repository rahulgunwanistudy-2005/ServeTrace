# tasks/lessons.md

Format: `[YYYY-MM-DD] - [what went wrong] -> [rule going forward]`

[2026-09-23] - A generator invariant test was written to assert "no fix in the +/-3h window
is near the claimed address" for contradicted cases. That is stronger than the engine's
own rule and would have failed on correct data. -> Write generator invariants against the
*engine's* stated decision rules (bible §11), not against a stricter intuition. Here the
rule that matters is §11.1.3: a fix inside the match radius within +/-15 min of the claim
makes it CONSISTENT.

[2026-09-23] - Ground-truth labels and the thing being measured must stay independent. The
generator decides `true_tier` from where it *placed* the person, and never by calling the
engine. -> Any future change to the generator must preserve this. A label derived from the
engine turns the eval into a tautology.

[2026-09-23] - Curated demo addresses were resolved by substring match with a silent
fallback to the first address in the borough, which quietly relocated a demo case when the
pinned address was not in the pool. -> Pinned fixtures fail loudly. `_address()` now raises.

[2026-09-23] - The evidence-quote grounding score compared a quote against a text window
*longer* than the quote, so the quote was penalised for the words around it: a single
OCR-style character slip in a 42-character address scored 0.87 and looked like an invented
quote. -> When scoring a fuzzy match, find the alignment first and then measure against a
window the same length as the needle. A threshold is only meaningful if the measurement
under it means what it says.

[2026-09-23] - A test in the extraction eval called `geocode()` on an address that was not
in the committed cache, so it silently made a real request to NYC GeoSearch and passed
because this machine happened to be online. -> Mocking each call site is a promise;
blocking the transport is a guarantee. `backend/tests/conftest.py` now refuses every real
httpx request in the suite, and has its own test, because a guard that quietly stops
working is worse than no guard.

[2026-09-23] - The demo extraction builder looked for each field's *value* on the page,
which failed for the three fields the affidavit form does not print as its value: the
court (capitals, across two lines, without "County of"), the method (printed as the
statutory wording, not as "308_2") and the description (a table row without its labels).
The first run produced demo cases with amber warnings on fields that are plainly legible.
-> When a fixture cannot find its own evidence, fix what is being searched for. Lowering
the grounding bar to make a fixture pass would have weakened the check that protects every
real user.
