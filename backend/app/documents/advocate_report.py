"""The advocate batch report as a PDF. Build prompt §6.4.

Like the packet, this decides *what* the document contains and hands the template numbers
and sentences from `copy.py`; it never writes prose of its own. The report is built from
a `BatchReport` the browser already holds, so the server recomputes nothing and keeps
nothing.
"""

from __future__ import annotations

from typing import Any

from app.documents import copy
from app.documents.packet import validate_map_png
from app.documents.render import render_html, render_pdf
from app.domain.models import BatchReport, BatchReportRequest, RuleRate, ServerReport
from app.engine.copy import fmt_datetime
from app.engine.params import PARAMS

TEMPLATE = "advocate_report.html.j2"

MAX_PAIRS_PER_AGENCY = 60
"""A long tail of pairs is a table nobody reads on paper; the CSV export carries them all."""


def _rates(rule_rates: list[RuleRate]) -> list[dict[str, Any]]:
    return [
        {
            "code": rate.rule_code,
            "name": copy.RULE_NAMES.get(rate.rule_code, rate.rule_code),
            "line": copy.rate_line(rate.flagged, rate.applicable),
            "percent": f"{rate.rate * 100:.0f}%",
        }
        for rate in rule_rates
    ]


def _pairs(servers: list[ServerReport]) -> list[dict[str, Any]]:
    rows = [
        {
            "server": report.server_id,
            "first": f"{fmt_datetime(pair.a.at)} · {pair.a.address or ''}",
            "second": f"{fmt_datetime(pair.b.at)} · {pair.b.address or ''}",
            "distance": f"{pair.distance_km:.1f} km",
            "minutes": f"{pair.minutes:.0f} min",
            "speed": f"{pair.required_speed_kmh:.0f} km/h",
        }
        for report in servers
        for pair in report.impossible_pairs
    ]
    return rows


def report_context(request: BatchReportRequest) -> dict[str, Any]:
    """Everything the template prints. Testable without a renderer."""
    report: BatchReport = request.report
    analysed = report.n_affidavits - len(report.rejected)
    by_server = {server.server_id: server for server in report.servers}
    maps = {key: validate_map_png(image) for key, image in request.map_images.items()}

    agencies = []
    for agency in report.agencies:
        servers = [by_server[s] for s in agency.servers if s in by_server]
        pairs = _pairs(servers)
        agencies.append(
            {
                "rank": agency.risk_rank,
                "key": agency.agency_key,
                "display": agency.agency_display,
                "n_affidavits": agency.n_affidavits,
                "servers": [
                    {
                        "id": s.server_id,
                        "records": s.n_records,
                        "pairs": len(s.impossible_pairs),
                        "per_hour": s.max_services_per_hour,
                    }
                    for s in servers
                ],
                "impossible_pairs": agency.impossible_pairs,
                "per_hour": agency.max_services_per_hour,
                "descriptions": [
                    {"text": text, "addresses": n} for text, n in agency.repeated_descriptions
                ],
                "rates": _rates(agency.rule_rates),
                "pairs": pairs[:MAX_PAIRS_PER_AGENCY],
                "pairs_more": max(0, len(pairs) - MAX_PAIRS_PER_AGENCY),
                "map": maps.get(agency.agency_key),
            }
        )

    return {
        "title": copy.ADVOCATE_TITLE,
        "subtitle": copy.ADVOCATE_SUBTITLE,
        "product": copy.PRODUCT,
        "disclaimer": copy.ADVOCATE_FOOTER,
        "generated_iso": copy.local(report.generated_at).isoformat(),
        "generated": copy.generated_line(
            report.generated_at, report.engine_version, report.params_version
        )
        + f" App {report.app_version}.",
        "intro": copy.advocate_intro(
            analysed, report.n_affidavits, request.unconfirmed, request.failed
        ),
        "sections": copy.ADVOCATE_SECTIONS,
        "totals": {
            "affidavits": analysed,
            "records": report.n_records,
            "servers": len(report.servers),
            "agencies": len(report.agencies),
        },
        "rates": _rates(report.rule_rates),
        "agencies": agencies,
        "rules": [
            {"code": code, "name": name, "text": copy.RULE_EXPLANATIONS[code]}
            for code, name in copy.RULE_NAMES.items()
        ],
        "method": copy.advocate_method(
            PARAMS.v_strong_kmh, PARAMS.adv_simultaneous_min, PARAMS.adv_simultaneous_km
        ),
        "limits": copy.ADVOCATE_LIMITS,
        "not_a_law_firm": copy.NOT_A_LAW_FIRM,
    }


def report_html(request: BatchReportRequest) -> str:
    return render_html(TEMPLATE, report_context(request))


def build_report(request: BatchReportRequest) -> bytes:
    return render_pdf(TEMPLATE, report_context(request))
