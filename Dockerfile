# ServeTrace ships as one container: FastAPI serves the built SvelteKit bundle.
# Bible §7 — single deployable, one Render web service, no database.

# ---------- stage 1: build the static frontend ----------
FROM node:22-bookworm-slim AS frontend

# The repo layout is mirrored rather than flattened, because three modules under
# `frontend/src` reach *out* of the frontend with `../../../../fixtures/demo_cases` — the
# advocate demo spreadsheet, the three demo cases, and the test fixtures. Building from a
# bare /build silently changes what those four `..` mean.
#
# It failed loudly for the static import and would have failed silently for the other two:
# `import.meta.glob` over a directory that is not there matches nothing and raises nothing,
# so /demo would have deployed with no cases and no error anywhere.
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
COPY fixtures/demo_cases /build/fixtures/demo_cases
RUN npm run build


# ---------- stage 2: python runtime ----------
FROM python:3.12-slim-bookworm AS runtime

# WeasyPrint renders the evidence packet, and it needs the real pango/cairo stack at
# runtime, not just at install time.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
        fonts-liberation2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8.23 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /srv/backend

# Dependencies resolve from the lockfile alone, so editing application code does not
# invalidate this layer.
COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --no-install-project --no-dev

COPY backend/ ./
RUN uv sync --no-dev

# main.py resolves the bundle as <repo>/frontend/build, two levels above app/.
COPY --from=frontend /build/frontend/build /srv/frontend/build

# Demo cases must work with no network and no LLM key (bible §17).
COPY fixtures/demo_cases /srv/fixtures/demo_cases

RUN useradd --create-home --uid 10001 servetrace && chown -R servetrace /srv
USER servetrace

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
