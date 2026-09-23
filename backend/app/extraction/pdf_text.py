"""Reading the uploaded document. Bible §12, §16.

Everything here happens in memory: no temp file is ever written, so none can be left
behind. Nothing in this module logs, because everything it touches is document text.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import Final, Literal

from app.api.errors import BadInputError, UnsupportedFileError

TEXT_MIN_CHARS: Final = 200
"""Bible §12: below this the text layer is treated as absent and the pages are rasterised."""

RASTER_DPI: Final = 200
RASTER_MAX_PAGES: Final = 3

SourceKind = Literal["pdf", "image"]

_PDF_MAGIC: Final = b"%PDF-"
_PNG_MAGIC: Final = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC: Final = b"\xff\xd8\xff"
_HEIC_BRANDS: Final = (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1")


@dataclass(frozen=True, slots=True)
class PdfText:
    text: str
    n_pages: int
    has_text_layer: bool


@dataclass(frozen=True, slots=True)
class PageImage:
    data: bytes
    media_type: str


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_heic(data: bytes) -> bool:
    # ISO-BMFF: [4-byte size]"ftyp"[4-byte brand]. HEIC is the iPhone default for photos.
    return len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12].lower() in _HEIC_BRANDS


def sniff(data: bytes) -> SourceKind:
    """Decide what was uploaded from its bytes, never from its name or declared type.

    A browser will happily label a HEIC photo `image/jpeg`, and a renamed `.pdf` is the
    oldest upload bug there is.
    """
    if data.startswith(_PDF_MAGIC):
        return "pdf"
    if data.startswith(_PNG_MAGIC) or data.startswith(_JPEG_MAGIC):
        return "image"
    if _is_heic(data):
        raise UnsupportedFileError(
            "That looks like an iPhone HEIC photo. Open it and save or share it as a "
            "JPEG or PDF, then upload that."
        )
    raise UnsupportedFileError("Please upload the affidavit as a PDF, JPEG or PNG.")


def extract_text(pdf_bytes: bytes) -> PdfText:
    """Pull the pdfplumber text layer. A layer under 200 chars means the scan path is used."""
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            n_pages = len(pdf.pages)
            pages = [page.extract_text() or "" for page in pdf.pages]
    except UnsupportedFileError:
        raise
    except Exception as exc:  # pdfplumber raises a zoo of pdfminer errors on a bad file
        raise BadInputError("We could not open that PDF. It may be damaged.") from exc

    text = "\n".join(pages).strip()
    return PdfText(text=text, n_pages=n_pages, has_text_layer=len(text) >= TEXT_MIN_CHARS)


def rasterize(
    pdf_bytes: bytes, dpi: int = RASTER_DPI, max_pages: int = RASTER_MAX_PAGES
) -> list[PageImage]:
    """Render the first pages to PNG for the vision path."""
    import pypdfium2 as pdfium

    try:
        document = pdfium.PdfDocument(pdf_bytes)
    except Exception as exc:
        raise BadInputError("We could not open that PDF. It may be damaged.") from exc

    images: list[PageImage] = []
    try:
        for index in range(min(len(document), max_pages)):
            page = document[index].render(scale=dpi / 72).to_pil().convert("RGB")
            buffer = io.BytesIO()
            page.save(buffer, format="PNG", optimize=True)
            images.append(PageImage(data=buffer.getvalue(), media_type="image/png"))
    finally:
        document.close()
    return images


def image_page(data: bytes) -> PageImage:
    """A single uploaded photo, passed through untouched so nothing is re-encoded."""
    media_type = "image/png" if data.startswith(_PNG_MAGIC) else "image/jpeg"
    return PageImage(data=data, media_type=media_type)
