"""What each page of an upload is, before anything reads fields off it. Bible §12 (v1.1).

People upload the whole court file: summons, complaint, the affidavit of service, the
default judgment. Only the affidavit pages go to field extraction, so a model is never
asked to find a process server's sworn time on page 2 of a complaint.

**Text-layer pages** are classified here, deterministically, by keyword scoring. Every
cue is a phrase the forms print; the scores are reproducible from the page text alone and
the tests pin them. **Image-only pages** are classified by one model call over small
thumbnails (`vision.py`); when that call fails or answers nonsense, every image page is
treated as a candidate affidavit page, because reading one page too many costs the user a
second of review and skipping the affidavit costs them the whole check.

**Continuation pages.** An affidavit runs onto a second page more often than not: the
attempts, the mailing paragraph, the signature and the notary. That page carries few
cues of its own, so a page that follows an affidavit page and is not confidently something
else is read as part of it.

**Several affidavits in one file** are split where a page carries the opening of an
affidavit ("being duly sworn") after a run that already had one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from app.domain.models import PageType

THRESHOLD: Final = 3.0
"""Below this, a page is OTHER. One stray "complaint" is not a complaint."""

PER_CUE_CAP: Final = 3
"""A word repeated down a page counts at most this many times."""

CUES: Final[dict[PageType, tuple[tuple[str, float], ...]]] = {
    PageType.AFFIDAVIT_OF_SERVICE: (
        ("affidavit of service", 2.0),
        ("being duly sworn", 2.0),
        ("licensed process server", 2.0),
        ("process server", 1.0),
        ("served the within", 2.0),
        ("deponent", 1.0),
        ("deposes and says", 2.0),
    ),
    PageType.JUDGMENT: (
        ("judgment", 1.0),
        ("entered", 1.0),
        ("clerk", 1.0),
        ("default", 1.0),
        ("judgment is entered", 2.0),
        ("default judgment", 2.0),
    ),
    PageType.SUMMONS_COMPLAINT: (
        ("summons", 1.0),
        ("complaint", 1.0),
        ("plaintiff demands", 2.0),
        ("you are hereby summoned", 2.0),
        # A verified complaint ends with a verification that is itself sworn ("being duly
        # sworn, deposes and says"), so without these that page reads as an affidavit.
        ("verified complaint", 2.0),
        ("verification", 2.0),
        ("foregoing complaint", 2.0),
    ),
}
"""Bible §12 v1.1 names the first cues of each group; the multi-word ones after them are
phrases the same forms print, weighted higher because they are hard to say by accident."""

MAX_CONTINUATION_RUN: Final = 3
"""An affidavit is one to three pages. Unlabelled pages beyond that are exhibits or
blank backs, not more of the affidavit, and are left alone."""

START_CUES: Final = ("being duly sworn", "deposes and says")
"""The opening of an affidavit. A second one in a run starts a second affidavit."""

_SPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _SPACE.sub(" ", text).lower()


def _count(haystack: str, phrase: str) -> int:
    return len(re.findall(r"\b" + re.escape(phrase) + r"\b", haystack))


def scores(text: str) -> dict[PageType, float]:
    """Each page type's score for one page of text."""
    haystack = _normalize(text)
    return {
        page_type: sum(min(_count(haystack, cue), PER_CUE_CAP) * w for cue, w in cues)
        for page_type, cues in CUES.items()
    }


def classify_text(text: str) -> PageType:
    """The highest-scoring type at or above the threshold, else OTHER.

    A tie that includes the affidavit goes to the affidavit, so a page that might be one is
    read rather than skipped.
    """
    ranked = scores(text)
    best = max(ranked.values())
    if best < THRESHOLD:
        return PageType.OTHER
    if ranked[PageType.AFFIDAVIT_OF_SERVICE] == best:
        return PageType.AFFIDAVIT_OF_SERVICE
    return max(ranked, key=lambda t: (ranked[t], t.value))


def starts_affidavit(text: str) -> bool:
    haystack = _normalize(text)
    return any(cue in haystack for cue in START_CUES)


@dataclass(frozen=True, slots=True)
class Grouping:
    page_types: list[PageType]
    """Final types, with continuation pages re-labelled as affidavit pages."""
    affidavits: list[list[int]]
    """0-based page indexes of each affidavit found, in file order."""
    continuations: list[int]
    """Pages that were OTHER and were read as part of the affidavit before them."""


def group(page_types: list[PageType], starts: list[bool]) -> Grouping:
    """Turn per-page types into affidavits, folding continuation pages in.

    `starts[i]` says page i opens an affidavit. For an image page nobody can tell, and it
    is False: an unreadable page next to an affidavit is read as part of that affidavit.
    """
    final = list(page_types)
    runs: list[list[int]] = []
    continuations: list[int] = []
    current: list[int] | None = None
    current_has_start = False

    for index, page_type in enumerate(page_types):
        if page_type is PageType.AFFIDAVIT_OF_SERVICE:
            if current is not None and not (starts[index] and current_has_start):
                current.append(index)
                current_has_start = current_has_start or starts[index]
                continue
            current = [index]
            current_has_start = starts[index]
            runs.append(current)
            continue
        if (
            page_type is PageType.OTHER
            and current is not None
            and not starts[index]
            and len(current) < MAX_CONTINUATION_RUN
        ):
            current.append(index)
            final[index] = PageType.AFFIDAVIT_OF_SERVICE
            continuations.append(index)
            continue
        current = None
        current_has_start = False

    return Grouping(page_types=final, affidavits=runs, continuations=continuations)
