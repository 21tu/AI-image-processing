# TASK-001-fix1 — Replace MinIO with SeaweedFS and make compose actually start

Read docs/decisions/ADR-001-s3-storage-backend.md first.

## Findings from review
F1 (BLOCKER): `minio/minio` images cannot be pulled; compose cannot start. Replace with SeaweedFS (pin a concrete version tag that you verify can be pulled; do not use `latest`). Rename service to `objectstore`, enable S3 API on port 9000 (host binding 127.0.0.1 only), configure access/secret keys from S3_ACCESS_KEY/S3_SECRET_KEY (use SeaweedFS S3 identity config; mount it from a repo file `docker/seaweedfs-s3.json` that references env-free dev placeholders OR generate it at start-up -- no real secrets), persist data in a named volume.
F2 (BLOCKER): bucket-init used `mc`, which is not in that image. Replace with a one-shot service using the backend image running a small Python/boto3 script (`scripts/init_bucket.py`, retry until the store is reachable, create bucket if missing, idempotent).
F3 (MAJOR): the old healthcheck used `curl` which may be absent. Use a healthcheck that works with the tools actually present in the chosen image; verify by inspecting the container.
F4 (MINOR): pin postgres and redis to minor tags (e.g. postgres:16.x, redis:7.x) that you verify exist locally.

## Acceptance (must be REAL, Docker daemon is up now)
- `docker compose up -d --build` -> all long-running services `healthy`, bucket-init exited 0.
- `python scripts/smoke_health.py` exits 0 (/health 200, /ready 200 with all checks ok).
- Stop the redis container -> /ready returns 503 with checks.redis=fail; restart -> 200 again. Report evidence.
- `docker compose down` at the end (keep volumes). Update README/.env.example/architecture-neutral wording in code comments only; do NOT edit docs/ or CLAUDE.md.
- Re-run pytest, ruff check, ruff format --check; all must pass.

## Rules
No git commit/push. Minimal diff beyond the above. Report real command output; mark anything not run as UNVERIFIED.
