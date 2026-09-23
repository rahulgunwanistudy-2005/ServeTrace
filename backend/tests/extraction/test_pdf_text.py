"""Reading the upload: what it is, what text it has, and what it looks like as pixels."""

import pytest

from app.api.errors import BadInputError, UnsupportedFileError
from app.extraction.pdf_text import (
    TEXT_MIN_CHARS,
    extract_text,
    image_page,
    rasterize,
    sha256_of,
    sniff,
)

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
    "00000049454e44ae426082"
)
JPEG_HEAD = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01"
HEIC_HEAD = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00heicmif1"


def test_a_pdf_is_recognised_from_its_bytes(demo_pdf: bytes) -> None:
    assert sniff(demo_pdf) == "pdf"


@pytest.mark.parametrize("data", [PNG_1PX, JPEG_HEAD])
def test_photos_are_recognised_from_their_bytes(data: bytes) -> None:
    assert sniff(data) == "image"


def test_a_heic_photo_is_refused_with_a_way_out() -> None:
    """The iPhone default. Telling the user to re-save it is the whole value of the error."""
    with pytest.raises(UnsupportedFileError) as caught:
        sniff(HEIC_HEAD)
    assert "JPEG" in str(caught.value)


def test_something_that_is_not_a_document_is_refused() -> None:
    with pytest.raises(UnsupportedFileError):
        sniff(b"index_number,served_at\n1,2\n")


def test_a_file_renamed_to_pdf_is_still_judged_by_its_bytes() -> None:
    """The name never reaches `sniff`, which is the point: only the bytes decide."""
    with pytest.raises(UnsupportedFileError):
        sniff(b"this file is called affidavit.pdf and is not one")


def test_a_rendered_affidavit_has_a_usable_text_layer(demo_pdf: bytes) -> None:
    layer = extract_text(demo_pdf)
    assert layer.has_text_layer
    assert layer.n_pages == 2
    assert len(layer.text) > TEXT_MIN_CHARS
    assert "Maria Delarmo" in layer.text


def test_a_scan_has_no_text_layer_so_the_vision_path_is_used(demo_scan: bytes) -> None:
    """This is what a user actually uploads: a photo of a photocopy."""
    layer = extract_text(demo_scan)
    assert not layer.has_text_layer
    assert layer.n_pages == 2


def test_a_damaged_pdf_is_a_plain_error_not_a_traceback() -> None:
    with pytest.raises(BadInputError):
        extract_text(b"%PDF-1.7\nnot really a pdf at all")


def test_rasterising_produces_png_pages(demo_scan: bytes) -> None:
    pages = rasterize(demo_scan, dpi=72)
    assert pages
    assert all(page.data.startswith(b"\x89PNG") for page in pages)
    assert all(page.media_type == "image/png" for page in pages)


def test_rasterising_stops_at_the_page_limit(demo_pdf: bytes) -> None:
    """Bible §12 caps this at three pages, so a 60-page court file cannot become 60 images."""
    assert len(rasterize(demo_pdf, dpi=72, max_pages=1)) == 1


def test_an_uploaded_photo_is_passed_through_untouched() -> None:
    page = image_page(JPEG_HEAD)
    assert page.media_type == "image/jpeg"
    assert page.data is JPEG_HEAD


def test_the_source_hash_is_of_the_bytes_as_uploaded(demo_pdf: bytes) -> None:
    """The packet cites this hash, so it must be the file's hash and nothing else."""
    assert sha256_of(demo_pdf) == sha256_of(demo_pdf)
    assert len(sha256_of(demo_pdf)) == 64
    assert sha256_of(demo_pdf) != sha256_of(demo_pdf + b" ")
