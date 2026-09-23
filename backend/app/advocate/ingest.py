"""A spreadsheet of service records in, `ServiceRecord`s and a list of refusals out.

Bible §11.4, and S5's one hard rule: **a row that cannot be used is returned with a
reason, never dropped.** An advocate is building something they will put their name to.
A parser that quietly discards the eleven rows whose dates it could not read hands them a
report whose denominator is wrong, and they have no way to know it.

So every refusal carries the row number the spreadsheet shows and the column at fault,
and never the cell's contents — the same discipline as the logs (bible §16), for the same
reason: these files are real case data about real defendants.

Nothing here is stored. The bytes live for one request.
"""

from __future__ import annotations

import asyncio
import csv
import io
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime
from datetime import time as time_cls
from typing import Any, Final
from zoneinfo import ZoneInfo

import httpx
from openpyxl import load_workbook

from app.api.errors import BadInputError, UnsupportedFileError, UpstreamError
from app.domain.models import (
    AdvocateColumnMapping,
    Affidavit,
    GeocodeResult,
    LatLng,
    RejectedRow,
    ServiceMethod,
    ServiceRecord,
)
from app.engine.params import PARAMS
from app.geo.geocode import MIN_CONFIDENCE, cached_result, geocode

TZ: Final = ZoneInfo(PARAMS.tz)

MAX_LOOKUPS_IN_FLIGHT: Final = 5
"""S5: at most this many address lookups outstanding at once. GeoSearch is a free public
service run by a city planning department, and a 50,000-row upload is not a reason to
point a thousand parallel requests at it."""

GEOCODE_TIMEOUT_S: Final = 5.0

CSV_EXTENSIONS: Final = (".csv", ".txt", ".tsv")
XLSX_EXTENSIONS: Final = (".xlsx", ".xlsm")

_DATETIME_FORMATS: Final = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%m/%d/%Y %I:%M:%S %p",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%y %I:%M %p",
    "%m/%d/%y %H:%M",
)
_DATE_FORMATS: Final = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d %B %Y", "%B %d, %Y")
_TIME_FORMATS: Final = ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p", "%I:%M%p")

TRUE_OUTCOMES: Final = {
    "served": "served",
    "serve": "served",
    "personal": "served",
    "substitute": "served",
    "affixed": "affixed",
    "affix": "affixed",
    "posted": "affixed",
    "not home": "not_home",
    "not_home": "not_home",
    "no answer": "not_home",
    "refused": "refused",
}
"""The outcome words a case-management export actually writes, mapped onto bible §10's
five. Anything unrecognised becomes "other" rather than a rejection: an outcome the
importer does not know is not a reason to throw away a filing's time and place."""


@dataclass(slots=True)
class IngestOutcome:
    records: list[ServiceRecord] = field(default_factory=list)
    rejected: list[RejectedRow] = field(default_factory=list)
    rows_read: int = 0
    addresses_geocoded: int = 0
    """Addresses resolved upstream. Cache hits are not lookups and are not counted."""


@dataclass(slots=True)
class _Pending:
    """A row that parsed, waiting only on an address lookup."""

    row: int
    server_id: str
    at: datetime
    loc: LatLng | None
    address: str | None
    case_ref: str | None
    outcome: str | None
    recipient_desc: str | None


# --- Reading the file ---------------------------------------------------------------------


def _clean(value: Any) -> Any:
    """A blank cell, whatever the writer used to mean blank, is `None`."""
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _read_csv(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel on Windows still writes this, and it is not the advocate's fault.
        text = data.decode("cp1252", errors="replace")

    sample = text[:4096]
    try:
        dialect: Any = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [h.strip() for h in (reader.fieldnames or []) if h]
    rows = [{(k or "").strip(): _clean(v) for k, v in row.items()} for row in reader]
    return headers, rows


def _read_xlsx(data: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises a zoo of exception types on a bad file
        raise BadInputError(
            "We could not open that spreadsheet. It may be damaged, or saved in an older "
            "Excel format — re-saving it as .xlsx or .csv will fix it."
        ) from exc

    try:
        sheet = workbook.worksheets[0]
        iterator = sheet.iter_rows(values_only=True)
        try:
            header_row = next(iterator)
        except StopIteration:
            return [], []
        headers = [str(h).strip() for h in header_row if h is not None]
        rows: list[dict[str, Any]] = []
        for values in iterator:
            if all(v is None for v in values):
                continue
            rows.append({h: _clean(v) for h, v in zip(headers, values, strict=False)})
        return headers, rows
    finally:
        workbook.close()


def read_table(data: bytes, filename: str) -> tuple[list[str], list[dict[str, Any]]]:
    """Header names and rows, from CSV or XLSX. The extension decides; content confirms."""
    lowered = filename.lower()
    if lowered.endswith(XLSX_EXTENSIONS) or data[:2] == b"PK":
        return _read_xlsx(data)
    if lowered.endswith(CSV_EXTENSIONS):
        return _read_csv(data)
    raise UnsupportedFileError(
        "ServeTrace reads service records as a .csv or .xlsx file. Most case-management "
        "systems can export either."
    )


def peek_headers(data: bytes, filename: str) -> list[str]:
    """The column names, so the user can map them before anything is parsed."""
    return read_table(data, filename)[0]


# --- Turning a row into a record ------------------------------------------------------------


def _as_datetime(value: Any) -> datetime | None:
    """A cell holding a whole date and time.

    XLSX stores real datetimes, so openpyxl hands back a `datetime` and there is nothing
    to parse. A CSV hands back whatever the exporting system wrote.
    """
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _as_date(value: Any) -> date_cls | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date_cls):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    try:
        return date_cls.fromisoformat(text)
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _as_time(value: Any) -> time_cls | None:
    if isinstance(value, datetime):
        return value.timetz()
    if isinstance(value, time_cls):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip().upper().replace(".", "")
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def localize(when: datetime) -> datetime:
    """Bible §11.1.1: a wall clock with no offset is New York time.

    On the autumn fold `zoneinfo` resolves to the first of the two readings, which is the
    same choice `lib/ingest/tz.ts` makes on the browser side and tells the user about.
    A batch file has no user to tell, so the convention has to be the documented one.
    """
    return when.replace(tzinfo=TZ) if when.tzinfo is None else when


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    try:
        return float(value.strip().replace("°", ""))
    except ValueError:
        return None


def _outcome_of(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return TRUE_OUTCOMES.get(value.strip().lower(), "other")


def _parse_row(
    row: dict[str, Any], mapping: AdvocateColumnMapping, row_number: int
) -> _Pending | RejectedRow:
    server_id = _text(row.get(mapping.server_id))
    if server_id is None:
        return RejectedRow(
            row=row_number,
            code="missing_server",
            reason=f"The “{mapping.server_id}” column is empty, so this filing cannot be "
            f"attributed to a process server.",
        )

    when = _read_time(row, mapping)
    if when is None:
        column = mapping.at or f"{mapping.date} / {mapping.time}"
        return RejectedRow(
            row=row_number,
            code="missing_time",
            reason=f"We could not read a date and time from the “{column}” column.",
        )

    loc: LatLng | None = None
    address = row.get(mapping.address) if mapping.address else None
    address = address.strip() if isinstance(address, str) else None

    if mapping.lat and mapping.lng:
        lat, lng = _as_float(row.get(mapping.lat)), _as_float(row.get(mapping.lng))
        if lat is not None and lng is not None:
            try:
                loc = LatLng(lat=lat, lng=lng)
            except ValueError:
                return RejectedRow(
                    row=row_number,
                    code="bad_coordinates",
                    reason=f"The “{mapping.lat}” and “{mapping.lng}” columns are not a "
                    f"latitude and longitude.",
                )
        elif not address:
            return RejectedRow(
                row=row_number,
                code="missing_place",
                reason=f"This row has no coordinates in “{mapping.lat}”/“{mapping.lng}” "
                f"and no address to look up instead.",
            )

    if loc is None and not address:
        return RejectedRow(
            row=row_number,
            code="missing_place",
            reason="This row has neither coordinates nor an address, so there is nowhere "
            "to put it on the map.",
        )

    return _Pending(
        row=row_number,
        server_id=server_id,
        at=localize(when),
        loc=loc,
        address=address,
        case_ref=_text(row.get(mapping.case_ref)) if mapping.case_ref else None,
        outcome=_outcome_of(row.get(mapping.outcome)) if mapping.outcome else None,
        recipient_desc=_text(row.get(mapping.recipient_desc)) if mapping.recipient_desc else None,
    )


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _read_time(row: dict[str, Any], mapping: AdvocateColumnMapping) -> datetime | None:
    if mapping.at:
        return _as_datetime(row.get(mapping.at))
    if mapping.date and mapping.time:
        day, clock = _as_date(row.get(mapping.date)), _as_time(row.get(mapping.time))
        if day is None or clock is None:
            return None
        return datetime.combine(day, clock)
    return None


# --- Addresses --------------------------------------------------------------------------


async def resolve_addresses(
    addresses: list[str], *, max_lookups: int, client: httpx.AsyncClient | None = None
) -> tuple[dict[str, GeocodeResult | None], int, set[str]]:
    """Resolve unique addresses, at most `MAX_LOOKUPS_IN_FLIGHT` at a time.

    Returns what resolved, how many needed an upstream call, and the addresses that were
    over the lookup budget — which are reported to the user as a fixable problem rather
    than as a failure, because adding latitude and longitude columns removes the need for
    any lookup at all.
    """
    unique = list(dict.fromkeys(a for a in addresses if a))
    if not unique:
        return {}, 0, set()

    # The committed cache answers the demo and the fixtures without a request, so the
    # budget is spent only on addresses nobody has looked up before.
    cached = {a: cached_result(a) for a in unique}
    need_lookup = [a for a, hit in cached.items() if hit is None]
    over_budget = set(need_lookup[max_lookups:])
    to_fetch = need_lookup[:max_lookups]

    resolved: dict[str, GeocodeResult | None] = {a: hit for a, hit in cached.items() if hit}
    if not to_fetch:
        return resolved, 0, over_budget

    semaphore = asyncio.Semaphore(MAX_LOOKUPS_IN_FLIGHT)

    async def one(address: str, session: httpx.AsyncClient) -> tuple[str, GeocodeResult | None]:
        async with semaphore:
            try:
                return address, await geocode(address, session)
            except (UpstreamError, httpx.HTTPError, ValueError):
                # One address that will not resolve must not fail the other 49,999.
                return address, None

    owned = client is None
    session = client or httpx.AsyncClient(timeout=GEOCODE_TIMEOUT_S)
    try:
        for address, hit in await asyncio.gather(*(one(a, session) for a in to_fetch)):
            resolved[address] = hit
    finally:
        if owned:
            await session.aclose()

    return resolved, len(to_fetch), over_budget


# --- The whole thing ----------------------------------------------------------------------


async def parse_records(
    data: bytes,
    filename: str,
    mapping: AdvocateColumnMapping,
    *,
    max_rows: int,
    max_lookups: int,
    client: httpx.AsyncClient | None = None,
) -> IngestOutcome:
    """Bytes and a column mapping in; records and refusals out."""
    if not mapping.has_time:
        raise BadInputError(
            "Tell us which column holds the date and time of each service — either one "
            "column with both, or a date column and a time column."
        )
    if not mapping.has_place:
        raise BadInputError(
            "Tell us which columns hold the location of each service — either latitude "
            "and longitude, or an address we can look up."
        )

    headers, rows = read_table(data, filename)
    if not rows:
        raise BadInputError("That file has a header row but no service records under it.")
    if len(rows) > max_rows:
        raise BadInputError(
            f"That file holds {len(rows):,} rows, and ServeTrace reads up to "
            f"{max_rows:,} at a time."
        )

    missing = [
        name
        for name in (
            mapping.server_id,
            mapping.at,
            mapping.date,
            mapping.time,
            mapping.lat,
            mapping.lng,
            mapping.address,
        )
        if name and name not in headers
    ]
    if missing:
        named = ", ".join(f"“{name}”" for name in missing)
        raise BadInputError(f"That file has no column called {named}.")

    outcome = IngestOutcome(rows_read=len(rows))
    pending: list[_Pending] = []
    for index, row in enumerate(rows):
        parsed = _parse_row(row, mapping, row_number=index + 2)  # header is row 1
        if isinstance(parsed, RejectedRow):
            outcome.rejected.append(parsed)
        else:
            pending.append(parsed)

    needs_address = [p.address for p in pending if p.loc is None and p.address]
    resolved, looked_up, over_budget = await resolve_addresses(
        needs_address, max_lookups=max_lookups, client=client
    )
    outcome.addresses_geocoded = looked_up

    for item in pending:
        loc = item.loc
        if loc is None and item.address:
            hit = resolved.get(item.address)
            if hit is not None and hit.confidence >= MIN_CONFIDENCE:
                loc = hit.location
        if loc is None:
            outcome.rejected.append(_unresolved(item, over_budget))
            continue
        outcome.records.append(
            ServiceRecord(
                server_id=item.server_id,
                at=item.at,
                loc=loc,
                address=item.address,
                case_ref=item.case_ref,
                outcome=item.outcome,
                recipient_desc=item.recipient_desc,
            )
        )

    outcome.rejected.sort(key=lambda r: r.row)
    return outcome


def _unresolved(item: _Pending, over_budget: set[str]) -> RejectedRow:
    if item.address in over_budget:
        return RejectedRow(
            row=item.row,
            code="lookup_budget",
            reason="We look up a limited number of new addresses per file. Adding "
            "latitude and longitude columns to your export removes the limit entirely.",
        )
    return RejectedRow(
        row=item.row,
        code="address_not_found",
        reason="We could not find that address in New York City. ServeTrace only knows "
        "the five boroughs.",
    )


# --- The other way in: affidavits the defendant flow already confirmed ---------------------


def records_from_affidavits(affidavits: list[Affidavit]) -> tuple[list[ServiceRecord], list[str]]:
    """Confirmed `Affidavit` objects into `ServiceRecord`s. S5 step 2.

    An advocate who has run several clients through the defendant flow already holds
    structured affidavits, and they are better evidence than a spreadsheet: every field
    was read off the document and then confirmed by the person it was sworn against.

    The server is keyed on its licence number where there is one. A name is a weaker
    identifier — it is spelled several ways across a year of filings — but it is what a
    file without licence numbers has, so it is the fallback rather than a refusal.

    Both the claimed service and every prior attempt become records, because bible §11.4
    is about the server's whole day and an attempt is a place the server swore to being.
    """
    records: list[ServiceRecord] = []
    skipped: list[str] = []

    for affidavit in affidavits:
        server_id = (affidavit.server_license or affidavit.server_name or "").strip()
        if not server_id:
            skipped.append(affidavit.source_sha256[:12])
            continue

        description = (
            affidavit.recipient_description.raw_text if affidavit.recipient_description else None
        )
        if affidavit.served_location is not None:
            records.append(
                ServiceRecord(
                    server_id=server_id,
                    at=affidavit.served_at,
                    loc=affidavit.served_location,
                    address=affidavit.served_address,
                    case_ref=affidavit.index_number,
                    outcome="affixed"
                    if affidavit.method is ServiceMethod.AFFIX_AND_MAIL
                    else "served",
                    recipient_desc=description,
                )
            )
        for attempt in affidavit.attempts:
            if attempt.location is None:
                continue
            records.append(
                ServiceRecord(
                    server_id=server_id,
                    at=attempt.at,
                    loc=attempt.location,
                    address=attempt.address,
                    case_ref=affidavit.index_number,
                    outcome=attempt.outcome,
                    recipient_desc=None,
                )
            )

    return records, skipped
