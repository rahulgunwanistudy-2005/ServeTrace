"""Where on the page a value was read. Bible §12 (v1.1).

The model returns, for every field, the words it read and the page they were on. On a
PDF with a text layer those words can be found again among pdfplumber's word boxes, and
the union of the matching boxes is drawn on the review screen, so the person checking a
field looks at the words on their own document rather than taking ServeTrace's word for
it.

The match is fuzzy for the same reason grounding is (validators.py): a text layer and a
model's copy of it differ in hyphens, curly quotes and line breaks. The bar is the same
0.90, measured against a window of words the same length as the quote. A quote that is
not found gets no box; the confidence cap for an ungrounded quote is the validators' job,
not this module's.
"""

from __future__ import annotations

from collections.abc import Sequence
from difflib import SequenceMatcher
from typing import Final

from app.extraction.pdf_text import Word
from app.extraction.validators import GROUNDING_MIN_RATIO, _normalize

BBox = tuple[float, float, float, float]

MAX_WINDOW_SLACK: Final = 3
"""Words either side of the quote's own word count tried as the window."""


def _union(words: Sequence[Word]) -> BBox:
    return (
        round(min(w.x0 for w in words), 2),
        round(min(w.top for w in words), 2),
        round(max(w.x1 for w in words), 2),
        round(max(w.bottom for w in words), 2),
    )


def _best_window(
    words: Sequence[Word], needle: str, *, every_start: bool = False
) -> tuple[float, int, int]:
    """(ratio, start, end) of the run of words that best matches the quote.

    By default only windows whose first word starts with the quote's first character are
    scored: a 600-word page is otherwise 600 x 7 full comparisons per field. `every_start`
    drops that shortcut, for the second pass on a quote the first pass did not find.
    """
    tokens = [_normalize(w.text) for w in words]
    target = len(needle.split())
    matcher = SequenceMatcher(None, autojunk=False)
    matcher.set_seq2(needle)
    best = (0.0, 0, 0)
    for start in range(len(tokens)):
        if not every_start and tokens[start][:1] != needle[:1]:
            continue
        for size in range(max(1, target - MAX_WINDOW_SLACK), target + MAX_WINDOW_SLACK + 1):
            end = start + size
            if end > len(tokens):
                break
            matcher.set_seq1(" ".join(tokens[start:end]))
            ratio = matcher.ratio()
            if ratio > best[0]:
                best = (ratio, start, end)
                if ratio == 1.0:
                    return best
    return best


def locate(
    quote: str | None,
    words_by_page: Sequence[Sequence[Word]],
    pages: Sequence[int],
    preferred: int | None = None,
) -> tuple[int, BBox] | None:
    """Find the quote among the given pages' words: (page, box) or None.

    The page the model named is searched first, then the rest of the affidavit's pages,
    because a model asked for a page number is right about the words more often than
    about the page.
    """
    needle = _normalize(quote or "")
    if not needle:
        return None
    first = [preferred] if preferred is not None and preferred in pages else []
    order: list[int] = first + [p for p in pages if p != preferred]
    for every_start in (False, True):
        best: tuple[float, int, BBox] | None = None
        for page in order:
            if not 0 <= page < len(words_by_page):
                continue
            words = words_by_page[page]
            if not words:
                continue
            ratio, start, end = _best_window(words, needle, every_start=every_start)
            if ratio >= GROUNDING_MIN_RATIO and (best is None or ratio > best[0]):
                best = (ratio, page, _union(words[start:end]))
                if ratio == 1.0:
                    break
        if best is not None:
            return best[1], best[2]
    return None
