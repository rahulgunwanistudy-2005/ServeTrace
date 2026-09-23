"""/api/advocate: a spreadsheet of filings in, servers ranked by impossibility out.

Stateless like everything else. The file is read in memory, analysed and forgotten; the
response carries the whole report back because there is nowhere to come back to.

Two shapes go in. A CSV or XLSX with a column mapping is the common one. A JSON list of
`Affidavit` objects is the other: an advocate who has run several clients through the
defendant flow already holds affidavits that were read off the document and then confirmed
by the person they were sworn against, which is better evidence than any export.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from pydantic import ValidationError

from app.advocate.ingest import parse_records, peek_headers, records_from_affidavits
from app.advocate.patterns import analyze_servers
from app.advocate.report import pairs_to_csv, servers_to_csv
from app.api.errors import BadInputError, DemoOnlyError, UploadTooLargeError
from app.api.rate_limit import enforce_rate_limit
from app.config import ENGINE_VERSION, get_settings
from app.domain.models import (
    AdvocateAnalysis,
    AdvocateColumnMapping,
    AdvocateStats,
    Affidavit,
    RejectedRow,
    ServerReport,
    ServiceRecord,
)
from app.engine.params import PARAMS, PARAMS_VERSION

router = APIRouter(tags=["advocate"], prefix="/advocate")

CHUNK = 1 << 20


async def _read_limited(upload: UploadFile, limit: int) -> bytes:
    """Read the upload, giving up as soon as it is over the ceiling.

    The same shape as `routes_extract._read_limited`, and deliberately not shared with it:
    the two differ in what they say when they refuse, and the sentence is the part that
    matters to whoever hit the limit.
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
                f"That file is larger than {limit // (1024 * 1024)} MB. Exporting only the "
                f"columns ServeTrace needs, or splitting it by date, will bring it under."
            )
        chunks.append(chunk)
    if total == 0:
        raise BadInputError("That file was empty.")
    return b"".join(chunks)


def _mapping_from(raw: str) -> AdvocateColumnMapping:
    try:
        return AdvocateColumnMapping.model_validate(json.loads(raw))
    except (ValidationError, ValueError) as exc:
        raise BadInputError(
            "We could not read which column holds which field. Please choose the columns again."
        ) from exc


def _records_for_map(
    reports: list[ServerReport], records: list[ServiceRecord], cap: int
) -> list[ServiceRecord]:
    """Whole servers at a time, highest-ranked first, until the cap is reached.

    Taking the first `cap` records off a flat list would hand the browser a server's
    Monday and Tuesday and no more, and a map of half a week is worse than no map: the
    cluster it is missing is exactly the context the flagged step is judged against. So
    the cut is between servers rather than inside one.
    """
    by_server: dict[str, list[ServiceRecord]] = {}
    for record in records:
        by_server.setdefault(record.server_id, []).append(record)

    kept: list[ServiceRecord] = []
    for report in reports:
        rows = by_server.get(report.server_id, [])
        if len(kept) + len(rows) > cap:
            break
        kept.extend(rows)
    return kept


def _stats(
    reports: list[ServerReport],
    records: list[ServiceRecord],
    rejected: list[RejectedRow],
    rows_read: int,
    geocoded: int,
    returned: int,
) -> AdvocateStats:
    return AdvocateStats(
        rows_read=rows_read,
        records=len(records),
        rejected=len(rejected),
        servers=len(reports),
        addresses_geocoded=geocoded,
        records_returned=returned,
        params_version=PARAMS_VERSION,
        engine_version=ENGINE_VERSION,
        generated_at=datetime.now(UTC),
    )


def _analysis(
    records: list[ServiceRecord],
    rejected: list[RejectedRow],
    rows_read: int,
    geocoded: int,
    mapping: AdvocateColumnMapping,
) -> AdvocateAnalysis:
    reports = analyze_servers(records, PARAMS)
    for_map = _records_for_map(reports, records, get_settings().max_advocate_map_records)
    return AdvocateAnalysis(
        reports=reports,
        rejected=rejected,
        records=for_map,
        mapping=mapping,
        stats=_stats(reports, records, rejected, rows_read, geocoded, len(for_map)),
    )


def _refuse_if_demo_only() -> None:
    if get_settings().demo_only:
        raise DemoOnlyError(
            "This is the demo deployment, so it does not accept uploads. The bundled "
            "example file shows what a batch report looks like."
        )


@router.post("/columns", dependencies=[Depends(enforce_rate_limit)])
async def columns(file: Annotated[UploadFile, File()]) -> dict[str, list[str]]:
    """The file's own column names, so the user can map them before anything is parsed.

    A separate call rather than a first pass of the analysis, because the mapping is a
    decision the user makes and the file has to be on screen before they can make it.
    """
    _refuse_if_demo_only()
    settings = get_settings()
    data = await _read_limited(file, settings.max_upload_bytes)
    try:
        return {"columns": peek_headers(data, file.filename or "")}
    finally:
        await file.close()


@router.post(
    "/analyze", response_model=AdvocateAnalysis, dependencies=[Depends(enforce_rate_limit)]
)
async def analyze_batch(
    file: Annotated[UploadFile, File()],
    mapping: Annotated[str, Form()],
) -> AdvocateAnalysis:
    _refuse_if_demo_only()
    settings = get_settings()
    column_map = _mapping_from(mapping)
    data = await _read_limited(file, settings.max_upload_bytes)
    try:
        outcome = await parse_records(
            data,
            file.filename or "",
            column_map,
            max_rows=settings.max_advocate_rows,
            max_lookups=settings.max_advocate_lookups,
        )
    finally:
        await file.close()

    return _analysis(
        outcome.records,
        outcome.rejected,
        outcome.rows_read,
        outcome.addresses_geocoded,
        column_map,
    )


@router.post(
    "/analyze-affidavits",
    response_model=AdvocateAnalysis,
    dependencies=[Depends(enforce_rate_limit)],
)
async def analyze_affidavits(affidavits: list[Affidavit]) -> AdvocateAnalysis:
    """The same report, built from affidavits the defendant flow already confirmed."""
    if len(affidavits) > get_settings().max_advocate_rows:
        raise BadInputError("That is more affidavits than ServeTrace reads at once.")

    records, skipped = records_from_affidavits(affidavits)
    rejected = [
        RejectedRow(
            row=index + 1,
            code="missing_server",
            reason="That affidavit names no process server and no licence number, so its "
            "filings cannot be grouped with anyone's.",
        )
        for index, _ in enumerate(skipped)
    ]
    # The fields came off confirmed affidavits rather than out of a spreadsheet, so the
    # mapping names the contract rather than anyone's column headings.
    return _analysis(
        records,
        rejected,
        len(affidavits),
        0,
        AdvocateColumnMapping(server_id="server_license", at="served_at", address="served_address"),
    )


@router.post("/export.csv", dependencies=[Depends(enforce_rate_limit)])
async def export_csv(reports: list[ServerReport], kind: str = "pairs") -> Response:
    """The report as a file, so it can be attached to something rather than screenshotted.

    The client posts back the report it already holds rather than the server recomputing
    it: there is no case id because there is nothing stored, and re-uploading the whole
    spreadsheet to get a CSV of a result already on screen would be the wrong trade.
    """
    body = servers_to_csv(reports) if kind == "servers" else pairs_to_csv(reports)
    name = "servetrace-servers.csv" if kind == "servers" else "servetrace-impossible-pairs.csv"
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"content-disposition": f'attachment; filename="{name}"'},
    )
