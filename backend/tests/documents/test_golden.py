"""The three demo cases' documents, word for word.

`tasks/lessons.md`: *snapshot the rendered output of anything a user will read* — the bug
that put "7:42 pm on 12 june 2025" in front of a court was invisible in the f-string and
obvious in the file. These documents are the most read-aloud thing ServeTrace produces, so
every sentence of them is pinned.

Like the engine's snapshots, these catch *change* and not correctness: they were written
by the code they test. What they are for is the moment somebody edits one sentence in
`documents/copy.py` and moves nine others without noticing, two days before a demo.

Regenerate deliberately, and read the diff:

    cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \\
        PYTHONPATH=.. uv run python -m tests.documents.test_golden
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.documents.affidavit import affidavit_context, build_paragraphs
from app.documents.packet import packet_context
from tests.documents.conftest import CASE_IDS, demo_analysis, demo_fixes, statement

GOLDEN = Path(__file__).resolve().parent / "golden"


def affiant_for(case_id: str) -> Any:
    """One affiant per case, with every tick on, so the snapshot covers every paragraph.

    Whether each tick *gates* its paragraph is asserted in `test_affidavit.py`. What this
    file pins is the wording, and a snapshot taken with the ticks off would pin less of it.
    """
    analysis = demo_analysis(case_id)
    return statement(
        name=analysis.affidavit.defendant_name,
        residence_address=analysis.affidavit.served_address,
        states_not_served=True,
        states_not_my_address=True,
        states_no_notice_in_time=True,
        defense_summary="I never opened an account with this company",
    )


def snapshot(case_id: str) -> dict[str, Any]:
    """Everything in both documents that a person reads, and nothing else.

    Coordinates and digests are left out: they are the input echoed back, they are
    asserted directly in `test_packet.py`, and a table of nineteen latitudes would bury
    the sentences this file exists to watch.
    """
    analysis = demo_analysis(case_id)
    packet = packet_context(analysis, demo_fixes(case_id), None, analysis.affidavit.defendant_name)
    affidavit = affidavit_context(analysis, affiant_for(case_id))

    return {
        "packet": {
            "intro": packet["intro"],
            "verdict": packet["verdict"],
            "claims": [
                {k: v for k, v in claim.items() if k != "tier_key"} for claim in packet["claims"]
            ],
            "findings": [
                {
                    "severity": f["severity"],
                    "title": f["title"],
                    "detail": f["detail"],
                    "legal_ref": f["legal_ref"],
                }
                for f in packet["findings"]
            ],
            "fixes_note": packet["fixes_note"],
            "deadlines": packet["deadlines"],
        },
        "affidavit": {
            "paragraphs": [
                {"source": p.source, "text": p.text}
                for p in build_paragraphs(analysis, affiant_for(case_id))
            ],
            "exhibits": affidavit["exhibits"],
        },
    }


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_the_documents_read_exactly_as_they_last_did(case_id: str) -> None:
    expected = json.loads((GOLDEN / f"{case_id}.json").read_text())
    assert snapshot(case_id) == expected


LOWER_CASE_CLOCK = re.compile(r"\d\s*[ap]\.?m\b")
"""A time written "7:42 pm". The engine's own version of this check searched for " am ",
which is a perfectly good English word in a document written in the first person — "I am
Maria Delarmo" failed it. The thing that is wrong is a lower-case meridiem *after a
number*, so that is what is looked for."""

NEVER_SAID = re.compile(r"\b(lied|lying|liar|fraud\w*|perjur\w*)\b")
"""Bible §6. Word boundaries because "relied" contains "lied", and `tasks/lessons.md`
already records the day a copy-discipline test matched a phrase instead of a word."""


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_no_sentence_starts_lower_case_in_a_court_document(case_id: str) -> None:
    """The `str.capitalize()` bug in `tasks/lessons.md`, asserted where it would land."""
    for paragraph in build_paragraphs(demo_analysis(case_id), affiant_for(case_id)):
        for sentence in paragraph.text.split(". "):
            assert sentence[:1] == sentence[:1].upper(), paragraph.text
        assert not LOWER_CASE_CLOCK.search(paragraph.text), paragraph.text


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_no_document_ever_says_anybody_lied(case_id: str) -> None:
    """Bible §6. ServeTrace says data conflicts, and it says it in court too.

    This is the sharpest place in the product for that rule: everything else is a screen
    somebody can close, and this is a sworn paragraph with their signature under it.
    """
    for paragraph in build_paragraphs(demo_analysis(case_id), affiant_for(case_id)):
        assert not NEVER_SAID.search(paragraph.text.lower()), paragraph.text


def regenerate() -> None:  # pragma: no cover - a maintenance command, not a test
    GOLDEN.mkdir(exist_ok=True)
    for case_id in CASE_IDS:
        path = GOLDEN / f"{case_id}.json"
        path.write_text(json.dumps(snapshot(case_id), indent=1, sort_keys=True) + "\n")
        print(f"wrote {path}")


if __name__ == "__main__":  # pragma: no cover
    regenerate()
