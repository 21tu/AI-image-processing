# TASK-001 — Repo skeleton, configuration, Docker Compose, health checks

Context: VisionGuard MLOps Phase 1; read CLAUDE.md and docs/architecture.md.

## Goal
`docker compose up` brings up postgres, redis, minio, backend, worker; `GET /health` and `GET /ready` work; unit tests pass on host.

## In scope
- `backend/pyproject.toml` (package `visionguard`, src layout, Python >=3.11), `backend/requirements.txt`, `backend/requirements-dev.txt` — all versions pinned with `==`.
- `backend/src/visionguard/core/config.py`: `Settings` (pydantic-settings) with DATABASE_URL, REDIS_URL, S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET, S3_REGION, APP_ENV, LOG_LEVEL, MAX_UPLOAD_BYTES. `get_settings()` cached.
- `backend/src/visionguard/core/logging.py`: structured (JSON) logging setup.
- `backend/src/visionguard/api/main.py`: `create_app()`; request-ID middleware (accept/generate `X-Request-ID`, echo in response header, include in logs); structured error handler returning `{"error":{"code","message","request_id"}}`.
- `api/routes/health.py`: `/health` (no deps), `/ready` (checks DB via `SELECT 1`, Redis PING, S3 head_bucket with short timeouts; 200 or 503 with `{"status":"ready|degraded","checks":{"database":"ok|fail","redis":..., "storage":...}}`; never leak exception text/credentials).
- `workers/celery_app.py`: minimal Celery app (broker=REDIS_URL, `acks_late=True`, `task_default_queue="inference"`), plus a `ping` task. No business tasks.
- `docker/backend.Dockerfile` (python:3.11-slim, non-root user, installs pinned requirements), `docker-compose.yml` (postgres:16, redis:7, minio with bucket-init one-shot, backend, worker; healthchecks; named volumes; ports bound to 127.0.0.1), `.env.example`, `.gitignore`, `.dockerignore`.
- Placeholder dirs with README: `frontend/`, `ml/`.
- `Makefile` or `scripts/` helpers: `scripts/smoke_health.py` (stdlib only; hits /health and /ready).
- `README.md` quick start (short).
- Tests in `backend/tests/`: settings defaults/override, request-ID echo, /health 200, /ready 200 with fakes and 503 when a check fails, error body shape, no secret leakage in /ready 503 body.
- ruff config in pyproject; code must pass `ruff check` and `ruff format --check`.

## Out of scope
DB models/Alembic, upload, inference endpoints, torch, frontend code, CI workflows, any cloud service.

## Interfaces
Health response schemas above. Dependency checks are injectable (FastAPI dependencies) so tests use fakes.

## Constraints
CPU-first, local Docker only, pinned deps, no secrets committed, no git commit/push, do not edit CLAUDE.md or docs/ (except noted), no files outside repo.

## Acceptance criteria
- `pytest` passes (report count).
- `ruff check` and `ruff format --check` pass.
- `docker compose config` valid. If the Docker daemon is running: `docker compose up -d --build` -> all services healthy, `python scripts/smoke_health.py` exits 0. If daemon is down, report as UNVERIFIED (do not claim success).
- `/ready` returns 503 (not 500) when a dependency is down.

## Verification (run and report exit codes)
`cd backend && pip install -r requirements-dev.txt && pytest -q`, `ruff check .`, `ruff format --check .`, `docker compose config -q`.

## Deliverable
Implementation + tests; report changed files, real command output, anything unverified.
