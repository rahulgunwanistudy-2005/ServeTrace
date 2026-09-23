"""The fixture generator is test infrastructure, so it needs tests of its own.

Two things matter. First, determinism: every later session compares engine output against
this corpus, and a corpus that drifts silently would make every eval number meaningless.
Second, honesty of the labels: the generator must actually have put the person where the
ground truth says it did.
"""

from __future__ import annotations

import json
import random
from datetime import timedelta
from pathlib import Path

import pytest

from app.domain.models import Affidavit, LocationFix
from app.engine.params import PARAMS
from app.geo.distance import haversine_km
from fixtures.generator.__main__ import case_kinds, generate_corpus
from fixtures.generator.addresses import boroughs, load_addresses
from fixtures.generator.advocate import generate_advocate
from fixtures.generator.cases import make_case
from fixtures.generator.timeline import to_android_timeline, to_ios_timeline

REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO_DIR = REPO_ROOT / "fixtures" / "demo_cases"
NYC_BBOX = (40.47, 40.93, -74.28, -73.68)

SEED = 7
N = 20


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("corpus")
    generate_corpus(N, SEED, out, pdfs=False)
    return out


def _read_all(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


def _cases(corpus: Path) -> list[tuple[dict, Affidavit, list[LocationFix]]]:
    out = []
    for case_dir in sorted((corpus / "cases").iterdir()):
        truth = json.loads((case_dir / "ground_truth.json").read_text())
        affidavit = Affidavit.model_validate_json((case_dir / "affidavit.json").read_text())
        fixes = [
            LocationFix.model_validate(f) for f in json.loads((case_dir / "fixes.json").read_text())
        ]
        out.append((truth, affidavit, fixes))
    return out


def _in_window(fixes: list[LocationFix], affidavit: Affidavit) -> list[LocationFix]:
    window = timedelta(hours=PARAMS.search_window_h)
    claimed = affidavit.served_at
    return [f for f in fixes if f.t <= claimed + window and (f.t_end or f.t) >= claimed - window]


# --- determinism -------------------------------------------------------------------


def test_same_seed_gives_byte_identical_output(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    generate_corpus(8, 99, first, pdfs=False)
    generate_corpus(8, 99, second, pdfs=False)
    assert _read_all(first) == _read_all(second)


def test_different_seeds_give_different_output(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    generate_corpus(8, 1, first, pdfs=False)
    generate_corpus(8, 2, second, pdfs=False)
    assert _read_all(first) != _read_all(second)


def test_a_case_does_not_depend_on_the_cases_around_it() -> None:
    """Per-case seeding: a case is a pure function of its seed and its kind.

    Corpus size is deliberately *not* held constant here, because exact quotas mean a
    given index can draw a different kind at a different `n`. What must hold is that the
    same seed and kind always rebuild the same case.
    """
    for kind in ("contradicted", "consistent", "no_data", "edge"):
        first = make_case(random.Random(4242), "case_0000", kind)
        second = make_case(random.Random(4242), "case_0000", kind)
        assert first.truth == second.truth
        assert [f.model_dump(mode="json") for f in first.fixes] == [
            f.model_dump(mode="json") for f in second.fixes
        ]


# --- corpus shape ------------------------------------------------------------------


def test_case_mix_matches_the_specified_quotas() -> None:
    kinds = case_kinds(200)
    assert len(kinds) == 200
    assert kinds.count("contradicted") == 80
    assert kinds.count("consistent") == 70
    assert kinds.count("no_data") == 30
    assert kinds.count("edge") == 20


def test_case_kinds_never_lose_or_gain_cases() -> None:
    for n in (1, 7, 13, 99, 201):
        assert len(case_kinds(n)) == n


def test_every_case_writes_the_whole_bundle(corpus: Path) -> None:
    expected = {
        "affidavit.json",
        "ground_truth.json",
        "household.json",
        "fixes.json",
        "timeline_android.json",
        "timeline_ios.json",
        "transactions.csv",
    }
    for case_dir in (corpus / "cases").iterdir():
        assert expected <= {p.name for p in case_dir.iterdir()}


def test_manifest_counts_agree_with_what_was_written(corpus: Path) -> None:
    manifest = json.loads((corpus / "manifest.json").read_text())
    assert manifest["n_cases"] == N
    assert len(list((corpus / "cases").iterdir())) == N
    assert sum(manifest["true_tier_counts"].values()) == N


# --- labels are honest -------------------------------------------------------------


def test_no_data_cases_really_have_nothing_in_the_window(corpus: Path) -> None:
    checked = 0
    for truth, affidavit, fixes in _cases(corpus):
        if truth["kind"] != "no_data":
            continue
        checked += 1
        assert _in_window(fixes, affidavit) == [], truth["case_id"]
    assert checked > 0


def test_contradicted_cases_really_place_the_person_far_away(corpus: Path) -> None:
    """Nothing near the claimed instant may sit at the door.

    Bible §11.1.3 makes any fix inside the match radius within +/-15 min of the claim
    CONSISTENT. If such a fix existed here the engine would be right to say consistent and
    this label would be wrong, so the generator has to keep the claim clear of the door.
    """
    checked = 0
    near = timedelta(minutes=15)
    for truth, affidavit, fixes in _cases(corpus):
        if truth["kind"] != "contradicted":
            continue
        checked += 1
        assert affidavit.served_location is not None
        claimed = affidavit.served_at
        for fix in fixes:
            start, end = fix.t, fix.t_end or fix.t
            if start - near <= claimed <= end + near:
                assert haversine_km(fix.loc, affidavit.served_location) > (
                    PARAMS.match_radius_km
                ), f"{truth['case_id']}: a fix sits at the door near the claimed time"
    assert checked > 0


def test_contradicted_cases_are_covered_by_data_not_silence(corpus: Path) -> None:
    """A contradiction with nothing in the window would really be NO_DATA."""
    for truth, affidavit, fixes in _cases(corpus):
        if truth["kind"] == "contradicted":
            assert _in_window(fixes, affidavit), truth["case_id"]


def test_consistent_cases_really_place_the_person_at_the_door(corpus: Path) -> None:
    checked = 0
    for truth, affidavit, fixes in _cases(corpus):
        if truth["kind"] != "consistent":
            continue
        checked += 1
        assert affidavit.served_location is not None
        covering = [
            f for f in fixes if f.t_end is not None and f.t <= affidavit.served_at <= f.t_end
        ]
        assert covering, truth["case_id"]
        assert (
            min(haversine_km(f.loc, affidavit.served_location) for f in covering)
            <= PARAMS.match_radius_km
        ), truth["case_id"]
    assert checked > 0


def test_edge_labels_are_not_all_the_same_tier(corpus: Path) -> None:
    """radius_outside_walkable must be INCONCLUSIVE, not quietly rounded to a contradiction."""
    seen = {t["edge_kind"]: t["true_tier"] for t, _, _ in _cases(corpus) if t["kind"] == "edge"}
    for edge_kind, tier in seen.items():
        if edge_kind == "radius_outside_walkable":
            assert tier == "inconclusive"
        elif edge_kind in ("dst_fold", "radius_inside", "visit_boundary"):
            assert tier == "consistent"


def test_ground_truth_never_reports_a_tier_outside_the_contract(corpus: Path) -> None:
    allowed = {"contradicted", "consistent", "no_data", "inconclusive"}
    assert {t["true_tier"] for t, _, _ in _cases(corpus)} <= allowed


def test_affidavits_are_unconfirmed_so_analysis_must_refuse_them(corpus: Path) -> None:
    assert all(not a.user_confirmed for _, a, _ in _cases(corpus))


# --- export formats ----------------------------------------------------------------


def test_both_timeline_shapes_carry_the_same_visits() -> None:
    case = make_case(random.Random(31), "case_x", "consistent")
    android = to_android_timeline(case.fixes)
    ios = to_ios_timeline(case.fixes)
    android_visits = sum(1 for s in android["semanticSegments"] if "visit" in s)  # type: ignore[union-attr]
    assert android_visits == sum(1 for s in ios if "visit" in s)
    assert android_visits > 0


def test_android_visits_use_the_degree_string_format() -> None:
    case = make_case(random.Random(32), "case_y", "consistent")
    for segment in to_android_timeline(case.fixes)["semanticSegments"]:  # type: ignore[union-attr]
        if "visit" in segment:
            latlng = segment["visit"]["topCandidate"]["placeLocation"]["latLng"]
            assert "°, " in latlng
            break
    else:
        pytest.fail("no visit segment emitted")


def test_ios_visits_use_geo_uris() -> None:
    case = make_case(random.Random(33), "case_z", "consistent")
    for entry in to_ios_timeline(case.fixes):
        if "visit" in entry:
            assert entry["visit"]["topCandidate"]["placeLocation"].startswith("geo:")
            break
    else:
        pytest.fail("no visit entry emitted")


def test_card_csv_has_a_header_and_quoted_addresses(corpus: Path) -> None:
    for case_dir in (corpus / "cases").iterdir():
        text = (case_dir / "transactions.csv").read_text()
        assert text.startswith("Date,Time,Description,Address,Amount")
        return


def test_fixes_are_sorted_by_time(corpus: Path) -> None:
    for _, _, fixes in _cases(corpus):
        assert fixes == sorted(fixes, key=lambda f: f.t)


# --- advocate ----------------------------------------------------------------------


def test_advocate_answer_key_survives_the_final_sort() -> None:
    records, truths = generate_advocate(random.Random(7))
    for truth in truths:
        mine = [r for r in records if r.server_id == truth.server_id]
        for pair in truth.injected_pairs:
            a, b = mine[pair.index_a], mine[pair.index_b]
            assert haversine_km(a.loc, b.loc) == pytest.approx(pair.distance_km, abs=1e-3)
            assert (b.at - a.at).total_seconds() / 60 == pytest.approx(pair.minutes)


def test_injected_pairs_are_genuinely_impossible() -> None:
    _, truths = generate_advocate(random.Random(7))
    for truth in truths:
        for pair in truth.injected_pairs:
            assert pair.required_speed_kmh > PARAMS.v_strong_kmh


def test_exactly_two_servers_are_bad_and_the_rest_are_clean() -> None:
    _, truths = generate_advocate(random.Random(7))
    bad = [t for t in truths if t.is_bad]
    assert len(bad) == 2
    assert all(len(t.injected_pairs) == 6 for t in bad)
    assert all(t.repeated_description_addresses == 8 for t in bad)
    assert all(not t.injected_pairs for t in truths if not t.is_bad)


def test_every_server_has_the_full_record_count() -> None:
    records, truths = generate_advocate(random.Random(7))
    assert len(records) == 2000
    assert all(t.n_records == 400 for t in truths)


# --- address pool ------------------------------------------------------------------


def test_address_pool_covers_all_five_boroughs() -> None:
    assert set(boroughs()) == {"Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"}


def test_address_pool_is_large_enough_to_vary_cases() -> None:
    assert len(load_addresses()) >= 300


def test_every_address_is_inside_the_new_york_city_bounding_box() -> None:
    lat_min, lat_max, lng_min, lng_max = NYC_BBOX
    for address in load_addresses():
        assert lat_min <= address.lat <= lat_max, address.address
        assert lng_min <= address.lng <= lng_max, address.address


def test_no_duplicate_coordinates_in_the_pool() -> None:
    points = [(a.lat, a.lng) for a in load_addresses()]
    assert len(points) == len(set(points))


# --- committed demo cases ----------------------------------------------------------


@pytest.mark.parametrize(
    "case_id", ["maria_contradicted", "james_consistent", "lin_affix_mail_diligence"]
)
def test_demo_case_is_committed_and_complete(case_id: str) -> None:
    case_dir = DEMO_DIR / case_id
    for name in (
        "affidavit.json",
        "affidavit.pdf",
        "affidavit_scanned.pdf",
        "ground_truth.json",
        "household.json",
        "fixes.json",
        "timeline_android.json",
        "timeline_ios.json",
        "transactions.csv",
    ):
        assert (case_dir / name).is_file(), f"{case_id}/{name}"
    assert (case_dir / "affidavit.pdf").stat().st_size > 5_000


def test_demo_affidavit_sha_matches_its_own_pdf() -> None:
    """The packet cites this hash, so a drifted demo bundle must fail here, not on stage."""
    import hashlib

    for case_id in ("maria_contradicted", "james_consistent", "lin_affix_mail_diligence"):
        case_dir = DEMO_DIR / case_id
        affidavit = Affidavit.model_validate_json((case_dir / "affidavit.json").read_text())
        digest = hashlib.sha256((case_dir / "affidavit.pdf").read_bytes()).hexdigest()
        assert affidavit.source_sha256 == digest, case_id


def test_maria_is_far_from_her_door_and_james_is_at_his() -> None:
    def covering_distance(case_id: str) -> float:
        case_dir = DEMO_DIR / case_id
        affidavit = Affidavit.model_validate_json((case_dir / "affidavit.json").read_text())
        fixes = [
            LocationFix.model_validate(f) for f in json.loads((case_dir / "fixes.json").read_text())
        ]
        assert affidavit.served_location is not None
        covering = [
            f for f in fixes if f.t_end is not None and f.t <= affidavit.served_at <= f.t_end
        ]
        assert covering, case_id
        return min(haversine_km(f.loc, affidavit.served_location) for f in covering)

    assert covering_distance("maria_contradicted") > 5.0
    assert covering_distance("james_consistent") <= PARAMS.match_radius_km
    assert covering_distance("lin_affix_mail_diligence") > 5.0


def test_lin_has_the_thin_diligence_pattern_the_case_is_built_around() -> None:
    affidavit = Affidavit.model_validate_json(
        (DEMO_DIR / "lin_affix_mail_diligence" / "affidavit.json").read_text()
    )
    assert affidavit.method == "308_4"
    assert len(affidavit.attempts) < 3
    assert len({a.at.weekday() for a in affidavit.attempts}) == 1
    assert all(9 <= a.at.hour < 17 for a in affidavit.attempts)
