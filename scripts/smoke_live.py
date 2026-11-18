# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright==1.56.0", "pillow", "piexif", "pillow-heif"]
# ///
"""Live smoke test of the deployed site, in a real browser, on a desktop and a phone.

    uv run scripts/smoke_live.py                          # https://servetrace.onrender.com
    uv run scripts/smoke_live.py --base-url http://localhost:5173
    uv run scripts/smoke_live.py --record                 # also the three video clips

`uv run` reads the dependencies above into a throwaway environment, so nothing is added
to the project. Playwright is pinned to 1.56.0 because that release drives the Chromium
build already in the Playwright cache on the machine this was written on; on a fresh
machine run `uv run --with playwright==1.56.0 playwright install chromium` once.

What it does, and what it never does:

- Visits every main page at 1440x900 and as an emulated iPhone: HTTP status, load time,
  console errors, horizontal overflow, a screenshot.
- Runs the /demo case (Maria) to its verdict and downloads the evidence packet; loads the
  attorney sample batch, compares it and downloads the PDF report and a CSV; imports three
  synthetic photos on /check against the bundled sample affidavit.
- Every one of those runs on bundled synthetic data and is sent with the demo header, so
  it lands in the demo column of the usage counts, never the real one.
- The /attorneys contact form is only checked to refuse an incomplete request. It is never
  submitted: the product has no dry-run flag, and a smoke test must not create a lead.

Writes `scripts/smoke_live_report.md` and screenshots (and clips) to `scripts/smoke_out/`,
which is gitignored. Exits non-zero if anything failed.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import Browser, BrowserContext, Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scripts" / "smoke_out"
REPORT = ROOT / "scripts" / "smoke_live_report.md"
PAGES = [
    "/",
    "/check",
    "/demo",
    "/attorneys",
    "/advocate",
    "/methodology",
    "/privacy",
    "/changelog",
]
DESKTOP = {"viewport": {"width": 1440, "height": 900}}
PHONE_NAME = "iPhone 13"
NY = ZoneInfo("America/New_York")

# Lin's sample affidavit (the one /check's "Try a sample affidavit" loads) swears the
# papers were taped to a Queens door at 4:30 PM on 2025-09-09. Her Timeline has her at work
# in Brooklyn 2 PM to 10 PM; these photos are taken there, around the claimed time.
LIN_WORK = (40.6771698, -73.9323105)
LIN_PHOTOS = (
    ("IMG_2041.jpg", 16, 12, False),
    ("IMG_2042.jpg", 16, 29, False),
    ("IMG_2043.heic", 16, 47, True),
)


@dataclass
class PageResult:
    viewport: str
    path: str
    status: int | None
    load_ms: float | None
    console_errors: list[str]
    overflow_px: int
    screenshot: str

    @property
    def ok(self) -> bool:
        return self.status == 200 and not self.console_errors and self.overflow_px <= 0


@dataclass
class FlowResult:
    name: str
    ok: bool
    seconds: float
    detail: str


@dataclass
class Run:
    base: str
    pages: list[PageResult] = field(default_factory=list)
    flows: list[FlowResult] = field(default_factory=list)
    clips: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------------------
# pages


def visit(context: BrowserContext, base: str, path: str, label: str) -> PageResult:
    page = context.new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text[:200]) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {str(e)[:200]}"))
    response = page.goto(base + path, wait_until="load", timeout=90_000)
    page.wait_for_load_state("networkidle", timeout=30_000)
    load_ms = page.evaluate(
        "() => { const n = performance.getEntriesByType('navigation')[0];"
        " return n ? n.loadEventEnd - n.startTime : null; }"
    )
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    name = f"{label}_{path.strip('/') or 'home'}.png"
    page.screenshot(path=OUT / name, full_page=True)
    page.close()
    return PageResult(
        label,
        path,
        response.status if response else None,
        round(load_ms) if load_ms else None,
        errors,
        int(overflow),
        name,
    )


# --------------------------------------------------------------------------------------
# flows


def flow(run: Run, name: str, body: Callable[[Page], str], page: Page) -> None:
    started = time.monotonic()
    try:
        detail = body(page)
        run.flows.append(FlowResult(name, True, time.monotonic() - started, detail))
    except Exception as error:  # a smoke test reports; it does not crash
        message = " / ".join(str(error).splitlines()[:4])[:400]
        run.flows.append(FlowResult(name, False, time.monotonic() - started, message))


def demo_flow(page: Page, base: str, pause: int = 0) -> str:
    page.goto(base + "/demo")
    page.wait_for_timeout(pause)
    page.get_by_role("button", name="Open this case").first.click()
    page.wait_for_url("**/result", timeout=60_000)
    headline = page.get_by_text("Your location data conflicts with the affidavit.").first
    expect(headline).to_be_visible(timeout=60_000)
    page.wait_for_timeout(pause)
    if pause:
        page.locator(".maplibregl-canvas").first.scroll_into_view_if_needed()
        page.wait_for_timeout(pause * 2)
        page.mouse.wheel(0, 500)
        page.wait_for_timeout(pause)
    with page.expect_download(timeout=90_000) as download:
        page.get_by_role("button", name="Download evidence packet").click()
    pdf = Path(download.value.path())
    head = pdf.read_bytes()[:5]
    assert head == b"%PDF-", f"packet is not a PDF: {head!r}"
    return f"verdict 'conflicts'; packet {pdf.stat().st_size:,} bytes"


def batch_flow(page: Page, base: str, pause: int = 0) -> str:
    page.goto(base + "/advocate")
    page.get_by_text("A folder of affidavits").click()
    page.wait_for_timeout(pause)
    page.get_by_role("button", name="Or load a sample batch").click()
    confirm = page.get_by_role("button", name=re.compile(r"^Confirm all \d+ ready"))
    expect(confirm).to_be_visible(timeout=60_000)
    page.wait_for_timeout(pause)
    confirm.click()
    compare = page.get_by_role("button", name=re.compile(r"^Compare \d+ confirmed"))
    expect(compare).to_be_enabled(timeout=30_000)
    n = compare.inner_text()
    compare.click()
    expect(page.get_by_role("heading", name="Agencies, ranked")).to_be_visible(timeout=90_000)
    page.wait_for_timeout(pause)
    if pause:
        for _ in range(6):
            page.mouse.wheel(0, 450)
            page.wait_for_timeout(pause // 2)
    sizes = []
    for label in ("Download the report (PDF)", "Sequences (CSV)"):
        with page.expect_download(timeout=120_000) as download:
            page.get_by_role("button", name=label).click()
        size = Path(download.value.path()).stat().st_size
        assert size > 0, f"{label} is empty"
        sizes.append(f"{label} {size:,} bytes")
    return f"{n.strip()}; " + "; ".join(sizes)


def make_photos(directory: Path) -> list[Path]:
    """Three synthetic photos at Lin's workplace around the claimed time (metadata only)."""
    sys.path.insert(0, str(ROOT))
    from fixtures.generator.photos import Photo, encode

    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, hour, minute, heic in LIN_PHOTOS:
        local = datetime(2025, 9, 9, hour, minute, tzinfo=NY)
        photo = Photo(name, local, LIN_WORK, gps_stamp=True, offset="-04:00", heic=heic)
        path = directory / name
        path.write_bytes(encode(photo))
        paths.append(path)
    return paths


def photo_flow(page: Page, base: str, photos: list[Path], pause: int = 0) -> str:
    page.goto(base + "/check")
    page.get_by_role("button", name="No papers to hand? Try a sample affidavit").click()
    expect(page.get_by_text("Nothing was flagged")).to_be_visible(timeout=30_000)
    page.wait_for_timeout(pause)
    page.get_by_role("button", name="Confirm all — these match my papers").click()
    page.get_by_role("button", name="Continue").click()
    expect(page.get_by_text("Where were you?").first).to_be_visible(timeout=30_000)
    page.get_by_text("Photos from that day").first.click()
    page.wait_for_timeout(pause)
    page.locator("input[type=file]").first.set_input_files([str(p) for p in photos])
    counts = page.get_by_text(re.compile(r"photos? read"))
    expect(counts).to_be_visible(timeout=30_000)
    text = counts.first.inner_text()
    assert "3 near the claimed time" in text, text
    page.wait_for_timeout(pause * 2)
    return text.strip()


def form_check(page: Page, base: str) -> str:
    posted: list[str] = []
    page.on("request", lambda r: posted.append(r.url) if "/api/leads" in r.url else None)
    page.goto(base + "/attorneys")
    page.locator("#lead-name").fill("Smoke Test")
    page.locator("#lead-email").fill("smoke@example.invalid")
    send = page.get_by_role("button", name="Send")
    expect(send).to_be_disabled()
    page.wait_for_timeout(1000)
    assert not posted, f"the form sent a request: {posted}"
    return (
        "name and email filled, consent not ticked: Send stays disabled, no request to /api/leads"
    )


# --------------------------------------------------------------------------------------


def record(browser: Browser, base: str, photos: list[Path], run: Run) -> None:
    directory = OUT / "video"
    directory.mkdir(parents=True, exist_ok=True)
    size = {"width": 1920, "height": 1080}
    for name, body in (
        ("a_demo_map_verdict", lambda p: demo_flow(p, base, pause=1500)),
        ("b_photo_import", lambda p: photo_flow(p, base, photos, pause=1500)),
        ("c_attorney_batch_report", lambda p: batch_flow(p, base, pause=1500)),
    ):
        context = browser.new_context(
            viewport=size,
            record_video_dir=str(directory / "tmp"),
            record_video_size=size,
            accept_downloads=True,
        )
        page = context.new_page()
        flow(run, f"record {name}", body, page)
        page.wait_for_timeout(1500)
        video = page.video
        context.close()
        if video:
            target = directory / f"{name}.webm"
            video.save_as(target)
            video.delete()
            run.clips.append(str(target.relative_to(ROOT)))


def write_report(run: Run, started: datetime) -> None:
    lines = [
        "# Live smoke test",
        "",
        f"Run {started:%Y-%m-%d %H:%M} UTC against {run.base} with `scripts/smoke_live.py`.",
        "Desktop is 1440x900; phone is Playwright's emulated iPhone 13 (390x844, touch, mobile",
        "user agent) in Chromium. Load time is the browser's navigation `loadEventEnd`.",
        "",
        "## Pages",
        "",
        "| Viewport | Page | Status | Load | Console errors | Horizontal overflow | Result |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for r in run.pages:
        lines.append(
            f"| {r.viewport} | `{r.path}` | {r.status} | {r.load_ms} ms | {len(r.console_errors)} "
            f"| {max(r.overflow_px, 0)} px | {'pass' if r.ok else 'FAIL'} |"
        )
    failures = [r for r in run.pages if r.console_errors]
    for r in failures:
        lines += ["", f"Console errors on {r.viewport} `{r.path}`:", ""]
        lines += [f"- `{e}`" for e in r.console_errors]
    lines += ["", "## Flows", "", "| Flow | Result | Time | Detail |", "|---|---|---:|---|"]
    for f in run.flows:
        detail = f.detail.replace("|", "\\|")
        lines.append(f"| {f.name} | {'pass' if f.ok else 'FAIL'} | {f.seconds:.1f} s | {detail} |")
    if run.clips:
        lines += ["", "## Clips", ""] + [f"- `{c}`" for c in run.clips]
    lines += ["", "Screenshots are in `scripts/smoke_out/` (gitignored).", ""]
    REPORT.write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default="https://servetrace.onrender.com")
    parser.add_argument("--record", action="store_true", help="also record the three clips")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC)
    run = Run(base)
    photos = make_photos(OUT / "photos")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        phone = {k: v for k, v in p.devices[PHONE_NAME].items() if k != "default_browser_type"}
        for label, options in (("desktop", DESKTOP), ("iphone", phone)):
            context = browser.new_context(**options, accept_downloads=True)
            for path in PAGES:
                run.pages.append(visit(context, base, path, label))
            flows: list[tuple[str, Callable[[Page], str]]] = [
                ("/demo case to verdict + packet", lambda pg: demo_flow(pg, base)),
            ]
            if label == "desktop":
                flows += [
                    ("attorney sample batch to report", lambda pg: batch_flow(pg, base)),
                    ("photo import on /check", lambda pg: photo_flow(pg, base, photos)),
                    ("contact form refuses, never submits", lambda pg: form_check(pg, base)),
                ]
            for name, body in flows:
                page = context.new_page()
                flow(run, f"{label}: {name}", body, page)
                page.close()
            context.close()
        if args.record:
            record(browser, base, photos, run)
        browser.close()

    write_report(run, started)
    bad = [r for r in run.pages if not r.ok] + [f for f in run.flows if not f.ok]
    print(REPORT.read_text())
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
