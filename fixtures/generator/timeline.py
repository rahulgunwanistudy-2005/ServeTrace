"""Turn a person's day into location fixes, then into each export format we must parse.

The generator owns the truth about where the person was. Nothing here consults the
engine: the engine is the thing under test, and a label derived from it would be circular.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.domain.models import FixKind, LatLng, LocationFix
from app.geo.distance import haversine_km

from .addresses import Address
from .names import MERCHANTS
from .people import TZ, Person

METERS_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True, slots=True)
class Stay:
    """A stretch the person spent in one place."""

    place: Address
    kind: str
    """"home" or "work"."""
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class DayTruth:
    """Where the person actually was, before any sampling or jitter."""

    day: date
    stays: tuple[Stay, ...]
    travels: tuple[tuple[Address, Address, datetime, datetime], ...]

    def place_at(self, when: datetime) -> Address | None:
        """The place the person was standing still at, or None while travelling."""
        for stay in self.stays:
            if stay.start <= when <= stay.end:
                return stay.place
        return None

    def is_travelling(self, when: datetime) -> bool:
        return any(start <= when <= end for _, _, start, end in self.travels)


def plan_day(person: Person, day: date, rng: random.Random | None = None) -> DayTruth:
    """The person's real movements for one calendar day, in local time."""
    if not person.works_on(day):
        return _rest_day(person, day, rng)

    commute_h = person.commute_minutes / 60.0
    start_h = float(person.shift.start_h)
    end_h = float(person.shift.end_h)
    if person.shift.crosses_midnight:
        end_h += 24.0

    depart_home = person.local(day, start_h - commute_h)
    arrive_work = person.local(day, start_h)
    leave_work = person.local(day, end_h)
    arrive_home = person.local(day, end_h + commute_h)

    stays = (
        Stay(person.home, "home", person.local(day, 0.0), depart_home),
        Stay(person.work, "work", arrive_work, leave_work),
        Stay(person.home, "home", arrive_home, person.local(day, end_h + commute_h + 3.0)),
    )
    travels = (
        (person.home, person.work, depart_home, arrive_work),
        (person.work, person.home, leave_work, arrive_home),
    )
    return DayTruth(day=day, stays=stays, travels=travels)


def _rest_day(person: Person, day: date, rng: random.Random | None) -> DayTruth:
    """A day off is not twenty-four hours motionless at home: there is an errand in it.

    Without this every rest-day case collapses to a single all-day visit, which is both
    unrealistic and useless for exercising the prism test.
    """
    if rng is None:
        return DayTruth(
            day=day,
            stays=(Stay(person.home, "home", person.local(day, 0.0), person.local(day, 23.99)),),
            travels=(),
        )

    errand = rng.choice(_nearby(person.home))
    out_h = rng.uniform(10.0, 15.0)
    leg_h = max(haversine_km(person.home.latlng, errand.latlng) / 18.0, 0.12)
    stay_h = rng.uniform(0.5, 2.0)

    depart = person.local(day, out_h)
    arrive = person.local(day, out_h + leg_h)
    leave = person.local(day, out_h + leg_h + stay_h)
    back = person.local(day, out_h + leg_h + stay_h + leg_h)

    return DayTruth(
        day=day,
        stays=(
            Stay(person.home, "home", person.local(day, 0.0), depart),
            Stay(errand, "errand", arrive, leave),
            Stay(person.home, "home", back, person.local(day, 23.99)),
        ),
        travels=(
            (person.home, errand, depart, arrive),
            (errand, person.home, leave, back),
        ),
    )


def _nearby(home: Address) -> list[Address]:
    """Addresses in the same borough, so an errand is an errand and not a road trip."""
    from .addresses import by_borough

    same = [a for a in by_borough(home.borough) if a.address != home.address]
    return same or [home]


def _jitter(rng: random.Random, point: LatLng, sigma_m: float) -> LatLng:
    """Gaussian GPS noise, in metres, converted to degrees at this latitude."""
    d_lat = rng.gauss(0.0, sigma_m) / METERS_PER_DEG_LAT
    d_lng = rng.gauss(0.0, sigma_m) / (METERS_PER_DEG_LAT * math.cos(math.radians(point.lat)))
    return LatLng(lat=round(point.lat + d_lat, 7), lng=round(point.lng + d_lng, 7))


def _interpolate(a: LatLng, b: LatLng, fraction: float) -> LatLng:
    """Straight-line interpolation. Over a NYC commute the great-circle error is metres."""
    return LatLng(
        lat=round(a.lat + (b.lat - a.lat) * fraction, 7),
        lng=round(a.lng + (b.lng - a.lng) * fraction, 7),
    )


def fixes_for_day(
    rng: random.Random,
    person: Person,
    truth: DayTruth,
    gaps: tuple[tuple[datetime, datetime], ...] = (),
) -> list[LocationFix]:
    """Sample the day into fixes: one VISIT per stay, PATH points along each commute.

    `gaps` are windows where the phone recorded nothing (battery dead, airplane mode).
    Any fix falling inside a gap is dropped, which is what produces NO_DATA cases.
    """
    sigma = rng.uniform(20.0, 60.0)
    fixes: list[LocationFix] = []

    for stay in truth.stays:
        if stay.end <= stay.start:
            continue
        fixes.append(
            LocationFix(
                t=stay.start,
                t_end=stay.end,
                loc=_jitter(rng, stay.place.latlng, sigma * 0.5),
                accuracy_m=round(rng.uniform(15.0, 45.0), 1),
                kind=FixKind.VISIT,
                source="timeline_android",
                label=f"Timeline visit: {stay.kind.upper()}",
            )
        )

    for origin, destination, start, end in truth.travels:
        total_s = (end - start).total_seconds()
        if total_s <= 0:
            continue
        step_s = rng.choice((120, 180, 240, 300))
        n_steps = max(1, int(total_s // step_s))
        for i in range(n_steps + 1):
            fraction = min(1.0, (i * step_s) / total_s)
            when = start + timedelta(seconds=i * step_s)
            if when > end:
                break
            fixes.append(
                LocationFix(
                    t=when,
                    loc=_jitter(
                        rng, _interpolate(origin.latlng, destination.latlng, fraction), sigma
                    ),
                    accuracy_m=round(rng.uniform(20.0, 90.0), 1),
                    kind=FixKind.PATH,
                    source="timeline_android",
                    label=None,
                )
            )

    kept = carve_gaps(fixes, gaps)
    kept.sort(key=lambda f: (f.t, f.kind.value, f.loc.lat, f.loc.lng))
    return kept


def carve_gaps(
    fixes: list[LocationFix], gaps: tuple[tuple[datetime, datetime], ...]
) -> list[LocationFix]:
    """Remove everything the phone could not have recorded during a gap.

    A path point inside a gap simply vanishes. A visit is *truncated*, because that is what
    a real export looks like when a phone dies mid-stay: the visit ends early and a fresh one
    begins when the phone comes back. Dropping only visits that a gap swallows whole would
    leave an eight-hour visit straddling the gap, and no case would ever be NO_DATA.
    """
    if not gaps:
        return list(fixes)

    out: list[LocationFix] = []
    for fix in fixes:
        if fix.t_end is None:
            if not any(start <= fix.t <= end for start, end in gaps):
                out.append(fix)
            continue

        pieces: list[tuple[datetime, datetime]] = [(fix.t, fix.t_end)]
        for gap_start, gap_end in gaps:
            next_pieces: list[tuple[datetime, datetime]] = []
            for piece_start, piece_end in pieces:
                if gap_end <= piece_start or gap_start >= piece_end:
                    next_pieces.append((piece_start, piece_end))
                    continue
                if piece_start < gap_start:
                    next_pieces.append((piece_start, gap_start))
                if piece_end > gap_end:
                    next_pieces.append((gap_end, piece_end))
            pieces = next_pieces

        for piece_start, piece_end in pieces:
            # A sliver shorter than a minute is noise, not a visit.
            if (piece_end - piece_start).total_seconds() < 60:
                continue
            out.append(fix.model_copy(update={"t": piece_start, "t_end": piece_end}))
    return out


def _deg_string(point: LatLng) -> str:
    return f"{point.lat:.7f}°, {point.lng:.7f}°"


def _geo_string(point: LatLng) -> str:
    return f"geo:{point.lat:.7f},{point.lng:.7f}"


def _iso(when: datetime) -> str:
    return when.astimezone(TZ).isoformat(timespec="milliseconds")


def to_android_timeline(fixes: list[LocationFix]) -> dict[str, object]:
    """Google Timeline, Android export shape. Bible §13."""
    segments: list[dict[str, object]] = []
    path_run: list[LocationFix] = []

    def flush_path() -> None:
        if not path_run:
            return
        segments.append(
            {
                "startTime": _iso(path_run[0].t),
                "endTime": _iso(path_run[-1].t),
                "timelinePath": [
                    {"point": _deg_string(f.loc), "time": _iso(f.t)} for f in path_run
                ],
            }
        )
        path_run.clear()

    for fix in fixes:
        if fix.kind is FixKind.VISIT:
            flush_path()
            segments.append(
                {
                    "startTime": _iso(fix.t),
                    "endTime": _iso(fix.t_end or fix.t),
                    "visit": {
                        "probability": 0.92,
                        "topCandidate": {
                            "placeLocation": {"latLng": _deg_string(fix.loc)},
                            "semanticType": (fix.label or "").split(": ")[-1] or "UNKNOWN",
                            "probability": 0.87,
                        },
                    },
                }
            )
        else:
            path_run.append(fix)
    flush_path()

    raw_signals = [
        {
            "position": {
                "LatLng": _deg_string(f.loc),
                "timestamp": _iso(f.t),
                "accuracyMeters": int(f.accuracy_m or 30),
            }
        }
        for f in fixes
        if f.kind is FixKind.PATH
    ]
    return {"semanticSegments": segments, "rawSignals": raw_signals}


def to_ios_timeline(fixes: list[LocationFix]) -> list[dict[str, object]]:
    """Google Timeline, iOS export shape: a top-level array using `geo:` strings. Bible §13."""
    out: list[dict[str, object]] = []
    path_run: list[LocationFix] = []

    def flush_path() -> None:
        if len(path_run) >= 2:
            out.append(
                {
                    "startTime": _iso(path_run[0].t),
                    "endTime": _iso(path_run[-1].t),
                    "activity": {
                        "start": _geo_string(path_run[0].loc),
                        "end": _geo_string(path_run[-1].loc),
                        "distanceMeters": round(
                            haversine_km(path_run[0].loc, path_run[-1].loc) * 1000, 1
                        ),
                        "topCandidate": {"type": "IN_PASSENGER_VEHICLE", "probability": 0.79},
                    },
                }
            )
        path_run.clear()

    for fix in fixes:
        if fix.kind is FixKind.VISIT:
            flush_path()
            out.append(
                {
                    "startTime": _iso(fix.t),
                    "endTime": _iso(fix.t_end or fix.t),
                    "visit": {
                        "hierarchyLevel": 0,
                        "probability": 0.9,
                        "topCandidate": {
                            "placeLocation": _geo_string(fix.loc),
                            "semanticType": (fix.label or "").split(": ")[-1] or "Unknown",
                            "probability": 0.84,
                        },
                    },
                }
            )
        else:
            path_run.append(fix)
    flush_path()
    return out


def to_card_csv(rng: random.Random, fixes: list[LocationFix], person: Person) -> str:
    """A bank/card statement export. Amounts stay on the device; only addresses are geocoded."""
    lines = ["Date,Time,Description,Address,Amount"]
    for fix in fixes:
        if fix.kind is not FixKind.VISIT:
            continue
        # One plausible purchase near the start of each stay.
        when = fix.t + timedelta(minutes=rng.randint(5, 40))
        if fix.t_end is not None and when > fix.t_end:
            continue
        place = person.work if "WORK" in (fix.label or "") else person.home
        lines.append(
            ",".join(
                (
                    when.strftime("%Y-%m-%d"),
                    when.strftime("%H:%M"),
                    rng.choice(MERCHANTS),
                    f'"{place.address}"',
                    f"{rng.uniform(3.5, 84.0):.2f}",
                )
            )
        )
    return "\n".join(lines) + "\n"
