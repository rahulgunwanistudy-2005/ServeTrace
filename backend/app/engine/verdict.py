"""Combine claim verdicts and findings into one case verdict. Bible §11.1.6. Session 3."""

from app.domain.models import AnalyzeRequest, CaseAnalysis


def analyze(request: AnalyzeRequest) -> CaseAnalysis:
    raise NotImplementedError("Session 3")
