"""New York timing and due-diligence rules R-T1..R-M1. Bible §11.3. Session 3.

Every finding this module emits carries the L-id from bible §5 that it encodes.
No legal statement may originate here that is not in that table.
"""

from app.domain.models import Affidavit, ClaimVerdict, Finding


def check_rules(affidavit: Affidavit, verdicts: list[ClaimVerdict]) -> list[Finding]:
    raise NotImplementedError("Session 3")
