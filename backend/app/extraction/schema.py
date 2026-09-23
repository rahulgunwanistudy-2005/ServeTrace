"""The contract between the model and ServeTrace. Bible §12.

One JSON Schema is handed to every provider and one parser reads every provider's answer,
so "what the model may say" and "what we do with it" cannot drift apart. The shape is
deliberately boring: every scalar field is `{value, confidence, evidence_quote}`, because
a per-field quote is what makes the grounding check in `validators.py` possible at all.

Nothing here interprets a value. Dates stay strings, `method` stays a string, and every
judgement about them is made deterministically in `validators.py`.
"""

from __future__ import annotations

from typing import Any, Final

from app.domain.models import AffidavitDraft, AttemptDraft, PersonDescription

SCALAR_FIELDS: Final[tuple[str, ...]] = (
    "index_number",
    "court",
    "plaintiff",
    "defendant_name",
    "server_name",
    "server_license",
    "agency_license",
    "method",
    "served_date",
    "served_time",
    "served_address",
    "recipient_name",
    "recipient_relationship",
    "mailing_date",
    "mailing_address",
    "proof_filed_date",
)
"""Every top-level field the model is asked for. Each is a field object in the payload and
a field of the same name on `AffidavitDraft`; a test asserts that correspondence."""

METHOD_VALUES: Final[tuple[str, ...]] = ("308_1", "308_2", "308_4", "unknown")

_DESCRIPTION_INTS: Final[tuple[str, ...]] = (
    "age_min",
    "age_max",
    "height_in_min",
    "height_in_max",
    "weight_lb_min",
    "weight_lb_max",
)


def _field(description: str, *, enum: tuple[str, ...] | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"type": "string", "description": description}
    if enum is not None:
        value["enum"] = list(enum)
    return {
        "type": "object",
        "properties": {
            "value": value,
            "confidence": {
                "type": "number",
                "description": "0 to 1. How sure you are this is what the document says.",
            },
            "evidence_quote": {
                "type": "string",
                "description": "The span of the document this was read from, copied verbatim.",
            },
        },
        "required": ["value", "confidence", "evidence_quote"],
    }


_FIELD_HELP: Final[dict[str, str]] = {
    "index_number": "The court index number, exactly as printed.",
    "court": "The full name of the court, including the county.",
    "plaintiff": "The plaintiff named in the caption.",
    "defendant_name": "The defendant named in the caption.",
    "server_name": "The process server who swore the affidavit.",
    "server_license": "The process server's licence number.",
    "agency_license": "The process serving agency's licence number.",
    "method": "How service is claimed to have been made.",
    "served_date": "Date of the claimed service, normalised to YYYY-MM-DD.",
    "served_time": "Local time of the claimed service, normalised to 24-hour HH:MM.",
    "served_address": "The address where service is claimed, as printed.",
    "recipient_name": "The person the papers were handed to, if named.",
    "recipient_relationship": "That person's stated relationship to the defendant.",
    "mailing_date": "Date of the follow-up mailing, normalised to YYYY-MM-DD.",
    "mailing_address": "The address the follow-up copy was mailed to.",
    "proof_filed_date": "Date proof of service was filed, normalised to YYYY-MM-DD.",
}


def response_json_schema() -> dict[str, Any]:
    """The schema handed to the provider. Flat and $ref-free so every provider accepts it."""
    properties: dict[str, Any] = {
        name: _field(_FIELD_HELP[name], enum=METHOD_VALUES if name == "method" else None)
        for name in SCALAR_FIELDS
    }
    properties["recipient_description"] = {
        "type": "object",
        "description": "The description of the person served, from the description block.",
        "properties": {
            "sex": {"type": "string", "enum": ["male", "female", "unknown"]},
            **{
                name: {"type": "integer", "description": f"{name.replace('_', ' ')}, if given."}
                for name in _DESCRIPTION_INTS
            },
            "hair": {"type": "string"},
            "raw_text": {"type": "string", "description": "The description block, verbatim."},
            "confidence": {"type": "number"},
            "evidence_quote": {"type": "string"},
        },
    }
    properties["attempts"] = {
        "type": "array",
        "description": "Prior attempts at service listed on the affidavit, in order.",
        "items": {
            "type": "object",
            "properties": {
                "at_date": {"type": "string", "description": "YYYY-MM-DD."},
                "at_time": {"type": "string", "description": "24-hour HH:MM."},
                "address": {"type": "string"},
                "outcome": {
                    "type": "string",
                    "enum": ["served", "affixed", "not_home", "refused", "other"],
                },
                "confidence": {"type": "number"},
                "evidence_quote": {"type": "string"},
            },
        },
    }
    return {
        "type": "object",
        "description": "Fields read from a New York affidavit of service.",
        "properties": properties,
    }


def _as_mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _clean_str(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_confidence(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return min(1.0, max(0.0, float(value)))


def _clean_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = value.strip()
        try:
            return int(digits)
        except ValueError:
            return None
    return None


def _read_field(payload: dict[str, Any], name: str) -> tuple[str | None, float | None, str | None]:
    """A field object, or a bare scalar when the model flattened it anyway."""
    raw = payload.get(name)
    if isinstance(raw, dict):
        return (
            _clean_str(raw.get("value")),
            _clean_confidence(raw.get("confidence")),
            _clean_str(raw.get("evidence_quote")),
        )
    return _clean_str(raw), None, None


def _description_from(
    payload: dict[str, Any],
) -> tuple[PersonDescription | None, float | None, str | None]:
    block = _as_mapping(payload.get("recipient_description"))
    if not block:
        return None, None, None

    sex = _clean_str(block.get("sex"))
    description = PersonDescription(
        sex=sex if sex in ("male", "female", "unknown") else None,
        age_min=_clean_int(block.get("age_min")),
        age_max=_clean_int(block.get("age_max")),
        height_in_min=_clean_int(block.get("height_in_min")),
        height_in_max=_clean_int(block.get("height_in_max")),
        weight_lb_min=_clean_int(block.get("weight_lb_min")),
        weight_lb_max=_clean_int(block.get("weight_lb_max")),
        hair=_clean_str(block.get("hair")),
        raw_text=_clean_str(block.get("raw_text")),
    )
    if description == PersonDescription():
        return None, None, None
    return (
        description,
        _clean_confidence(block.get("confidence")),
        _clean_str(block.get("evidence_quote")),
    )


def draft_from_payload(payload: object) -> AffidavitDraft:
    """Turn whatever JSON the provider returned into a draft, discarding what makes no sense.

    Tolerant by design. A model that omits a field, flattens a field object or answers
    "N/A" must cost that one field, never the whole document.
    """
    body = _as_mapping(payload)
    values: dict[str, Any] = {}
    confidence: dict[str, float] = {}
    quotes: dict[str, str] = {}

    for name in SCALAR_FIELDS:
        value, score, quote = _read_field(body, name)
        if value is not None:
            values[name] = value
        if score is not None:
            confidence[name] = score
        if quote is not None:
            quotes[name] = quote

    description, desc_confidence, desc_quote = _description_from(body)
    if description is not None:
        values["recipient_description"] = description
        if desc_confidence is not None:
            confidence["recipient_description"] = desc_confidence
        if desc_quote is not None:
            quotes["recipient_description"] = desc_quote

    attempts: list[AttemptDraft] = []
    raw_attempts = body.get("attempts")
    for index, item in enumerate(raw_attempts if isinstance(raw_attempts, list) else []):
        entry = _as_mapping(item)
        if not entry:
            continue
        attempts.append(
            AttemptDraft(
                at_date=_clean_str(entry.get("at_date")),
                at_time=_clean_str(entry.get("at_time")),
                address=_clean_str(entry.get("address")),
                outcome=_clean_str(entry.get("outcome")),
            )
        )
        score = _clean_confidence(entry.get("confidence"))
        if score is not None:
            confidence[f"attempts[{index}]"] = score
        quote = _clean_str(entry.get("evidence_quote"))
        if quote is not None:
            quotes[f"attempts[{index}]"] = quote

    return AffidavitDraft(
        **values,
        attempts=attempts,
        field_confidence=confidence,
        evidence_quotes=quotes,
    )
