"""Text-layer extraction from an uploaded affidavit PDF. Bible §12. Session 2."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PdfText:
    text: str
    n_pages: int
    has_text_layer: bool


def extract_text(pdf_bytes: bytes) -> PdfText:
    """Pull the pdfplumber text layer. A layer under 200 chars means the scan path is used."""
    raise NotImplementedError("Session 2")


def rasterize(pdf_bytes: bytes, dpi: int = 200, max_pages: int = 3) -> list[bytes]:
    """Render pages to PNG bytes for the vision path."""
    raise NotImplementedError("Session 2")
