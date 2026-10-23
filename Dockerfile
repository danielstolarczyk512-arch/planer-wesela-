# syntax=docker/dockerfile:1
# Jeden obraz dla procesów api, worker i migrate (ADR-0001). Etap "test" tylko do testów.

# --- etap 1: instalacja zależności (uv tylko tutaj) ---
FROM python:3.12-slim-bookworm AS builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --- etap 2: obraz uruchomieniowy (bez uv i cache) ---
FROM python:3.12-slim-bookworm AS runtime
# FORWARDED_ALLOW_IPS i WEB_CONCURRENCY czyta uvicorn: zaufane proxy (X-Forwarded-*)
# i liczba procesów API. W produkcji nadpisywane w deploy/compose.prod.yaml.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    WP_STORAGE_DIR=/app/storage \
    FORWARDED_ALLOW_IPS=127.0.0.1 \
    WEB_CONCURRENCY=2

# OCR: Tesseract (Apache-2.0) z językiem polskim; czcionki DejaVu do testów korpusu.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-pol fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app app ./app
RUN mkdir -p /app/storage && chown app:app /app /app/storage
USER app

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2).status == 200 else 1)"

# Bez access logu uvicorna: zapisałby surowe ścieżki z tokenami. Żądania loguje API
# (app/core/logging.py) — z szablonem trasy zamiast ścieżki.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-access-log"]

# --- etap 3: testy w kontenerze (te same biblioteki systemowe co produkcja, w tym OCR) ---
FROM runtime AS test
USER root
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY --chown=app:app tests ./tests
COPY --chown=app:app scripts ./scripts
USER app
CMD ["pytest", "-q", "-p", "no:cacheprovider"]
