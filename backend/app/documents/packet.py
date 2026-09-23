"""Evidence Packet PDF. Deterministic Jinja2 + WeasyPrint, never an LLM. Bible §15. Session 5."""

from app.domain.models import CaseAnalysis


def build_packet(analysis: CaseAnalysis, map_png: bytes | None) -> bytes:
    raise NotImplementedError("Session 5")
