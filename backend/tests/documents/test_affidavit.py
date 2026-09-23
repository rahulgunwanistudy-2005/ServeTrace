"""The Draft Supporting Affidavit. Bible §15.

Almost every test here is about a paragraph that should *not* be in the document. That is
the shape of the risk: a packet with a section missing is incomplete, and an affidavit
with a paragraph too many is somebody swearing to something they did not say.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pytest

import app.engine
from app.documents import copy
from app.documents.affidavit import (
    EXCLUDED_CODES,
    HANDLED_CODES,
    INFO_ONLY_CODES,
    affidavit_context,
    annexes_packet,
    build_draft_affidavit,
    build_paragraphs,
    cplr_317_eligible,
)
from app.documents.render import render_html
from app.domain.models import ServiceMethod, Severity
from tests.documents.conftest import (
    AT_HOME,
    AT_WORK,
    CASE_IDS,
    CLAIM_AT,
    PASSING_BY,
    built,
    demo_analysis,
    member,
    statement,
)


def sources(analysis, affiant) -> list[str]:  # type: ignore[no-untyped-def]
    return [p.source for p in build_paragraphs(analysis, affiant)]


def texts(analysis, affiant) -> str:  # type: ignore[no-untyped-def]
    return " ".join(p.text for p in build_paragraphs(analysis, affiant))


# --- Provenance ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_every_paragraph_traces_to_a_provision_a_finding_or_the_user(case_id: str) -> None:
    """Bible §18.6: no legal statement outside §5, and nothing invented in between."""
    allowed_l_ids = set(copy.LEGAL_REF_NAMES)
    for paragraph in build_paragraphs(demo_analysis(case_id), statement()):
        assert (
            paragraph.source == "user"
            or paragraph.source in allowed_l_ids
            or paragraph.source.startswith(("F-", "R-"))
        ), paragraph


def test_every_code_the_engine_can_emit_is_accounted_for() -> None:
    """The failure this guards against is a rule added in some later session quietly
    writing prose into a document somebody signs under oath.

    A code that gets no paragraph is fine — silence is the safe default here — but it has
    to be a decision rather than an oversight. So the engine's own source is read for the
    codes it constructs, and each one has to appear in one of the three sets. A new rule
    fails this test, which is the moment to choose.
    """
    engine = Path(app.engine.__file__).parent
    emitted = {
        code
        for module in engine.glob("*.py")
        for code in re.findall(r'code="([A-Z0-9-]+)"', module.read_text())
    }
    emitted |= {
        code
        for module in (Path(app.engine.__file__).parents[1] / "engine").glob("*.py")
        for code in re.findall(r'code="([A-Z0-9-]+)"', module.read_text())
    }
    accounted = HANDLED_CODES | INFO_ONLY_CODES | EXCLUDED_CODES

    assert emitted, "no finding codes were found: this test has stopped testing anything"
    assert emitted <= accounted, f"unaccounted finding codes: {sorted(emitted - accounted)}"


# --- Paragraphs the user did not confirm are excluded, not softened -----------------------


def test_the_not_served_paragraph_appears_only_when_it_was_ticked() -> None:
    analysis = built()
    said = copy.para_not_served(analysis.affidavit.served_at)

    assert said in texts(analysis, statement(states_not_served=True))
    assert said not in texts(analysis, statement(states_not_served=False))


def test_an_unticked_statement_is_absent_rather_than_hedged() -> None:
    """There is no "I do not recall being served". A hedged sworn statement is worse for
    the person signing it than a shorter affidavit."""
    text = texts(built(), statement(states_not_served=False))
    assert "not served" not in text.lower()
    assert "do not recall" not in text.lower()


def test_the_address_paragraph_appears_only_when_it_was_ticked() -> None:
    analysis = built(method=ServiceMethod.SUBSTITUTE)
    said = copy.para_not_my_address(analysis.affidavit.served_address)

    assert said in texts(analysis, statement(states_not_my_address=True))
    assert said not in texts(analysis, statement(states_not_my_address=False))


def test_the_address_paragraph_is_left_out_after_personal_delivery() -> None:
    """L1 does not turn on the address being anybody's home, so the paragraph would be a
    true sentence that does no work — and a judge has to read every line of this."""
    analysis = built(method=ServiceMethod.PERSONAL)
    said = copy.para_not_my_address(analysis.affidavit.served_address)
    assert said not in texts(analysis, statement(states_not_my_address=True))


# --- One paragraph per STRONG or MODERATE finding -----------------------------------------


def test_a_strong_location_finding_becomes_a_paragraph_with_its_numbers() -> None:
    analysis = built(fixes=[AT_WORK])
    text = texts(analysis, statement())
    km = analysis.verdicts[0].nearest_fix_km

    assert km is not None
    assert copy.fmt_km(km) in text
    assert "F-VISIT" in sources(analysis, statement())


def test_a_prism_paragraph_quotes_the_speed_and_the_gap() -> None:
    analysis = built(fixes=[PASSING_BY])
    speed = analysis.verdicts[0].required_speed_kmh
    text = texts(analysis, statement())

    assert speed is not None
    assert copy.fmt_speed(speed) in text


def test_an_info_finding_never_becomes_a_paragraph() -> None:
    """A consistent case still produces findings. None of them is a fact worth swearing to."""
    analysis = built(fixes=[AT_HOME])
    assert all(f.severity is Severity.INFO for f in analysis.findings)
    assert not [s for s in sources(analysis, statement()) if s.startswith(("F-", "R-"))]


def test_a_timing_rule_becomes_a_paragraph_with_the_day_count() -> None:
    analysis = built(mailing_date=CLAIM_AT.date() + timedelta(days=40))
    assert "R-T2" in sources(analysis, statement())
    assert "40 days" in texts(analysis, statement())


def test_a_missing_mailing_becomes_a_paragraph() -> None:
    analysis = built(mailing_date=None)
    assert "R-T1" in sources(analysis, statement())


def test_a_description_paragraph_never_counts_the_household_twice() -> None:
    """The roster includes the person signing, so a head count is always one out."""
    analysis = built(
        recipient_description={"sex": "male", "age_min": 55, "age_max": 65},
        household=[member("Me", sex="female", age=34, is_defendant=True)],
    )
    text = texts(analysis, statement())

    assert "F-DESC" in sources(analysis, statement())
    assert "anyone else living at that address" in text
    assert "any of the 1 people" not in text


# --- The records paragraph and Exhibit B --------------------------------------------------


def test_a_consistent_case_does_not_annex_the_records_that_work_against_it() -> None:
    """Bible §6 says report a consistent result honestly. Honestly does not mean filing it
    against yourself: with no location finding there is nothing the records support, and
    pointing a judge at an exhibit that places you at the door would be malpractice."""
    analysis = built(fixes=[AT_HOME])
    text = texts(analysis, statement())

    assert "I keep a location history" not in text
    assert copy.PARA_PACKET not in text
    assert annexes_packet(analysis, statement()) is False
    assert [e["letter"] for e in affidavit_context(analysis, statement())["exhibits"]] == ["A"]


def test_a_contradicted_case_annexes_the_packet_as_exhibit_b() -> None:
    analysis = built(fixes=[AT_WORK])
    assert annexes_packet(analysis, statement()) is True
    assert [e["letter"] for e in affidavit_context(analysis, statement())["exhibits"]] == ["A", "B"]


def test_the_records_paragraph_names_the_kinds_of_record_actually_relied_on() -> None:
    analysis = built(fixes=[AT_WORK])
    assert copy.FIX_KIND_IN_SENTENCE["visit"] in texts(analysis, statement())


# --- CPLR 317 (L6) ------------------------------------------------------------------------

TODAY = date(2026, 9, 23)


def test_the_317_paragraph_appears_when_all_three_conditions_hold() -> None:
    analysis = built(method=ServiceMethod.SUBSTITUTE)
    assert cplr_317_eligible(analysis, statement(states_no_notice_in_time=True), TODAY)
    assert "L6" in sources(analysis, statement())


def test_personal_delivery_gets_no_317_paragraph() -> None:
    """L6 is for somebody served other than by personal delivery."""
    analysis = built(method=ServiceMethod.PERSONAL)
    assert not cplr_317_eligible(analysis, statement(), TODAY)
    assert "L6" not in sources(analysis, statement())


def test_without_the_no_notice_statement_there_is_no_317_paragraph() -> None:
    """Only the person can say notice never reached them in time, so only they can offer
    this ground."""
    analysis = built()
    assert not cplr_317_eligible(analysis, statement(states_no_notice_in_time=False), TODAY)


def test_a_deadline_already_passed_removes_the_paragraph() -> None:
    analysis = built(knowledge_date=date(2020, 1, 1), judgment_entry_date=date(2019, 1, 1))
    assert not cplr_317_eligible(analysis, statement(), TODAY)


def test_an_unknown_deadline_is_not_a_passed_one() -> None:
    """Dropping a statutory ground because a form field was left blank would cost somebody
    a route on a missing input."""
    analysis = built(knowledge_date=None, judgment_entry_date=None)
    assert cplr_317_eligible(analysis, statement(), TODAY)


def test_the_deadline_paragraph_carries_the_date_the_engine_computed() -> None:
    analysis = built()
    deadline = analysis.deadlines.cplr_317_deadline
    assert deadline is not None
    assert copy.fmt_date(deadline) in texts(analysis, statement())


def test_the_users_own_words_are_the_defence_and_ours_are_a_blank() -> None:
    analysis = built()
    mine = texts(analysis, statement(defense_summary="I never opened this account"))
    theirs = texts(analysis, statement(defense_summary=None))

    assert "I never opened this account." in mine
    assert "[state your defence here in your own words]" in theirs


# --- Relief, always -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("paragraph", "source"),
    [
        (copy.PARA_RELIEF_5015, "L5"),
        (copy.PARA_TRAVERSE, "L5"),
        (copy.PARA_STAY, "L5"),
        (copy.PARA_GPS, "L7"),
    ],
)
def test_the_relief_requested_is_in_every_draft(paragraph: str, source: str) -> None:
    analysis = built()
    assert paragraph in texts(analysis, statement())
    assert source in sources(analysis, statement())


# --- Identity -----------------------------------------------------------------------------


def test_a_name_that_differs_from_the_papers_is_stated_without_comment() -> None:
    analysis = built(defendant_name="M. DELARMO")
    assert copy.para_named_differently("M. DELARMO") in texts(analysis, statement(name="Maria"))


def test_a_matching_name_gets_no_extra_paragraph() -> None:
    analysis = built(defendant_name="Maria Delarmo")
    assert "The papers in this action name the defendant as" not in texts(
        analysis, statement(name="Maria Delarmo")
    )


# --- Structure ----------------------------------------------------------------------------


def test_the_paragraphs_are_numbered_by_the_list_not_by_the_text() -> None:
    """A document with two paragraph 6s is a document nobody trusts, and the way never to
    have one is never to write the numbers."""
    analysis, affiant = built(), statement()
    html = render_html("affidavit.html.j2", affidavit_context(analysis, affiant))
    body = html.split('<ol class="paragraphs">')[1].split("</ol>")[0]

    assert body.count("<li>") == len(build_paragraphs(analysis, affiant))


def test_the_signature_and_notary_blocks_are_left_blank() -> None:
    html = render_html("affidavit.html.j2", affidavit_context(built(), statement()))
    assert copy.NOTARY_BLOCK in html
    assert copy.SIGNATURE_LABEL in html


def test_the_document_says_it_is_a_draft() -> None:
    context = affidavit_context(built(), statement())
    html = render_html("affidavit.html.j2", context)
    assert copy.DISCLAIMER in html
    assert 'class="draft"' in html


def test_it_says_it_attaches_to_the_courts_own_form_rather_than_replacing_it() -> None:
    assert "does not replace that form" in copy.AFFIDAVIT_NOTE


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_every_demo_case_renders(case_id: str, needs_pdf: None) -> None:
    pdf = build_draft_affidavit(demo_analysis(case_id), statement())
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 10_000
