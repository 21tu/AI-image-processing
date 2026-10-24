# ADR-001: S3-compatible local storage backend

Date: 2026-10-25. Status: accepted (Claude Code, architect).

## Context
`docker compose up` with `minio/minio:RELEASE.2025-04-22T22-12-26Z` failed on this machine: `pull access denied for minio/minio` (also `minio/minio:latest`). `quay.io/minio/*` returned `unauthorized`. `bitnami/minio` manifest not found. `chrislusf/seaweedfs:latest` pulled successfully. (Evidence: docker pull outputs, 2026-10-25.)

## Decision
Use SeaweedFS (single container, S3 API enabled) as the local S3-compatible store. The application only speaks the S3 API via boto3 (`S3_ENDPOINT_URL`), so the backend is swappable. Pin an explicit SeaweedFS version tag (not `latest`). Bucket creation is done by a one-shot init service that reuses the backend image (boto3) rather than an `mc` image.

## Consequences
- Compose service renamed `minio` -> `objectstore`; no MinIO console.
- If MinIO images become available again, only compose/env change.
- Unverified: SeaweedFS behaviour parity for presigned URLs/multipart (not needed in Phase 1).
