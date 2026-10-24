# Progress

| Task | Status | Notes |
|---|---|---|
| Audit | done 2026-10-25 | Repo empty except CLAUDE.md. Codex CLI 0.164.0 logged in (CODEX_OK). Docker 27.0.3 installed, daemon NOT running at audit. gh CLI absent (no push planned). |
| TASK-001 | DONE 2026-10-25 | pytest 19 passed, ruff ok, compose up: all healthy, smoke PASS, redis-down /ready=503 -> recovered 200 (verified by Claude on real Docker). Fix1 replaced MinIO with SeaweedFS (ADR-001). Python 3.11 runtime tests only via Docker image; host tests on 3.13. |
| TASK-002 | DONE 2026-10-25 | 4 tables + Alembic 0001/0002. pytest 60 passed (real PG16), ruff ok, Docker: upgrade/check/downgrade/upgrade OK, smoke PASS. Known MINOR (not fixed): predictions.model_version_id not DB-enforced equal to job model; no index on predictions.model_version_id. |
| TASK-003..006 | pending | |

## Decisions
- D-001: repo at `seg/visionguard-mlops/` (new git repo, branch main, local only; no remote/push).
- D-002: single `visionguard` Python package, `workers/` and `ml/` import it.
- D-003: MinIO images not pullable -> SeaweedFS 3.85 (ADR-001).
- Process note: Codex sandbox cannot access Docker pipe; Claude runs Docker verification.
- D-004: Python 3.15 (container 3.15.1, host uv-managed 3.15.0rc3) + uv 0.13.5 in Docker, uv.lock committed (ADR-002). Verified: compose healthy, smoke PASS, redis-down 503 -> 200, pytest 19 passed. Risk: PyTorch wheels for 3.15 (TASK-005). Note: ruff 0.17 formats `except A, B:` (PEP 758); code now requires >=3.14 syntax.
- D-005: host-run URLs use 127.0.0.1 not localhost (Windows IPv6 fallback hung DB tests).
