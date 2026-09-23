"""Advocate CSV and PDF report rendering. Bible §14.6. Session 4."""

from app.domain.models import ServerReport


def to_csv(reports: list[ServerReport]) -> bytes:
    raise NotImplementedError("Session 4")


def to_pdf(reports: list[ServerReport]) -> bytes:
    raise NotImplementedError("Session 4")
