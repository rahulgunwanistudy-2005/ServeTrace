"""The single boundary between ServeTrace and WeasyPrint. Bible §15.

Everything above this module deals in a context dictionary; everything below it is HTML,
CSS and PDF bytes. Three properties are enforced here rather than trusted to each caller:

- **Autoescape is on and `Undefined` is strict.** Every value in these documents came off
  a scanned affidavit or out of a text box, and two of them are a person's own name and
  address. A field that renders as markup is a defect in a document meant for a court, and
  a field the template forgot is a blank space on a page somebody swears to — so a missing
  key raises here instead of printing nothing.
- **Nothing is fetched.** WeasyPrint resolves URLs it finds in a document. The fetcher
  below allows exactly one protocol — `data:`, which is how the map image is embedded —
  and treats a fetch of anything else as fatal rather than as a warning and a missing
  image. So a document render cannot reach the network by any route: not by accident, not
  by a crafted field, and not in a test (bible §16). This uses WeasyPrint's own allow-list
  rather than a hand-written fetcher, so it cannot drift away from how the library
  actually resolves things.
- **The bytes are a function of the input.** WeasyPrint writes no `/CreationDate` of its
  own, so identical HTML gives identical PDFs. The documents therefore take their
  timestamp from `CaseAnalysis.generated_at` rather than reading a clock, and
  `test_render.py` asserts the two renders match byte for byte.

**The native stack.** WeasyPrint needs pango, cairo and harfbuzz at import time. The
Dockerfile installs them; a developer machine may not have them where dyld looks. The
failure that produces is a cffi traceback that names none of that, so it is caught once,
here, and re-raised as a sentence with the fix in it.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.api.errors import DocumentsUnavailableError

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
PRINT_CSS = STATIC_DIR / "print.css"

_MISSING_LIBS = (
    "The PDF renderer is not available on this server. Everything else still works — "
    "the result page has the same verdict, the same numbers and the same findings."
)

_DEV_HINT = """
WeasyPrint could not load pango/cairo/harfbuzz.

  macOS:  brew install pango cairo gdk-pixbuf libffi
          export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
          (Homebrew installs to /opt/homebrew/lib on Apple Silicon, which is not on
          macOS's default dyld search path, so the libraries are present and invisible.)

  Debian: the Dockerfile's runtime stage already installs them.
"""


@lru_cache(maxsize=1)
def _weasyprint() -> Any:
    """Import WeasyPrint once, and turn a missing native stack into a sentence.

    Cached because the import costs about a second and because a machine that could not
    load pango a moment ago will not have grown it since.
    """
    try:
        import weasyprint
    except OSError as exc:  # pragma: no cover - depends on the host, not on the code
        print(_DEV_HINT, file=sys.stderr)
        raise DocumentsUnavailableError(_MISSING_LIBS) from exc
    return weasyprint


def pdf_available() -> bool:
    """Whether this process can render a PDF at all. For `/api/health` and for tests."""
    try:
        _weasyprint()
    except DocumentsUnavailableError:
        return False
    return True


ALLOWED_PROTOCOLS = frozenset({"data"})
"""The map image, embedded as a `data:` URI by the browser that drew it. Nothing else.

`file:` is not on the list either. The stylesheet is handed to WeasyPrint as a filename
and read directly rather than fetched, so allowing `file:` would buy nothing and would
turn a crafted field into a way to read this server's disk.
"""


def url_fetcher() -> Any:
    """A fetcher that can reach `data:` and nothing else, and says so by failing.

    `fail_on_errors` matters as much as the allow-list. Without it a refused URL is a
    warning and a missing image, which is a document that quietly lost a section; with it,
    a document that tried to reach the network does not render at all.
    """
    weasyprint = _weasyprint()
    fetcher: Any = weasyprint.urls.URLFetcher(
        allowed_protocols=ALLOWED_PROTOCOLS, fail_on_errors=True, timeout=1
    )
    return fetcher


@lru_cache(maxsize=1)
def environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_html(template_name: str, context: dict[str, Any]) -> str:
    """The document as HTML. Separated from `render_pdf` so tests can read the words.

    Most of what can go wrong in a document — a missing paragraph, an unescaped name, a
    number formatted two ways on one page — is visible here and invisible in a PDF.
    """
    return environment().get_template(template_name).render(**context)


def render_pdf(template_name: str, context: dict[str, Any]) -> bytes:
    weasyprint = _weasyprint()
    fetcher = url_fetcher()
    html = weasyprint.HTML(
        string=render_html(template_name, context),
        base_url=str(TEMPLATE_DIR),
        url_fetcher=fetcher,
    )
    css = weasyprint.CSS(filename=str(PRINT_CSS), url_fetcher=fetcher)
    pdf: bytes = html.write_pdf(stylesheets=[css], uncompressed_pdf=False)
    return pdf
