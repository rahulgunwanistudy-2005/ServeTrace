"""CPLR 317 deadline arithmetic. Encodes bible §5 L6 only.

Two dates, two limits, and the earlier one governs:

- one year after the person learned of the judgment;
- five years after the judgment was entered.

Nothing here decides whether CPLR 317 is available at all — that also needs service to
have been by some means other than personal delivery, and a defence worth hearing (L6).
Those are facts about the case, not arithmetic, so they belong in the note and in the
draft affidavit's conditional paragraph, never in a computed date.

There is deliberately no countdown. A packet downloaded today may be read next month, and
"you have 43 days left" printed on a PDF ages into a lie.
"""

from __future__ import annotations

from calendar import isleap
from datetime import date

from app.domain.models import Deadlines
from app.engine import copy

KNOWLEDGE_YEARS = 1
"""L6: one year after learning of the judgment."""

ENTRY_YEARS = 5
"""L6: and no more than five years after entry."""


def add_years(start: date, years: int) -> date:
    """The same calendar date `years` later, with 29 February landing on the 28th.

    `date.replace(year=...)` raises on a leap day, and a deadline calculator that throws
    once every four years is worse than one that is a day conservative.
    """
    if start.month == 2 and start.day == 29 and not isleap(start.year + years):
        return date(start.year + years, 2, 28)
    return start.replace(year=start.year + years)


def compute_deadlines(knowledge_date: date | None, judgment_entry_date: date | None) -> Deadlines:
    knowledge_deadline = add_years(knowledge_date, KNOWLEDGE_YEARS) if knowledge_date else None
    outer_limit = add_years(judgment_entry_date, ENTRY_YEARS) if judgment_entry_date else None
    return Deadlines(
        knowledge_date=knowledge_date,
        judgment_entry_date=judgment_entry_date,
        cplr_317_deadline=knowledge_deadline,
        cplr_317_outer_limit=outer_limit,
        note=copy.deadline_note(knowledge_deadline, outer_limit),
    )


def effective_deadline(deadlines: Deadlines) -> date | None:
    """Whichever of the two limits falls first. None when neither date was given."""
    candidates = [
        d for d in (deadlines.cplr_317_deadline, deadlines.cplr_317_outer_limit) if d is not None
    ]
    return min(candidates) if candidates else None
