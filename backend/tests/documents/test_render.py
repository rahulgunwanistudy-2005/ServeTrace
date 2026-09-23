"""The render boundary: escaping, strictness, and what a document is allowed to reach.

These are the properties that do not depend on which document is being rendered, so they
are asserted once here rather than in both document suites.
"""

from __future__ import annotations

import pytest
from jinja2 import UndefinedError

from app.api.errors import DocumentsUnavailableError
from app.documents import render
from app.documents.affidavit import affidavit_context, build_draft_affidavit
from app.documents.packet import build_packet, packet_context
from tests.documents.conftest import built, demo_analysis, demo_fixes, statement

HOSTILE = '<script>alert("x")</script> & "quoted" <b>bold</b>'
"""A name nobody has, on a document that will be printed. Autoescape is the only thing
standing between an extraction reading this off a scanned page and it becoming markup."""


# --- Escaping ----------------------------------------------------------------------------


def test_a_field_full_of_markup_is_printed_as_text_not_rendered_as_markup() -> None:
    analysis = built(defendant_name=HOSTILE)
    html = render.render_html("packet.html.j2", packet_context(analysis, [], None, HOSTILE))

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


def test_the_affidavit_escapes_the_name_somebody_signs_it_with() -> None:
    analysis = built()
    html = render.render_html(
        "affidavit.html.j2", affidavit_context(analysis, statement(name=HOSTILE))
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_a_defence_the_user_typed_is_escaped_too() -> None:
    """The one genuinely free-text field in either document. Bible §16."""
    analysis = built()
    html = render.render_html(
        "affidavit.html.j2",
        affidavit_context(analysis, statement(defense_summary=HOSTILE)),
    )

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# --- Strictness ---------------------------------------------------------------------------


def test_a_missing_context_key_raises_rather_than_printing_a_blank() -> None:
    """A field the template forgot is a blank space on a page somebody swears to."""
    context = packet_context(built(), [])
    del context["verdict"]

    with pytest.raises(UndefinedError):
        render.render_html("packet.html.j2", context)


# --- What a document may reach ------------------------------------------------------------


def test_the_map_image_can_be_read_from_a_data_uri(needs_pdf: None) -> None:
    """The one protocol a document needs, and the only one it gets."""
    tiny = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
    response = render.url_fetcher().fetch(tiny)
    try:
        assert response.read()
    finally:
        response.close()


@pytest.mark.parametrize(
    "url",
    [
        "https://example.invalid/tracker.png",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
    ],
)
def test_a_document_may_not_fetch_anything_else(url: str, needs_pdf: None) -> None:
    """Bible §16. The renderer resolves URLs it finds; this is the door being shut."""
    with pytest.raises(ValueError, match="disallowed protocol"):
        render.url_fetcher().fetch(url)


def test_a_refused_url_stops_the_render_rather_than_dropping_a_section(
    needs_pdf: None,
) -> None:
    """A warning and a missing image would be a document that quietly lost a page."""
    assert render.url_fetcher()._fail_on_errors is True


# --- Determinism --------------------------------------------------------------------------


def test_the_same_analysis_renders_the_same_packet_bytes(needs_pdf: None) -> None:
    """S6: deterministic output given identical input.

    It holds because WeasyPrint writes no creation date of its own and the documents take
    their timestamp from the analysis rather than from a clock. Session 1 recorded the
    opposite belief in `tasks/todo.md`; this test is what settles it.
    """
    analysis, fixes = demo_analysis("maria_contradicted"), demo_fixes("maria_contradicted")
    assert build_packet(analysis, fixes) == build_packet(analysis, fixes)


def test_the_same_analysis_renders_the_same_affidavit_bytes(needs_pdf: None) -> None:
    analysis, affiant = demo_analysis("maria_contradicted"), statement()
    assert build_draft_affidavit(analysis, affiant) == build_draft_affidavit(analysis, affiant)


def test_a_different_generation_time_changes_the_document() -> None:
    """The stamp is real: two packets an hour apart are not the same document."""
    analysis = demo_analysis("maria_contradicted")
    later = analysis.model_copy(
        update={"generated_at": analysis.generated_at.replace(hour=analysis.generated_at.hour - 1)}
    )
    assert render.render_html("packet.html.j2", packet_context(analysis, [])) != render.render_html(
        "packet.html.j2", packet_context(later, [])
    )


# --- The native stack ---------------------------------------------------------------------


def test_a_missing_native_stack_becomes_a_sentence_not_a_cffi_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The only thing a user could ever see of this failure is the message, so it is the
    thing worth asserting."""

    def refuse(name: str, *args: object, **kwargs: object) -> object:
        if name == "weasyprint":
            raise OSError("cannot load library 'libgobject-2.0-0'")
        return __import__(name, *args, **kwargs)  # type: ignore[arg-type]

    render._weasyprint.cache_clear()
    monkeypatch.setattr("builtins.__import__", refuse)
    try:
        with pytest.raises(DocumentsUnavailableError) as raised:
            render._weasyprint()
    finally:
        render._weasyprint.cache_clear()

    assert "still works" in raised.value.message
    assert "libgobject" not in raised.value.message


def test_pdf_availability_is_reported_rather_than_assumed(needs_pdf: None) -> None:
    assert render.pdf_available() is True
