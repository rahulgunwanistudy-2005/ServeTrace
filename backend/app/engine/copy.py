"""Every sentence the engine can put in front of a user.

Two rules, and they are the reason this module exists at all:

- **No free text anywhere else in `engine/`.** A rule decides whether it fires and hands
  its numbers to a template here. That keeps wording reviewable in one place and makes it
  impossible for a rule to grow an opinion in passing.
- **Every legal statement traces to a row of bible §5**, and carries that row's L-id on the
  `Finding`. Nothing here may state a legal fact that is not in that table, and nothing
  here may say that anyone lied. Bible §6: ServeTrace says *data conflicts*.

Formatting is done by hand rather than with `%-I` or `babel`, because `strftime` padding
flags are not portable and locale is not something a verdict should depend on.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.engine.params import PARAMS

TZ = ZoneInfo(PARAMS.tz)

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


# --- Formatting -------------------------------------------------------------------------


def local(when: datetime) -> datetime:
    """Bible §11.1.1: everything is computed in UTC and shown in New York time."""
    return when.astimezone(TZ)


def fmt_time(when: datetime) -> str:
    """7:42 PM"""
    at = local(when)
    hour = at.hour % 12 or 12
    return f"{hour}:{at.minute:02d} {'AM' if at.hour < 12 else 'PM'}"


def fmt_date(day: date | datetime) -> str:
    """June 12, 2025.

    Month first, because this is written for people in New York reading about a New York
    court, and because the browser formats the same dates that way beside these sentences.
    Two conventions on one card is the kind of detail that makes a document look machine-
    made.
    """
    if isinstance(day, datetime):
        day = local(day).date()
    return f"{MONTHS[day.month - 1]} {day.day}, {day.year}"


def fmt_datetime(when: datetime) -> str:
    """7:42 PM on June 12, 2025"""
    return f"{fmt_time(when)} on {fmt_date(when)}"


def fmt_km(km: float) -> str:
    """Kilometres below one are metres: "300 metres" is a distance, "0.3 km" is a number."""
    if km < 1.0:
        return f"{round(km * 1000):,} metres"
    return f"{km:.1f} km"


def fmt_speed(kmh: float) -> str:
    return f"{round(kmh):,} km/h"


def fmt_minutes(minutes: float) -> str:
    total = max(1, round(minutes))
    if total < 60:
        return f"{total} minute{'' if total == 1 else 's'}"
    hours, rest = divmod(total, 60)
    if rest == 0:
        return f"{hours} hour{'' if hours == 1 else 's'}"
    return f"{hours} hour{'' if hours == 1 else 's'} {rest} minute{'' if rest == 1 else 's'}"


def fmt_list(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def sentence_case(text: str) -> str:
    """Start a sentence with `text`.

    `str.capitalize()` would lower-case everything after the first letter, which turns
    "7:42 PM on 12 June 2025" into "7:42 pm on 12 june 2025" — caught by a golden snapshot
    rather than by anyone reading the template.
    """
    return text[:1].upper() + text[1:]


def claim_phrase(claim_ref: str, claimed_at: datetime) -> str:
    """How a claim is named in a sentence: "the service claimed at 7:42 PM on 12 June 2025"."""
    what = "the service" if claim_ref == "served_at" else "the attempt"
    return f"{what} claimed at {fmt_datetime(claimed_at)}"


METHOD_NAMES = {
    "308_1": "handing the papers to you in person",
    "308_2": "leaving the papers with someone else at your address and mailing a copy",
    "308_4": "taping the papers to your door and mailing a copy",
    "unknown": "this kind of service",
}


# --- Feasibility findings ---------------------------------------------------------------


def visit_conflict(
    claim_ref: str, claimed_at: datetime, km: float, start: datetime, end: datetime
) -> tuple[str, str]:
    return (
        "Your phone was somewhere else at that time",
        f"Your location history has you in one place from {fmt_time(start)} to "
        f"{fmt_time(end)} on {fmt_date(start)}, and that place is {fmt_km(km)} from the "
        f"address on the affidavit. {sentence_case(claim_phrase(claim_ref, claimed_at))} "
        f"falls inside that stay.",
    )


def prism_conflict(
    claim_ref: str,
    claimed_at: datetime,
    speed_kmh: float,
    km: float,
    minutes: float,
    fix_at: datetime,
) -> tuple[str, str]:
    return (
        f"Getting there in time would have taken about {fmt_speed(speed_kmh)}",
        f"At {fmt_time(fix_at)} on {fmt_date(fix_at)} your phone was {fmt_km(km)} from the "
        f"address on the affidavit. {sentence_case(claim_phrase(claim_ref, claimed_at))} is "
        f"{fmt_minutes(minutes)} away from that point, so covering that distance in that "
        f"time means moving at about {fmt_speed(speed_kmh)}.",
    )


def simultaneous_conflict(
    claim_ref: str, claimed_at: datetime, km: float, fix_at: datetime
) -> tuple[str, str]:
    """No speed is quoted here on purpose: inside a minute there is no journey to describe."""
    return (
        "Your phone was somewhere else at that same minute",
        f"At {fmt_time(fix_at)} on {fmt_date(fix_at)} your phone was {fmt_km(km)} from the "
        f"address on the affidavit. That is the same minute as "
        f"{claim_phrase(claim_ref, claimed_at)}, so there is no journey that fits between "
        f"the two.",
    )


def visit_match(
    claim_ref: str, claimed_at: datetime, km: float, start: datetime, end: datetime
) -> tuple[str, str]:
    return (
        "Your phone was at that address at that time",
        f"Your location history has you in one place from {fmt_time(start)} to "
        f"{fmt_time(end)} on {fmt_date(start)}, within {fmt_km(km)} of the address on the "
        f"affidavit, and {claim_phrase(claim_ref, claimed_at)} falls inside that stay.",
    )


def data_disagrees(claim_ref: str, claimed_at: datetime) -> tuple[str, str]:
    """Bible §6: never accuse on data that argues with itself, and never hide that it does."""
    return (
        "Your own location data disagrees with itself here",
        f"Some of your location points put you at the address on the affidavit around "
        f"{claim_phrase(claim_ref, claimed_at)}, and some put you elsewhere. We treated "
        f"this as consistent with the affidavit, because we do not go against a sworn "
        f"statement on data that does not agree with itself.",
    )


def near_claim(
    claim_ref: str, claimed_at: datetime, km: float, fix_at: datetime
) -> tuple[str, str]:
    return (
        "Your phone was at that address around that time",
        f"Your location history puts you within {fmt_km(km)} of the address on the "
        f"affidavit at {fmt_time(fix_at)} on {fmt_date(fix_at)}, which is around "
        f"{claim_phrase(claim_ref, claimed_at)}.",
    )


def no_data(claim_ref: str, claimed_at: datetime, window_h: int) -> tuple[str, str]:
    return (
        "No location data for that time",
        f"Your file has no location points in the {window_h} hours either side of "
        f"{claim_phrase(claim_ref, claimed_at)}, so this check could not run for it.",
    )


def ambiguous_clock(claim_ref: str, claimed_at: datetime) -> tuple[str, str]:
    return (
        "That time happens twice that night",
        f"The clocks change on {fmt_date(claimed_at)}, so {fmt_time(claimed_at)} that night "
        f"means two different moments an hour apart. We checked both and kept the answer "
        f"that goes least against the affidavit.",
    )


def no_coordinates(claim_ref: str, claimed_at: datetime) -> tuple[str, str]:
    return (
        "We could not put that address on the map",
        f"ServeTrace could not find the address for {claim_phrase(claim_ref, claimed_at)} "
        f"in its map of New York City, so the location check could not run for it. The "
        f"checks on dates and paperwork below still apply.",
    )


# --- Description (bible §11.2) ----------------------------------------------------------


def description_mismatch_personal(described: str, yours: str) -> tuple[str, str]:
    """L1: 308(1) is personal delivery, so the description should be of the defendant."""
    return (
        "That description does not match you",
        f"The affidavit says the papers were handed to you in person, and describes that "
        f"person as {described}. What you told us about yourself is {yours}.",
    )


def description_mismatch_substitute(described: str, n_members: int) -> tuple[str, str]:
    """L2: 308(2) is delivery to a person of suitable age and discretion at the address."""
    people = "the person" if n_members == 1 else f"any of the {n_members} people"
    return (
        "Nobody in your household matches that description",
        f"The affidavit says the papers were left with someone else at your address, and "
        f"describes that person as {described}. That does not match {people} you listed.",
    )


def height_words(inches: int) -> str:
    return f"{inches // 12}'{inches % 12}\""


def _range_words(low: int | None, high: int | None, render: object) -> str | None:
    fmt = render if callable(render) else str
    if low is None and high is None:
        return None
    if low is not None and high is not None and low != high:
        return f"{fmt(low)} to {fmt(high)}"
    return str(fmt(low if low is not None else high))


def describe_recipient(
    sex: str | None,
    age_min: int | None,
    age_max: int | None,
    height_in_min: int | None,
    height_in_max: int | None,
) -> str:
    """The described person, in the three fields the check actually compares.

    Weight and hair are on the form and are deliberately not read back here: the check
    does not use them (bible §11.2), and quoting a field the engine ignored would suggest
    it counted.
    """
    parts: list[str] = []
    if sex in ("male", "female"):
        parts.append(sex)
    age = _range_words(age_min, age_max, str)
    if age is not None:
        parts.append(f"aged {age}")
    height = _range_words(height_in_min, height_in_max, height_words)
    if height is not None:
        parts.append(height)
    return fmt_list(parts) if parts else "a person, with no details given"


def describe_member(label: str, sex: str | None, age: int | None, height_in: int | None) -> str:
    parts: list[str] = []
    if sex in ("male", "female"):
        parts.append(sex)
    if age is not None:
        parts.append(f"aged {age}")
    if height_in is not None:
        parts.append(height_words(height_in))
    return f"{label} ({fmt_list(parts)})" if parts else label


# --- New York rules (bible §11.3) -------------------------------------------------------


def missing_mailing(method: str) -> tuple[str, str]:
    """L2 / L3: 308(2) and 308(4) both require a mailing as well as the delivery."""
    return (
        "The affidavit does not show the required mailing",
        f"Service by {METHOD_NAMES[method]} is only complete when a copy is also mailed. "
        f"This affidavit gives no mailing date.",
    )


def mailing_too_late(days: int, limit: int) -> tuple[str, str]:
    """L2 / L3: the delivery and the mailing must be within 20 days of each other."""
    return (
        f"The mailing is {days} days from the delivery",
        f"The delivery and the mailing have to be within {limit} days of each other. This "
        f"affidavit shows {days} days between them.",
    )


def proof_filed_late(days: int, limit: int) -> tuple[str, str]:
    """L2 / L3: proof of service is filed within 20 days of the later of the two."""
    return (
        f"Proof of service was filed {days} days later",
        f"Proof of service has to be filed within {limit} days of whichever came later, the "
        f"delivery or the mailing. This affidavit shows {days} days.",
    )


def thin_diligence(reasons: list[str]) -> tuple[str, str]:
    """L3 / L4: due diligence before affix-and-mail. L4 is practice, never stated as statute."""
    return (
        "The attempts before the papers were taped to the door look thin",
        f"Papers may only be taped to a door and mailed when the server could not serve you "
        f"in person or leave them with someone at your address, after trying with due "
        f"diligence. Courts commonly expect three attempts, on at least two different days, "
        f"at different times of day. Here, {fmt_list(reasons)}. This is worth asking a "
        f"lawyer or the Court Help Center about.",
    )


def diligence_too_few(n: int) -> str:
    if n == 0:
        return "the affidavit shows no earlier attempts at all"
    return f"the affidavit shows {n} attempt{'' if n == 1 else 's'}"


def diligence_one_day(n_days: int) -> str:
    return "all of them fall on the same day" if n_days <= 1 else f"they cover only {n_days} days"


def diligence_office_hours() -> str:
    return "all of them fall on a weekday between 9 AM and 5 PM"


def contradicted_attempts(n: int) -> tuple[str, str]:
    """L3: the attempts are what justifies affix-and-mail, so a conflict there matters."""
    return (
        f"Your data also conflicts with {n} earlier attempt{'' if n == 1 else 's'}",
        f"Taping the papers to a door is only allowed after real attempts to serve you "
        f"another way. Your location history conflicts with "
        f"{n} of the attempt{'' if n == 1 else 's'} this affidavit relies on.",
    )


def method_unknown() -> tuple[str, str]:
    return (
        "We could not tell which kind of service this was",
        "The affidavit does not say clearly whether the papers were handed to you, left "
        "with someone else, or taped to your door. The checks on dates and mailing depend "
        "on which one it was, so they were skipped.",
    )


# --- Deadlines (bible §5 L5, L6) --------------------------------------------------------

DEADLINE_NOTE_NO_DATES = (
    "Tell us when you first found out about the judgment, and the date it was entered, and "
    "we can work out this deadline for you."
)

DEADLINE_NOTE_L5 = (
    "A judgment can be reopened when the court did not have jurisdiction, which includes "
    "service that was not done properly. There is no stated one-year limit for that ground, "
    "but act promptly."
)

DEADLINE_NOTE_L6 = (
    "If you were served in any way other than in person, and you did not personally get "
    "notice in time to defend the case, you may be able to ask the court to reopen it "
    "within one year of learning about the judgment, and no more than five years after it "
    "was entered. You also have to show you have a defence worth hearing."
)


def deadline_note(knowledge_deadline: date | None, outer_limit: date | None) -> str:
    if knowledge_deadline is None and outer_limit is None:
        return f"{DEADLINE_NOTE_L6} {DEADLINE_NOTE_NO_DATES} {DEADLINE_NOTE_L5}"
    dates: list[str] = []
    if knowledge_deadline is not None:
        dates.append(f"one year after you found out, which is {fmt_date(knowledge_deadline)}")
    if outer_limit is not None:
        dates.append(f"five years after the judgment was entered, which is {fmt_date(outer_limit)}")
    whichever = " The earlier of the two is the one that matters." if len(dates) == 2 else ""
    return f"{DEADLINE_NOTE_L6} For you that is {fmt_list(dates)}.{whichever} {DEADLINE_NOTE_L5}"
