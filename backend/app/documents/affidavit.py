"""Draft supporting affidavit. Numbered paragraphs from confirmed fields only.

Attaches to the court's own Order to Show Cause form; it does not replace it.
Bible §15. Session 5.
"""

from app.domain.models import CaseAnalysis


def build_draft_affidavit(analysis: CaseAnalysis) -> bytes:
    raise NotImplementedError("Session 5")
