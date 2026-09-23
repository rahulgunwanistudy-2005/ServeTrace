"""Every sentence that appears in a generated document. Bible §5, §6, §15.

The same discipline as `engine/copy.py`, for the same reasons, with one addition that
matters more here than anywhere else in the product:

- **No free text in `packet.py` or `affidavit.py`.** Those modules decide *which*
  paragraphs a document contains and hand this module the numbers. Templates hold
  structure and column headings. Prose lives here, in one file somebody can read end to
  end and check against bible §5.
- **Every legal statement carries its L-id**, and no legal statement exists that is not in
  that table. Nothing here says anyone lied (bible §6): the documents say what the
  affidavit claims, what the data records, and that the two do not fit.
- **The affidavit's paragraphs are in the first person, and they are sworn.** That is why
  they are not the findings' own sentences with the pronouns changed. A `Finding` explains
  something to the person reading their result; a paragraph of an affidavit is that person
  telling a court a fact, and it may contain only facts they are in a position to state —
  their own name, their own address, what their own records say, and what the filed
  affidavit says. Every inference is left to the court.

Formatting comes from `engine/copy.py` so that a date on the result page, a date in a
finding and a date in a court document are written the same way (see `tasks/lessons.md`).
"""

from __future__ import annotations

from datetime import date, datetime

from app.engine.copy import (
    MONTHS,
    fmt_date,
    fmt_datetime,
    fmt_km,
    fmt_list,
    fmt_minutes,
    fmt_speed,
    fmt_time,
    local,
)

__all__ = [
    "MONTHS",
    "fmt_date",
    "fmt_datetime",
    "fmt_km",
    "fmt_list",
    "fmt_speed",
    "fmt_time",
    "local",
]


# --- Shared, on every page of both documents ---------------------------------------------

DISCLAIMER = (
    "DRAFT — not legal advice. Review with the NYC Civil Court Help Center or a legal aid "
    "organization."
)
"""Bible §5. Printed in the footer of every page of both documents."""

LIMITATION = (
    "Location history shows where your phone was, not proof of where you were. A judge "
    "decides what happened."
)
"""Bible §6. Ends the verdict section of the packet, as it ends every result card."""

PRODUCT = "ServeTrace"
NOT_A_LAW_FIRM = (
    "ServeTrace is not a law firm and does not give legal advice. It compares the times "
    "and places sworn to in an affidavit of service against records the person supplied, "
    "and reports where the two do not fit."
)


# --- The packet --------------------------------------------------------------------------

PACKET_TITLE = "Evidence Packet"
PACKET_SUBTITLE = "An affidavit of service, checked against location records"

TIER_HEADLINES = {
    "contradicted": "Your location data conflicts with the affidavit.",
    "consistent": "Your location data is consistent with the affidavit.",
    "no_data": "We don't have location data for that time.",
    "inconclusive": "Your data doesn't settle this either way.",
}
"""Bible §6 verbatim, and in the second person like everything else here.

The packet quotes the engine's findings word for word, and those are addressed to the
person whose case it is. Writing the surrounding prose in the third person would have put
two voices on one page and made "your phone was somewhere else" read as though the judge
owned the phone. So the packet is what its cover says it is — a report prepared *for* this
person — and one voice runs through it. What gets filed with the court is the affidavit,
which is in the first person throughout, and this is its Exhibit B."""

TIER_MEANINGS = {
    "contradicted": (
        "Your own records put you away from the address on the affidavit at the time the "
        "server swore to, by more than the margins set out under “How this was worked "
        "out”."
    ),
    "consistent": (
        "Your records put you at or near the address on the affidavit around that time. "
        "That does not mean the service was proper, but this particular check does not "
        "help you."
    ),
    "no_data": (
        "Your file has no usable points near that time, so this check could not run. That "
        "is not evidence either way."
    ),
    "inconclusive": (
        "There are records near that time, but under the margins set out below they "
        "neither match the affidavit nor conflict with it."
    ),
}

SECTION_VERDICT = "What this check found"
SECTION_MAP = "Where the records place the phone"
SECTION_CLAIMS = "Each sworn moment, checked"
SECTION_FINDINGS = "Findings"
SECTION_FIXES = "The location records used"
SECTION_METHOD = "How this was worked out"
SECTION_INTEGRITY = "What this packet was built from"
SECTION_DEADLINE = "Deadlines"

MAP_ALT = (
    "A map could not be included in this packet. The coordinates behind it are in the tables below."
)
"""Bible §14: the map always has a text alternative, and here the table *is* the map."""

FINDINGS_NONE = "This check produced no findings."

LEGAL_REF_NAMES = {
    "L1": "CPLR 308(1) — personal delivery to the defendant",
    "L2": "CPLR 308(2) — delivery to a person of suitable age and discretion, and mailing",
    "L3": "CPLR 308(4) — affixing to the door, and mailing",
    "L4": "What courts commonly expect before papers may be affixed to a door",
    "L5": "CPLR 5015(a)(4) — vacating a judgment for lack of jurisdiction",
    "L6": "CPLR 317 — the time to move after learning of the judgment",
    "L7": "NYC Admin Code § 20-410 — process servers must record GPS",
}
"""Bible §5. Names of the provisions the engine encodes, never statements of what they say:
the statement is the finding's own text, which comes from `engine/copy.py`."""

METHOD_FORMAL = {
    "308_1": "personal delivery under CPLR 308(1)",
    "308_2": "delivery to a person of suitable age and discretion, and mailing, under CPLR 308(2)",
    "308_4": "affixing to the door, and mailing, under CPLR 308(4)",
    "unknown": "a method the affidavit does not state clearly",
}

SEVERITY_LABELS = {"strong": "Strong", "moderate": "Worth checking", "info": "Note"}

TIER_LABELS = {
    "contradicted": "Conflicts",
    "consistent": "Consistent",
    "no_data": "No data",
    "inconclusive": "Unsettled",
}

FIX_KIND_LABELS = {
    "visit": "Stay",
    "path": "Journey point",
    "transaction": "Card transaction",
    "manual": "Stated by hand",
}
"""Column values in the packet's table of records, where a heading supplies the context."""

FIX_KIND_IN_SENTENCE = {
    "visit": "recorded stays in one place",
    "path": "recorded points along a journey",
    "transaction": "card transactions with a time and a place",
    "manual": "times and places I wrote down myself",
}
"""The same four kinds inside a sentence somebody swears to, where nothing supplies context.

Two dictionaries rather than one because a table cell and a clause in an affidavit are
different pieces of writing: "Stay" is a perfectly good column value, and "the records I
rely on below are stay" is not English."""

SOURCE_LABELS = {
    "timeline_android": "Google Timeline (Android export)",
    "timeline_ios": "Google Timeline (iOS export)",
    "card_csv": "Card or bank statement",
    "manual": "Entered by hand",
}
"""Where a record came from, for the packet's table. A source id that is not in here is
printed as it is: an unrecognised id is still true, and inventing a friendly name for one
would be the kind of guess an exhibit should not contain."""


def packet_intro(defendant: str, index_number: str | None) -> str:
    where = f", index number {index_number}," if index_number else ""
    return (
        f"This packet compares the affidavit of service filed against {defendant}{where} "
        f"with the location records you supplied. It sets out what the affidavit claims, "
        f"what your records show, and where the two cannot both be true. It draws no "
        f"conclusion about what happened, and it is not a finding of fact."
    )


def verdict_line(nearest_km: float | None, required_speed_kmh: float | None) -> str | None:
    """Bible §14.5: one sentence under the headline, carrying the key number.

    Returns None when the engine measured no distance, because a confident sentence with
    nothing behind it is worse than no sentence.
    """
    if nearest_km is None:
        return None
    if required_speed_kmh is None:
        return f"Your nearest location record is {fmt_km(nearest_km)} from that address."
    return (
        f"Your nearest location record is {fmt_km(nearest_km)} from that address. Covering "
        f"that distance in the time available means travelling at about "
        f"{fmt_speed(required_speed_kmh)}."
    )


def claimed_sentence(when: datetime, address: str, method: str) -> str:
    return (
        f"The affidavit swears that you were served at {fmt_datetime(when)} at {address}, "
        f"by {METHOD_FORMAL[method]}."
    )


def methodology_body(
    radius_km: float, window_h: int, strong_kmh: float, moderate_kmh: float
) -> str:
    return (
        f"Each sworn moment is compared with your location records within {window_h} hours "
        f"of it, on either side. A record within {fmt_km(radius_km)} of the sworn address "
        f"counts as being there; a record's own stated accuracy is added to that margin. "
        f"Where the records place your phone elsewhere, the speed needed to reach the sworn "
        f"address in the time available is calculated, and compared against "
        f"{fmt_speed(strong_kmh)} and {fmt_speed(moderate_kmh)} door to door. Those margins "
        f"are deliberately generous towards the affidavit: they are set so that a conflict "
        f"is reported only where the records leave no room for the sworn account."
    )


METHODOLOGY_LIMITS = (
    "This is a comparison of records, not a finding of fact. Location history can be "
    "wrong, a phone can be left behind or lent to somebody else, and an address can be "
    "geocoded to the wrong doorway. Nothing in this packet says that anybody lied."
)

INTEGRITY_BODY = (
    "These are SHA-256 digests. Anyone holding the same affidavit file, or the same "
    "location records, can compute them and confirm that this packet describes those and "
    "not something else."
)


def generated_line(when: datetime, engine_version: str, params_version: str) -> str:
    return (
        f"Prepared by {PRODUCT} at {fmt_datetime(when)} (New York time). "
        f"Engine {engine_version}, thresholds {params_version}."
    )


def fixes_note(shown: int, total: int) -> str:
    if shown >= total:
        return (
            f"All {total:,} location records used in this check are listed. They are the "
            f"records close in time to the sworn moments above; the rest of your location "
            f"history was never sent off the device it was read on."
        )
    return (
        f"The first {shown:,} of {total:,} records are listed. The digest above covers all "
        f"{total:,} of them."
    )


# --- The draft supporting affidavit -------------------------------------------------------
#
# Each function below is one numbered paragraph. They are written to be read aloud in a
# courtroom, and every one of them states something the person swearing it is in a
# position to know.

AFFIDAVIT_TITLE = "Affidavit in Support of Order to Show Cause"
DRAFT_MARK = "DRAFT"

AFFIDAVIT_PREAMBLE = "being duly sworn, deposes and says:"

AFFIDAVIT_NOTE = (
    "This draft is written to be attached to the Order to Show Cause form the court "
    "provides. It does not replace that form. Every paragraph is built from details the "
    "person named above confirmed, and from the comparison set out in the annexed packet. "
    "Read it, correct anything that is not right, and sign it only in front of a notary."
)

STATE_COUNTY = "STATE OF NEW YORK, COUNTY OF ______________, ss.:"


def para_identity(name: str, residence: str | None) -> str:
    if residence:
        return (
            f"I am {name}, the defendant in this action. I reside at {residence}. I make "
            f"this affidavit in support of my application to vacate the default judgment "
            f"entered against me."
        )
    return (
        f"I am {name}, the defendant in this action. I make this affidavit in support of "
        f"my application to vacate the default judgment entered against me."
    )


def para_named_differently(defendant_name: str) -> str:
    """Only when the affiant's name and the name on the papers are not the same string."""
    return f"The papers in this action name the defendant as {defendant_name}."


def para_affidavit_of_service(
    when: datetime, address: str, method: str, server_name: str | None
) -> str:
    """L1 / L2 / L3: what the filed affidavit claims, in its own terms."""
    by = f" by {server_name}" if server_name else ""
    return (
        f"An affidavit of service has been filed in this action. It states that service "
        f"was made upon me{by} on {fmt_date(when)} at {fmt_time(when)}, at {address}, by "
        f"{METHOD_FORMAL[method]}. A copy is annexed as Exhibit A."
    )


def para_not_served(when: datetime) -> str:
    """Included only when the person confirmed they are willing to swear to it."""
    return (
        f"I was not served with the summons and complaint in this action. No papers were "
        f"delivered to me on {fmt_date(when)}, and I did not learn of this action until "
        f"long after that date."
    )


def para_not_my_address(address: str) -> str:
    """L2 / L3: both provisions require the dwelling place or usual place of abode."""
    return (
        f"{address}, the address at which service is claimed, was not my dwelling place, "
        f"my usual place of abode or my place of business on that date."
    )


def para_records_intro(sources: str) -> str:
    return (
        f"I keep a location history. The records I rely on below are {sources}. They are "
        f"annexed as part of Exhibit B, in full for the hours around the time sworn to."
    )


def para_visit(when: datetime, km: float, address: str, start: datetime, end: datetime) -> str:
    """F-VISIT, and the strongest thing this document can say from records."""
    return (
        f"My location history records me in one place from {fmt_time(start)} to "
        f"{fmt_time(end)} on {fmt_date(start)}, which includes {fmt_time(when)}, the time "
        f"of the service sworn to. That place is {fmt_km(km)} from {address}."
    )


def para_prism(
    when: datetime,
    km: float,
    address: str,
    fix_at: datetime,
    minutes: float,
    speed_kmh: float,
) -> str:
    """F-PRISM with a measurable gap: the number the whole method turns on."""
    return (
        f"At {fmt_time(fix_at)} on {fmt_date(fix_at)}, my location history places me "
        f"{fmt_km(km)} from {address}. That is {fmt_minutes(minutes)} from "
        f"{fmt_time(when)}, the time of the service sworn to. Covering that distance in "
        f"that time would require travelling at about {fmt_speed(speed_kmh)}."
    )


def para_simultaneous(when: datetime, km: float, address: str) -> str:
    """F-PRISM inside a minute: there is no journey to describe, so none is described."""
    return (
        f"At {fmt_time(when)} on {fmt_date(when)}, the same minute as the service sworn "
        f"to, my location history places me {fmt_km(km)} from {address}."
    )


def para_attempt(when: datetime, km: float, address: str) -> str:
    """The same facts, about a prior attempt the affidavit relies on rather than the service."""
    return (
        f"The affidavit also records an attempt at {fmt_time(when)} on {fmt_date(when)}. "
        f"My location history places me {fmt_km(km)} from {address} at that time."
    )


def para_description(described: str, method: str) -> str:
    """F-DESC. L1 for personal delivery, L2 for substituted.

    No head count. The roster the check ran against includes the person signing this, so
    "any of the 2 people living at that address" double-counts them — and a number that is
    one out is worse in a sworn paragraph than no number at all. What they can swear to is
    that nobody there matches, which is also the stronger statement.
    """
    if method == "308_1":
        return (
            f"The affidavit describes the person served as {described}. That is not a "
            f"description of me."
        )
    return (
        f"The affidavit describes the person who accepted the papers as {described}. That "
        f"is not a description of me, and it is not a description of anyone else living at "
        f"that address."
    )


def para_mailing_missing(method: str) -> str:
    """R-T1. L2 / L3: service by these methods is not complete without the mailing."""
    return (
        f"Service by {METHOD_FORMAL[method]} is complete only where a copy is also mailed. "
        f"The affidavit of service states no mailing date."
    )


def para_mailing_late(days: int, limit: int) -> str:
    """R-T2. L2 / L3: delivery and mailing within twenty days of each other."""
    return (
        f"The delivery and the mailing must be within {limit} days of each other. The "
        f"affidavit of service shows {days} days between them."
    )


def para_proof_late(days: int, limit: int) -> str:
    """R-T3. L2 / L3: proof filed within twenty days of the later of the two."""
    return (
        f"Proof of service must be filed within {limit} days of whichever came later, the "
        f"delivery or the mailing. The affidavit of service was filed {days} days after "
        f"that date."
    )


def para_diligence(attempts: int, distinct_days: int) -> str:
    """R-D1. L3 for the requirement, L4 for the pattern — and L4 is practice, not statute."""
    counted = (
        "no earlier attempt at all"
        if attempts == 0
        else f"{attempts} earlier attempt{'' if attempts == 1 else 's'}"
    )
    days = "" if attempts == 0 else f", on {distinct_days} day{'' if distinct_days == 1 else 's'}"
    return (
        f"Papers may be affixed to a door and mailed only where the defendant cannot be "
        f"served in person, or by delivery to a person of suitable age and discretion, "
        f"with due diligence. The affidavit of service records {counted}{days}. I "
        f"respectfully ask the court to consider whether that satisfies due diligence."
    )


def para_attempts_contradicted(n: int) -> str:
    """R-D2. L3: the attempts are what permits affixing at all."""
    return (
        f"My location records also conflict with {n} of the earlier attempt"
        f"{'' if n == 1 else 's'} on which that affidavit relies, as set out in Exhibit B."
    )


PARA_PACKET = (
    "The comparison of my location records with the affidavit of service, the distances "
    "and times relied on above, and the method by which they were calculated, are set out "
    "in the Evidence Packet annexed as Exhibit B."
)

PARA_RELIEF_5015 = (
    "On these facts the court did not acquire personal jurisdiction over me, and the "
    "judgment entered against me should be vacated under CPLR 5015(a)(4)."
)
"""L5."""

PARA_TRAVERSE = (
    "Because the facts of service are disputed, I respectfully request a traverse hearing "
    "at which the process server may be examined."
)
"""L5: a disputed service claim may lead the court to order a traverse hearing."""

PARA_STAY = (
    "I respectfully request that enforcement of the judgment, including any restraint on "
    "my bank account or wages, be stayed while this application is decided."
)

PARA_GPS = (
    "A process server licensed in New York City must carry a device that electronically "
    "records the location, date and time of every service and every attempt. I "
    "respectfully request that the plaintiff be directed to produce that record for the "
    "service and attempts described in the affidavit of service."
)
"""L7."""


def para_317(method: str, defense: str | None) -> str:
    """L6, and only when eligible. The conditions are stated because they are the ground."""
    ground = (
        f"In the alternative, I was served, if at all, by {METHOD_FORMAL[method]}, and not "
        f"by personal delivery. I did not personally receive notice of this action in time "
        f"to defend it."
    )
    # A blank left in square brackets is how a draft says "this part is yours" without
    # inventing it. Nothing in this product may write somebody's defence for them.
    said = _as_sentence(defense) if defense else "[state your defence here in your own words]."
    return (
        f"{ground} I have a meritorious defence to this action: {said} I therefore ask the "
        f"court to allow me to defend under CPLR 317."
    )


def _as_sentence(text: str) -> str:
    """The user's own words, ended so the paragraph around them reads as one sentence."""
    said = " ".join(text.split())
    return said if said.endswith((".", "!", "?")) else f"{said}."


def para_317_deadline(deadline: date) -> str:
    """L6: the arithmetic, stated so the court can see the application is in time."""
    return f"That application is made within the time allowed, which runs to {fmt_date(deadline)}."


PARA_WHEREFORE = (
    "WHEREFORE, I respectfully request an order vacating the judgment entered against me, "
    "staying its enforcement in the meantime, and granting such other relief as the court "
    "finds just."
)

EXHIBITS = (
    ("A", "The affidavit of service filed in this action."),
    ("B", "The Evidence Packet: the location records relied on above, and how they were compared."),
)

SIGNATURE_LABEL = "Signature of defendant"
NOTARY_BLOCK = "Sworn to before me this ______ day of ____________, 20____."
NOTARY_LABEL = "Notary Public"
