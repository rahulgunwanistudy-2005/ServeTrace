"""Deterministic post-checks on whatever the LLM returned. Bible §12. Session 2."""

from app.extraction.vision import ExtractionResult


def validate(result: ExtractionResult, source_text: str | None) -> ExtractionResult:
    """Date sanity, licence pattern, method inference, evidence-quote grounding.

    A field whose `evidence_quote` does not appear in the source text layer has its
    confidence capped, so the UI flags it for the user to correct.
    """
    raise NotImplementedError("Session 2")
