# VisionGuard MLOps — Architecture (Phase 1)

Status: draft v0.1 (TASK-001 baseline). Source of truth for scope: `CLAUDE.md`.

## 1. Goals / non-goals
Goal: local-first, zero-cloud-cost moderation MLOps platform. Phase 1 = upload -> store -> async inference -> persisted result via REST.
Non-goals (Phase 1): Next.js UI, CVAT, MLflow, video, GPU, auth/multi-tenant, any paid cloud service.

## 2. Components
```
client --HTTP--> backend (FastAPI) --SQL--> postgres
                    |  \--S3 API--> minio (S3-compatible)
                    \--outbox row--> dispatcher --> redis (broker) --> worker (Celery)
                                                                         |--> postgres (job state, predictions)
                                                                         \--> minio (read image), ml/ adapter
```
| Dir | Responsibility |
|---|---|
| `backend/` | FastAPI app, Pydantic v2 schemas, SQLAlchemy 2 models, Alembic, REST routes |
| `workers/` | Celery app + tasks; imports shared domain from `backend` package (`visionguard`) |
| `ml/` | model adapter interface, preprocessing, demo backend (later tasks) |
| `docker/` | Dockerfiles, compose helpers |
| `docs/` | architecture, tasks, decisions, progress |
| `scripts/` | smoke tests |
| `note/` | development log / article drafts |

Single installable Python package `visionguard` (src layout under `backend/src/visionguard`) with subpackages `api`, `core` (settings, logging), `db`, `storage`, `jobs`, `ml`. `workers/` and `ml/` entrypoints import it, avoiding duplicated domain code.

## 3. Configuration
All via env vars (pydantic-settings, prefix-less, documented in `.env.example`). No secrets in Git; `.env` ignored. Local-only default credentials in `.env.example` are dev placeholders.

## 4. Runtime defaults (pinned)
Python 3.11 (Docker image `python:3.11-slim`), PostgreSQL 16, Redis 7, MinIO (pinned release tag), CPU-only. Dependencies pinned with `==` in `backend/requirements.txt` / `requirements-dev.txt`. Torch added in TASK-005 (CPU wheel).

## 5. Health contract
- `GET /health`: liveness, no dependencies, 200 `{"status":"ok"}`.
- `GET /ready`: checks postgres, redis, object storage; 200 when all ok, 503 with per-dependency status otherwise.
- Compose healthchecks on postgres/redis/minio/backend; backend and worker `depends_on: condition: service_healthy`.

## 6. Job state machine & reliability (implemented TASK-004)
`QUEUED -> RUNNING -> SUCCEEDED`; `RUNNING -> RETRYING -> RUNNING`; `RUNNING|RETRYING -> FAILED` after bounded retries. Transitions via atomic conditional UPDATE (`WHERE state IN (...)`), `predictions.job_id` UNIQUE. Enqueue uses transactional outbox + dispatcher to survive commit-ok/publish-fail. Celery `acks_late`, retry with backoff; at-least-once, idempotent handlers.

## 7. ML honesty rule
Moderation scores come only from an explicitly configured licensed multi-label checkpoint. Otherwise a demo backend returns clearly labeled mock scores (`model.name = "demo-mock"`, `is_demo = true`). ImageNet outputs are never presented as moderation scores.

## 8. Extension points (not built in Phase 1)
`annotation_tasks`, `annotations`, `annotation_reviews`, `dataset_versions`, `experiment_runs` tables reserved by naming only; MLflow/CVAT as additional compose profiles; frontend/ placeholder directory.

## 9. Task sequence
TASK-001 skeleton+compose -> 002 DB/Alembic -> 003 upload -> 004 jobs/outbox/Celery -> 005 model adapter -> 006 e2e/README.
