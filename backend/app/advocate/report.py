"""Exports an advocate can attach to something. Bible §14.6.

CSV, because the thing an advocate does with this is put it in front of somebody else:
a supervisor, opposing counsel, or DCWP, which bible §5 L7 says takes complaints about
process servers from legal advocates. A screen they have to screenshot is not evidence.

The PDF report is session 6's, where the print stylesheet and the Jinja templates live.
"""

from __future__ import annotations

import csv
import io

from app.domain.models import BatchReport, ServerReport
from app.engine.copy import fmt_datetime

PAIR_COLUMNS = (
    "risk_rank",
    "server_id",
    "first_at",
    "first_address",
    "first_case_ref",
    "second_at",
    "second_address",
    "second_case_ref",
    "distance_km",
    "minutes_apart",
    "required_speed_kmh",
)

SERVER_COLUMNS = (
    "risk_rank",
    "server_id",
    "records",
    "impossible_pairs",
    "max_services_per_hour",
    "repeated_descriptions",
)


def pairs_to_csv(reports: list[ServerReport]) -> bytes:
    """Every sequence that does not add up, one per row, worst server first.

    Times are written in New York local time the way the rest of the product writes them,
    rather than as ISO instants: the reader of this file is checking it against a paper
    affidavit that says "7:42 PM".
    """
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(PAIR_COLUMNS)
    for report in reports:
        for pair in report.impossible_pairs:
            writer.writerow(
                (
                    report.risk_rank,
                    report.server_id,
                    fmt_datetime(pair.a.at),
                    pair.a.address or "",
                    pair.a.case_ref or "",
                    fmt_datetime(pair.b.at),
                    pair.b.address or "",
                    pair.b.case_ref or "",
                    f"{pair.distance_km:.3f}",
                    f"{pair.minutes:.1f}",
                    f"{pair.required_speed_kmh:.1f}",
                )
            )
    # utf-8-sig: Excel reads a plain UTF-8 CSV as cp1252 and mangles every street name
    # with an accent in it.
    return buffer.getvalue().encode("utf-8-sig")


def servers_to_csv(reports: list[ServerReport]) -> bytes:
    """One row per server: the summary table, in the order the screen ranks them."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(SERVER_COLUMNS)
    for report in reports:
        writer.writerow(
            (
                report.risk_rank,
                report.server_id,
                report.n_records,
                len(report.impossible_pairs),
                report.max_services_per_hour,
                len(report.repeated_descriptions),
            )
        )
    return buffer.getvalue().encode("utf-8-sig")


FLAG_COLUMNS = ("affidavit", "index_number", "server_id", "agency_key", "rule", "flagged")

AGENCY_COLUMNS = (
    "risk_rank",
    "agency_key",
    "agency",
    "affidavits",
    "servers",
    "impossible_pairs",
    "max_services_per_hour",
    "repeated_descriptions",
    *(f"{code}_flagged_of_applicable" for code in ("R-T1", "R-T2", "R-T3", "R-D1", "R-M1")),
)


def flags_to_csv(report: BatchReport) -> bytes:
    """One row per affidavit and rule that applies to it, flagged or not, so every rate in
    the report can be recounted from this file by hand."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(FLAG_COLUMNS)
    for flag in report.flags:
        writer.writerow(
            (
                flag.index + 1,
                flag.case_ref or "",
                flag.server_id,
                flag.agency_key,
                flag.rule_code,
                "yes" if flag.flagged else "no",
            )
        )
    return buffer.getvalue().encode("utf-8-sig")


def agencies_to_csv(report: BatchReport) -> bytes:
    """The agency ranking, with each rule as `flagged/applicable` (blank where it never
    applied, so a 0 always means "applied and never fired")."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(AGENCY_COLUMNS)
    for agency in report.agencies:
        by_code = {rate.rule_code: rate for rate in agency.rule_rates}
        writer.writerow(
            (
                agency.risk_rank,
                agency.agency_key,
                agency.agency_display,
                agency.n_affidavits,
                " ".join(agency.servers),
                agency.impossible_pairs,
                agency.max_services_per_hour,
                len(agency.repeated_descriptions),
                *(
                    f"{by_code[code].flagged}/{by_code[code].applicable}" if code in by_code else ""
                    for code in ("R-T1", "R-T2", "R-T3", "R-D1", "R-M1")
                ),
            )
        )
    return buffer.getvalue().encode("utf-8-sig")
