"""/api/extract: an uploaded affidavit in, a draft the user can correct out.

Nothing is persisted. The bytes live in memory for the length of one request, and the
response is the only copy of anything read off them.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.errors import BadInputError, DemoOnlyError, UploadTooLargeError
from app.api.rate_limit import enforce_rate_limit
from app.config import get_settings
from app.domain.models import ExtractionResult, LatLng
from app.extraction.vision import extract_affidavit
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


async def _attach_locations(result: ExtractionResult) -> ExtractionResult:
    """Geocode the addresses on the draft, and attach a point only when it is a confident one.

    An unresolved address is not an error: the user confirms every address anyway, and a
    wrong pin on a map is worse than no pin.
    """
    draft = result.draft
    addresses = [draft.served_address or "", *(a.address or "" for a in draft.attempts)]
    resolved = await geocode_all(addresses)

    def point(address: str | None) -> LatLng | None:
        hit = resolved.get(address or "")
        return hit.location if hit and hit.confidence >= MIN_CONFIDENCE else None

    updated = draft.model_copy(
        update={
            "served_location": point(draft.served_address),
            "attempts": [
                attempt.model_copy(update={"location": point(attempt.address)})
                for attempt in draft.attempts
            ],
        }
    )
    return result.model_copy(update={"draft": updated})


@router.post(
    "/extract", response_model=ExtractionResult, dependencies=[Depends(enforce_rate_limit)]
)
async def extract(file: Annotated[UploadFile, File()]) -> ExtractionResult:
    settings = get_settings()
    if settings.demo_only:
        raise DemoOnlyError(
            "This is the demo deployment, so it does not accept uploads. "
            "The bundled example cases show what a real check looks like."
        )

    data = await _read_limited(file, settings.max_upload_bytes)
    try:
        result = await extract_affidavit(data)
    finally:
        await file.close()
    return await _attach_locations(result)
