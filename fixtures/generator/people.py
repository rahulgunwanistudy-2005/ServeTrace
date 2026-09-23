"""Synthetic people and their weekly rhythm.

A person is defined entirely by a seeded `random.Random`, so the same seed always
produces the same person, household, shift and commute.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.domain.models import HouseholdMember
from app.geo.distance import haversine_km

from .addresses import Address, boroughs, by_borough
from .names import GIVEN_FEMALE, GIVEN_MALE, GIVEN_NEUTRAL, SURNAMES

TZ = ZoneInfo("America/New_York")

Sex = str  # "male" | "female" | "other"


@dataclass(frozen=True, slots=True)
class Shift:
    start_h: int
    end_h: int
    """Local hour the person leaves work. Night shifts wrap past midnight."""
    workdays: tuple[int, ...]
    """Python weekday numbers, Monday is 0."""

    @property
    def crosses_midnight(self) -> bool:
        return self.end_h <= self.start_h


@dataclass(frozen=True, slots=True)
class Person:
    name: str
    sex: Sex
    age: int
    height_in: int
    home: Address
    work: Address
    shift: Shift
    commute_speed_kmh: float
    household: tuple[HouseholdMember, ...]

    @property
    def commute_km(self) -> float:
        return haversine_km(self.home.latlng, self.work.latlng)

    @property
    def commute_minutes(self) -> float:
        return self.commute_km / self.commute_speed_kmh * 60.0

    def works_on(self, day: date) -> bool:
        return day.weekday() in self.shift.workdays

    def local(self, day: date, hour_float: float) -> datetime:
        """Local wall-clock datetime, tolerating hours past 24 by rolling into the next day."""
        whole_days, rem = divmod(hour_float, 24.0)
        hours, minutes = divmod(round(rem * 60), 60)
        # round() can push 23.999h to 24:00; normalise that back into the next day.
        extra, hours = divmod(hours, 24)
        stamp = datetime.combine(
            day + timedelta(days=int(whole_days) + extra), time(hours, minutes), tzinfo=TZ
        )
        return stamp


def _household(
    rng: random.Random, person_name: str, sex: Sex, age: int, height: int
) -> tuple[HouseholdMember, ...]:
    members = [
        HouseholdMember(label=person_name, sex=sex, age=age, height_in=height, is_defendant=True)
    ]
    adult_labels = {
        "male": ("Partner", "Father", "Brother", "Roommate"),
        "female": ("Partner", "Mother", "Sister", "Roommate"),
    }
    child_labels = {"male": ("Son", "Nephew"), "female": ("Daughter", "Niece")}
    for _ in range(rng.randint(0, 3)):
        member_sex = rng.choice(("male", "female"))
        # Roughly half the extra members are adults, half are children. The label has to
        # follow the age, or the description-check fixtures read as nonsense.
        is_adult = rng.random() < 0.55
        member_age = rng.randint(19, 68) if is_adult else rng.randint(2, 17)
        labels = (adult_labels if is_adult else child_labels)[member_sex]
        members.append(
            HouseholdMember(
                label=rng.choice(labels),
                sex=member_sex,
                age=member_age,
                height_in=rng.randint(60, 75) if is_adult else rng.randint(34, 64),
                is_defendant=False,
            )
        )
    return tuple(members)


def make_person(rng: random.Random) -> Person:
    sex: Sex = rng.choice(("female", "male", "other"))
    if sex == "female":
        given = rng.choice(GIVEN_FEMALE)
    elif sex == "male":
        given = rng.choice(GIVEN_MALE)
    else:
        given = rng.choice(GIVEN_NEUTRAL)
    name = f"{given} {rng.choice(SURNAMES)}"

    home_borough = rng.choice(boroughs())
    home = rng.choice(by_borough(home_borough))

    # Work is usually in a different borough, which is what makes the commute long enough
    # for a contradiction to be unambiguous rather than a rounding artefact.
    work_borough = rng.choice(tuple(b for b in boroughs() if b != home_borough))
    work = rng.choice(by_borough(work_borough))

    start_h, end_h = rng.choice(((8, 16), (9, 17), (7, 15), (12, 20), (14, 22), (22, 6)))
    workdays = rng.choice(((0, 1, 2, 3, 4), (0, 1, 2, 3, 4, 5), (1, 2, 3, 4, 5)))

    age = rng.randint(21, 67)
    height = rng.randint(60, 76)
    return Person(
        name=name,
        sex=sex,
        age=age,
        height_in=height,
        home=home,
        work=work,
        shift=Shift(start_h=start_h, end_h=end_h, workdays=workdays),
        commute_speed_kmh=round(rng.uniform(15.0, 30.0), 2),
        household=_household(rng, name, sex, age, height),
    )
