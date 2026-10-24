# ADR-003: Media upload validation and metadata stripping

Date: 2026-10-25. Status: accepted (Claude Code, architect).

## Decision
- File type is determined by magic bytes (JPEG/PNG/WebP) and a full Pillow decode. Client `Content-Type` and filename are never trusted and never stored or echoed.
- Stored bytes are the **sanitized re-encode** (EXIF orientation applied, then EXIF/XMP/ICC/text chunks dropped). Original bytes are not kept. `sha256`, `size_bytes`, width/height describe the stored bytes. Re-encoding JPEG is lossy (quality 95); PNG and WebP are re-encoded losslessly where the format allows.
- Limits: `MAX_UPLOAD_BYTES` (stream-checked, 413), `MAX_IMAGE_PIXELS` (default 50,000,000; decompression bomb -> 422), multi-frame/animated images rejected (422) in Phase 1.
- Object key `media/{asset_uuid}.{ext}` generated server-side. No dedupe by hash (sha256 index is non-unique, see TASK-002).
- No endpoint serves image bytes in Phase 1 (safe-preview default for sensitive content).

## Consequences
Hash is of sanitized content, so identical visual uploads from different metadata hash equal. Lossy JPEG re-encode may slightly change pixels; acceptable for moderation inference, documented. Revisit if training-data fidelity matters.
