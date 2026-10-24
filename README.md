# VisionGuard MLOps

Local-first moderation MLOps platform. TASK-001 provides configuration, health
endpoints and a Celery ping task; upload and inference arrive in later tasks.

## Local services

Requires Docker Engine and Docker Compose v2. From the repository root:

```sh
cp .env.example .env
docker compose up -d --build
python scripts/smoke_health.py
docker compose ps
docker compose down
```

All exposed ports bind to `127.0.0.1`. Backend: <http://127.0.0.1:8000>, OpenAPI:
<http://127.0.0.1:8000/docs>, SeaweedFS S3: <http://127.0.0.1:9000>.
The example credentials are local development placeholders. Compose explicitly
sets internal DB/Redis/S3 addresses; other settings come from `.env` or defaults.
The storage-config service generates the SeaweedFS S3 identity from
S3_ACCESS_KEY/S3_SECRET_KEY in a named volume before the store starts.
The bucket-init service retries startup, creates the configured bucket and then exits successfully.
Named volumes preserve data after `docker compose down`.

## Host development

Install uv and use Python 3.15. Run these commands from the repository root;
uv manages the virtual environment in `backend/.venv`:

```sh
uv python install 3.15
uv sync --project backend --frozen
uv run --project backend pytest -q
uv run --project backend ruff check .
uv run --project backend ruff format --check .
uv lock --project backend --check
```

Settings read environment variables (see `.env.example`); host processes do not
automatically load `.env`. Export settings when overriding the localhost defaults.
With dependency services running, start the host API using:

```sh
uv run --project backend uvicorn visionguard.api.main:app --no-access-log
```

`/health` always reports liveness without contacting dependencies. `/ready` runs
Postgres `SELECT 1`, Redis PING and S3 head_bucket using short timeouts, returning
503 with per-service `fail` statuses when unavailable. Errors omit exception
details. Every response echoes a valid `X-Request-ID` or generates a UUID; request
completion logs are JSON. Accepted IDs contain 1–128 ASCII letters, digits, `.`,
`_` or `-`; other values are replaced to keep headers and logs safe.

Worker ping (inside the running Compose stack):

```sh
docker compose exec worker celery -A workers.celery_app:app call visionguard.ping
```
