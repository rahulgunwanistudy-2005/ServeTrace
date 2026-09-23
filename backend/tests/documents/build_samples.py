"""Write the committed samples in `docs/samples/`. A maintenance command, not a test.

    cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \\
        PYTHONPATH=.. uv run python -m tests.documents.build_samples

It lives beside the document tests and reuses their builders on purpose: the samples have
to be what the code actually produces, and a separate script with its own fixtures would
drift into being a picture of something nobody downloads.
"""

from __future__ import annotations

from pathlib import Path

from app.documents.affidavit import build_draft_affidavit
from app.documents.packet import build_packet
from tests.documents.conftest import demo_analysis, demo_fixes, statement

SAMPLES = Path(__file__).resolve().parents[3] / "docs" / "samples"
CASE = "maria_contradicted"


def build() -> None:
    analysis = demo_analysis(CASE)
    affiant = statement(
        name=analysis.affidavit.defendant_name,
        residence_address="1275 Grand Concourse, Apt 4B, Bronx, NY 10452",
        states_not_served=True,
        states_not_my_address=True,
        states_no_notice_in_time=True,
        defense_summary="I never opened an account with this company",
    )

    documents = {
        "evidence-packet.pdf": build_packet(
            analysis, demo_fixes(CASE), None, analysis.affidavit.defendant_name
        ),
        "draft-affidavit.pdf": build_draft_affidavit(analysis, affiant),
    }
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for name, pdf in documents.items():
        (SAMPLES / name).write_bytes(pdf)
        print(f"wrote {SAMPLES / name} ({len(pdf):,} bytes)")


if __name__ == "__main__":
    build()
