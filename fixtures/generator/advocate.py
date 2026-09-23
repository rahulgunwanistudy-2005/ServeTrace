"""Advocate-mode fixtures: many service records from several process servers.

Two of the five servers have impossible sequences deliberately injected, and the injected
pairs are written out as an answer key so the batch engine can be scored rather than
eyeballed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.domain.models import LatLng, ServiceRecord
from app.geo.distance import haversine_km

from .addresses import Address, boroughs, by_borough
from .affidavit import HAIR, SKIN
from .people import TZ

N_SERVERS = 5
RECORDS_PER_SERVER = 400
BAD_SERVER_INDEXES = (1, 3)
IMPOSSIBLE_PAIRS_PER_BAD_SERVER = 6
REPEATED_DESCRIPTION_ADDRESSES = 8


@dataclass(frozen=True, slots=True)
class InjectedPair:
    index_a: int
    index_b: int
    distance_km: float
    minutes: float
    required_speed_kmh: float


@dataclass
class ServerTruth:
    server_id: str
    n_records: int
    is_bad: bool
    injected_pairs: list[InjectedPair] = field(default_factory=list)
    repeated_description: str | None = None
    repeated_description_addresses: int = 0


def _describe(rng: random.Random) -> str:
    return (
        f"{rng.choice(('M', 'F'))}/{rng.choice(SKIN)}/{rng.choice(HAIR)}/"
        f"{rng.randrange(25, 70, 5)}/{rng.randrange(60, 76)}/{rng.randrange(120, 220, 10)}"
    )


def _far_partner(rng: random.Random, origin: Address, min_km: float) -> Address:
    """An address at least `min_km` away, for injecting a sequence nobody could have driven."""
    pool = [a for b in boroughs() for a in by_borough(b)]
    for _ in range(200):
        candidate = rng.choice(pool)
        if haversine_km(origin.latlng, candidate.latlng) >= min_km:
            return candidate
    return rng.choice(pool)


def _round(point: LatLng) -> LatLng:
    return LatLng(lat=round(point.lat, 6), lng=round(point.lng, 6))


def generate_advocate(
    rng: random.Random,
) -> tuple[list[ServiceRecord], list[ServerTruth]]:
    records: list[ServiceRecord] = []
    truths: list[ServerTruth] = []

    for server_index in range(N_SERVERS):
        server_id = f"SRV-{server_index + 1:03d}"
        is_bad = server_index in BAD_SERVER_INDEXES
        truth = ServerTruth(server_id=server_id, n_records=0, is_bad=is_bad)

        # Each server mostly works one borough, which is what makes a cross-borough
        # three-minute hop stand out as impossible rather than merely busy.
        home_borough = boroughs()[server_index % len(boroughs())]
        local_pool = list(by_borough(home_borough))

        server_records: list[ServiceRecord] = []
        day = date(2025, 3, 3)
        while len(server_records) < RECORDS_PER_SERVER:
            if day.weekday() >= 5:
                day += timedelta(days=1)
                continue
            when = datetime(day.year, day.month, day.day, 9, 0, tzinfo=TZ)
            per_day = rng.randint(8, 14)
            for _ in range(per_day):
                if len(server_records) >= RECORDS_PER_SERVER:
                    break
                when += timedelta(minutes=rng.randint(14, 48))
                if when.hour >= 21:
                    break
                place = rng.choice(local_pool)
                server_records.append(
                    ServiceRecord(
                        server_id=server_id,
                        at=when,
                        loc=_round(place.latlng),
                        address=place.address,
                        case_ref=f"CV-{rng.randint(1000, 99999):06d}-25",
                        outcome=rng.choices(
                            ("served", "affixed", "not_home"), weights=(0.6, 0.2, 0.2)
                        )[0],
                        recipient_desc=_describe(rng),
                    )
                )
            day += timedelta(days=1)

        if is_bad:
            _inject_impossible(rng, server_records, truth)
            _inject_repeated_description(rng, server_records, truth)

        server_records.sort(key=lambda r: (r.at, r.address or ""))
        truth.n_records = len(server_records)
        records.extend(server_records)
        truths.append(truth)

    return records, truths


def _inject_impossible(
    rng: random.Random, server_records: list[ServiceRecord], truth: ServerTruth
) -> None:
    """Rewrite selected records so that the step into them could not have been travelled.

    Indexes in the answer key refer to positions in the server's final time-sorted list,
    so they are resolved after sorting, below.
    """
    chosen = rng.sample(range(1, len(server_records) - 1), IMPOSSIBLE_PAIRS_PER_BAD_SERVER)
    for index in sorted(chosen):
        previous = server_records[index - 1]
        origin = next(a for b in boroughs() for a in by_borough(b) if a.address == previous.address)
        far = _far_partner(rng, origin, min_km=8.0)
        minutes = float(rng.randint(2, 5))
        server_records[index] = server_records[index].model_copy(
            update={
                "at": previous.at + timedelta(minutes=minutes),
                "loc": _round(far.latlng),
                "address": far.address,
            }
        )
        distance = haversine_km(previous.loc, far.latlng)
        truth.injected_pairs.append(
            InjectedPair(
                index_a=index - 1,
                index_b=index,
                distance_km=round(distance, 4),
                minutes=minutes,
                required_speed_kmh=round(distance / (minutes / 60.0), 2),
            )
        )


def _inject_repeated_description(
    rng: random.Random, server_records: list[ServiceRecord], truth: ServerTruth
) -> None:
    """The same person of suitable age and discretion, at eight different doors."""
    description = _describe(rng)
    seen_addresses: set[str] = set()
    for index in rng.sample(range(len(server_records)), len(server_records)):
        record = server_records[index]
        if record.address in seen_addresses:
            continue
        seen_addresses.add(record.address or "")
        server_records[index] = record.model_copy(update={"recipient_desc": description})
        if len(seen_addresses) >= REPEATED_DESCRIPTION_ADDRESSES:
            break
    truth.repeated_description = description
    truth.repeated_description_addresses = len(seen_addresses)


def to_csv(records: list[ServiceRecord]) -> str:
    lines = ["server_id,at,lat,lng,address,case_ref,outcome,recipient_desc"]
    for record in records:
        lines.append(
            ",".join(
                (
                    record.server_id,
                    record.at.isoformat(),
                    f"{record.loc.lat:.6f}",
                    f"{record.loc.lng:.6f}",
                    f'"{record.address or ""}"',
                    record.case_ref or "",
                    record.outcome or "",
                    record.recipient_desc or "",
                )
            )
        )
    return "\n".join(lines) + "\n"
