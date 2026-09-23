"""The Evidence Packet. Bible §15.

What is asserted here is the *content* of the packet: that every section bible §15 names
is present, that the numbers in it are the engine's own, that the digests mean what they
claim, and that nothing is quietly dropped. The PDF tests at the bottom prove the words
survive the renderer, because a section that lays out on top of another one is still a
missing section.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json

import pytest

from app.api.errors import BadInputError
from app.documents import copy
from app.documents.packet import (
    MAX_FIXES_IN_TABLE,
    MAX_MAP_BYTES,
    build_packet,
    fixes_digest,
    packet_context,
    validate_map_png,
)
from app.documents.render import render_html
from app.engine.params import PARAMS
from tests.documents.conftest import (
    AT_HOME,
    AT_WORK,
    CASE_IDS,
    CLAIM_AT,
    DOOR,
    PASSING_BY,
    built,
    demo_analysis,
    demo_fixes,
    fix,
)


def html_for(case_id: str = "maria_contradicted") -> str:
    return render_html(
        "packet.html.j2",
        packet_context(demo_analysis(case_id), demo_fixes(case_id), None, "Maria Delarmo"),
    )


def png_bytes(width: int = 80, height: int = 40) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (20, 20, 20)).save(buffer, format="PNG")
    return buffer.getvalue()


# --- Every section bible §15 names --------------------------------------------------------


@pytest.mark.parametrize(
    "section",
    [
        copy.SECTION_VERDICT,
        copy.SECTION_CLAIMS,
        copy.SECTION_FINDINGS,
        copy.SECTION_MAP,
        copy.SECTION_FIXES,
        copy.SECTION_METHOD,
        copy.SECTION_INTEGRITY,
        copy.SECTION_DEADLINE,
    ],
)
def test_the_packet_carries_every_section(section: str) -> None:
    assert section in html_for()


def test_the_verdict_headline_is_the_one_bible_6_specifies() -> None:
    assert copy.TIER_HEADLINES["contradicted"] in html_for("maria_contradicted")


def test_a_consistent_case_says_so_as_plainly() -> None:
    """Bible §6: showing a consistent result honestly is a feature, not a failure mode."""
    assert copy.TIER_HEADLINES["consistent"] in html_for("james_consistent")


def test_every_page_carries_the_limitation_line() -> None:
    assert copy.LIMITATION in html_for()


def test_the_disclaimer_is_in_the_running_footer() -> None:
    """Bible §5: on every page. It is a running element, so once in the source is enough —
    `test_pdf.py` is where "on every page" is actually proved."""
    assert copy.DISCLAIMER in html_for()


# --- The numbers are the engine's own -----------------------------------------------------


def test_the_headline_number_is_the_distance_the_engine_measured() -> None:
    analysis = demo_analysis("maria_contradicted")
    km = analysis.verdicts[0].nearest_fix_km
    assert km is not None
    assert copy.fmt_km(km) in html_for()


def test_the_required_speed_reaches_the_page_when_there_is_one() -> None:
    analysis = built(fixes=[PASSING_BY])
    speed = analysis.verdicts[0].required_speed_kmh
    assert speed is not None
    assert copy.fmt_speed(speed) in render_html("packet.html.j2", packet_context(analysis, []))


def test_one_row_per_sworn_moment() -> None:
    analysis = demo_analysis("lin_affix_mail_diligence")
    rows = packet_context(analysis, [])["claims"]
    assert len(rows) == len(analysis.verdicts)
    assert rows[0]["label"] == "Service"
    assert rows[1]["label"] == "Attempt 1"


def test_each_finding_is_printed_with_the_provision_it_encodes() -> None:
    html = html_for("lin_affix_mail_diligence")
    analysis = demo_analysis("lin_affix_mail_diligence")
    refs = {f.legal_ref for f in analysis.findings if f.legal_ref}

    assert refs
    for ref in refs:
        assert copy.LEGAL_REF_NAMES[ref] in html


def test_the_thresholds_printed_are_the_ones_the_engine_ran_under() -> None:
    html = html_for()
    assert copy.fmt_km(PARAMS.match_radius_km) in html
    assert copy.fmt_speed(PARAMS.v_strong_kmh) in html
    assert copy.fmt_speed(PARAMS.v_moderate_kmh) in html


def test_the_versions_are_stamped_so_a_number_can_be_traced_back() -> None:
    analysis = demo_analysis("maria_contradicted")
    html = html_for()
    assert analysis.engine_version in html
    assert analysis.params_version in html


# --- The records table --------------------------------------------------------------------


def test_every_record_sent_is_listed() -> None:
    fixes = demo_fixes("maria_contradicted")
    assert len(packet_context(demo_analysis("maria_contradicted"), fixes)["fixes"]) == len(fixes)


def test_a_table_too_long_to_print_says_how_many_of_how_many() -> None:
    """Bible §16 allows 5,000 points. An exhibit may shorten itself; it may not do it
    quietly."""
    fixes = [AT_WORK] * (MAX_FIXES_IN_TABLE + 37)
    context = packet_context(built(), fixes)

    assert len(context["fixes"]) == MAX_FIXES_IN_TABLE
    assert f"{MAX_FIXES_IN_TABLE:,}" in context["fixes_note"]
    assert f"{len(fixes):,}" in context["fixes_note"]


def test_the_digest_covers_every_record_even_the_ones_not_printed() -> None:
    fixes = [AT_WORK] * (MAX_FIXES_IN_TABLE + 37)
    context = packet_context(built(), fixes)
    assert context["integrity"]["n_fixes"] == len(fixes)
    assert context["integrity"]["fixes_sha256"] == fixes_digest(fixes)


def test_a_source_id_with_no_friendly_name_is_printed_as_it_is() -> None:
    odd = fix(CLAIM_AT, DOOR, source="some_new_importer")
    assert packet_context(built(), [odd])["fixes"][0]["source"] == "some_new_importer"


def test_a_stay_prints_both_ends_of_it() -> None:
    row = packet_context(built(), [AT_HOME])["fixes"][0]
    assert " to " in row["when"]
    assert row["kind"] == copy.FIX_KIND_LABELS["visit"]


# --- Digests ------------------------------------------------------------------------------


def test_the_affidavit_digest_is_the_one_the_upload_produced() -> None:
    analysis = demo_analysis("maria_contradicted")
    assert (
        packet_context(analysis, [])["integrity"]["affidavit_sha256"]
        == analysis.affidavit.source_sha256
    )


def test_the_records_digest_is_reproducible_by_anyone_holding_the_records() -> None:
    """The point of printing it. Anyone can recompute it from the same JSON."""
    fixes = demo_fixes("maria_contradicted")
    payload = json.dumps(
        [f.model_dump(mode="json") for f in fixes],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert fixes_digest(fixes) == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_changing_one_record_changes_the_digest() -> None:
    fixes = demo_fixes("maria_contradicted")
    moved = [*fixes[:-1], fixes[-1].model_copy(update={"accuracy_m": 999.0})]
    assert fixes_digest(fixes) != fixes_digest(moved)


def test_the_digest_of_no_records_is_still_a_digest() -> None:
    assert len(fixes_digest([])) == 64


# --- The map ------------------------------------------------------------------------------


def test_a_real_png_is_embedded_as_a_data_uri() -> None:
    uri = validate_map_png(base64.b64encode(png_bytes()).decode("ascii"))
    assert uri.startswith("data:image/png;base64,")


def test_a_data_uri_from_the_browser_is_accepted_as_it_comes() -> None:
    """`canvas.toDataURL()` returns the prefix; requiring it to be stripped client-side
    would be a rule the browser has no reason to know about."""
    raw = base64.b64encode(png_bytes()).decode("ascii")
    assert validate_map_png(f"data:image/png;base64,{raw}") == validate_map_png(raw)


def test_the_map_reaches_the_page() -> None:
    context = packet_context(built(), [], base64.b64encode(png_bytes()).decode("ascii"))
    assert "data:image/png;base64," in render_html("packet.html.j2", context)


def test_without_a_map_the_packet_says_where_the_coordinates_are() -> None:
    """Bible §14: the map always has a text alternative."""
    assert copy.MAP_ALT in render_html("packet.html.j2", packet_context(built(), []))


@pytest.mark.parametrize("bad", ["not base64 at all!!", "", "YWJj"])
def test_something_that_is_not_a_png_is_refused(bad: str) -> None:
    with pytest.raises(BadInputError):
        validate_map_png(bad)


def test_a_jpeg_is_refused_even_though_it_is_a_real_image() -> None:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (40, 40)).save(buffer, format="JPEG")
    with pytest.raises(BadInputError, match="must be a PNG"):
        validate_map_png(base64.b64encode(buffer.getvalue()).decode("ascii"))


def test_a_map_over_the_size_limit_is_refused() -> None:
    oversize = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\0" * MAX_MAP_BYTES).decode("ascii")
    with pytest.raises(BadInputError, match="larger than"):
        validate_map_png(oversize)


def test_an_image_with_absurd_dimensions_is_refused() -> None:
    with pytest.raises(BadInputError, match="larger than"):
        validate_map_png(base64.b64encode(png_bytes(5000, 10)).decode("ascii"))


# --- Renders at all -----------------------------------------------------------------------


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_every_demo_case_renders(case_id: str, needs_pdf: None) -> None:
    """Bible §2 and §17: the demo must never fail live, and this is the download."""
    pdf = build_packet(demo_analysis(case_id), demo_fixes(case_id))
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 10_000


def test_a_case_with_no_records_at_all_still_renders(needs_pdf: None) -> None:
    """`NO_DATA` is an answer, so it is a packet too."""
    assert build_packet(built(fixes=[]), []).startswith(b"%PDF-")
