"""The City's licence register, and the rules that read it. Bible §5 L7."""

from __future__ import annotations

import json
from datetime import date

import pytest

from app.licences.registry import (
    CACHE_PATH,
    LicenceCategory,
    Standing,
    in_force_on,
    look_up,
    normalise,
    register_size,
)


class TestNormalise:
    """The register writes `0745503-DCA`; an affidavit writes `745503`. Both must meet."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("0745503-DCA", "745503"),
            ("745503", "745503"),
            ("0000745503", "745503"),
            ("  745503  ", "745503"),
            ("License No. 745503", "745503"),
        ],
    )
    def test_reduces_every_spelling_to_the_same_key(self, raw: str, expected: str) -> None:
        assert normalise(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "   ", "DCA", "-", "0", "000"])
    def test_returns_none_when_there_is_no_number_in_it(self, raw: str | None) -> None:
        # A field with no digits stays out of the lookup entirely rather than matching
        # something by accident.
        assert normalise(raw) is None


class TestTheCommittedCache:
    def test_holds_both_categories_and_is_not_empty(self) -> None:
        counts = register_size()
        assert counts[LicenceCategory.INDIVIDUAL.value] > 500
        assert counts[LicenceCategory.AGENCY.value] > 50

    def test_carries_no_name_and_no_address(self) -> None:
        """Bible §18.7. These are real people, and the check does not need who they are.

        Asserted against the file rather than against the builder, because the builder is
        a one-off run by hand and this is the artefact that actually ships.
        """
        rows = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        allowed = {"number", "category", "status", "issued", "expires"}
        seen: set[str] = set()
        for row in rows:
            seen |= set(row)
        assert seen == allowed, f"unexpected fields in the committed register: {seen - allowed}"


def _one_with_status(status: str) -> str | None:
    """A real licence number whose current status is `status`, or None if there is none.

    Looked up rather than hard-coded: the register is refreshed by hand, and a test that
    pinned a specific number would fail the day somebody's licence was renewed.
    """
    rows = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    for row in rows:
        if row["status"].strip().lower() == status and row["category"] == "individual":
            return str(row["number"])
    return None


class TestInForceOn:
    ANY_DAY = date(2025, 6, 12)

    def test_a_number_not_in_the_register_is_reported_as_unknown(self) -> None:
        assert in_force_on("9999999", LicenceCategory.INDIVIDUAL, self.ANY_DAY) is (
            Standing.UNKNOWN_NUMBER
        )

    def test_an_absent_number_produces_no_finding_rather_than_an_unknown_one(self) -> None:
        # An affidavit that states no licence number is not an affidavit stating a false
        # one, and the engine must not treat the two the same way.
        assert in_force_on(None, LicenceCategory.INDIVIDUAL, self.ANY_DAY) is Standing.NO_FINDING
        assert in_force_on("", LicenceCategory.INDIVIDUAL, self.ANY_DAY) is Standing.NO_FINDING

    def test_a_licence_is_expired_for_a_date_after_its_expiry(self) -> None:
        number = _one_with_status("expired")
        assert number is not None, "the register should contain expired licences"
        licence = look_up(number, LicenceCategory.INDIVIDUAL)
        assert licence is not None and licence.expires is not None
        after = date(licence.expires.year + 1, 1, 1)
        assert in_force_on(number, LicenceCategory.INDIVIDUAL, after) is Standing.EXPIRED

    def test_a_licence_is_not_yet_issued_for_a_date_before_it_was_granted(self) -> None:
        number = _one_with_status("active")
        assert number is not None
        licence = look_up(number, LicenceCategory.INDIVIDUAL)
        assert licence is not None and licence.issued is not None
        before = date(licence.issued.year - 1, 1, 1)
        assert in_force_on(number, LicenceCategory.INDIVIDUAL, before) is Standing.NOT_YET_ISSUED

    def test_a_live_licence_inside_its_dates_produces_no_finding(self) -> None:
        number = _one_with_status("active")
        assert number is not None
        licence = look_up(number, LicenceCategory.INDIVIDUAL)
        assert licence is not None and licence.issued is not None
        inside = date(licence.issued.year + 1, 1, 1)
        if licence.expires is not None and licence.expires < inside:
            pytest.skip("this licence's window is shorter than a year")
        assert in_force_on(number, LicenceCategory.INDIVIDUAL, inside) is Standing.NO_FINDING

    def test_the_two_categories_are_separate_registers(self) -> None:
        """An agency number is not a server number, and the engine must not accept one
        for the other — that is the whole reason the key carries a category."""
        rows = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        agency = next(r["number"] for r in rows if r["category"] == "agency")
        assert look_up(agency, LicenceCategory.AGENCY) is not None
        assert look_up(agency, LicenceCategory.INDIVIDUAL) is None
