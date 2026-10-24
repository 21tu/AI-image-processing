FROM python:3.15-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock /app/backend/
RUN uv sync --project backend --frozen --no-dev --no-install-project
COPY backend /app/backend
RUN uv sync --project backend --frozen --no-dev --no-editable \
    && useradd --create-home --uid 10001 visionguard
COPY workers /app/workers
COPY scripts /app/scripts
USER visionguard
EXPOSE 8000
CMD ["uvicorn", "visionguard.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
