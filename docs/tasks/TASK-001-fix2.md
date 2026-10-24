# TASK-001-fix2 — Python 3.15 + uv in Docker

Read docs/decisions/ADR-002-python-uv.md first. Docker daemon access is NOT available to you: do Docker-free work and mark Docker steps UNVERIFIED; Claude will run them.

## Scope
1. `backend/pyproject.toml`: requires-python ">=3.15"; dependencies declared in `[project].dependencies` with exact `==` pins (use the newest versions that install on 3.15 -- check with `uv`); `[dependency-groups] dev = [pytest, ruff, httpx]` pinned; keep setuptools build backend (or uv_build if it works) with src layout; remove `dynamic` requirements file usage.
2. Generate and commit `backend/uv.lock` (`uv lock`). Delete `backend/requirements.txt` and `requirements-dev.txt`.
3. `docker/backend.Dockerfile`: `FROM python:3.15-slim` (pin verified tag), `COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/`, `UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never`, layer-cached `uv sync --frozen --no-dev --no-install-project` then project install; run as non-root; use `/app/.venv/bin` on PATH. Compose build context must keep working (worker needs `workers/` and `scripts/`).
4. Root `pyproject.toml`: update ruff target-version to py315 (if ruff supports it; otherwise highest supported and note it) and pytest paths; make `uv run --project backend pytest` work from repo root OR document the exact command in README.
5. README: replace pip/venv instructions with uv commands.
6. Do not change application behavior.

## Acceptance
- On host: `uv python install 3.15` (if needed), `uv sync --frozen` in backend, `uv run pytest -q` passes (>=19 tests), `uv run ruff check .` and `uv run ruff format --check .` pass, `uv lock --check` passes, `docker compose config -q` passes.
- Report exact resolved versions and any package that had to change major version. Report real outputs; UNVERIFIED for Docker build/run.
- No git commit/push. Do not edit docs/ or CLAUDE.md. Keep uv cache/temp outside the repo or in .venv.
