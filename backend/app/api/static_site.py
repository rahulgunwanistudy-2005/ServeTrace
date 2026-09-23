"""Serve the prerendered SvelteKit bundle. Bible §7: one deployable, FastAPI serves `/`.

`StaticFiles` alone is not enough. adapter-static writes `methodology.html`, not
`methodology/index.html`, so an extensionless request for a real page would 404, and the
SPA fallback (`200.html`) would never be used for client-routed paths.
"""

from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.errors import envelope

SPA_FALLBACK = "200.html"
INDEX = "index.html"


def _resolve(root: Path, url_path: str) -> Path | None:
    """Map a URL path to a file inside `root`, or None.

    The candidate is resolved and checked to be under `root` before it is opened, so a
    crafted path cannot walk out of the bundle and serve something else off the disk.
    """
    relative = url_path.strip("/")
    if not relative:
        return root / INDEX

    candidates = (
        root / relative,
        root / f"{relative}.html",
        root / relative / INDEX,
    )
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if not resolved.is_file():
            continue
        if not resolved.is_relative_to(root):
            return None
        return resolved
    return None


def mount_frontend(app: FastAPI, build_dir: Path) -> None:
    """Mount the bundle at `/`, with `/api/*` reserved for the API."""
    if not build_dir.is_dir():
        return

    root = build_dir.resolve()
    assets = root / "_app"
    if assets.is_dir():
        # Hashed filenames, so these are safe to cache hard.
        app.mount("/_app", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve(request: Request, full_path: str) -> Response:
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content=envelope("not_found", "No such endpoint."))

        target = _resolve(root, full_path)
        if target is not None:
            return FileResponse(target)

        # A path the bundle does not prerender is handed to the client router.
        fallback = root / SPA_FALLBACK
        if fallback.is_file():
            return FileResponse(fallback, status_code=200)
        return JSONResponse(status_code=404, content=envelope("not_found", "Page not found."))
