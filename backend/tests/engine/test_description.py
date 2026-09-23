"""Bible §11.2. The check that must never produce a finding out of two blank fields."""

from __future__ import annotations

import pytest

from app.domain.models import PersonDescription, ServiceMethod, Severity
from app.engine.description import check_description
from app.engine.params import PARAMS
from tests.engine.conftest import affidavit, member


def described(**fields: object) -> PersonDescription:
    return PersonDescription.model_validate(fields)


def check(method: ServiceMethod, description: PersonDescription | None, household: list):
    return check_description(
        affidavit(method=method, recipient_description=description), household, PARAMS
    )


DEFENDANT = member("The defendant", sex="female", age=34, height_in=63, is_defendant=True)


# --- 308(1): the description is of the defendant -----------------------------------------


def test_personal_service_compares_against_the_defendant_alone() -> None:
    """A housemate who happens to fit is not who the affidavit says was handed the papers."""
    fits = member("Housemate", sex="male", age=60, height_in=73)
    findings = check(
        ServiceMethod.PERSONAL,
        described(sex="male", age_min=56, age_max=66, height_in_min=71, height_in_max=75),
        [DEFENDANT, fits],
    )
    assert [f.code for f in findings] == ["F-DESC"]
    assert findings[0].legal_ref == "L1"
    assert findings[0].severity is Severity.MODERATE


def test_a_description_that_fits_the_defendant_produces_nothing() -> None:
    assert (
        check(ServiceMethod.PERSONAL, described(sex="female", age_min=30, age_max=38), [DEFENDANT])
        == []
    )


# --- 308(2): anyone at the address will do -----------------------------------------------


def test_substituted_service_compares_against_everyone() -> None:
    partner = member("Partner", sex="male", age=39, height_in=71)
    assert (
        check(
            ServiceMethod.SUBSTITUTE,
            described(sex="male", age_min=36, age_max=44, height_in_min=69, height_in_max=73),
            [DEFENDANT, partner],
        )
        == []
    )


def test_nobody_matching_is_a_finding_against_the_whole_household() -> None:
    child = member("Daughter", sex="female", age=9, height_in=52)
    findings = check(
        ServiceMethod.SUBSTITUTE,
        described(sex="male", age_min=56, age_max=66, height_in_min=71, height_in_max=75),
        [DEFENDANT, child],
    )
    assert [f.code for f in findings] == ["F-DESC"]
    assert findings[0].legal_ref == "L2"
    assert findings[0].numbers["household_size"] == 2


# --- Tolerances ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("age", "expected_finding"),
    [(34, False), (25, False), (24, True), (48, False), (49, True)],
)
def test_the_age_range_is_widened_before_anyone_is_ruled_out(
    age: int, expected_finding: bool
) -> None:
    """Described 30-43, so tolerance makes the accepted range 25-48. Bible §11.2."""
    who = member("Someone", age=age)
    findings = check(ServiceMethod.SUBSTITUTE, described(age_min=30, age_max=43), [who])
    assert bool(findings) is expected_finding


@pytest.mark.parametrize(
    ("height_in", "expected_finding"),
    [(69, False), (67, False), (66, True), (75, False), (76, True)],
)
def test_the_height_range_is_widened_too(height_in: int, expected_finding: bool) -> None:
    """Described 5'9"-6'1", accepted 5'7"-6'3"."""
    who = member("Someone", height_in=height_in)
    findings = check(ServiceMethod.SUBSTITUTE, described(height_in_min=69, height_in_max=73), [who])
    assert bool(findings) is expected_finding


# --- What is never counted as a mismatch --------------------------------------------------


def test_a_missing_field_on_either_side_is_ignored() -> None:
    """Two blanks are not a disagreement."""
    who = member("Someone", sex=None, age=None, height_in=None)
    assert check(ServiceMethod.SUBSTITUTE, described(sex="male", age_min=60), [who]) == []


def test_an_unknown_described_sex_states_nothing() -> None:
    who = member("Someone", sex="female", age=34)
    assert (
        check(ServiceMethod.SUBSTITUTE, described(sex="unknown", age_min=30, age_max=40), [who])
        == []
    )


def test_a_household_member_recorded_as_other_is_not_ruled_out_by_sex() -> None:
    """The roster offers three options and the affidavit form offers two. That mismatch is
    the form's, and it must not cost the user a finding they cannot answer."""
    who = member("Someone", sex="other", age=34)
    assert (
        check(ServiceMethod.SUBSTITUTE, described(sex="male", age_min=30, age_max=40), [who]) == []
    )


def test_weight_and_hair_are_never_compared() -> None:
    who = member("Someone", sex="female", age=34, height_in=63)
    assert (
        check(
            ServiceMethod.SUBSTITUTE,
            described(sex="female", age_min=30, age_max=40, weight_lb_min=300, hair="Green"),
            [who],
        )
        == []
    )


# --- When the check does not run ----------------------------------------------------------


def test_no_description_means_no_check() -> None:
    assert check(ServiceMethod.SUBSTITUTE, None, [DEFENDANT]) == []


def test_an_empty_roster_means_no_check() -> None:
    """The roster is optional (bible §14 step 3). Skipping it must cost nothing."""
    assert check(ServiceMethod.SUBSTITUTE, described(sex="male", age_min=60), []) == []


def test_a_description_with_nothing_comparable_in_it_means_no_check() -> None:
    assert (
        check(
            ServiceMethod.SUBSTITUTE, described(hair="Brown", raw_text="Hair: Brown"), [DEFENDANT]
        )
        == []
    )


@pytest.mark.parametrize("method", [ServiceMethod.AFFIX_AND_MAIL, ServiceMethod.UNKNOWN])
def test_no_recipient_means_nobody_to_compare(method: ServiceMethod) -> None:
    """Papers taped to a door were not handed to anyone, so a mismatch would mean nothing."""
    assert (
        check(
            method,
            described(sex="male", age_min=74, age_max=84, height_in_min=74, height_in_max=78),
            [DEFENDANT],
        )
        == []
    )


def test_personal_service_with_no_defendant_on_the_roster_stays_quiet() -> None:
    assert (
        check(ServiceMethod.PERSONAL, described(sex="male", age_min=60), [member("Partner")]) == []
    )
