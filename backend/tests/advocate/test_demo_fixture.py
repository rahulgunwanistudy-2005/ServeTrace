"""The committed demo spreadsheet, end to end through the real ingest and the real engine.

This is the file a judge opens. It is committed as XLSX rather than CSV for two reasons:
it is what a case-management system exports, and it means the demo path and the openpyxl
path are the same path — a demo that works through a code route nobody else uses is a
demo that proves nothing.

The expected answers are written by `fixtures/generator/advocate_demo.py`, which decides
them from what it *injected* and never by asking this engine.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.advocate.ingest import parse_records
from app.advocate.patterns import analyze_servers
from app.advocate.report import pairs_to_csv
from app.domain.models import AdvocateColumnMapping
from app.engine.params import PARAMS

DEMO_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "demo_cases"
XLSX = DEMO_DIR / "advocate_servers.xlsx"
EXPECTED = DEMO_DIR / "advocate_expected.json"

pytestmark = pytest.mark.skipif(
    not XLSX.is_file(),
    reason="demo file missing; run `python -m fixtures.generator.advocate_demo`",
)


@pytest.fixture(scope="module")
def expected() -> dict:
    return json.loads(EXPECTED.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def truth(expected: dict) -> dict[str, dict]:
    return {server["server_id"]: server for server in expected["servers"]}


async def _reports(expected: dict):
    mapping = AdvocateColumnMapping.model_validate(expected["mapping"])
    outcome = await parse_records(
        XLSX.read_bytes(), "advocate_servers.xlsx", mapping, max_rows=50_000, max_lookups=0
    )
    return outcome, analyze_servers(outcome.records, PARAMS)


@pytest.mark.asyncio
async def test_every_row_of_the_demo_file_is_usable(expected: dict) -> None:
    """Nothing to explain away on the one file that must never fail in front of a judge."""
    outcome, _ = await _reports(expected)

    assert outcome.rows_read == expected["n_rows"]
    assert outcome.rejected == []
    assert len(outcome.records) == expected["n_rows"]


@pytest.mark.asyncio
async def test_the_demo_file_needs_no_network(expected: dict) -> None:
    """It carries coordinates, so the lookup budget can be zero and nothing is refused.

    `tests/conftest.py` blocks the transport outright, so a regression that reintroduced
    a lookup here would fail loudly rather than work on a machine that happens to be
    online.
    """
    outcome, _ = await _reports(expected)

    assert outcome.addresses_geocoded == 0


@pytest.mark.asyncio
async def test_each_server_is_found_with_the_filings_it_was_built_with(
    expected: dict, truth: dict[str, dict]
) -> None:
    _, reports = await _reports(expected)

    assert {r.server_id for r in reports} == set(truth)
    for report in reports:
        assert report.n_records == truth[report.server_id]["n_records"]


@pytest.mark.asyncio
async def test_exactly_the_injected_hops_are_reported(
    expected: dict, truth: dict[str, dict], capsys
) -> None:
    """Precision and recall on the demo file, both 1.0, or the demo tells a false story."""
    _, reports = await _reports(expected)

    with capsys.disabled():
        print("\ndemo advocate file:")
        for report in reports:
            print(
                f"  rank {report.risk_rank}  server {report.server_id}  "
                f"{report.n_records} filings  {len(report.impossible_pairs)} impossible  "
                f"{len(report.repeated_descriptions)} reused descriptions  "
                f"busiest hour {report.max_services_per_hour}"
            )

    for report in reports:
        assert len(report.impossible_pairs) == truth[report.server_id]["impossible_hops"]


@pytest.mark.asyncio
async def test_the_two_servers_with_nothing_to_find_are_ranked_last(
    expected: dict, truth: dict[str, dict]
) -> None:
    _, reports = await _reports(expected)

    clean = [r for r in reports if truth[r.server_id]["impossible_hops"] == 0]

    assert {r.risk_rank for r in clean} == {3, 4}
    assert all(r.repeated_descriptions == [] for r in clean)


@pytest.mark.asyncio
async def test_the_reused_description_is_found_at_every_door_it_was_planted_at(
    expected: dict, truth: dict[str, dict]
) -> None:
    _, reports = await _reports(expected)

    for report in reports:
        planted = truth[report.server_id]["reused_description"]
        if planted is None:
            continue
        found = dict(report.repeated_descriptions)
        assert found.get(planted) == truth[report.server_id]["reused_description_doors"]


@pytest.mark.asyncio
async def test_the_demo_exports_a_csv_with_one_line_per_reported_sequence(
    expected: dict,
) -> None:
    _, reports = await _reports(expected)

    lines = pairs_to_csv(reports).decode("utf-8-sig").strip().splitlines()

    assert len(lines) == 1 + sum(len(r.impossible_pairs) for r in reports)


@pytest.mark.asyncio
async def test_the_demo_file_carries_no_real_persons_data(expected: dict) -> None:
    """Bible §16. Descriptions are coded strings and case numbers are invented; the only
    real thing in the file is the geography."""
    outcome, _ = await _reports(expected)

    assert all(record.case_ref and record.case_ref.startswith("CV-") for record in outcome.records)
    assert all(
        record.recipient_desc and record.recipient_desc.count("/") == 5
        for record in outcome.records
    )
