"""Impossible travel, throughput and repeated descriptions across a server's filings.

Bible §11.4. This is the same physics as `engine/feasibility.py` pointed at a different
question. The defendant flow asks whether one person's phone can be reconciled with one
sworn claim. Advocate mode asks whether a *server's own filings* can be reconciled with
each other, which needs no location history from anybody: two sworn services eleven
kilometres apart three minutes apart are in conflict whatever either defendant was doing.

That difference matters for how strongly this may be read, and the copy says so. A
contradicted service is a dispute between two accounts. Six sequences nobody could have
driven, in one server's own filings, is a pattern in a single account — which is the thing
bible §5 L7 says DCWP takes complaints about, and the reason the report exports.

Everything here is deterministic and depends only on the records and `EngineParams`.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque
from datetime import timedelta
from itertools import pairwise
from typing import Final

from app.domain.models import ImpossiblePair, ServerReport, ServiceRecord
from app.engine.feasibility import MIN_ELAPSED_S
from app.engine.params import EngineParams
from app.geo.distance import haversine_km

COMPLETED_OUTCOMES: Final = frozenset({"served", "affixed"})
"""Bible §11.4 counts *completed* services per hour, not doors knocked on.

A `not_home` is the opposite of a completed service: it is the evidence of diligence that
308(4) asks for. Counting attempts would give the server who documents six fruitless
visits a worse throughput number than the one who claims six services, which inverts what
the check is for."""

_PUNCTUATION: Final = re.compile(r"[^A-Z0-9]+")


def normalize_description(text: str) -> str:
    """The key two descriptions are the same under.

    Case, spacing and punctuation vary with whoever typed the row and with which system
    exported it; `M/W/BRN/45` and `m w brn 45` are one description. Deliberately the same
    normalisation `geo/geocode.py` uses for an address, because a half-remembered second
    convention is how two modules come to disagree about whether two strings match.
    """
    return _PUNCTUATION.sub(" ", text.upper()).strip()


def _place_key(record: ServiceRecord) -> str:
    """What counts as a different door.

    The address when there is one, and otherwise the coordinate to about a metre. A file
    of bare lat/lng still has to be able to say "the same description at eight places".
    """
    if record.address and record.address.strip():
        return normalize_description(record.address)
    return f"{record.loc.lat:.5f},{record.loc.lng:.5f}"


def _required_speed_kmh(distance_km: float, elapsed_s: float) -> float:
    """km/h implied by a step between two filings.

    The floor on elapsed time is `engine/feasibility.py`'s and is imported rather than
    re-declared: the two halves of the product must price the same journey identically, or
    an advocate and a defendant looking at the same two points get different numbers.
    """
    return distance_km / (max(abs(elapsed_s), MIN_ELAPSED_S) / 3600.0)


def impossible_pairs(ordered: list[ServiceRecord], params: EngineParams) -> list[ImpossiblePair]:
    """Consecutive filings the server could not have travelled between.

    Bible §11.4: flagged when the implied speed exceeds the same `V_STRONG` the defendant
    engine calls impossible, or when two filings are effectively simultaneous and far
    apart. The second clause exists because a short enough gap stops being a journey to
    price: at thirty seconds apart, the speed is an artefact of how the times were rounded,
    and what is actually being said is that the server was in two places at once.
    """
    pairs: list[ImpossiblePair] = []
    for earlier, later in pairwise(ordered):
        elapsed_s = (later.at - earlier.at).total_seconds()
        minutes = elapsed_s / 60.0
        distance_km = haversine_km(earlier.loc, later.loc)
        speed_kmh = _required_speed_kmh(distance_km, elapsed_s)

        too_fast = speed_kmh > params.v_strong_kmh
        at_once = (
            minutes <= params.adv_simultaneous_min and distance_km >= params.adv_simultaneous_km
        )
        if not (too_fast or at_once):
            continue

        pairs.append(
            ImpossiblePair(
                a=earlier,
                b=later,
                distance_km=round(distance_km, 3),
                minutes=round(minutes, 1),
                required_speed_kmh=round(speed_kmh, 1),
            )
        )
    return pairs


def max_services_per_hour(ordered: list[ServiceRecord]) -> int:
    """The most completed services in any rolling sixty minutes.

    The window is half-open — it holds what happened in the *last* sixty minutes, so two
    services exactly an hour apart are not in it together. Flagging needs the count to go
    above a threshold, so the half-open reading is the one that flags less.

    One pass over the sorted records with a deque; each record is appended and popped at
    most once, so the whole thing is O(n) after the sort.
    """
    window: deque[ServiceRecord] = deque()
    best = 0
    for record in ordered:
        if record.outcome not in COMPLETED_OUTCOMES:
            continue
        window.append(record)
        cutoff = record.at - timedelta(hours=1)
        while window and window[0].at <= cutoff:
            window.popleft()
        best = max(best, len(window))
    return best


def repeated_descriptions(
    ordered: list[ServiceRecord], params: EngineParams
) -> list[tuple[str, int]]:
    """Descriptions of the person who took the papers, reused at several different doors.

    Returned with the description as it was first written rather than as it was normalised,
    because an advocate reads this list and `M/MED/BRN/45/68/180` is legible where
    `M MED BRN 45 68 180` is not. The count is the number of *distinct* addresses, not the
    number of rows: the same description twice at one address is a household, not a
    pattern.
    """
    places: defaultdict[str, set[str]] = defaultdict(set)
    first_seen: dict[str, str] = {}
    for record in ordered:
        raw = (record.recipient_desc or "").strip()
        if not raw:
            continue
        key = normalize_description(raw)
        if not key:
            continue
        first_seen.setdefault(key, raw)
        places[key].add(_place_key(record))

    found = [
        (first_seen[key], len(addresses))
        for key, addresses in places.items()
        if len(addresses) >= params.adv_repeated_desc_min_addresses
    ]
    # Most-reused first, then alphabetically, so the report is stable run to run.
    found.sort(key=lambda item: (-item[1], item[0]))
    return found


def _risk_key(report: ServerReport) -> tuple[int, int, int, str]:
    """Bible §11.4: impossible pairs, then repeated descriptions, then throughput.

    `server_id` breaks the remaining ties so that two servers with identical findings keep
    a stable order, which a snapshot test and a printed report both need.
    """
    return (
        -len(report.impossible_pairs),
        -len(report.repeated_descriptions),
        -report.max_services_per_hour,
        report.server_id,
    )


def analyze_servers(records: list[ServiceRecord], params: EngineParams) -> list[ServerReport]:
    """Group by server, sort by time, and run bible §11.4 over each.

    O(n log n) per server and O(n) memory. Returned in risk order, which is the order an
    advocate wants to read them in, with `risk_rank` starting at 1.
    """
    by_server: defaultdict[str, list[ServiceRecord]] = defaultdict(list)
    for record in records:
        by_server[record.server_id].append(record)

    reports: list[ServerReport] = []
    for server_id, rows in by_server.items():
        # Address is the tiebreak so that two filings at the same instant keep a stable
        # order, and with it a stable set of consecutive pairs.
        ordered = sorted(rows, key=lambda r: (r.at, r.address or "", r.case_ref or ""))
        reports.append(
            ServerReport(
                server_id=server_id,
                n_records=len(ordered),
                impossible_pairs=impossible_pairs(ordered, params),
                max_services_per_hour=max_services_per_hour(ordered),
                repeated_descriptions=repeated_descriptions(ordered, params),
                risk_rank=0,
            )
        )

    reports.sort(key=_risk_key)
    return [report.model_copy(update={"risk_rank": rank}) for rank, report in enumerate(reports, 1)]
