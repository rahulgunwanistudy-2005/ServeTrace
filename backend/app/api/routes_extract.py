"""/api/extract: an uploaded affidavit in, a draft the user can correct out.

Nothing is persisted. The bytes live in memory for the length of one request, and the
response is the only copy of anything read off them.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile

from app.api.errors import BadInputError, DemoOnlyError, UploadTooLargeError
from app.api.rate_limit import enforce_extract_rate_limit
from app.config import get_settings
from app.domain.models import AffidavitDraft, ExtractionResult, LatLng, PageType
from app.extraction.vision import extract_document
from app.geo.geocode import MIN_CONFIDENCE, geocode_all

router = APIRouter(tags=["extract"])

CHUNK = 1 << 20


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    """Read the upload, giving up as soon as it is over the ceiling.

    Read in chunks rather than in one call so a 2 GB upload costs 15 MB of memory and one
    error, not 2 GB of memory and an outage.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise UploadTooLargeError(
                f"That file is larger than {limit // (1024 * 1024)} MB. "
                "A photo of each page, or the PDF from the court file, will be smaller."
            )
        chunks.append(chunk)
    if total == 0:
        raise BadInputError("That file was empty.")
    return b"".join(chunks)


async def _locate(draft: AffidavitDraft) -> AffidavitDraft:
    """Geocode the addresses on a draft, and attach a point only when it is a confident one.

    An unresolved address is not an error: the user confirms every address anyway, and a
    wrong pin on a map is worse than no pin.
    """
    addresses = [draft.served_address or "", *(a.address or "" for a in draft.attempts)]
    resolved = await geocode_all(addresses)

    def point(address: str | None) -> LatLng | None:
        hit = resolved.get(address or "")
        return hit.location if hit and hit.confidence >= MIN_CONFIDENCE else None

    return draft.model_copy(
        update={
            "served_location": point(draft.served_address),
            "attempts": [
                attempt.model_copy(update={"location": point(attempt.address)})
                for attempt in draft.attempts
            ],
        }
    )


def _page_types(raw: str | None) -> list[PageType] | None:
    if raw is None or raw == "":
        return None
    try:
        return [PageType(part.strip()) for part in raw.split(",")]
    except ValueError as exc:
        raise BadInputError("Those page labels were not recognised.") from exc


def _page_list(raw: str | None) -> list[int] | None:
    if raw is None or raw == "":
        return None
    try:
        pages = [int(part) for part in raw.split(",")]
    except ValueError as exc:
        raise BadInputError("Those page numbers were not recognised.") from exc
    if any(p < 0 for p in pages):
        raise BadInputError("Those page numbers were not recognised.")
    return pages


@router.post(
    "/extract", response_model=ExtractionResult, dependencies=[Depends(enforce_extract_rate_limit)]
)
async def extract(
    file: Annotated[UploadFile, File()],
    previews: Annotated[bool, Query(description="Return page previews for review.")] = True,
    page_types: Annotated[
        str | None,
        Query(description="Comma list, one label per page, replacing classification."),
    ] = None,
    extract_pages: Annotated[
        str | None,
        Query(description="Comma list of 0-based pages: read only affidavits touching these."),
    ] = None,
) -> ExtractionResult:
    settings = get_settings()
    if settings.demo_only:
        raise DemoOnlyError(
            "This is the demo deployment, so it does not accept uploads. "
            "The bundled example cases show what a real check looks like."
        )
    labels = _page_types(page_types)
    wanted = _page_list(extract_pages)

    data = await _read_limited(file, settings.max_upload_bytes)
    try:
        result = await extract_document(
            data, previews=previews, page_types=labels, extract_pages=wanted
        )
    finally:
        await file.close()
    located = [
        found.model_copy(update={"draft": await _locate(found.draft)})
        for found in result.affidavits
    ]
    return result.model_copy(update={"affidavits": located})
