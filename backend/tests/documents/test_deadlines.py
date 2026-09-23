"""CPLR 317 arithmetic. Bible §5 L6, and nothing else."""

from __future__ import annotations

from datetime import date

import pytest

from app.documents.deadlines import add_years, compute_deadlines, effective_deadline

KNEW = date(2026, 3, 14)
ENTERED = date(2024, 11, 2)


def test_one_year_from_learning_of_the_judgment() -> None:
    assert compute_deadlines(KNEW, None).cplr_317_deadline == date(2027, 3, 14)


def test_five_years_from_entry() -> None:
    assert compute_deadlines(None, ENTERED).cplr_317_outer_limit == date(2029, 11, 2)


def test_the_earlier_of_the_two_is_the_one_that_governs() -> None:
    """A judgment entered long ago can run out before the year from learning of it does."""
    deadlines = compute_deadlines(date(2026, 3, 14), date(2022, 1, 10))
    assert effective_deadline(deadlines) == date(2027, 1, 10)


def test_the_year_governs_when_the_judgment_is_recent() -> None:
    deadlines = compute_deadlines(date(2026, 3, 14), date(2025, 6, 1))
    assert effective_deadline(deadlines) == date(2027, 3, 14)


def test_both_dates_are_echoed_back() -> None:
    deadlines = compute_deadlines(KNEW, ENTERED)
    assert (deadlines.knowledge_date, deadlines.judgment_entry_date) == (KNEW, ENTERED)


# --- Missing input -------------------------------------------------------------------------


def test_no_dates_means_no_deadline_and_a_note_that_says_why() -> None:
    deadlines = compute_deadlines(None, None)
    assert deadlines.cplr_317_deadline is None
    assert deadlines.cplr_317_outer_limit is None
    assert effective_deadline(deadlines) is None
    assert "when you first found out" in deadlines.note


def test_one_date_still_produces_the_limit_it_can() -> None:
    assert effective_deadline(compute_deadlines(KNEW, None)) == date(2027, 3, 14)


# --- Leap days -----------------------------------------------------------------------------


def test_a_leap_day_lands_on_the_28th_rather_than_raising() -> None:
    """`date.replace(year=...)` throws on 29 February. A deadline calculator that fails
    once every four years is worse than one that is a day conservative."""
    assert add_years(date(2024, 2, 29), 1) == date(2025, 2, 28)


def test_a_leap_day_five_years_on_is_still_a_leap_day() -> None:
    assert add_years(date(2024, 2, 29), 4) == date(2028, 2, 29)


@pytest.mark.parametrize("years", [1, 5])
def test_ordinary_dates_keep_their_day(years: int) -> None:
    assert add_years(date(2025, 7, 31), years).day == 31


# --- The note ------------------------------------------------------------------------------


def test_the_note_states_both_limits_and_which_one_wins() -> None:
    note = compute_deadlines(KNEW, ENTERED).note
    assert "March 14, 2027" in note
    assert "November 2, 2029" in note
    assert "earlier of the two" in note


def test_the_note_carries_the_conditions_the_statute_attaches() -> None:
    """L6: other than personal delivery, no notice in time to defend, a meritorious
    defence. A date on its own would read like an entitlement."""
    note = compute_deadlines(KNEW, ENTERED).note
    assert "other than in person" in note
    assert "defence worth hearing" in note


def test_the_note_also_carries_the_other_ground() -> None:
    """L5: improper service is a jurisdiction problem, with no stated one-year limit."""
    assert "did not have jurisdiction" in compute_deadlines(KNEW, ENTERED).note


def test_the_note_never_counts_down() -> None:
    """A packet downloaded today may be read next month, and "43 days left" printed on a
    PDF ages into a lie."""
    note = compute_deadlines(KNEW, ENTERED).note
    assert "days left" not in note and "today" not in note
