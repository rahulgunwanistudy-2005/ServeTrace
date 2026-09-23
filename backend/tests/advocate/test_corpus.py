"""The advocate acceptance gate: the batch engine against an answer key it never sees.

`fixtures/generator/advocate.py` builds five servers' filings and deliberately rewrites
some of them into sequences nobody could have travelled, recording exactly which ones.
It decides that from where it *put* the records, and never by asking this engine — the
same independence `tests/engine/test_fixture_sweep.py` rests on, and the same reason it
is worth more than any snapshot.

Two numbers matter, and they are not symmetric. Recall says how much of a pattern the
report would surface. Precision says whether an advocate can rely on what it surfaced,
and a false pair in a DCWP complaint damages the person who filed it, so precision is the
gate.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import pytest

from app.advocate.patterns import analyze_servers
from app.domain.models import LatLng, ServerReport, ServiceRecord
from app.engine.params import PARAMS

CORPUS = Path(__file__).resolve().parents[3] / "fixtures" / "out" / "advocate"


def _records() -> list[ServiceRecord]:
    with (CORPUS / "records.csv").open(encoding="utf-8") as handle:
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


@pytest.fixture(scope="module")
def corpus() -> tuple[list[ServiceRecord], dict[str, dict], list[ServerReport]]:
    if not (CORPUS / "records.csv").is_file():
        pytest.skip("corpus not generated; run `python -m fixtures.generator`")
    records = _records()
    truth = {
        server["server_id"]: server
        for server in json.loads((CORPUS / "ground_truth.json").read_text())["servers"]
    }
    return records, truth, analyze_servers(records, PARAMS)


def _found_indices(records: list[ServiceRecord], report: ServerReport) -> set[tuple[int, int]]:
    """Turn the pairs back into positions in the server's time-sorted filings.

    The answer key is written in those terms because that is the only stable name a
    record has: two filings at the same door on the same day are otherwise identical.
    """
    ordered = sorted(
        (r for r in records if r.server_id == report.server_id),
        key=lambda r: (r.at, r.address or "", r.case_ref or ""),
    )
    position = {(r.at, r.address, r.case_ref): i for i, r in enumerate(ordered)}
    return {
        (
            position[(p.a.at, p.a.address, p.a.case_ref)],
            position[(p.b.at, p.b.address, p.b.case_ref)],
        )
        for p in report.impossible_pairs
    }


def _confusion(corpus) -> tuple[int, int, int]:
    records, truth, reports = corpus
    true_positive = false_positive = false_negative = 0
    for report in reports:
        found = _found_indices(records, report)
        wanted = {(p["index_a"], p["index_b"]) for p in truth[report.server_id]["injected_pairs"]}
        true_positive += len(found & wanted)
        false_positive += len(found - wanted)
        false_negative += len(wanted - found)
    return true_positive, false_positive, false_negative


def test_no_clean_server_is_accused_of_anything(corpus, capsys) -> None:
    """The gate. Three of the five servers did nothing wrong, and the report must say so.

    This is advocate mode's version of the no-false-accusation gate: the thing that would
    actually hurt someone is a report that names a server whose filings are consistent.
    """
    records, truth, reports = corpus
    clean = [r for r in reports if not truth[r.server_id]["is_bad"]]

    with capsys.disabled():
        true_positive, false_positive, false_negative = _confusion(corpus)
        print(
            f"\nadvocate corpus: {len(records)} filings, {len(reports)} servers\n"
            f"  impossible pairs  TP={true_positive} FP={false_positive} FN={false_negative}\n"
            f"  precision={true_positive / max(true_positive + false_positive, 1):.4f}  "
            f"recall={true_positive / max(true_positive + false_negative, 1):.4f}\n"
        )

    assert len(clean) == 3
    assert all(report.impossible_pairs == [] for report in clean)
    assert all(report.repeated_descriptions == [] for report in clean)


def test_every_injected_pair_is_found(corpus) -> None:
    """Recall 1.0. S5's acceptance gate."""
    _, _, false_negative = _confusion(corpus)

    assert false_negative == 0


def test_nothing_is_reported_that_was_not_injected(corpus) -> None:
    """Precision 1.0 over 2,000 filings of ordinary work."""
    _, false_positive, _ = _confusion(corpus)

    assert false_positive == 0


def test_the_answer_key_is_not_empty(corpus) -> None:
    """A gate over zero injected pairs would pass for the wrong reason."""
    true_positive, _, _ = _confusion(corpus)

    assert true_positive == 12


def test_the_two_bad_servers_rank_above_the_three_clean_ones(corpus) -> None:
    """What the advocate actually reads is the order of the table."""
    _, truth, reports = corpus

    top_two = {report.server_id for report in reports[:2]}

    assert top_two == {sid for sid, t in truth.items() if t["is_bad"]}


def test_the_reused_description_is_found_at_the_number_of_doors_it_was_planted_at(
    corpus,
) -> None:
    _, truth, reports = corpus

    for report in reports:
        expected = truth[report.server_id]
        if not expected["repeated_description"]:
            continue
        found = dict(report.repeated_descriptions)
        assert expected["repeated_description"] in found
        assert found[expected["repeated_description"]] == expected["repeated_description_addresses"]


def test_no_ordinary_day_trips_the_throughput_flag(corpus) -> None:
    """Twelve completed services in one hour is a high bar, and eight to fourteen spread
    across a day does not come near it. A flag that fired here would be noise."""
    _, _, reports = corpus

    assert all(report.max_services_per_hour <= PARAMS.adv_max_per_hour for report in reports)
