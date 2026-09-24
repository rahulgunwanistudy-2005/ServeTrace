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

[2026-09-23] - Session 1 recorded that "WeasyPrint stamps a creation date, so PDF bytes
differ run to run", and S6 asked for deterministic documents, so the plan was going to be
a fixed-timestamp parameter threaded through both renderers. WeasyPrint 70 writes no
`/CreationDate` at all unless the HTML asks for one, which took one command to find out.
-> A constraint inherited from an earlier session is a claim, not a fact. Check it before
designing around it; this one was going to cost an argument in two function signatures
and buy nothing.

[2026-09-23] - A copy-discipline test asserting that no court document ever says anybody
lied failed on "the distances and times relied on above", and the companion check for a
lower-case meridiem failed on "I am Maria Delarmo". Both were the same mistake as the one
already in this file about the word "lied" in `en.ts`, made again on the first draft. ->
When a rule is about a *word*, match a word. `\blied\b` and `\d\s*[ap]m\b`. The engine's
version of the second check could search for " am " because findings are written in the
second person and never say "I am"; a first-person document is exactly where that
shortcut breaks, so a check copied between modules needs its assumption re-read, not just
its threshold.

[2026-09-23] - The draft affidavit rendered as three pages: the last one carried a single
grey "prepared by" line and nothing else, because the notary block above it has
`break-inside: avoid` and left no room. Separately, the two numeric column headers in the
packet sat over the left edge of their columns while the numbers under them were right
aligned, because `table.data th` outranks a bare `.num`. Clean lint, clean types, 619
passing tests, and both obvious in the first rendered page. -> Print layout is the same
class of problem as the MapLibre bug in session 5: the failure is real, the tooling is
silent, and the diagnosis costs one screenshot. Render every page of anything that goes
on paper and look at it. The fix for the orphan is worth keeping too - content that
belongs to the page rather than to the text belongs in the page margin, where it cannot
be orphaned by whatever the layout does above it.

[2026-09-23] - A first cut hand-wrote a WeasyPrint `url_fetcher` function that served one
stylesheet and raised on everything else. WeasyPrint 70 calls `url_fetcher._fail_on_errors`
on the failure path and expects a `URLFetcherResponse`, so the function worked until an
image was actually embedded and then crashed inside the renderer - caught by the one test
that put a real PNG through the whole route. The library already has the mechanism:
`URLFetcher(allowed_protocols={"data"}, fail_on_errors=True)`. -> Before writing a
security boundary against a library, look for the one it ships. A hand-rolled version has
to be kept in step with how that library actually resolves things, and the day it falls
out of step is the day it stops enforcing anything.

[2026-09-23] - The draft affidavit for a CONSISTENT case was, on the first pass, a
complete document: it introduced the person's location history, annexed it as Exhibit B,
and pointed the court at records that place them at the sworn address at the sworn time.
Every test passed, because every test was about whether paragraphs were built correctly.
-> Bible §6 says report a consistent result honestly, and the result page does. It does
not follow that a document meant to be *filed* should carry the same material: honest to
the user and useful against them are different things, and the question to ask of every
generated paragraph is not "is this true" but "does this person want a judge reading it".

[2026-09-23] - Session 6 made contrast "a property of the layout rather than of wherever
the gradient happened to land", by bottom-aligning copy into the flat part of a static
scrim. Session 8 made the field underneath move and did not re-examine that sentence. The
12px eyebrow on the landing hero measured 5.29:1 on the frame it was first checked on and
3.88:1 fourteen seconds later, under a specular peak that had clipped to white - a real AA
failure that a screenshot, a type-check, a lint and 283 passing tests all agreed was fine.
-> When a decoration starts animating, every guarantee that was measured against it has to
be re-measured *across time*, not on a frame. And the fix belongs at the cause: the peaks
were clipping, so the shader now rolls its top end off to a ceiling. Dimming the whole
field would have cost the effect to buy the same number; bounding the brightest pixel it
can ever emit is what turns "this frame passes" back into "every frame passes".

[2026-09-23] - A GLSL comment inside the fragment shader said `fract` with backticks, and
the shader is a JavaScript template literal, so the string ended there and the module
stopped parsing. Loud, and fixed in a minute. Its sibling is not loud: `${` inside the
same string interpolates silently and compiles a shader nobody wrote. -> A template
literal holding another language is a quoting boundary, and the test file now asserts the
quiet half of it. The loud half needs no test - running `vitest` at all would have caught
it, and the reason it did not was that the shader was edited after the tests were run.

[2026-09-23] - The iridescent canvas mounted, sized itself, compiled its shader, and
stayed at opacity 0 in the browser pane. The cause was the component working exactly as
designed: the pane reports `document.visibilityState === "hidden"` and suspends
`requestAnimationFrame` outright, which is the condition the renderer pauses on. The
symptom - a canvas that never draws - is indistinguishable from a renderer that is broken.
-> Before debugging an animation that will not start, check whether the environment is
running the clock. Overriding the `visibilityState` getter and backing `rAF` with
`setTimeout` before the component mounts exercises the real component end to end, which is
worth more than reading the code and declaring it correct.

[2026-09-23] - The iridescent field was reported as working on the strength of a boolean:
pixels read from the drawing buffer differed between two samples, so the loop was running,
so it was animating. Rahul looked at it and saw a still image. Read back, the evidence had
said so too - 53,54,53 to 49,51,50 over a second and a half - and that number was quoted
in the report without anyone asking whether it was a lot. It was about a twelfth of what
the reference does. -> "Is it moving" is the wrong question when the answer wanted is "does
it look like that". Frames sampled out of the reference recording at 8fps differ from their
neighbours by 7.6 grey levels of 255, and by 36 over a second; the same measurement now
runs against the shader, normalised per frame so it compares pattern change rather than
brightness, and the drift rates are whatever makes the two agree. A reference video is not
only a picture of the target, it is a measurement of it.

[2026-09-23] - Comparing the shader to the reference by mean absolute pixel difference
said it was five times too slow. Normalising each frame to zero mean and unit variance
first said three times. The first number was measuring darkness as much as stillness: a
darker field has smaller absolute differences at identical motion. -> Before tuning
against a metric, check the metric is not reading a second property. The fix was two lines
and it changed the answer by 40%.

[2026-09-24] - The engine got the City's real licence register, and every demo case
immediately grew two findings saying the licence number was not in it. They were: the
generator invents a seven-digit number. The findings were true of the fixture and false of
the scenario, and the worst of them landed on the consistent case, whose entire purpose is
to report honestly that the data supports the affidavit. -> The moment a product starts
checking a field against reality, every fixture that fills that field with plausible noise
becomes a fixture that lies. The fix is not to give the fixture real data, which here would
tie a real licensee to an invented accusation, and not to special-case the rule for demo
data, which puts a fixture's convenience into production code. It is for the fixture to
stop asserting what it cannot back: the generator now leaves the licence numbers absent.

[2026-09-24] - Deleting the two `rng.randint` calls that produced those licence numbers
re-rolled every value drawn after them, because the generator is a pure function of its
seed. A two-field change arrived as an 800-line diff across every committed fixture, with
the real change buried in coordinate noise. -> In a seeded generator, removing a draw is a
change to every later draw. Keep the call and throw the result away, in the same position,
with a comment saying why. The diff is the point: a reviewer who cannot see what changed
cannot check it.

[2026-09-24] - A first cut asserted `licence.expires.isoformat() in found[0].detail` and
failed, because `detail` reads "it expired on April 3, 2023" - the product's own date
format, for a person to read. The same mistake is already in this file from session 4, and
the rule it produced was written down: tests assert on the code, never on the sentence.
-> The finding carries the ISO date in `numbers`, which exists for exactly this. Re-read
the lesson before writing the assertion, not after the failure.

[2026-09-24] - A `DEMO` pill sat directly beside a sentence reading "The people and cases
are invented", and the pill was defended on the grounds that bible §16 requires a chip.
§16 requires the screen to disclose; the chip was how one session chose to do it. -> Read a
rule for what it protects before defending its wording. The sentence was the disclosure and
the badge was decoration on top of it, so removing the badge cost nothing and removing the
sentence would have cost everything. The same reading is what said no to deleting the
label outright an hour earlier - it is one test, not two positions.

[2026-09-24] - `new Date('2025-06-12T19:42').toISOString()` reads a wall clock in the
*browser's* zone. The wizard built the claimed moment that way, and on a machine set to IST
a service typed as 19:42 reached the engine as 10:12 AM - nine and a half hours of error in
the single number every verdict turns on, producing a confident wrong answer for any user
outside New York. It was caught only because the result page printed the time back and it
did not match what had been typed. -> A wall clock without a zone is not a time. Session 3
had already built `nyLocalToInstant` for exactly this, handling both DST edges, and the
wizard reimplemented the problem instead of importing the answer. Before writing a date
conversion, look for the one this repo already made.

[2026-09-24] - The result map filtered its points by distance from a fix's *start* time, so
a recorded stay from 8:00 AM to 8:00 PM measured as eleven hours from a 7:42 PM claim and
was dropped from a ±90 minute window. The scrubber read "0 of 1" on the demo case built
specifically to be contradicted by that stay. -> A VISIT is an interval and the engine's
own visit test turns on whether it *covers* the claimed moment (bible §11.1.2). Any second
implementation of "is this fix near that time" has to answer it the same way the engine
does, or the picture disagrees with the verdict printed above it.

[2026-09-24] - A `map.on('error', () => onCapture(null))` handler was added so a half-drawn
basemap could not reach an evidence packet. MapLibre fires `error` for every survivable
thing - a tile that did not arrive, a glyph range that 404'd - so in practice it overwrote
every good capture and every packet printed its text alternative. The bug looked like the
capture failing. -> A defensive handler that fires on a broad event is not defensive, it is
a race with the success path. The fix was to stop pushing a captured frame and let the
caller pull one when it needs it, which removed the timing question entirely and also fixed
a second bug nobody had noticed: the pushed frame predated anything the user did with the
scrubber.
