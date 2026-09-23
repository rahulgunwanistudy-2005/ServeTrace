"""Exports an advocate can attach to something. Bible §14.6.

CSV, because the thing an advocate does with this is put it in front of somebody else:
a supervisor, opposing counsel, or DCWP, which bible §5 L7 says takes complaints about
process servers from legal advocates. A screen they have to screenshot is not evidence.

The PDF report is session 6's, where the print stylesheet and the Jinja templates live.
"""

from __future__ import annotations

import csv
import io

from app.domain.models import ServerReport
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
