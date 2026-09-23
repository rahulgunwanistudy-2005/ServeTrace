"""Bible §11.4, rule by rule.

The thing being protected here is precision. An advocate takes this report to a
supervisor, to opposing counsel, or to DCWP, and a false impossible pair damages the
person who filed it. So most of these tests are about what the engine must *not* say.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from app.advocate.patterns import (
    analyze_servers,
    impossible_pairs,
    max_services_per_hour,
    normalize_description,
    repeated_descriptions,
)
from app.engine.params import PARAMS
from tests.advocate.conftest import record

# --- Impossible pairs ---------------------------------------------------------------------


def test_an_ordinary_working_day_produces_no_pairs() -> None:
    """Half an hour and two kilometres between doors is a process server's job."""
    day = [record(minutes=30 * i, km=2.0 * i) for i in range(12)]

    assert impossible_pairs(day, PARAMS) == []


def test_eleven_kilometres_in_three_minutes_is_impossible() -> None:
    pairs = impossible_pairs([record(0), record(3, km=11.0)], PARAMS)

    assert len(pairs) == 1
    assert pairs[0].distance_km == 11.0
    assert pairs[0].minutes == 3.0
    assert pairs[0].required_speed_kmh > PARAMS.v_strong_kmh


def test_just_under_the_speed_threshold_is_not_flagged() -> None:
    """79 km/h through New York is implausible and the engine says nothing about it.

    Bible §11 sets `V_STRONG` generously on purpose. The point of the threshold is that
    everything above it is indefensible, not that everything below it is innocent.
    """
    # 60 minutes at 79 km/h, and under the 2 km / 5 min simultaneity clause by time.
    pairs = impossible_pairs([record(0), record(60, km=79.0)], PARAMS)

    assert pairs == []


def test_two_kilometres_within_five_minutes_is_flagged_even_below_the_speed_limit() -> None:
    """Bible §11.4's second clause. 2 km in 5 minutes is 24 km/h — an easy drive.

    What makes it impossible is not the speed but the service: a server cannot walk to a
    door, find a person, identify them and hand over papers twice in five minutes two
    kilometres apart.
    """
    pairs = impossible_pairs([record(0), record(5, km=2.5)], PARAMS)

    assert len(pairs) == 1
    assert pairs[0].required_speed_kmh < PARAMS.v_strong_kmh


def test_a_short_hop_inside_five_minutes_is_an_ordinary_pair_of_doors() -> None:
    """The other side of the same clause: 1.5 km in five minutes is one street to the next."""
    assert impossible_pairs([record(0), record(5, km=1.5)], PARAMS) == []


def test_two_kilometres_in_six_minutes_is_outside_the_simultaneity_clause() -> None:
    assert impossible_pairs([record(0), record(6, km=2.5)], PARAMS) == []


def test_records_at_the_same_instant_get_a_finite_speed() -> None:
    """Infinity is not JSON, and a report that cannot be serialised is not a report.

    The elapsed-time floor is `engine/feasibility.py`'s, so the same two points are priced
    the same whichever half of the product is looking at them.
    """
    pairs = impossible_pairs([record(0), record(0, km=9.0, bearing=270)], PARAMS)

    assert len(pairs) == 1
    assert pairs[0].minutes == 0.0
    assert pairs[0].required_speed_kmh == 9.0 * 60  # the 60-second floor, in km/h


def test_duplicate_rows_are_not_an_impossible_pair() -> None:
    """The same filing exported twice is a data problem, not evidence of anything."""
    assert impossible_pairs([record(0, km=3.0), record(0, km=3.0)], PARAMS) == []


def test_only_consecutive_records_are_compared() -> None:
    """Bible §11.4 compares consecutive records. A far-apart pair with a plausible stop
    between them is a journey, and calling it impossible would be wrong."""
    day = [record(0), record(30, km=20.0), record(60, km=40.0)]

    assert impossible_pairs(day, PARAMS) == []


# --- Throughput ---------------------------------------------------------------------------


def test_throughput_counts_the_busiest_hour_not_the_average() -> None:
    quiet = [record(minutes=120 * i) for i in range(4)]
    burst = [record(minutes=600 + i) for i in range(9)]

    assert max_services_per_hour(sorted(quiet + burst, key=lambda r: r.at)) == 9


def test_the_hour_window_is_half_open_at_its_start() -> None:
    """Two services exactly an hour apart are not in one 60-minute window.

    Flagging needs the count to rise above a threshold, so the reading that counts fewer
    is the one that accuses less, which is the direction bible §11 says to err.
    """
    assert max_services_per_hour([record(0), record(60)]) == 1
    assert max_services_per_hour([record(0), record(59)]) == 2


def test_attempts_are_not_counted_as_completed_services() -> None:
    """A `not_home` is the evidence of diligence 308(4) asks for. Counting it would give
    the server who documents fruitless visits the worse number."""
    knocking = [record(minutes=i, outcome="not_home") for i in range(20)]

    assert max_services_per_hour(knocking) == 0


def test_affixing_counts_as_completed() -> None:
    """Under 308(4) the affixing is the service. Bible §5 L3."""
    assert max_services_per_hour([record(0, outcome="affixed"), record(5, outcome="affixed")]) == 2


def test_an_empty_day_has_no_busiest_hour() -> None:
    assert max_services_per_hour([]) == 0


# --- Repeated descriptions ------------------------------------------------------------------


def test_one_description_at_three_doors_is_reported() -> None:
    same = "M/Medium/Brown/45/70/180"
    rows = [record(minutes=60 * i, km=float(i + 1), desc=same) for i in range(3)]

    assert repeated_descriptions(rows, PARAMS) == [(same, 3)]


def test_two_doors_is_not_enough() -> None:
    same = "M/Medium/Brown/45/70/180"
    rows = [record(minutes=60 * i, km=float(i + 1), desc=same) for i in range(2)]

    assert repeated_descriptions(rows, PARAMS) == []


def test_the_same_description_at_one_address_is_a_household_not_a_pattern() -> None:
    """Three visits to one door finding the same person is exactly what should happen."""
    rows = [
        record(minutes=60 * i, km=1.0, address="1 SYNTHETIC STREET", desc="F/45") for i in range(5)
    ]

    assert repeated_descriptions(rows, PARAMS) == []


def test_case_spacing_and_punctuation_do_not_split_one_description_in_two() -> None:
    written = ("M/Medium/Brown/45", "m medium brown 45", "  M - MEDIUM - BROWN - 45 ")
    rows = [record(minutes=60 * i, km=float(i + 1), desc=text) for i, text in enumerate(written)]

    assert repeated_descriptions(rows, PARAMS) == [(written[0], 3)]


def test_the_description_is_reported_as_it_was_first_written() -> None:
    """An advocate reads this list. `M/MED/BRN/45` is legible; its normalised key is not."""
    rows = [record(minutes=60 * i, km=float(i + 1), desc="M/MED/BRN/45") for i in range(3)]

    assert repeated_descriptions(rows, PARAMS)[0][0] == "M/MED/BRN/45"


def test_rows_without_a_description_are_ignored_rather_than_grouped() -> None:
    rows = [
        record(minutes=60 * i, km=float(i + 1), desc=desc)
        for i, desc in enumerate((None, "", "   "))
    ]

    assert repeated_descriptions(rows, PARAMS) == []


def test_addresses_are_counted_by_coordinate_when_the_file_has_no_addresses() -> None:
    rows = [record(minutes=60 * i, km=float(i + 1), address="", desc="F/60") for i in range(3)]

    assert repeated_descriptions(rows, PARAMS) == [("F/60", 3)]


def test_normalize_description_is_idempotent() -> None:
    once = normalize_description("M / Medium / Brown / 45")

    assert normalize_description(once) == once


# --- Assembly and ranking ---------------------------------------------------------------------


def test_servers_are_separated_and_never_compared_with_each_other() -> None:
    """Two servers a borough apart at the same minute are two people doing their jobs."""
    records = [
        record(0, km=0.0, server_id="SRV-001"),
        record(0, km=12.0, server_id="SRV-002"),
    ]

    reports = analyze_servers(records, PARAMS)

    assert len(reports) == 2
    assert all(report.impossible_pairs == [] for report in reports)


def test_ranking_puts_the_server_with_more_impossible_pairs_first() -> None:
    clean = [record(minutes=30 * i, km=1.0 * i, server_id="AAA-clean") for i in range(6)]
    dirty = [record(0, server_id="ZZZ-dirty"), record(3, km=11.0, server_id="ZZZ-dirty")]

    reports = analyze_servers(clean + dirty, PARAMS)

    assert [r.server_id for r in reports] == ["ZZZ-dirty", "AAA-clean"]
    assert [r.risk_rank for r in reports] == [1, 2]


def test_identical_servers_are_ranked_by_id_so_the_report_is_stable() -> None:
    rows = [record(minutes=30 * i, server_id=name) for name in ("SRV-B", "SRV-A") for i in range(3)]

    first = analyze_servers(rows, PARAMS)
    second = analyze_servers(list(reversed(rows)), PARAMS)

    assert [r.server_id for r in first] == ["SRV-A", "SRV-B"]
    assert [r.server_id for r in first] == [r.server_id for r in second]


def test_the_report_does_not_depend_on_the_order_rows_arrive_in() -> None:
    rows = [record(0), record(3, km=11.0), record(45, km=12.0), record(90, km=1.0)]

    forward = analyze_servers(rows, PARAMS)
    backward = analyze_servers(list(reversed(rows)), PARAMS)

    assert forward == backward


def test_n_records_counts_that_servers_rows_only() -> None:
    rows = [record(minutes=30 * i, server_id="SRV-001") for i in range(4)]
    rows += [record(minutes=30 * i, server_id="SRV-002") for i in range(7)]

    by_id = {r.server_id: r for r in analyze_servers(rows, PARAMS)}

    assert by_id["SRV-001"].n_records == 4
    assert by_id["SRV-002"].n_records == 7


def test_raising_the_speed_threshold_can_only_remove_pairs() -> None:
    """A monotonicity check in the same spirit as the engine's §11.1 invariants.

    The two clauses of bible §11.4 are independent, and this shows it: the three-minute
    hop survives a fourfold rise in the speed limit because it was never the speed that
    made it impossible, while the ten-minute dash does not.
    """
    hop = [record(0), record(3, km=11.0)]
    dash = [record(60), record(70, km=20.0)]

    strict = impossible_pairs(hop + dash, PARAMS)
    lenient = impossible_pairs(hop + dash, replace(PARAMS, v_strong_kmh=PARAMS.v_strong_kmh * 4))

    assert len(strict) == 2
    assert all(pair in strict for pair in lenient)
    assert [pair.minutes for pair in lenient] == [3.0]


def test_a_day_spanning_the_spring_forward_gap_is_measured_in_real_elapsed_time() -> None:
    """2 AM does not exist on 9 March 2025, and a wall clock would read the gap as an hour.

    Every time in a `ServiceRecord` is already aware, so subtraction is real elapsed time.
    The value of this test is that it would fail the day someone reaches for wall-clock
    arithmetic.
    """
    first = record(0)
    second = first.model_copy(update={"at": first.at + timedelta(minutes=3)})
    moved = second.model_copy(update={"loc": record(3, km=11.0).loc})

    assert len(impossible_pairs([first, moved], PARAMS)) == 1
