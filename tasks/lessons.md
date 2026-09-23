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
