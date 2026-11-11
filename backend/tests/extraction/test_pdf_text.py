"""Reading the upload: what it is, what text it has, and what it looks like as pixels."""

import io

import pytest

from app.api.errors import BadInputError, TooManyPagesError, UnsupportedFileError
from app.extraction.pdf_text import (
    IMAGE_MAX_EDGE,
    MAX_PAGES,
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


def test_a_heic_photo_is_accepted_v11() -> None:
    """The iPhone default. v1.0 asked people to re-save it; v1.1 reads it."""
    assert sniff(HEIC_HEAD) == "image"


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


def _photo(size: tuple[int, int], orientation: int | None = None, fmt: str = "JPEG") -> bytes:
    from PIL import Image

    image = Image.new("RGB", size, (200, 30, 30))
    exif = Image.Exif()
    if orientation is not None:
        exif[0x0112] = orientation
    exif[0x8825] = {2: (40.0, 47.0, 0.0)}  # a GPS block: where the photo was taken
    buffer = io.BytesIO()
    if fmt == "HEIF":
        import pillow_heif

        pillow_heif.register_heif_opener()
    image.save(buffer, format=fmt, exif=exif.tobytes())
    return buffer.getvalue()


def test_a_photo_is_turned_upright_from_its_exif_orientation() -> None:
    """Orientation 6 is how a phone held upright stores a portrait page: pixels on their
    side, and a tag saying so. The model must see the page the right way up."""
    page = image_page(_photo((300, 100), orientation=6))
    assert (page.width, page.height) == (100, 300)
    assert page.media_type == "image/jpeg"


def test_a_large_photo_is_capped_on_its_long_edge() -> None:
    page = image_page(_photo((4800, 1200)))
    assert max(page.width, page.height) == IMAGE_MAX_EDGE


def test_a_heic_photo_is_read_like_any_other() -> None:
    page = image_page(_photo((120, 80), fmt="HEIF"))
    assert page.data.startswith(b"\xff\xd8\xff")
    assert (page.width, page.height) == (120, 80)


def test_re_encoding_drops_where_the_photo_was_taken() -> None:
    """The phone's EXIF can carry GPS coordinates; nothing of it goes to a provider."""
    from PIL import Image

    page = image_page(_photo((64, 64)))
    with Image.open(io.BytesIO(page.data)) as reread:
        assert not reread.getexif()


def test_a_photo_that_is_not_a_photo_is_a_plain_error() -> None:
    with pytest.raises(BadInputError):
        image_page(JPEG_HEAD)


def test_a_court_file_over_the_page_limit_is_refused(demo_pdf: bytes) -> None:
    import pypdfium2 as pdfium

    source = pdfium.PdfDocument(demo_pdf)
    big = pdfium.PdfDocument.new()
    for _ in range(MAX_PAGES // 2 + 1):
        big.import_pages(source)
    buffer = io.BytesIO()
    big.save(buffer)
    with pytest.raises(TooManyPagesError):
        extract_text(buffer.getvalue())


def test_each_page_keeps_its_own_text_and_word_boxes(demo_pdf: bytes) -> None:
    layer = extract_text(demo_pdf)
    assert len(layer.pages) == len(layer.words) == len(layer.sizes) == layer.n_pages
    assert all(w.x0 < w.x1 and w.top < w.bottom for w in layer.words[0])


def test_the_source_hash_is_of_the_bytes_as_uploaded(demo_pdf: bytes) -> None:
    """The packet cites this hash, so it must be the file's hash and nothing else."""
    assert sha256_of(demo_pdf) == sha256_of(demo_pdf)
    assert len(sha256_of(demo_pdf)) == 64
    assert sha256_of(demo_pdf) != sha256_of(demo_pdf + b" ")
