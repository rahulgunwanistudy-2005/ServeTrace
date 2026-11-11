"""Reading the uploaded document. Bible §12, §16.

Everything here happens in memory: no temp file is ever written, so none can be left
behind. Nothing in this module logs, because everything it touches is document text.

v1.1 accepts what people actually upload: a PDF from the court file, or a phone photo of a
page — JPEG, PNG, or the iPhone's HEIC. A photo is turned the right way up from its EXIF
orientation, converted to RGB and capped at 2400 px on the long edge, because a 48 MP
photo of one sheet of paper is not more legible to a model than a 2400 px one, only
slower and dearer.
"""

from __future__ import annotations

import base64
import hashlib
import io
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from app.api.errors import BadInputError, TooManyPagesError, UnsupportedFileError

if TYPE_CHECKING:
    from PIL import Image

TEXT_MIN_CHARS: Final = 200
"""Bible §12: below this the text layer is treated as absent and the pages are rasterised."""

PAGE_TEXT_MIN_CHARS: Final = 80
"""A page of a text-layer PDF with less than this is a scanned page inside a typed file."""

RASTER_DPI: Final = 200
RASTER_MAX_PAGES: Final = 3
"""Pages sent to the model for one affidavit. An affidavit of service is one or two."""

MAX_PAGES: Final = 25
"""v1.1: a whole court file is summons, complaint, affidavit and judgment, rarely more."""

IMAGE_MAX_EDGE: Final = 2400
THUMBNAIL_EDGE: Final = 768
"""Bible §12 (v1.1): page classification sees every page at this size, never larger."""

PREVIEW_EDGE: Final = 1000
PREVIEW_QUALITY: Final = 72

SourceKind = Literal["pdf", "image"]

_PDF_MAGIC: Final = b"%PDF-"
_PNG_MAGIC: Final = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC: Final = b"\xff\xd8\xff"
_HEIC_BRANDS: Final = (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1")

UNSUPPORTED = "Please upload the affidavit as a PDF, or as a photo (JPEG, PNG or HEIC)."


@dataclass(frozen=True, slots=True)
class Word:
    """One word of a text layer and its box, in PDF points from the page's top-left."""

    text: str
    x0: float
    top: float
    x1: float
    bottom: float


@dataclass(frozen=True, slots=True)
class PdfText:
    text: str
    n_pages: int
    has_text_layer: bool
    pages: tuple[str, ...] = ()
    """Each page's text, in order. `text` is these joined."""
    words: tuple[tuple[Word, ...], ...] = ()
    sizes: tuple[tuple[float, float], ...] = ()
    """Each page's (width, height) in PDF points."""


@dataclass(frozen=True, slots=True)
class PageImage:
    data: bytes
    media_type: str
    width: int = 0
    height: int = 0
    page: int = 0
    """0-based index of this page in the uploaded file."""


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_heic(data: bytes) -> bool:
    # ISO-BMFF: [4-byte size]"ftyp"[4-byte brand]. HEIC is the iPhone default for photos.
    return len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12].lower() in _HEIC_BRANDS


def sniff(data: bytes) -> SourceKind:
    """Decide what was uploaded from its bytes, never from its name or declared type.

    A browser will happily label a HEIC photo `image/jpeg`, and a renamed `.pdf` is the
    oldest upload bug there is.
    """
    if data.startswith(_PDF_MAGIC):
        return "pdf"
    if data.startswith(_PNG_MAGIC) or data.startswith(_JPEG_MAGIC) or is_heic(data):
        return "image"
    raise UnsupportedFileError(UNSUPPORTED)


def open_image(data: bytes) -> Image.Image:
    """A photo the right way up, in RGB, no larger than `IMAGE_MAX_EDGE` on its long edge."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if is_heic(data):
        import pillow_heif

        pillow_heif.register_heif_opener()
    try:
        with Image.open(io.BytesIO(data)) as raw:
            image = ImageOps.exif_transpose(raw).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise BadInputError("We could not open that photo. It may be damaged.") from exc
    image.thumbnail((IMAGE_MAX_EDGE, IMAGE_MAX_EDGE), Image.Resampling.LANCZOS)
    return image


def _jpeg(image: Image.Image, quality: int = 90) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def image_page(data: bytes) -> PageImage:
    """An uploaded photo as one page: oriented, RGB, capped, re-encoded as JPEG.

    Re-encoding is what makes HEIC readable by every provider, and it also drops every
    EXIF tag the phone wrote — including where the photo was taken, which is nobody's
    business but the person who took it.
    """
    image = open_image(data)
    return PageImage(
        data=_jpeg(image), media_type="image/jpeg", width=image.width, height=image.height
    )


def _check_page_count(n_pages: int) -> None:
    if n_pages > MAX_PAGES:
        raise TooManyPagesError(
            f"That file has {n_pages} pages. ServeTrace reads up to {MAX_PAGES}: upload the "
            "pages with the affidavit of service, and the judgment if you have it."
        )


def extract_text(pdf_bytes: bytes) -> PdfText:
    """The pdfplumber text layer, page by page, with each word's box for provenance."""
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            n_pages = len(pdf.pages)
            _check_page_count(n_pages)
            pages: list[str] = []
            words: list[tuple[Word, ...]] = []
            sizes: list[tuple[float, float]] = []
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
                sizes.append((float(page.width), float(page.height)))
                words.append(
                    tuple(
                        Word(
                            text=str(w["text"]),
                            x0=float(w["x0"]),
                            top=float(w["top"]),
                            x1=float(w["x1"]),
                            bottom=float(w["bottom"]),
                        )
                        for w in page.extract_words(keep_blank_chars=False)
                    )
                )
    except (UnsupportedFileError, TooManyPagesError):
        raise
    except Exception as exc:  # pdfplumber raises a zoo of pdfminer errors on a bad file
        raise BadInputError("We could not open that PDF. It may be damaged.") from exc

    text = "\n".join(pages).strip()
    return PdfText(
        text=text,
        n_pages=n_pages,
        has_text_layer=len(text) >= TEXT_MIN_CHARS,
        pages=tuple(pages),
        words=tuple(words),
        sizes=tuple(sizes),
    )


def rasterize(
    pdf_bytes: bytes,
    dpi: int = RASTER_DPI,
    max_pages: int = RASTER_MAX_PAGES,
    pages: list[int] | None = None,
    max_edge: int | None = None,
    media: Literal["png", "jpeg"] = "png",
) -> list[PageImage]:
    """Render pages of a PDF to images, for the model or for the user's own preview.

    `pages` picks which (0-based); without it, the first `max_pages`. `max_edge` shrinks
    each render to fit, which is how thumbnails and previews are made from the same call.
    """
    import pypdfium2 as pdfium
    from PIL import Image

    try:
        document = pdfium.PdfDocument(pdf_bytes)
    except Exception as exc:
        raise BadInputError("We could not open that PDF. It may be damaged.") from exc

    images: list[PageImage] = []
    try:
        _check_page_count(len(document))
        wanted = pages if pages is not None else list(range(min(len(document), max_pages)))
        for index in wanted:
            if not 0 <= index < len(document):
                continue
            rendered = document[index].render(scale=dpi / 72).to_pil().convert("RGB")
            if max_edge is not None:
                rendered.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            if media == "jpeg":
                rendered.save(buffer, format="JPEG", quality=PREVIEW_QUALITY, optimize=True)
            else:
                rendered.save(buffer, format="PNG", optimize=True)
            images.append(
                PageImage(
                    data=buffer.getvalue(),
                    media_type=f"image/{media}",
                    width=rendered.width,
                    height=rendered.height,
                    page=index,
                )
            )
    finally:
        document.close()
    return images


def shrink(page: PageImage, edge: int, quality: int = PREVIEW_QUALITY) -> PageImage:
    """A smaller JPEG of a page image: a thumbnail for classification or a preview."""
    from PIL import Image

    with Image.open(io.BytesIO(page.data)) as raw:
        image = raw.convert("RGB")
    image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
    return PageImage(
        data=_jpeg(image, quality),
        media_type="image/jpeg",
        width=image.width,
        height=image.height,
        page=page.page,
    )


def data_url(page: PageImage) -> str:
    return f"data:{page.media_type};base64,{base64.b64encode(page.data).decode('ascii')}"
