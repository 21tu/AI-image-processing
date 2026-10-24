# TASK-003 — Secure media upload, MIME sniffing, decoding, SHA-256, S3 adapter, API

Read CLAUDE.md, docs/architecture.md, ADR-002, ADR-003 (docs/decisions/). Python 3.15 / uv. Postgres 127.0.0.1:5432 and the S3-compatible store 127.0.0.1:9000 (keys visionguard-local / local-dev-only, bucket `visionguard`) are running for you. Docker is not available to you.

## Goal
`POST /api/v1/media` and `GET /api/v1/media/{id}` work end to end: validated, sanitized image stored in object storage, metadata persisted in `media_assets`.

## In scope
1. Dependencies via `uv add` (pinned, uv.lock updated): Pillow, python-multipart. Verify 3.15 wheels; report versions.
2. `visionguard.storage`: `ObjectStorage` Protocol (`put_bytes(key, data, content_type)`, `delete(key)`, `exists(key)`), `S3ObjectStorage` (boto3, path-style, timeouts, same config as /ready), in-memory `FakeObjectStorage` for tests. FastAPI dependency `get_storage`.
3. `visionguard.media`: pure functions, no FastAPI/DB imports: `sniff_mime(head: bytes)`, `sanitize_image(data: bytes, *, max_pixels) -> SanitizedImage(data, mime, ext, width, height, sha256)`; custom exceptions `UnsupportedMediaType`, `InvalidImage`, `ImageTooLarge`. Follow ADR-003 exactly (EXIF transpose then strip all metadata; reject multi-frame; set Pillow MAX_IMAGE_PIXELS handling safely; treat DecompressionBombWarning as error).
4. `visionguard.db` session dependency `get_session` (request-scoped, commit/rollback) usable with dependency overrides in tests.
5. API `api/routes/media.py` under `/api/v1`:
   - `POST /media` multipart field `file`. Read the stream in chunks, abort with 413 once > `MAX_UPLOAD_BYTES` (also reject early on a too-large Content-Length). Missing/empty file -> 400 `missing_file`... use the existing structured error body `{"error":{"code","message","request_id"}}`. Codes: 413 `payload_too_large`, 415 `unsupported_media_type`, 422 `invalid_image`. Success: 201 `MediaAssetResponse` {id, mime_type, size_bytes, width, height, sha256, validation_status, created_at}. Order: validate -> put object -> insert row (status VALID) -> commit; if the DB step fails, best-effort delete the object and return structured 500. Invalid input creates NO object and NO row.
   - `GET /media/{id}`: 200 same schema; 404 `not_found` (structured); non-UUID -> 422 `validation_error`.
   - Never echo client filename/content-type, exception text, or object key in responses or logs (log asset id, sha256, size, mime only).
   - Response models defined in `api/schemas/media.py`; OpenAPI must show both routes.
6. Config: add `max_image_pixels` (default 50_000_000) to Settings, `.env.example`, compose env passthrough.
7. `scripts/smoke_upload.py` (stdlib + Pillow-free: generate a tiny PNG/JPEG by bytes or via Pillow from the backend env -- document) uploads a valid image, fetches metadata, uploads a text file renamed `.png` and expects 415/422. README section.

## Tests (write first, see them fail)
- Unit (no DB): sniff for each format and for spoofed content (text as .png, PNG header + garbage, JPEG with trailing ZIP/HTML polyglot -> either sanitized re-encode with trailer dropped or rejection; assert trailer absent from output), EXIF GPS/XMP/ICC removed in output (assert via Pillow on output and raw-bytes absence of marker strings), orientation applied, truncated image rejected, pixel-bomb rejected, animated GIF/WebP/APNG rejected, sha256 equals hashlib of returned bytes, max sizes.
- API (real Postgres test DB + FakeObjectStorage via dependency overrides): happy path per format, DB row matches response and stored object bytes hash, oversize 413 without partial row/object, wrong type 415, corrupt 422, no filename leakage in response/logs (caplog), DB failure after put -> object deleted, GET 404/422, request-id header present.
- One `s3`-marker integration test against the real store at 127.0.0.1:9000 (put/exists/delete roundtrip). Fails loudly if unreachable unless `SKIP_S3_TESTS=1`.
- Existing 60 tests keep passing.

## Out of scope
Inference, Celery, outbox, auth, serving image bytes, thumbnails, dedupe, video, virus scanning.

## Constraints
Pinned deps, no secrets, no git commit/push, do not edit CLAUDE.md or docs/, caches outside repo or in .venv, use 127.0.0.1 not localhost.

## Verification (report real outputs)
`uv run --project backend pytest -q`, `ruff check .`, `ruff format --check .`, `uv lock --check`, `alembic check`. Start the app with uvicorn against the running Postgres/store and run `scripts/smoke_upload.py` if feasible.
