# TASK-002 — SQLAlchemy entities, Alembic migrations, constraints/indexes, DB tests

Context: VisionGuard MLOps Phase 1; read CLAUDE.md, docs/architecture.md, docs/decisions/ADR-002-python-uv.md. Python 3.15, uv (`uv run --project backend ...`), SQLAlchemy 2.1, PostgreSQL 16.

## Goal
Four tables exist via an Alembic migration, with DB-enforced integrity, and tests prove upgrade/downgrade, constraints and model/migration parity against a real PostgreSQL.

## In scope (package `visionguard.db`, under backend/src)
- `base.py` (DeclarativeBase, naming convention for constraints/indexes), `session.py` (engine/sessionmaker factory from Settings; sync SQLAlchemy 2 style; no global engine at import time), `enums.py`, `models/` with one module per entity.
- Entities (all PK `id` UUID, generated app-side with uuid4; all timestamps `timestamptz`, UTC, `created_at` server default now()):
  - `media_assets`: object_key (unique, not null), sha256 (char(64), lowercase hex CHECK, indexed, NOT unique -- same bytes may be uploaded twice), mime_type (CHECK in image/jpeg|image/png|image/webp), size_bytes (>0), width (>0), height (>0), validation_status enum `PENDING|VALID|INVALID`, created_at, updated_at.
  - `model_versions`: name, version (UNIQUE(name, version)), artifact_uri (nullable: demo has none), artifact_checksum (nullable), label_schema_version, labels (JSONB list of strings, non-empty), is_demo bool default false, is_active bool default false, created_at. Partial unique index: at most one active row per name.
  - `inference_jobs`: media_asset_id FK (RESTRICT), model_version_id FK (RESTRICT), state enum `QUEUED|RUNNING|RETRYING|SUCCEEDED|FAILED` default QUEUED, attempt_count int default 0 CHECK >=0, idempotency_key (unique, not null, length 1..255), celery_task_id nullable, error_code/error_message nullable, created_at, updated_at, started_at, finished_at. CHECK: state='FAILED' => error_code NOT NULL; finished_at NOT NULL iff state in (SUCCEEDED,FAILED). Indexes: (state, created_at), media_asset_id.
  - `predictions`: job_id FK UNIQUE (CASCADE not allowed; RESTRICT), model_version_id FK, label_scores JSONB (object), thresholds JSONB (object), decisions JSONB (object), latency_ms float CHECK >=0, preprocessing_version, created_at. Raw scores and policy decisions are separate columns.
- No `annotation_*`, `dataset_versions`, `experiment_runs` tables (naming reserved only; mention in a code comment in models/__init__).
- Alembic: `backend/alembic.ini`, `backend/alembic/env.py` (URL from Settings, never hard-coded; supports `-x`/env override for tests), migration `0001_initial_schema` hand-reviewed (explicit names), working `downgrade`.
- Add `alembic` as pinned dependency via `uv add` (update uv.lock). Dockerfile must still build and include alembic files; `docker compose run --rm backend alembic upgrade head` must work.
- Tests (`backend/tests/db/`), marker `db`, using a dedicated database `visionguard_test` on the compose Postgres (URL env `TEST_DATABASE_URL`, default localhost). If the DB is unreachable, tests must FAIL loudly with a clear message (not silently skip) unless env `SKIP_DB_TESTS=1`:
  - upgrade head -> all tables/indexes/constraints present; downgrade base -> empty; upgrade again works.
  - model metadata vs migration parity (alembic `compare_metadata` returns no diffs).
  - each CHECK / UNIQUE / FK violation is rejected (IntegrityError), including: duplicate (name, version), two active versions same name, duplicate idempotency_key, second prediction for same job_id, FAILED without error_code, deleting a media_asset referenced by a job.
  - happy-path round trip of a full chain media -> model -> job -> prediction.
- Existing 19 tests must keep passing.

## Out of scope
Upload/inference endpoints, outbox table, repositories/services, seed data, data migrations, CVAT/annotation tables.

## Constraints
Pinned deps, no secrets, no git commit/push, do not edit CLAUDE.md or docs/. You cannot use Docker; Claude has started Postgres on localhost:5432 (user visionguard / password local-dev-only, db visionguard). Create `visionguard_test` yourself in test setup (CREATE DATABASE via admin connection) or document the one-time command.

## Verification (run and report real outputs)
`uv run --project backend pytest -q`, `ruff check .`, `ruff format --check .`, `uv lock --check`, `alembic upgrade head` / `downgrade base` against the dev DB, `alembic check`.
