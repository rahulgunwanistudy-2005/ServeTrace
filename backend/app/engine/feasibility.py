"""Space-time feasibility for one claim. Bible §11.1. Session 3."""

from datetime import datetime

from app.domain.models import ClaimVerdict, Finding, LatLng, LocationFix
from app.engine.params import EngineParams


def evaluate_claim(
    claim_ref: str,
    claimed_at: datetime,
    claimed_location: LatLng,
    fixes: list[LocationFix],
    params: EngineParams,
) -> tuple[ClaimVerdict, list[Finding]]:
    """Visit test, then Hagerstrand prism test, then the no-data fallback."""
    raise NotImplementedError("Session 3")
