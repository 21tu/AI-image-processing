# ADR-002: Latest Python (3.15) and uv for dependency management

Date: 2026-10-25. Status: accepted (user request: "use latest Python, use uv in Docker").

## Decision
- Runtime/base image: `python:3.15-slim` (verified pullable; reports Python 3.15.1). Pin the exact tag that is verified.
- Dependency management with uv: `backend/pyproject.toml` declares dependencies (+ `dev` dependency group); `backend/uv.lock` is committed; Docker installs with `uv sync --frozen --no-dev` using `COPY --from=ghcr.io/astral-sh/uv:<pinned> /uv /bin/uv` (verified: uv 0.13.5). requirements*.txt are removed.
- Host dev/test also use uv (`uv sync`, `uv run pytest`), with `uv python install 3.15` when needed.
- ruff target-version and requires-python updated to the new baseline.

## Risks
- Wheel availability on 3.15 for pydantic-core, psycopg-binary, greenlet, and especially PyTorch (TASK-005). If a needed package has no 3.15 wheel, pin the newest version that works and record it here; if PyTorch lacks 3.15 wheels at TASK-005, the ML worker image may need its own Python version (decide then via a new ADR; do not silently downgrade the API image).
