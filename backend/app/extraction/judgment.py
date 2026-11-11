"""The date a default judgment was entered, read off the judgment page. Bible §12 (v1.1).

The entry date starts the outer limit in the CPLR 317 deadline (bible §5 L6), and people
rarely know it: it is printed on the judgment, which is often in the same file as the
affidavit. Reading it saves a trip back to the papers.

It is a draft like everything else read off a document. The user sees it, with the words
it came from, and confirms it; nothing computes a deadline from an unconfirmed date.

Text-layer pages are read here with a regular expression anchored on "entered", then on
"judgment". Image pages are read by one small model call on that page alone (`vision.py`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Final

from app.extraction.validators import parse_date

_MONTHS: Final = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
    "|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
)

DATE_RE: Final = re.compile(
    rf"(?P<long>(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})"
    r"|(?P<num>\b\d{1,2}/\d{1,2}/\d{2,4}\b)"
    r"|(?P<iso>\b\d{4}-\d{2}-\d{2}\b)",
    re.IGNORECASE,
)

ANCHORS: Final = (
    re.compile(r"\bentered\b", re.IGNORECASE),
    re.compile(r"\bjudgment\b", re.IGNORECASE),
)
"""In order of trust: a date next to "entered" is the entry date; next to "judgment" it
usually is, and is still only a draft."""

AFTER_CHARS: Final = 80
BEFORE_CHARS: Final = 40


@dataclass(frozen=True, slots=True)
class JudgmentDate:
    value: date
    quote: str
    page: int


_MONTH_NUMBER: Final = {
    name: index
    for index, names in enumerate(
        (
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ),
        start=1,
    )
    for name in names
}

_LONG: Final = re.compile(r"([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", re.IGNORECASE)


def _as_date(raw: str) -> date | None:
    """A printed date to a `date`: "September 3, 2025", "SEP 03 2025", "09/03/2025"."""
    long = _LONG.fullmatch(raw.strip())
    if long:
        month = _MONTH_NUMBER.get(long.group(1).lower())
        if month is None:
            return None
        try:
            return date(int(long.group(3)), month, int(long.group(2)))
        except ValueError:
            return None
    return parse_date(raw.strip())


def _nearest_date(text: str, at: int) -> tuple[date, str] | None:
    """The first date after the anchor, else the last one before it, within reach."""
    after = text[at : at + AFTER_CHARS]
    for found in DATE_RE.finditer(after):
        value = _as_date(found.group(0))
        if value is not None:
            return value, found.group(0)
    before = text[max(0, at - BEFORE_CHARS) : at]
    for found in reversed(list(DATE_RE.finditer(before))):
        value = _as_date(found.group(0))
        if value is not None:
            return value, found.group(0)
    return None


def read_entry_date(pages: dict[int, str]) -> JudgmentDate | None:
    """Read the entry date from the judgment pages' text, or say nothing.

    `pages` maps a 0-based page index to that page's text. The quote returned is the date
    exactly as printed, so it can be located on the page like any other evidence.
    """
    for anchor in ANCHORS:
        for index in sorted(pages):
            text = pages[index]
            for match in anchor.finditer(text):
                hit = _nearest_date(text, match.end())
                if hit is not None:
                    return JudgmentDate(value=hit[0], quote=hit[1], page=index)
    return None
