# TASK-003-fix1 — Object store volume limit + finish unverified TASK-003 checks

Root cause (verified by Claude): docker-compose.yml runs SeaweedFS with `-volume.max=5`. Five volumes get used up, so a new collection (the `visionguard` bucket) cannot grow volumes: "Not enough data nodes found" -> every PUT returns 500/InternalError/timeout. With `-volume.max=0` (auto) a PUT succeeds in 0.22s (Claude tested with a temp compose copy).

1. In docker-compose.yml change `-volume.max=5` to `-volume.max=0`; keep `-master.volumeSizeLimitMB=100`. Add a short comment explaining why (small fixed max starves new bucket collections). Do not touch other services.
2. The currently running store already uses max=0 (Claude restarted it), at 127.0.0.1:9000. Now run and report REAL results for the previously blocked items: the `s3`-marker integration test (put/exists/delete), full `pytest -q`, and the uvicorn-based `scripts/smoke_upload.py` against the running Postgres + store. If any still fails, diagnose and fix within TASK-003 scope; do not weaken tests.
3. No other changes. No git commit/push; do not edit docs/ or CLAUDE.md.
