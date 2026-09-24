"""The City's register of licensed process servers. Bible §5 L7.

NYC licenses process servers individually and licenses the agencies that employ them
(NYC Admin Code § 20-403 et seq.; DCWP publishes the register as open data). An affidavit
of service states the server's licence number, so the number on the paper can be checked
against the register.

This is the one place in the product that uses real data about real people, and it is
deliberately the thinnest slice that answers the question. The published register also
carries each licensee's **name** and **home ZIP** — mostly residential addresses — and
neither is here. Matching a name would make a stronger finding and would mean committing
899 real people's names to this repo and accusing one of them of a mismatch, which bible
§18.7 forbids and which the product has no business doing. A number, a category, a status
and two dates answer "is this licence real and was it in force", and nothing more is taken.

`cache.json` is committed and never written at runtime, exactly as `geo/cache.json` is, so
the analysis path makes no network call and bible §16's demo-with-the-network-off holds.
Rebuild it with `fixtures/generator/build_licences.py`.

**What this data can and cannot say.** The register is a snapshot of *now*, not a history:
`status` is today's status and `expires` today's expiry. So it can never establish what a
licence's standing was on some past date. `in_force_on` is therefore deliberately
one-sided — it can find that a licence had already expired or had not yet been issued when
service was sworn, and it can never report that a licence *was* valid then.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Final

CACHE_PATH: Final = Path(__file__).resolve().parent / "cache.json"


class LicenceCategory(StrEnum):
    INDIVIDUAL = "individual"
    AGENCY = "agency"


class Standing(StrEnum):
    """Where a licence number stands against the register. Never a legal conclusion."""

    UNKNOWN_NUMBER = "unknown_number"
    """No such number in the register, in this category."""
    NOT_YET_ISSUED = "not_yet_issued"
    """First issued after the date asked about."""
    EXPIRED = "expired"
    """Expiry date falls before the date asked about, and it has not been renewed since."""
    REVOKED = "revoked"
    """Revoked or suspended as of the register's snapshot. Says nothing about a past date."""
    NO_FINDING = "no_finding"
    """Nothing the register can object to. Emphatically not a statement that it was valid."""


REVOKED_STATUSES: Final = frozenset({"revoked", "suspended"})


@dataclass(frozen=True, slots=True)
class Licence:
    number: str
    category: LicenceCategory
    status: str
    issued: date | None
    expires: date | None


def normalise(number: str | None) -> str | None:
    """A licence number as the register keys it: bare digits, no leading zeros.

    The register writes `0745503-DCA`; an affidavit writes `745503` or `0745503`. Reducing
    both to digits is what lets the two meet. Returns None for anything with no digits in
    it at all, which is how an empty or junk field stays out of the lookup.
    """
    if number is None:
        return None
    digits = "".join(ch for ch in number if ch.isdigit()).lstrip("0")
    return digits or None


@lru_cache(maxsize=1)
def _register() -> dict[tuple[LicenceCategory, str], Licence]:
    if not CACHE_PATH.exists():  # pragma: no cover - the cache is committed
        return {}
    rows = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    out: dict[tuple[LicenceCategory, str], Licence] = {}
    for row in rows:
        number = normalise(row["number"])
        if number is None:
            continue
        category = LicenceCategory(row["category"])
        out[(category, number)] = Licence(
            number=number,
            category=category,
            status=row["status"],
            issued=date.fromisoformat(row["issued"]) if row.get("issued") else None,
            expires=date.fromisoformat(row["expires"]) if row.get("expires") else None,
        )
    return out


def look_up(number: str | None, category: LicenceCategory) -> Licence | None:
    key = normalise(number)
    if key is None:
        return None
    return _register().get((category, key))


def in_force_on(number: str | None, category: LicenceCategory, when: date) -> Standing:
    """Where the number stands against the register, for service sworn on `when`.

    One-sided by design, for the reason in the module docstring: every value other than
    `NO_FINDING` is something the register positively shows, and `NO_FINDING` means only
    that it shows nothing to object to.
    """
    if normalise(number) is None:
        return Standing.NO_FINDING

    licence = look_up(number, category)
    if licence is None:
        return Standing.UNKNOWN_NUMBER
    if licence.issued is not None and licence.issued > when:
        return Standing.NOT_YET_ISSUED
    if licence.expires is not None and licence.expires < when:
        return Standing.EXPIRED
    if licence.status.strip().lower() in REVOKED_STATUSES:
        return Standing.REVOKED
    return Standing.NO_FINDING


def register_size() -> dict[str, int]:
    """Counts, for the methodology page. Cheap enough to call per request."""
    counts = {category.value: 0 for category in LicenceCategory}
    for (category, _), _licence in _register().items():
        counts[category.value] += 1
    return counts
