"""F-DESC: does anyone in the household match the described recipient? Bible §11.2. Session 3."""

from app.domain.models import Affidavit, Finding, HouseholdMember


def check_description(affidavit: Affidavit, household: list[HouseholdMember]) -> list[Finding]:
    """Missing fields are ignored, never counted as a mismatch. Photos are never used."""
    raise NotImplementedError("Session 3")
