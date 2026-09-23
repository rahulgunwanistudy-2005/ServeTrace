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

[2026-09-23] - The rate limiter bounded its bucket map by dropping the least recently used
client. A test written to assert that a spray of fresh addresses cannot clear someone's
bucket failed, and it was right to: a client that has just been refused stops making
requests, so it is *precisely* the least recently used, and a hundred junk addresses would
hand it a fresh bucket. -> When bounding a security-relevant cache, evict by what the entry
*protects*, not by when it was touched. Buckets are now dropped in order of how many tokens
they have left, so the client at zero is the last one forgotten.

[2026-09-23] - The streaming JSON scanner kept one `returnTo` field for both "where to go
when this array ends" and "where to go when this skipped value ends". A skipped value
inside an array overwrote the array's own return, and the scanner read the rest of the
document as though it were still inside that array - silently, on files that parsed fine
until they contained a scalar. -> A state machine needs one return slot per kind of nesting
it can be in. The bug was found by a test that cuts the same document at every position and
asserts the same answer; that test is worth more than any number of hand-picked inputs.

[2026-09-23] - `stats.total` counted Android's `rawSignals` as separate points, so a day
holding 19 distinct fixes was reported to the user as 35. The duplicate is by design: the
export writes every journey point in `timelinePath` and again as a raw signal. -> A count
shown to a user has to mean what they would mean by it. Stats and dedupe now share one
`fixKey`, so the number on screen and the list that is sent can never disagree.

[2026-09-23] - Appending to a string one character at a time cost more than the rest of the
scan put together: 11.5 MB parsed in 1056 ms, of which the actual state machine was 181 ms
and `JSON.parse` 150 ms. Collecting into an array and joining once per item took it to
687 ms. -> Measure before optimising, and measure the parts separately. The obvious suspect
(the character loop) was not the expensive one.

[2026-09-23] - A test asserted on the wording of an error message, and broke when that
message moved into `copy/en.ts` and changed tense. -> Tests assert on the code, never on the
sentence. The sentence belongs to the copy module and has to stay free to change.

[2026-09-23] - Bible §11.1.3 guards sub-minute gaps with an infinite required speed
whenever the fix is outside the match radius. Implemented literally, that called a phone
450 m from a door at the claimed minute a STRONG contradiction of a sworn statement - a
two-minute walk, and the width of a geocoding error. The S1 generator had independently
labelled that exact case INCONCLUSIVE and was right. -> When the spec and the fixtures
disagree, work out which one is describing reality before changing either. The guard is
now a floor on elapsed time, which is continuous, monotone, uses the same thresholds and
needs no special case. A threshold that produces a cliff at the radius was the tell.

[2026-09-23] - The confusion matrix looked like the engine was wrong about four `no_data`
and `inconclusive` cases. It was not: the engine's verdict on the *claimed moment* was
right in all 200, and the disagreement was entirely about what `overall` should say when a
prior attempt is contradicted but the service claim is not. -> Score like against like.
The generator labels one moment, so the headline number compares the engine's verdict on
that moment. A second, product-level number is reported beside it rather than blended in,
because an average would have hidden which of the two actually moved.

[2026-09-23] - The eval reported R-T3 as "6 missed". Every one was a 308(1) affidavit: the
generator seeds a late proof-of-service date on personal service, and bible §11.3 scopes
R-T3 to 308(2) and 308(4) because §5 gives no authority for a filing deadline on personal
delivery. -> A miss is only a miss inside the rule's own scope. Counting those would have
penalised the engine for obeying §5, and silently dropping them would have been the other
kind of lie, so `rule_recall` carries an `out_of_scope` column that names them.

[2026-09-23] - `str.capitalize()` lower-cases everything after the first letter, so a
finding read "The service claimed at 7:42 pm on 12 june 2025" in a document meant for a
court. It was caught by a golden snapshot, not by anyone reading the template. -> Snapshot
the rendered output of anything a user will read. The bug is invisible in the f-string and
obvious in the file.

[2026-09-23] - The deadline card showed "June 1, 2027" from the browser and "1 June 2027"
from the server in the same paragraph. Two date conventions on one card is what makes a
document look machine-made. -> Any value that can be rendered on both sides of the wire
needs one agreed format, chosen for the reader. This is a product for people in New York,
so both are month-first now.

[2026-09-23] - A body element carrying `bg-white text-slate-900` from the original app
shell beat the base-layer tokens in `app.css`, so the page rendered dark cards on a white
background with dark text on them. Separately, `` `border-${tone}` `` in a component
produced a class Tailwind never generated, because Tailwind scans source text. -> Neither
was visible in a type-check, a lint or a test; both were obvious in one screenshot. Look at
the page.

[2026-09-23] - A first cut of the copy-discipline test forbade the word "lied" anywhere in
`en.ts`, and immediately failed on "It never says anyone lied" - the disclaimer that same
rule requires. -> A rule about what a product claims has to read the sentence, not the
phrase. The test now asserts these words only ever appear inside a sentence that denies
them, and the source list is exempt because a citation is a quotation and misquoting an
article title to satisfy our own copy rule would be worse than the word.

[2026-09-23] - A performance test asserting one claim was sublinear in the number of fixes
failed, and was measuring the wrong thing: the index was rebuilt on every call, so the
bisect saved nothing. -> A performance assertion that fails should be read as a question
about the design, not the bound. The index is now built once per request and shared by
every claim, which is what makes four claims cost less than four passes - and the test now
asserts that, which is the property that was actually wanted.

[2026-09-23] - The advocate map drew its pins and neither of its line layers, with a clean
type-check, a clean lint, a clean test run and no error in the console. Two separate
causes, both invisible except on screen. First, `app.css` defines the palette in `oklch`
and MapLibre parses style colours itself and understands none of it, so every layer was
added with a colour it rejected. Second, and the expensive one: the symbol layer that
labels each impossible edge had no `text-font`, MapLibre's default is `Open Sans Regular`,
and OpenFreeMap serves only Noto - so the glyph request 404'd, the worker errored the
whole *tile*, and a tile belongs to a source rather than to a layer. An unlabelled symbol
layer silently took down the two line layers that shared its source. -> A failure inside a
map worker is scoped to the source, not to the layer that caused it, so "one layer is
misconfigured" and "three layers render nothing" are the same symptom. The diagnosis came
from `map.style.sourceCaches[id]._tiles`, where every tile read `state: "errored"`; that
is the first thing to look at when a source with valid data draws nothing. Design tokens
now reach the map through `lib/map/color.ts`, which rasterises one pixel and reads the
sRGB bytes back rather than reimplementing OKLCH, so the map and the page can never
disagree about what a colour is.

[2026-09-23] - A test asserted the §11.4 simultaneity clause at exactly its threshold, by
placing a record 2.0 km from the origin, and failed: the polar-coordinate test helper
round-trips through the sphere and came back 1.2 nanometres short of 2 km. -> The helper
is right, the engine is right, and the test was asserting a float equality dressed up as a
threshold. A threshold test belongs clearly inside and clearly outside the boundary; at
the boundary it asserts the rounding behaviour of the test's own constructor.

[2026-09-23] - `published.json` grew a second block when advocate figures joined the
Methodology page, and the staleness test failed because it compared the whole file against
the engine scorer's output alone. The tempting fix was to exclude the new block. -> The
value of that test is that *everything* on that page is whatever the eval last said, so
the new block is compared against its own scorer instead. Only the two figures that
measure a machine rather than a decision - per-case latency and batch runtime - are
checked for shape rather than equality, and for the same stated reason.
