# Progress

| Task | Status | Notes |
|---|---|---|
| Audit | done 2026-10-25 | Repo empty except CLAUDE.md. Codex CLI 0.164.0 logged in (CODEX_OK). Docker 27.0.3 installed, daemon NOT running at audit. gh CLI absent (no push planned). |
| TASK-001 | DONE 2026-10-25 | pytest 19 passed, ruff ok, compose up: all healthy, smoke PASS, redis-down /ready=503 -> recovered 200 (verified by Claude on real Docker). Fix1 replaced MinIO with SeaweedFS (ADR-001). Python 3.11 runtime tests only via Docker image; host tests on 3.13. |
| TASK-002..006 | pending | |

## Decisions
- D-001: repo at `seg/visionguard-mlops/` (new git repo, branch main, local only; no remote/push).
- D-002: single `visionguard` Python package, `workers/` and `ml/` import it.
- D-003: MinIO images not pullable -> SeaweedFS 3.85 (ADR-001).
- Process note: Codex sandbox cannot access Docker pipe; Claude runs Docker verification.
