"""`POST /api/advocate/*`: the batch engine behind stateless requests."""

from __future__ import annotations

import io
import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.config import get_settings
from app.domain.models import ServiceMethod
from app.main import create_app
from tests.engine.conftest import affidavit

HEADER = "server_id,at,lat,lng,address,case_ref,outcome,recipient_desc"
MAPPING = json.dumps(
    {
        "server_id": "server_id",
        "at": "at",
        "lat": "lat",
        "lng": "lng",
        "address": "address",
        "outcome": "outcome",
        "recipient_desc": "recipient_desc",
    }
)

# 11 km apart, three minutes apart: one sequence nobody could have travelled.
ROWS = (
    "SRV-1,2025-03-04T09:00:00-05:00,40.853454,-73.867397,1 SYNTHETIC ST,CV-1-25,served,F/45",
    "SRV-1,2025-03-04T09:03:00-05:00,40.853454,-73.736833,2 SYNTHETIC ST,CV-2-25,served,M/50",
    "SRV-1,2025-03-04T10:30:00-05:00,40.853454,-73.860000,3 SYNTHETIC ST,CV-3-25,served,F/30",
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def upload(*rows: str, name: str = "records.csv") -> dict[str, tuple[str, io.BytesIO, str]]:
    body = ("\n".join((HEADER, *rows)) + "\n").encode()
    return {"file": (name, io.BytesIO(body), "text/csv")}


def post(client: TestClient, *rows: str, mapping: str = MAPPING, name: str = "records.csv"):
    return client.post(
        "/api/advocate/analyze", files=upload(*rows, name=name), data={"mapping": mapping}
    )


# --- The happy path ---------------------------------------------------------------------------


def test_a_spreadsheet_of_filings_comes_back_as_a_ranked_report(client: TestClient) -> None:
    response = post(client, *ROWS)

    assert response.status_code == 200
    body = response.json()
    assert len(body["reports"]) == 1
    report = body["reports"][0]
    assert report["server_id"] == "SRV-1"
    assert report["risk_rank"] == 1
    assert len(report["impossible_pairs"]) == 1
    assert report["impossible_pairs"][0]["required_speed_kmh"] > 80


def test_the_stats_account_for_every_row_that_went_in(client: TestClient) -> None:
    """The denominator. `rows_read` must equal records plus rejections, always."""
    body = post(client, *ROWS).json()

    stats = body["stats"]
    assert stats["rows_read"] == 3
    assert stats["records"] + stats["rejected"] == stats["rows_read"]
    assert stats["servers"] == 1


def test_the_response_is_stamped_with_the_versions_that_produced_it(client: TestClient) -> None:
    """The same discipline as `CaseAnalysis`: a number without its thresholds is not
    reproducible, and this one may end up in a complaint."""
    stats = post(client, *ROWS).json()["stats"]

    assert stats["params_version"]
    assert stats["engine_version"]
    assert stats["generated_at"]


def test_column_names_can_be_read_before_any_mapping_is_chosen(client: TestClient) -> None:
    response = client.post("/api/advocate/columns", files=upload(*ROWS))

    assert response.status_code == 200
    assert response.json()["columns"] == HEADER.split(",")


def test_an_xlsx_upload_is_read_the_same_way_as_a_csv(client: TestClient) -> None:
    book = Workbook()
    sheet = book.active
    sheet.append(HEADER.split(","))
    for row in ROWS:
        cells = row.split(",")
        sheet.append([cells[0], cells[1], float(cells[2]), float(cells[3]), *cells[4:]])
    buffer = io.BytesIO()
    book.save(buffer)

    response = client.post(
        "/api/advocate/analyze",
        files={"file": ("records.xlsx", io.BytesIO(buffer.getvalue()), "application/vnd.ms-excel")},
        data={"mapping": MAPPING},
    )

    assert response.status_code == 200
    assert len(response.json()["reports"][0]["impossible_pairs"]) == 1


# --- Refusals ---------------------------------------------------------------------------------


def test_a_row_that_cannot_be_read_comes_back_in_the_rejected_list(client: TestClient) -> None:
    body = post(client, *ROWS, "SRV-1,who knows,40.85,-73.9,4 SYNTHETIC ST,CV-4-25,served,").json()

    assert body["stats"]["rows_read"] == 4
    assert [r["row"] for r in body["rejected"]] == [5]
    assert body["rejected"][0]["code"] == "missing_time"


def test_an_empty_upload_is_refused_with_the_typed_envelope(client: TestClient) -> None:
    response = client.post(
        "/api/advocate/analyze",
        files={"file": ("records.csv", io.BytesIO(b""), "text/csv")},
        data={"mapping": MAPPING},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_input"


def test_a_mapping_that_is_not_json_is_refused_without_echoing_it(client: TestClient) -> None:
    response = post(client, *ROWS, mapping="{not json")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_input"
    assert "not json" not in response.json()["error"]["message"]


def test_a_mapping_missing_the_time_column_is_refused(client: TestClient) -> None:
    response = post(client, *ROWS, mapping=json.dumps({"server_id": "server_id", "lat": "lat"}))

    assert response.status_code == 400


def test_an_unsupported_file_type_is_refused(client: TestClient) -> None:
    response = post(client, *ROWS, name="records.pdf")

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file"


def test_the_demo_deployment_takes_no_uploads(client: TestClient) -> None:
    get_settings.cache_clear()
    try:
        settings = get_settings()
        object.__setattr__(settings, "demo_only", True)
        response = post(client, *ROWS)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "demo_only"
    finally:
        get_settings.cache_clear()


# --- Affidavits in, the same report out -----------------------------------------------------------


def test_confirmed_affidavits_can_be_analysed_without_any_spreadsheet(client: TestClient) -> None:
    """An advocate who has run clients through the defendant flow already holds these."""
    one = affidavit(server_license="1234567", method=ServiceMethod.SUBSTITUTE)

    response = client.post(
        "/api/advocate/analyze-affidavits", json=[one.model_dump(mode="json")] * 2
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reports"][0]["server_id"] == "1234567"
    assert body["stats"]["records"] == 2


def test_an_affidavit_naming_no_server_is_reported_rather_than_dropped(client: TestClient) -> None:
    anonymous = affidavit(server_license=None, server_name=None)

    body = client.post(
        "/api/advocate/analyze-affidavits", json=[anonymous.model_dump(mode="json")]
    ).json()

    assert body["reports"] == []
    assert body["rejected"][0]["code"] == "missing_server"


# --- Export -----------------------------------------------------------------------------------


def test_the_impossible_pairs_export_is_a_csv_the_browser_will_download(
    client: TestClient,
) -> None:
    reports = post(client, *ROWS).json()["reports"]

    response = client.post("/api/advocate/export.csv", json=reports)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    body = response.content.decode("utf-8-sig")
    assert body.splitlines()[0].startswith("risk_rank,server_id")
    assert "SRV-1" in body


def test_the_server_summary_export_has_one_row_per_server(client: TestClient) -> None:
    reports = post(client, *ROWS).json()["reports"]

    response = client.post("/api/advocate/export.csv?kind=servers", json=reports)

    assert response.status_code == 200
    lines = response.content.decode("utf-8-sig").strip().splitlines()
    assert len(lines) == 2  # header plus one server


def test_the_export_writes_times_the_way_the_rest_of_the_product_writes_them(
    client: TestClient,
) -> None:
    """The reader is checking this against a paper affidavit that says "9:00 AM"."""
    reports = post(client, *ROWS).json()["reports"]

    body = client.post("/api/advocate/export.csv", json=reports).content.decode("utf-8-sig")

    assert "9:00 AM on March 4, 2025" in body


# --- The filings the map draws --------------------------------------------------------------


def test_the_filings_come_back_so_the_map_can_draw_the_whole_week(client: TestClient) -> None:
    """Without them a map would show only the flagged steps, implying they were the
    server's entire output."""
    body = post(client, *ROWS).json()

    assert len(body["records"]) == 3
    assert body["stats"]["records_returned"] == 3


def test_a_file_over_the_map_cap_keeps_whole_servers_rather_than_half_a_week(
    client: TestClient,
) -> None:
    """Half a server's week is worse than none of it: the cluster the flagged step is
    judged against is exactly what would be missing."""
    get_settings.cache_clear()
    try:
        settings = get_settings()
        object.__setattr__(settings, "max_advocate_map_records", 3)
        rows = [
            f"SRV-{server},2025-03-04T{9 + i:02d}:00:00-05:00,40.85345,-73.8674,"
            f"{i} SYNTHETIC ST,CV-{server}{i}-25,served,F/45"
            for server in (1, 2)
            for i in range(3)
        ]
        body = post(client, *rows).json()

        returned = {record["server_id"] for record in body["records"]}
        assert len(returned) == 1
        assert body["stats"]["records"] == 6
        assert body["stats"]["records_returned"] == 3
    finally:
        get_settings.cache_clear()
