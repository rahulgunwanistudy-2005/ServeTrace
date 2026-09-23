"""The Evidence Packet. Bible §15.

A deterministic rendering of a `CaseAnalysis`: cover verdict, the map the person saw, one
row per sworn moment, the findings with the provision each encodes, the location records
the check ran over, the thresholds it ran under, and a digest of both inputs.

Three things about this document are deliberate.

**It shows every record, not the decisive ones.** The engine leans on two or three fixes
per claim. A packet that printed only those would invite the one question it exists to
answer, so it prints the whole windowed set — the records that were sent — and says how
many there were. The rest of the person's location history never left their device and is
not here to print.

**It carries digests, not copies.** The affidavit PDF and the location records are the
person's own; the packet names them by SHA-256 so that anyone holding the same files can
confirm this packet describes those and not something else, without the packet becoming a
second copy of data that should travel as an exhibit.

**It takes its timestamp from the analysis.** `CaseAnalysis.generated_at` is the moment
the numbers were computed, which is what this document reports; a second clock read at
download time would be a different, less meaningful number, and would make the bytes
non-reproducible for no gain.

No LLM. Ever (bible §15).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
from typing import Any, Final

from app.api.errors import BadInputError
from app.documents import copy
from app.documents.deadlines import effective_deadline
from app.documents.render import render_pdf
from app.domain.models import (
    Affidavit,
    CaseAnalysis,
    ClaimVerdict,
    Finding,
    LocationFix,
)
from app.engine.params import PARAMS

TEMPLATE: Final = "packet.html.j2"

MAX_MAP_BYTES: Final = 3 * 1024 * 1024
"""Bible §15. A map bigger than this is not a map of New York, it is a mistake."""

MAX_MAP_PIXELS: Final = 4096
"""Per side. A canvas capture is a few thousand pixels wide at most; anything far beyond
that is either a decompression bomb or a screenshot of something else."""

MAX_FIXES_IN_TABLE: Final = 500
"""Bible §16 allows 5,000 fixes per analysis, which is roughly eighty pages of table.

The packet is an exhibit, so it may not quietly shorten itself: over this many records it
prints the first `MAX_FIXES_IN_TABLE`, says how many of how many, and the digest above the
table still covers every one of them.
"""


def fixes_digest(fixes: list[LocationFix]) -> str:
    """SHA-256 over the canonical JSON of the records, in the order they were sent.

    Canonical because a digest that changes with key order proves nothing: sorted keys,
    no whitespace, dates as the wire format. Order of the list itself is preserved rather
    than sorted — it is part of what was sent.
    """
    payload = json.dumps(
        [fix.model_dump(mode="json") for fix in fixes],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_map_png(encoded: str) -> str:
    """Return a `data:` URI for a capture that really is a PNG, or refuse it.

    Refusing is cheap and the alternative is not: this string arrives from a browser, goes
    into a document, and is decoded by an image library. It is checked for what it claims
    to be before any of that happens.
    """
    try:
        raw = base64.b64decode(encoded.split(",", 1)[-1], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise BadInputError("The map image could not be read.") from exc

    if len(raw) > MAX_MAP_BYTES:
        raise BadInputError(f"The map image is larger than {MAX_MAP_BYTES // (1024 * 1024)} MB.")

    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(raw)) as image:
            fmt, size = image.format, image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise BadInputError("The map image could not be read.") from exc

    if fmt != "PNG":
        raise BadInputError("The map image must be a PNG.")
    if max(size) > MAX_MAP_PIXELS:
        raise BadInputError("The map image is larger than this packet can hold.")

    return f"data:image/png;base64,{base64.b64encode(raw).decode('ascii')}"


def _claim_address(affidavit: Affidavit, claim_ref: str) -> str:
    """The address a claim is about, named the way the affidavit names it."""
    if claim_ref == "served_at":
        return affidavit.served_address
    try:
        index = int(claim_ref.removeprefix("attempt[").removesuffix("]"))
        return affidavit.attempts[index].address
    except (ValueError, IndexError):  # pragma: no cover - claim_ref comes from the engine
        return affidavit.served_address


def _claim_label(claim_ref: str) -> str:
    if claim_ref == "served_at":
        return "Service"
    index = claim_ref.removeprefix("attempt[").removesuffix("]")
    return f"Attempt {int(index) + 1}" if index.isdigit() else "Attempt"


def _claim_row(affidavit: Affidavit, verdict: ClaimVerdict) -> dict[str, Any]:
    return {
        "label": _claim_label(verdict.claim_ref),
        "when": copy.fmt_datetime(verdict.claimed_at),
        "address": _claim_address(affidavit, verdict.claim_ref),
        "tier": copy.TIER_LABELS[verdict.tier.value],
        "tier_key": verdict.tier.value,
        "distance": copy.fmt_km(verdict.nearest_fix_km)
        if verdict.nearest_fix_km is not None
        else "—",
        "speed": copy.fmt_speed(verdict.required_speed_kmh)
        if verdict.required_speed_kmh is not None
        else "—",
    }


def _finding_row(finding: Finding) -> dict[str, Any]:
    return {
        "code": finding.code,
        "severity": copy.SEVERITY_LABELS[finding.severity.value],
        "severity_key": finding.severity.value,
        "title": finding.title,
        "detail": finding.detail,
        "legal_ref": copy.LEGAL_REF_NAMES.get(finding.legal_ref or "", None),
    }


def _fix_row(fix: LocationFix) -> dict[str, Any]:
    when = copy.fmt_datetime(fix.t)
    if fix.t_end is not None:
        when = f"{when} to {copy.fmt_time(fix.t_end)}"
    return {
        "when": when,
        "kind": copy.FIX_KIND_LABELS[fix.kind.value],
        "coords": f"{fix.loc.lat:.5f}, {fix.loc.lng:.5f}",
        "accuracy": f"± {round(fix.accuracy_m):,} m" if fix.accuracy_m is not None else "—",
        "source": fix.label or copy.SOURCE_LABELS.get(fix.source, fix.source),
    }


def packet_context(
    analysis: CaseAnalysis,
    fixes: list[LocationFix],
    map_png_base64: str | None = None,
    affiant_name: str | None = None,
) -> dict[str, Any]:
    """Everything the template prints, decided here so it can be tested without a renderer."""
    affidavit = analysis.affidavit
    main = next((v for v in analysis.verdicts if v.claim_ref == "served_at"), None)
    shown = fixes[:MAX_FIXES_IN_TABLE]
    deadline = effective_deadline(analysis.deadlines)

    return {
        "title": copy.PACKET_TITLE,
        "subtitle": copy.PACKET_SUBTITLE,
        "disclaimer": copy.DISCLAIMER,
        "limitation": copy.LIMITATION,
        "generated": copy.generated_line(
            analysis.generated_at, analysis.engine_version, analysis.params_version
        ),
        "generated_iso": copy.local(analysis.generated_at).isoformat(),
        "intro": copy.packet_intro(affidavit.defendant_name, affidavit.index_number),
        "case": {
            "court": affidavit.court,
            "index_number": affidavit.index_number,
            "plaintiff": affidavit.plaintiff,
            "defendant": affidavit.defendant_name,
            "server_name": affidavit.server_name,
            "server_license": affidavit.server_license,
            "prepared_for": affiant_name,
        },
        "verdict": {
            "tier": analysis.overall.value,
            "label": copy.TIER_LABELS[analysis.overall.value],
            "headline": copy.TIER_HEADLINES[analysis.overall.value],
            "meaning": copy.TIER_MEANINGS[analysis.overall.value],
            "line": copy.verdict_line(
                main.nearest_fix_km if main else None,
                main.required_speed_kmh if main else None,
            ),
            "claimed": copy.claimed_sentence(
                affidavit.served_at, affidavit.served_address, affidavit.method.value
            ),
        },
        "map_data_uri": validate_map_png(map_png_base64) if map_png_base64 else None,
        "map_alt": copy.MAP_ALT,
        "claims": [_claim_row(affidavit, v) for v in analysis.verdicts],
        "findings": [_finding_row(f) for f in analysis.findings],
        "fixes": [_fix_row(f) for f in shown],
        "fixes_note": copy.fixes_note(len(shown), len(fixes)),
        "methodology": copy.methodology_body(
            PARAMS.match_radius_km,
            PARAMS.search_window_h,
            PARAMS.v_strong_kmh,
            PARAMS.v_moderate_kmh,
        ),
        "methodology_limits": copy.METHODOLOGY_LIMITS,
        "integrity": {
            "body": copy.INTEGRITY_BODY,
            "affidavit_sha256": affidavit.source_sha256,
            "fixes_sha256": fixes_digest(fixes),
            "n_fixes": len(fixes),
        },
        "deadlines": {
            "note": analysis.deadlines.note,
            "effective": copy.fmt_date(deadline) if deadline else None,
        },
        "sections": {
            "verdict": copy.SECTION_VERDICT,
            "map": copy.SECTION_MAP,
            "claims": copy.SECTION_CLAIMS,
            "findings": copy.SECTION_FINDINGS,
            "fixes": copy.SECTION_FIXES,
            "method": copy.SECTION_METHOD,
            "integrity": copy.SECTION_INTEGRITY,
            "deadline": copy.SECTION_DEADLINE,
        },
        "findings_none": copy.FINDINGS_NONE,
        "not_a_law_firm": copy.NOT_A_LAW_FIRM,
        "product": copy.PRODUCT,
    }


def build_packet(
    analysis: CaseAnalysis,
    fixes: list[LocationFix] | None = None,
    map_png_base64: str | None = None,
    affiant_name: str | None = None,
) -> bytes:
    return render_pdf(TEMPLATE, packet_context(analysis, fixes or [], map_png_base64, affiant_name))
