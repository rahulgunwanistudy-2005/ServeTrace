"""Score the batch engine against the advocate corpus' answer key.

`fixtures/generator/advocate.py` builds five servers' filings and rewrites some of them
into sequences nobody could have travelled, writing down exactly which. It decides that
from where it *placed* the records and never by calling this engine — the same
independence the case corpus rests on, and the same reason these numbers are worth
publishing rather than eyeballing.

Precision leads here, where recall leads nowhere. The defendant flow's worst failure is
telling somebody their own data conflicts with an affidavit when it does not; advocate
mode's worst failure is naming a process server whose filings are consistent, in a report
that goes to a supervisor or to DCWP under somebody's name. A missed pair costs an
advocate one line of evidence. A false pair costs them their credibility.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.advocate.patterns import analyze_servers
from app.domain.models import LatLng, ServerReport, ServiceRecord
from app.engine.params import PARAMS, PARAMS_VERSION


@dataclass
class AdvocateReport:
    params_version: str
    n_records: int = 0
    n_servers: int = 0
    n_flagged_servers: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    clean_servers: int = 0
    clean_servers_accused: int = 0
    """The gate. A server the generator built as ordinary, named by the report."""
    description_doors_expected: int = 0
    description_doors_found: int = 0
    runtime_ms: float = 0.0
    per_server: list[dict[str, Any]] = field(default_factory=list)


def load_records(path: Path) -> list[ServiceRecord]:
    with path.open(encoding="utf-8") as handle:
        return [
            ServiceRecord(
                server_id=row["server_id"],
                at=datetime.fromisoformat(row["at"]),
                loc=LatLng(lat=float(row["lat"]), lng=float(row["lng"])),
                address=row["address"] or None,
                case_ref=row["case_ref"] or None,
                outcome=row["outcome"] or None,
                recipient_desc=row["recipient_desc"] or None,
            )
            for row in csv.DictReader(handle)
        ]


def _positions(records: list[ServiceRecord], server_id: str) -> dict[tuple[Any, ...], int]:
    """The answer key names records by their position in the server's time-sorted filings.

    That is the only stable name a record has: two filings at the same door on the same
    day are otherwise identical, and a positional key is what keeps the scoring honest
    about *which* pair was found rather than merely how many.
    """
    ordered = sorted(
        (r for r in records if r.server_id == server_id),
        key=lambda r: (r.at, r.address or "", r.case_ref or ""),
    )
    return {(r.at, r.address, r.case_ref): index for index, r in enumerate(ordered)}


def _found(records: list[ServiceRecord], report: ServerReport) -> set[tuple[int, int]]:
    position = _positions(records, report.server_id)
    return {
        (
            position[(pair.a.at, pair.a.address, pair.a.case_ref)],
            position[(pair.b.at, pair.b.address, pair.b.case_ref)],
        )
        for pair in report.impossible_pairs
    }


def score(records: list[ServiceRecord], truth: dict[str, dict[str, Any]]) -> AdvocateReport:
    started = time.perf_counter()
    reports = analyze_servers(records, PARAMS)
    runtime_ms = (time.perf_counter() - started) * 1000

    scored = AdvocateReport(
        params_version=PARAMS_VERSION,
        n_records=len(records),
        n_servers=len(reports),
        runtime_ms=round(runtime_ms, 1),
    )

    for report in reports:
        expected = truth[report.server_id]
        found = _found(records, report)
        wanted = {(p["index_a"], p["index_b"]) for p in expected["injected_pairs"]}

        scored.true_positives += len(found & wanted)
        scored.false_positives += len(found - wanted)
        scored.false_negatives += len(wanted - found)

        flagged = bool(report.impossible_pairs or report.repeated_descriptions)
        scored.n_flagged_servers += int(flagged)
        if not expected["is_bad"]:
            scored.clean_servers += 1
            scored.clean_servers_accused += int(flagged)

        doors = dict(report.repeated_descriptions)
        if expected["repeated_description"]:
            scored.description_doors_expected += expected["repeated_description_addresses"]
            scored.description_doors_found += doors.get(expected["repeated_description"], 0)

        scored.per_server.append(
            {
                "server_id": report.server_id,
                "risk_rank": report.risk_rank,
                "is_bad": expected["is_bad"],
                "n_records": report.n_records,
                "pairs_found": len(found),
                "pairs_injected": len(wanted),
                "max_services_per_hour": report.max_services_per_hour,
                "repeated_descriptions": len(report.repeated_descriptions),
            }
        )

    positives = scored.true_positives + scored.false_positives
    actual = scored.true_positives + scored.false_negatives
    scored.precision = round(scored.true_positives / positives, 4) if positives else 1.0
    scored.recall = round(scored.true_positives / actual, 4) if actual else 1.0
    return scored


def format_report(report: AdvocateReport) -> str:
    lines = [
        "ServeTrace advocate evaluation",
        f"params {report.params_version} · {report.n_records} filings · "
        f"{report.n_servers} process servers",
        "",
        f"CLEAN SERVERS NAMED: {report.clean_servers_accused} of {report.clean_servers}",
        "",
        f"impossible pairs  TP {report.true_positives}  FP {report.false_positives}  "
        f"FN {report.false_negatives}",
        f"precision {report.precision:.1%}   recall {report.recall:.1%}",
        f"reused descriptions: {report.description_doors_found}/"
        f"{report.description_doors_expected} doors found",
        f"runtime: {report.runtime_ms} ms for {report.n_records} filings",
        "",
        "per server:",
    ]
    lines += [
        f"  rank {row['risk_rank']}  {row['server_id']:<10} "
        f"{'flagged by generator' if row['is_bad'] else 'ordinary':<22} "
        f"{row['n_records']:>5} filings  "
        f"pairs {row['pairs_found']}/{row['pairs_injected']}  "
        f"busiest hour {row['max_services_per_hour']}"
        for row in report.per_server
    ]
    return "\n".join(lines)


def published_figures(report: AdvocateReport) -> dict[str, Any]:
    """What the Methodology page publishes about batch mode."""
    return {
        "n_records": report.n_records,
        "n_servers": report.n_servers,
        "true_positives": report.true_positives,
        "false_positives": report.false_positives,
        "false_negatives": report.false_negatives,
        "precision": report.precision,
        "recall": report.recall,
        "clean_servers": report.clean_servers,
        "clean_servers_accused": report.clean_servers_accused,
        "runtime_ms": report.runtime_ms,
    }


def run(corpus: Path, out: Path) -> AdvocateReport:
    advocate_dir = corpus / "advocate"
    records = load_records(advocate_dir / "records.csv")
    truth = {
        server["server_id"]: server
        for server in json.loads((advocate_dir / "ground_truth.json").read_text())["servers"]
    }
    report = score(records, truth)

    out.mkdir(parents=True, exist_ok=True)
    (out / "advocate.json").write_text(json.dumps(asdict(report), indent=1, sort_keys=True) + "\n")
    return report
