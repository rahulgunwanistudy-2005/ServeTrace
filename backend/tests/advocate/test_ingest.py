"""Reading a real advocate's spreadsheet, including the rows it cannot read.

The rule S5 states and this file enforces: **no row is ever silently dropped.** Every
assertion about a rejection is really an assertion about the denominator of a report
somebody is going to put their name to.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from openpyxl import Workbook

from app.advocate.ingest import (
    localize,
    parse_records,
    peek_headers,
    read_table,
    records_from_affidavits,
)
from app.api.errors import BadInputError, UnsupportedFileError
from app.domain.models import AdvocateColumnMapping, LatLng, ServiceAttempt, ServiceMethod
from tests.engine.conftest import affidavit

HEADER = "server_id,at,lat,lng,address,case_ref,outcome,recipient_desc"
ROW = "SRV-001,2025-03-04T09:34:00-05:00,40.85494,-73.905919,2100 JEROME AVENUE,CV-1-25,served,F/45"

COORDS = AdvocateColumnMapping(server_id="server_id", at="at", lat="lat", lng="lng")
LIMITS: dict[str, Any] = {"max_rows": 1000, "max_lookups": 10}


def csv_bytes(*rows: str, header: str = HEADER) -> bytes:
    return ("\n".join((header, *rows)) + "\n").encode()


async def parse(data: bytes, mapping: AdvocateColumnMapping = COORDS, name: str = "f.csv"):
    return await parse_records(data, name, mapping, **LIMITS)


# --- Reading the file itself ----------------------------------------------------------------


def test_headers_can_be_read_before_anything_is_parsed() -> None:
    """The user maps columns before the file is interpreted, so this must not need a mapping."""
    assert peek_headers(csv_bytes(ROW), "records.csv") == HEADER.split(",")


def test_a_semicolon_separated_export_is_read_as_one() -> None:
    """Excel in much of Europe writes CSV with semicolons, and it is still a CSV."""
    data = b"server_id;at;lat;lng\nSRV-1;2025-03-04 09:34;40.8;-73.9\n"

    headers, rows = read_table(data, "records.csv")

    assert headers == ["server_id", "at", "lat", "lng"]
    assert rows[0]["server_id"] == "SRV-1"


def test_a_byte_order_mark_does_not_become_part_of_the_first_column_name() -> None:
    data = "﻿".encode() + csv_bytes(ROW)

    assert peek_headers(data, "records.csv")[0] == "server_id"


def test_an_xlsx_is_recognised_by_its_contents_not_only_its_name() -> None:
    book = Workbook()
    sheet = book.active
    sheet.append(["server_id", "at", "lat", "lng"])
    sheet.append(["SRV-1", datetime(2025, 3, 4, 9, 34), 40.85, -73.9])
    buffer = io.BytesIO()
    book.save(buffer)

    assert peek_headers(buffer.getvalue(), "no-extension") == ["server_id", "at", "lat", "lng"]


def test_a_pdf_is_refused_with_a_sentence_that_names_what_would_work() -> None:
    with pytest.raises(UnsupportedFileError, match="csv"):
        read_table(b"%PDF-1.7 not a spreadsheet", "affidavit.pdf")


# --- Times -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "written",
    [
        "2025-03-04T09:34:00-05:00",
        "2025-03-04 09:34:00",
        "2025-03-04 09:34",
        "03/04/2025 9:34 AM",
        "03/04/2025 09:34",
    ],
)
@pytest.mark.asyncio
async def test_the_date_formats_case_management_systems_actually_export(written: str) -> None:
    outcome = await parse(csv_bytes(f"SRV-1,{written},40.85,-73.9", header="server_id,at,lat,lng"))

    assert len(outcome.records) == 1
    assert outcome.records[0].at.astimezone(UTC).hour == 14  # 09:34 EST


@pytest.mark.asyncio
async def test_a_separate_date_column_and_time_column_are_combined() -> None:
    mapping = AdvocateColumnMapping(
        server_id="server_id", date="date", time="time", lat="lat", lng="lng"
    )
    data = csv_bytes("SRV-1,03/04/2025,9:34 AM,40.85,-73.9", header="server_id,date,time,lat,lng")

    outcome = await parse(data, mapping)

    assert len(outcome.records) == 1
    assert outcome.records[0].at.astimezone(UTC).hour == 14


def test_a_clock_with_no_offset_is_read_as_new_york_time() -> None:
    """Bible §11.1.1. A spreadsheet of NYC filings that writes bare wall times means EST."""
    assert localize(datetime(2025, 3, 4, 9, 34)).utcoffset().total_seconds() == -5 * 3600


def test_an_offset_that_is_written_down_is_believed() -> None:
    written = datetime.fromisoformat("2025-03-04T09:34:00+01:00")

    assert localize(written) == written


@pytest.mark.asyncio
async def test_a_row_whose_time_cannot_be_read_is_returned_with_its_row_number() -> None:
    data = csv_bytes(ROW, "SRV-001,sometime tuesday,40.85,-73.9,,,,")

    outcome = await parse(data)

    assert len(outcome.records) == 1
    assert [(r.row, r.code) for r in outcome.rejected] == [(3, "missing_time")]
    assert "“at”" in outcome.rejected[0].reason


@pytest.mark.asyncio
async def test_a_rejection_never_echoes_the_cell_that_caused_it() -> None:
    """Bible §16: these files are real case data about real defendants. The reason names
    the column, never its contents."""
    data = csv_bytes("SRV-001,NOT-A-DATE-12 MARIA GARCIA,40.85,-73.9,,,,")

    outcome = await parse(data)

    assert "MARIA" not in outcome.rejected[0].reason
    assert "NOT-A-DATE" not in outcome.rejected[0].reason


# --- Places ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_row_with_no_place_at_all_is_rejected_rather_than_placed_at_zero() -> None:
    data = csv_bytes("SRV-001,2025-03-04T09:34:00-05:00,,,,,,")

    outcome = await parse(data)

    assert outcome.records == []
    assert outcome.rejected[0].code == "missing_place"


@pytest.mark.asyncio
async def test_coordinates_outside_the_possible_range_are_rejected_not_clamped() -> None:
    data = csv_bytes("SRV-001,2025-03-04T09:34:00-05:00,999,-73.9,,,,")

    outcome = await parse(data)

    assert outcome.rejected[0].code == "bad_coordinates"


@pytest.mark.asyncio
async def test_an_address_is_used_when_the_coordinate_columns_are_blank() -> None:
    """A committed cache entry, so no network: `tests/conftest.py` would fail the test if
    this reached GeoSearch."""
    mapping = AdvocateColumnMapping(
        server_id="server_id", at="at", lat="lat", lng="lng", address="address"
    )
    data = csv_bytes(
        "SRV-1,2025-03-04T09:34:00-05:00,,,2100 JEROME AVENUE Bronx NY 10453",
        header="server_id,at,lat,lng,address",
    )

    outcome = await parse(data, mapping)

    assert len(outcome.records) + len(outcome.rejected) == 1


@pytest.mark.asyncio
async def test_an_unresolvable_address_is_rejected_with_a_reason_and_not_dropped() -> None:
    mapping = AdvocateColumnMapping(server_id="server_id", at="at", address="address")
    data = csv_bytes(
        "SRV-1,2025-03-04T09:34:00-05:00,NOWHERE AT ALL IN ANY BOROUGH",
        header="server_id,at,address",
    )

    def empty(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"features": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(empty)) as client:
        outcome = await parse_records(data, "f.csv", mapping, **LIMITS, client=client)

    assert outcome.records == []
    assert outcome.rejected[0].code == "address_not_found"
    assert "New York City" in outcome.rejected[0].reason


@pytest.mark.asyncio
async def test_addresses_over_the_lookup_budget_are_told_how_to_avoid_the_limit() -> None:
    """The budget exists because GeoSearch is a free city service, not to punish the user.

    So the refusal names the fix — a lat/lng column needs no lookups at all — and the row
    still appears in the report's denominator.
    """
    mapping = AdvocateColumnMapping(server_id="server_id", at="at", address="address")
    data = csv_bytes(
        "SRV-1,2025-03-04T09:34:00-05:00,SOMEWHERE NOBODY HAS LOOKED UP",
        header="server_id,at,address",
    )

    outcome = await parse_records(data, "f.csv", mapping, max_rows=10, max_lookups=0)

    assert outcome.rejected[0].code == "lookup_budget"
    assert "latitude and longitude" in outcome.rejected[0].reason
    assert outcome.addresses_geocoded == 0


@pytest.mark.asyncio
async def test_a_cached_address_costs_no_lookup() -> None:
    """The committed cache is what makes the demo and the fixtures work offline."""
    mapping = AdvocateColumnMapping(server_id="server_id", at="at", address="address")
    data = csv_bytes(
        "SRV-1,2025-03-04T09:34:00-05:00,2100 JEROME AVENUE Bronx NY 10453",
        header="server_id,at,address",
    )

    outcome = await parse_records(data, "f.csv", mapping, max_rows=10, max_lookups=0)

    assert len(outcome.records) == 1
    assert outcome.addresses_geocoded == 0


# --- Mapping and limits ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_mapping_with_no_time_column_is_refused_before_the_file_is_read() -> None:
    mapping = AdvocateColumnMapping(server_id="server_id", lat="lat", lng="lng")

    with pytest.raises(BadInputError, match="date and time"):
        await parse(csv_bytes(ROW), mapping)


@pytest.mark.asyncio
async def test_a_mapping_with_no_place_columns_is_refused() -> None:
    mapping = AdvocateColumnMapping(server_id="server_id", at="at")

    with pytest.raises(BadInputError, match="location"):
        await parse(csv_bytes(ROW), mapping)


@pytest.mark.asyncio
async def test_a_mapping_naming_a_column_the_file_does_not_have_says_which_one() -> None:
    mapping = AdvocateColumnMapping(server_id="officer", at="at", lat="lat", lng="lng")

    with pytest.raises(BadInputError, match="officer"):
        await parse(csv_bytes(ROW), mapping)


@pytest.mark.asyncio
async def test_a_file_with_only_a_header_row_is_refused_rather_than_analysed_as_empty() -> None:
    with pytest.raises(BadInputError, match="no service records"):
        await parse(csv_bytes())


@pytest.mark.asyncio
async def test_a_file_over_the_row_cap_is_refused_with_the_cap_in_the_sentence() -> None:
    rows = [f"SRV-1,2025-03-04T09:3{i % 10}:00-05:00,40.85,-73.9" for i in range(5)]

    with pytest.raises(BadInputError, match="3"):
        await parse_records(
            csv_bytes(*rows, header="server_id,at,lat,lng"),
            "f.csv",
            COORDS,
            max_rows=3,
            max_lookups=0,
        )


@pytest.mark.asyncio
async def test_a_row_with_no_server_cannot_be_attributed_to_anyone() -> None:
    data = csv_bytes(",2025-03-04T09:34:00-05:00,40.85,-73.9")

    outcome = await parse(data)

    assert outcome.rejected[0].code == "missing_server"


@pytest.mark.asyncio
async def test_rows_read_counts_every_row_including_the_refused_ones() -> None:
    data = csv_bytes(ROW, ",2025-03-04T09:34:00-05:00,40.85,-73.9,,,,", "SRV-1,no,40.85,-73.9,,,,")

    outcome = await parse(data)

    assert outcome.rows_read == 3
    assert len(outcome.records) + len(outcome.rejected) == 3


@pytest.mark.asyncio
async def test_rejections_come_back_in_the_order_the_spreadsheet_shows_them() -> None:
    rows = [",2025-03-04T09:34:00-05:00,40.85,-73.9,,,,"] * 4

    outcome = await parse(csv_bytes(*rows))

    assert [r.row for r in outcome.rejected] == [2, 3, 4, 5]


@pytest.mark.asyncio
async def test_an_unfamiliar_outcome_word_keeps_the_row_rather_than_losing_its_place() -> None:
    """A filing's time and place are the evidence. An outcome vocabulary we do not know is
    not a reason to throw them away."""
    data = csv_bytes("SRV-1,2025-03-04T09:34:00-05:00,40.85,-73.9,,,SUBSTITUTED-PER-308(2),")

    outcome = await parse(
        data,
        AdvocateColumnMapping(
            server_id="server_id", at="at", lat="lat", lng="lng", outcome="outcome"
        ),
    )

    assert len(outcome.records) == 1
    assert outcome.records[0].outcome == "other"


# --- The other way in: confirmed affidavits -------------------------------------------------------


def test_an_affidavit_becomes_one_record_for_the_service_and_one_per_attempt() -> None:
    attempts = [
        ServiceAttempt(
            at=datetime.fromisoformat("2025-03-01T10:00:00-05:00"),
            address="1 SYNTHETIC STREET",
            location=LatLng(lat=40.85, lng=-73.9),
            outcome="not_home",
        )
    ]
    source = affidavit(
        method=ServiceMethod.AFFIX_AND_MAIL, attempts=attempts, server_license="1234567"
    )

    records, skipped = records_from_affidavits([source])

    assert skipped == []
    assert len(records) == 2
    assert {r.outcome for r in records} == {"affixed", "not_home"}


def test_the_licence_number_is_preferred_over_the_name_as_the_server_key() -> None:
    """A name is spelled several ways across a year of filings. A licence number is not."""
    source = affidavit(server_license="1234567", server_name="J. Smith")

    records, _ = records_from_affidavits([source])

    assert records[0].server_id == "1234567"


def test_an_affidavit_naming_nobody_is_reported_rather_than_grouped_under_a_blank() -> None:
    source = affidavit(server_license=None, server_name=None)

    records, skipped = records_from_affidavits([source])

    assert records == []
    assert len(skipped) == 1


def test_an_attempt_without_coordinates_is_left_out_of_the_geometry() -> None:
    """Bible §11.4 is about distance. A place that could not be resolved has none."""
    attempts = [
        ServiceAttempt(
            at=datetime.fromisoformat("2025-03-01T10:00:00-05:00"),
            address="UNRESOLVED",
            location=None,
            outcome="not_home",
        )
    ]

    records, _ = records_from_affidavits([affidavit(attempts=attempts, server_license="1234567")])

    assert len(records) == 1
    assert records[0].outcome == "served"
