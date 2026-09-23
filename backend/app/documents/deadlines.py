"""CPLR 317 deadline arithmetic. Encodes bible §5 L6 only. Session 5."""

from datetime import date

from app.domain.models import Deadlines


def compute_deadlines(knowledge_date: date | None, judgment_entry_date: date | None) -> Deadlines:
    raise NotImplementedError("Session 5")
