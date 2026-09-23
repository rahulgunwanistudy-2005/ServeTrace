"""Deterministic post-checks on whatever the LLM returned. Bible §12.

Nothing in this module asks a model anything. Every note it produces is reproducible from
the draft and the document's text layer alone, which is what lets the Methodology page
describe the checks exactly and lets the tests pin them one by one.

The output is never a rejection. A draft that fails every check still comes back, with the
failing fields flagged and their confidence capped, because the user can correct a field
they can see and cannot correct one that was silently dropped.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time
from difflib import SequenceMatcher
from typing import Final
from zoneinfo import ZoneInfo

from app.domain.models import AffidavitDraft, AttemptDraft, ValidationNote
from app.engine.params import PARAMS

TZ: Final = ZoneInfo(PARAMS.tz)

GROUNDING_MIN_RATIO: Final = 0.90
"""Bible §12. Below this the quote is not considered to come from the document."""

UNGROUNDED_CAP: Final = 0.5
"""Confidence ceiling for a value whose quote is not in the text layer, or has no quote."""

NO_TEXT_LAYER_CAP: Final = 0.6
"""Bible §12. Nothing read off a scan can be checked, so nothing off a scan is trusted."""

FLAGGED_CAP: Final = 0.4
"""Confidence ceiling for a value a deterministic check found implausible."""

MAILING_MAX_DAYS: Final = 60
"""Bible §12 sanity bound. The 20-day legal rule is R-T2's job, in the engine, not here."""

LICENSE_RE: Final = re.compile(r"^\d{7}$")
"""NYC process server and agency licence numbers are seven digits."""

_DATE_FORMATS: Final = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y")
_TIME_FORMATS: Final = ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I:%M:%S %p")

_METHOD_ALIASES: Final[dict[str, str]] = {
    "308_1": "308_1",
    "3081": "308_1",
    "308(1)": "308_1",
    "personal": "308_1",
    "personal service": "308_1",
    "308_2": "308_2",
    "3082": "308_2",
    "308(2)": "308_2",
    "substitute": "308_2",
    "substituted": "308_2",
    "substituted service": "308_2",
    "suitable age": "308_2",
    "308_4": "308_4",
    "3084": "308_4",
    "308(4)": "308_4",
    "affix": "308_4",
    "affix and mail": "308_4",
    "nail and mail": "308_4",
    "conspicuous": "308_4",
}

_METHOD_KEYWORDS: Final[tuple[tuple[str, str], ...]] = (
    # Order matters: 308(4) says "suitable age and discretion" too, in the negative
    # ("unable to find ... a person of suitable age and discretion"), so it is tested first.
    ("affixing", "308_4"),
    ("affixed", "308_4"),
    ("conspicuous place", "308_4"),
    ("door of said premises", "308_4"),
    ("suitable age and discretion", "308_2"),
    ("person of suitable age", "308_2"),
    ("personally", "308_1"),
    ("personal service", "308_1"),
)

_WHITESPACE = re.compile(r"\s+")


_TYPOGRAPHY = {
    0x2018: "'",
    0x2019: "'",
    0x201C: '"',
    0x201D: '"',
    0x2013: "-",
    0x2014: "-",
    0x00A0: " ",
}
"""Curly quotes, dashes and hard spaces a PDF text layer produces but a quote may not."""


def _normalize(text: str) -> str:
    """Case, whitespace and typography are not evidence. The words are."""
    return _WHITESPACE.sub(" ", text.translate(_TYPOGRAPHY)).strip().lower()


def grounding_ratio(source_text: str, quote: str) -> float:
    """How well `quote` matches some span of `source_text`, 0 to 1.

    An exact match after normalisation scores 1. Otherwise the longest run the two have in
    common locates the span, and the ratio is measured against a window the same length as
    the quote, nudged a few characters either way. Measuring against a longer window would
    punish a quote for the text around it, which is how a one-character OCR slip ends up
    looking like an invented quote.
    """
    haystack = _normalize(source_text)
    needle = _normalize(quote)
    if not needle or not haystack:
        return 0.0
    if needle in haystack:
        return 1.0

    size = len(needle)
    matcher = SequenceMatcher(None, haystack, needle, autojunk=False)
    anchor = matcher.find_longest_match(0, len(haystack), 0, size)
    if anchor.size == 0:
        return 0.0

    aligned = anchor.a - anchor.b
    slack = max(2, size // 10)
    best = 0.0
    window_matcher = SequenceMatcher(None, autojunk=False)
    window_matcher.set_seq2(needle)
    for offset in range(-slack, slack + 1):
        begin = aligned + offset
        if begin < 0 or begin + size > len(haystack):
            continue
        window_matcher.set_seq1(haystack[begin : begin + size])
        best = max(best, window_matcher.ratio())
    return best


def parse_date(text: str | None) -> date | None:
    if not text:
        return None
    candidate = text.strip().replace(".", "")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return None


def parse_time(text: str | None) -> time | None:
    if not text:
        return None
    candidate = _WHITESPACE.sub(" ", text.strip().replace(".", "")).upper()
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).time()
        except ValueError:
            continue
    return None


def localize(day: date, clock: time) -> tuple[datetime, bool]:
    """Attach America/New_York to a wall-clock reading, and say whether it is ambiguous.

    Bible §11.1: an affidavit prints a local time with no offset. Twice a year that means
    two different instants, or none at all. Both cases are flagged here and resolved
    conservatively by the engine; neither is guessed at.
    """
    local = datetime.combine(day, clock, tzinfo=TZ)
    folded = local.replace(fold=1)
    ambiguous = local.utcoffset() != folded.utcoffset()
    nonexistent = local.astimezone(UTC).astimezone(TZ).replace(tzinfo=TZ) != local
    return local, ambiguous or nonexistent


def normalize_method(value: str | None) -> str | None:
    """Map whatever the model wrote onto a `ServiceMethod` value, or give up."""
    if not value:
        return None
    key = _normalize(value)
    if key in _METHOD_ALIASES:
        return _METHOD_ALIASES[key]
    for alias, method in _METHOD_ALIASES.items():
        if alias in key:
            return method
    return None


def infer_method(source_text: str | None) -> tuple[str, str] | None:
    """Bible §12: fall back to the form's own wording when the model would not commit.

    Returns the method and the verbatim span it was read from, so an inferred value is
    evidenced on the page exactly like an extracted one and the user can see why.
    """
    if not source_text:
        return None
    for keyword, method in _METHOD_KEYWORDS:
        pattern = re.compile(
            r"\s+".join(re.escape(word) for word in keyword.split()), re.IGNORECASE
        )
        found = pattern.search(source_text)
        if found:
            return method, found.group(0)
    return None


class _Notes:
    """Collects notes and confidence caps so each check stays a few readable lines."""

    def __init__(self, confidence: dict[str, float]) -> None:
        self.notes: list[ValidationNote] = []
        self.confidence = dict(confidence)

    def add(self, field: str, level: str, message: str, cap: float | None = None) -> None:
        self.notes.append(
            ValidationNote(
                field=field,
                level="info" if level == "info" else "warning" if level == "warning" else "error",
                message=message,
            )
        )
        if cap is not None:
            self.cap(field, cap)

    def cap(self, field: str, ceiling: float) -> None:
        current = self.confidence.get(field)
        self.confidence[field] = ceiling if current is None else min(current, ceiling)


def _check_grounding(draft: AffidavitDraft, source_text: str | None, notes: _Notes) -> None:
    """Every quoted field must be traceable to the document. Bible §12."""
    if source_text is None:
        for field in list(notes.confidence) + _valued_fields(draft):
            notes.cap(field, NO_TEXT_LAYER_CAP)
        return

    for field in _valued_fields(draft):
        quote = draft.evidence_quotes.get(field)
        if not quote:
            notes.add(
                field,
                "warning",
                "We could not point to where this came from on the document. Please check it.",
                UNGROUNDED_CAP,
            )
            continue
        if grounding_ratio(source_text, quote) < GROUNDING_MIN_RATIO:
            notes.add(
                field,
                "warning",
                "We could not find these words on the document. Please check this one.",
                UNGROUNDED_CAP,
            )


def _valued_fields(draft: AffidavitDraft) -> list[str]:
    """The fields the extractor actually filled in, in a stable order."""
    named = [
        name
        for name in (
            "index_number",
            "court",
            "plaintiff",
            "defendant_name",
            "server_name",
            "server_license",
            "agency_license",
            "method",
            "served_date",
            "served_time",
            "served_address",
            "recipient_name",
            "recipient_relationship",
            "recipient_description",
            "mailing_date",
            "mailing_address",
            "proof_filed_date",
        )
        if getattr(draft, name, None)
    ]
    return named + [f"attempts[{i}]" for i in range(len(draft.attempts))]


def _check_licences(draft: AffidavitDraft, notes: _Notes) -> None:
    for field in ("server_license", "agency_license"):
        value = getattr(draft, field)
        if value and not LICENSE_RE.match(value.strip()):
            notes.add(
                field,
                "warning",
                "A New York City process server licence number is seven digits. "
                "Please check this one.",
                FLAGGED_CAP,
            )


def _resolve_attempts(draft: AffidavitDraft, notes: _Notes) -> list[AttemptDraft]:
    resolved: list[AttemptDraft] = []
    for index, attempt in enumerate(draft.attempts):
        day = parse_date(attempt.at_date)
        clock = parse_time(attempt.at_time)
        if day is None or clock is None:
            notes.add(
                f"attempts[{index}]",
                "warning",
                "We could not read the date and time of this earlier attempt.",
                FLAGGED_CAP,
            )
            resolved.append(attempt)
            continue
        when, _ = localize(day, clock)
        resolved.append(
            attempt.model_copy(
                update={
                    "at": when,
                    "at_date": day.isoformat(),
                    "at_time": clock.strftime("%H:%M"),
                }
            )
        )
    return resolved


def _resolve_service_datetime(
    draft: AffidavitDraft, notes: _Notes, now: datetime
) -> dict[str, object]:
    day = parse_date(draft.served_date)
    clock = parse_time(draft.served_time)
    update: dict[str, object] = {}

    if day is None:
        if draft.served_date:
            notes.add("served_date", "error", "We could not read this date.", 0.0)
        return update
    update["served_date"] = day.isoformat()

    if clock is None:
        if draft.served_time:
            notes.add("served_time", "error", "We could not read this time.", 0.0)
        return update
    update["served_time"] = clock.strftime("%H:%M")

    served_at, ambiguous = localize(day, clock)
    update["served_at"] = served_at
    update["served_at_ambiguous"] = ambiguous
    if ambiguous:
        notes.add(
            "served_time",
            "info",
            "The clocks changed that night, so this time could mean one of two moments. "
            "We check both and use whichever is better for the affidavit.",
        )
    if served_at > now:
        notes.add(
            "served_date",
            "warning",
            "This date is in the future. Please check it against your papers.",
            FLAGGED_CAP,
        )
    return update


def _check_mailing(draft: AffidavitDraft, served_day: date | None, notes: _Notes) -> str | None:
    """Sanity only. Whether the mailing is *legally* in time is R-T2's job, in the engine."""
    if not draft.mailing_date:
        return None
    mailed = parse_date(draft.mailing_date)
    if mailed is None:
        notes.add("mailing_date", "warning", "We could not read this date.", FLAGGED_CAP)
        return draft.mailing_date
    if served_day is not None and abs((mailed - served_day).days) > MAILING_MAX_DAYS:
        notes.add(
            "mailing_date",
            "warning",
            "This mailing date is months away from the date of service. Please check it.",
            FLAGGED_CAP,
        )
    return mailed.isoformat()


def validate(
    draft: AffidavitDraft, source_text: str | None, now: datetime | None = None
) -> tuple[AffidavitDraft, list[ValidationNote]]:
    """Normalise a draft and say, field by field, what is worth a second look.

    `now` is a parameter so the "service is not in the future" check is testable without
    the wall clock deciding whether the suite passes.
    """
    moment = now or datetime.now(UTC)
    notes = _Notes(draft.field_confidence)
    update: dict[str, object] = {}

    method = normalize_method(draft.method)
    if method is None:
        inferred = infer_method(source_text)
        if inferred is not None:
            method, quote = inferred
            update["evidence_quotes"] = {**draft.evidence_quotes, "method": quote}
            notes.add(
                "method",
                "info",
                "We worked out how service was claimed from the wording of the affidavit.",
                UNGROUNDED_CAP,
            )
    if method is not None:
        update["method"] = method
    elif draft.method:
        # The model said something, and it maps to nothing. "unknown" is the honest value,
        # and the engine's R-M1 raises it again once the user has had a chance to correct it.
        notes.add("method", "warning", "We could not tell how service was claimed.", 0.0)
        update["method"] = "unknown"
    else:
        update["method"] = None

    update |= _resolve_service_datetime(draft, notes, moment)
    served_day = parse_date(str(update.get("served_date") or draft.served_date or "")) or None
    update["mailing_date"] = _check_mailing(draft, served_day, notes)

    filed = parse_date(draft.proof_filed_date)
    if draft.proof_filed_date and filed is None:
        notes.add("proof_filed_date", "warning", "We could not read this date.", FLAGGED_CAP)
    update["proof_filed_date"] = filed.isoformat() if filed else draft.proof_filed_date

    _check_licences(draft, notes)
    update["attempts"] = _resolve_attempts(draft, notes)

    normalized = draft.model_copy(update=update)
    _check_grounding(normalized, source_text, notes)
    normalized = normalized.model_copy(update={"field_confidence": notes.confidence})
    return normalized, notes.notes
