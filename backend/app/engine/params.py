"""Every threshold the engine uses, in one versioned frozen object. Bible §11.

Thresholds are deliberately generous towards the affidavit: a wide match radius and a
high "impossible" speed mean the engine contradicts a sworn claim only when the user's
own data leaves no room for doubt. Changing any value here changes the meaning of every
published verdict, so `PARAMS_VERSION` must be bumped with it and it is stamped onto
every `CaseAnalysis` and every generated document.
"""

from dataclasses import dataclass
from typing import Final

PARAMS_VERSION: Final = "2026.09-v1"


@dataclass(frozen=True, slots=True)
class EngineParams:
    match_radius_km: float = 0.30
    """A fix this close to the claimed point counts as being there. Fix accuracy is added."""

    visit_tolerance_min: int = 10
    """A visit covers T when t - tolerance <= T <= t_end + tolerance."""

    search_window_h: int = 3
    """Only fixes within this many hours of a claim are considered, or sent to the server."""

    v_strong_kmh: float = 80.0
    """Door-to-door NYC travel above this is treated as impossible."""

    v_moderate_kmh: float = 40.0

    consistent_window_min: int = 15
    """A fix inside the match radius this close to the claimed time makes it CONSISTENT.

    Bible §11.1.3. Separate from `visit_tolerance_min`: that one extends an interval the
    export already asserts, this one is how much slack a single instantaneous point gets.
    """

    desc_age_tolerance_y: int = 5
    """Bible §11.2. A described age range is widened by this much at both ends before it is
    called a mismatch, because a stranger's estimate of an age is exactly that."""

    desc_height_tolerance_in: int = 2

    adv_simultaneous_min: float = 5.0
    adv_simultaneous_km: float = 2.0
    adv_max_per_hour: int = 12

    tz: str = "America/New_York"


PARAMS: Final = EngineParams()
