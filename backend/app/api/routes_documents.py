"""/api/documents: the two PDFs, rendered from an analysis the client already holds.

Stateless like everything else. There is no case id because there is nothing stored, so
the analysis travels back up with the request exactly as the fixes travelled up with the
one that produced it. The round trip is deliberate and it is not a cost worth optimising
away: it is what makes the server able to forget.

The route guards and delegates. Which paragraphs a document contains, and what they say,
is decided in `documents/`, which is pure and has no idea it is behind HTTP.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Response

from app.api.errors import AffidavitNotConfirmedError, BadInputError
from app.api.rate_limit import enforce_rate_limit
from app.config import get_settings
from app.documents.affidavit import build_draft_affidavit
from app.documents.packet import build_packet
from app.domain.models import CaseAnalysis, DraftAffidavitRequest, PacketRequest

router = APIRouter(tags=["documents"], prefix="/documents")

_UNSAFE_IN_FILENAME = re.compile(r"[^A-Za-z0-9._]+")
"""A hyphen is not in the safe set even though a hyphen is safe, so that a run of unsafe
characters collapses into one separator rather than into one per character."""


def _guard(analysis: CaseAnalysis, n_fixes: int = 0) -> None:
    """Bible §10 and §16, the same two guards `/api/analyze` applies to the same data.

    A document is a stronger artefact than a result page — it is the thing that gets
    printed and handed over — so the rule that analysis refuses an unconfirmed affidavit
    has to hold here too. Without this, an affidavit could be confirmed for the analysis
    and a different one submitted for the document.
    """
    if not analysis.affidavit.user_confirmed:
        raise AffidavitNotConfirmedError(
            "Please confirm that the details we read off your papers are right before we "
            "put them in a document. Every line of it is built from those details."
        )
    settings = get_settings()
    if n_fixes > settings.max_fixes:
        raise BadInputError(
            f"That is more than {settings.max_fixes:,} location points. Only the hours "
            f"around the times on the affidavit need to be sent."
        )


def _filename(stem: str, defendant: str) -> str:
    """A file the person can find again on their phone, named after their own case.

    The name is scrubbed rather than trusted: it comes off a scanned document, it goes
    into a `Content-Disposition` header, and a newline in a header is a response-splitting
    bug in anybody's HTTP stack.
    """
    safe = _UNSAFE_IN_FILENAME.sub("-", defendant).strip("-")[:40]
    return f"servetrace-{stem}-{safe}.pdf" if safe else f"servetrace-{stem}.pdf"


def _pdf(body: bytes, filename: str) -> Response:
    return Response(
        content=body,
        media_type="application/pdf",
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/packet", dependencies=[Depends(enforce_rate_limit)])
async def packet(body: PacketRequest) -> Response:
    _guard(body.analysis, len(body.fixes))
    pdf = build_packet(body.analysis, body.fixes, body.map_png_base64, body.affiant_name)
    return _pdf(pdf, _filename("evidence-packet", body.analysis.affidavit.defendant_name))


@router.post("/affidavit", dependencies=[Depends(enforce_rate_limit)])
async def affidavit(body: DraftAffidavitRequest) -> Response:
    _guard(body.analysis)
    pdf = build_draft_affidavit(body.analysis, body.affiant)
    return _pdf(pdf, _filename("draft-affidavit", body.analysis.affidavit.defendant_name))
