---
phase: 92-photo-attachments
plan: "01"
subsystem: integrations/storage + messaging
tags: [storage, s3, attachments, migration, docker, filetype, aioboto3]
dependency_graph:
  requires: []
  provides:
    - app.integrations.storage (Storage Protocol, StorageSettings, guess_allowed_mime, build_storage)
    - migration-0066 (message_attachments table + messages.attachment_id)
    - MessageAttachment ORM model
    - docker S3 service (SeaweedFS on port 8333)
  affects:
    - apps/backend/app/modules/messaging/models.py
    - apps/backend/docker-compose.yml
    - apps/backend/pyproject.toml
tech_stack:
  added:
    - filetype==1.2.0 (magic-byte MIME detection; no libmagic dependency)
    - chrislusf/seaweedfs:3.84 (S3-compatible local dev object storage)
  patterns:
    - Storage Protocol (typing.Protocol, runtime_checkable) — same boundary isolation as Email/YooKassa integrations
    - StorageSettings standalone BaseSettings (env_prefix=S3_) — mirrors YooKassaSettings discipline (D-47-08)
    - aioboto3 session-as-factory (open fresh client per operation) — mirrors EmailClient discipline (D-42-01/02)
    - Magic-byte-only MIME allowlist (filetype.guess, 261-byte read) — T-92-01 LOCKED INVARIANT
key_files:
  created:
    - apps/backend/app/integrations/storage/__init__.py
    - apps/backend/app/integrations/storage/types.py
    - apps/backend/app/integrations/storage/settings.py
    - apps/backend/app/integrations/storage/mime.py
    - apps/backend/app/integrations/storage/s3.py
    - apps/backend/app/integrations/storage/factory.py
    - apps/backend/alembic/versions/0066_message_attachments.py
    - apps/backend/docker/seaweedfs-s3.json
    - apps/backend/tests/messaging/test_attachment_mime.py
  modified:
    - apps/backend/pyproject.toml (filetype dep + filetype.* mypy override)
    - apps/backend/app/modules/messaging/models.py (MessageAttachment + Message.attachment_id)
    - apps/backend/docker-compose.yml (SeaweedFS S3 service + S3_* env vars on backend)
    - apps/backend/.env.example (S3_* env var documentation)
decisions:
  - "Storage Protocol uses typing.Protocol + runtime_checkable to allow test doubles without aioboto3"
  - "open_stream keeps aioboto3 client context open for iterator lifetime (streaming correctness)"
  - "ensure_bucket is head_bucket-first + swallows BucketAlreadyOwnedByYou for idempotency"
  - "SeaweedFS 3.84 chosen over MinIO (MinIO Community archived/unmaintained per research)"
  - "dev-safe defaults in StorageSettings so fresh clone boots without S3 config"
  - "WebP MAGIC requires RIFF....WEBPVP8  (16 bytes) not RIFF....WEBP (12 bytes) for filetype detection"
metrics:
  duration: "~30 minutes"
  completed: "2026-06-07"
  tasks_completed: 3
  files_created: 9
  files_modified: 4
---

# Phase 92 Plan 01: Storage Seam + MIME Guard + Schema Foundation Summary

**One-liner:** S3-compatible storage adapter (aioboto3 + StorageSettings + magic-byte MIME guard) with migration 0066 message_attachments table and SeaweedFS local dev S3 service.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Storage settings + protocol + MIME guard (TDD) | `20b9b5e0` | integrations/storage/{__init__,types,settings,mime}.py + tests/messaging/test_attachment_mime.py |
| 2 | S3Storage adapter + factory | `98cc34d5` | integrations/storage/{s3,factory}.py |
| 3 | Migration 0066 + MessageAttachment ORM + docker S3 | `631f4ab6` | alembic/versions/0066_message_attachments.py + messaging/models.py + docker-compose.yml |

## What Was Built

### Storage Integration Package (`app/integrations/storage/`)
- **`types.py`**: `Storage` Protocol with `put()`, `open_stream()`, `ensure_bucket()` — async methods only; no aioboto3/botocore types at boundary
- **`settings.py`**: `StorageSettings(BaseSettings)` with `env_prefix='S3_'`; dev-safe defaults for SeaweedFS; `SecretStr` for access keys (T-92-02 mitigation)
- **`mime.py`**: `guess_allowed_mime(head: bytes) -> str | None`; reads ≤261 bytes via filetype.guess; allowlist={image/jpeg, image/png, image/webp}; SVG/GIF/text/* all return None; Content-Type header never consulted (T-92-01 LOCKED INVARIANT)
- **`s3.py`**: `S3Storage` class implementing the Storage protocol via aioboto3; session-as-factory pattern (fresh `async with session.client("s3", ...)` per operation); `open_stream` is an async generator that keeps client open for stream lifetime; `ensure_bucket` is idempotent
- **`factory.py`**: `build_storage(settings) -> S3Storage`; sync construction; no boot probe; no caching

### Database Schema (migration 0066)
- New table `message_attachments`: `id UUID PK`, `thread_id UUID NOT NULL FK→message_threads.id RESTRICT`, `client_id UUID NOT NULL FK→clients.id RESTRICT` (IDOR ownership anchor per T-92-03), `mime_type TEXT NOT NULL`, `object_key TEXT NOT NULL`, `size_bytes INTEGER NOT NULL`, `created_at/updated_at TIMESTAMPTZ`
- New column `messages.attachment_id UUID NULL FK→message_attachments.id RESTRICT`
- Reversible: downgrade drops the column + FK then drops the table

### ORM Models
- `MessageAttachment(Base, UUIDPkMixin, TimestampMixin)` added to `messaging/models.py`
- `Message.attachment_id: Mapped[UUIDType | None]` replaces the "deferred to Phase 92" comment

### Docker S3 Service
- `chrislusf/seaweedfs:3.84` in `server -s3 -s3.config=/etc/seaweedfs/s3.json` mode
- Port 8333; dev-default credentials `dev-access-key` / `dev-secret-key`
- `docker/seaweedfs-s3.json` IAM identity config
- Backend service gets `S3_ENDPOINT_URL=http://s3:8333` + all four S3_* vars
- `backend` depends_on `s3: service_healthy`

## Verification Results

All gates green:

| Gate | Result |
|------|--------|
| `uv run pytest tests/messaging/test_attachment_mime.py` | 9/9 PASSED |
| `uv run mypy --strict app/integrations/storage/ app/modules/messaging/models.py` | Success: no issues in 7 source files |
| `uv run ruff check app/integrations/storage/ app/modules/messaging/` | All checks passed |
| `uv run lint-imports` | 3 kept, 0 broken |
| `alembic upgrade → downgrade -1 → upgrade head` | Round-trip clean |
| `docker compose config -q` | No output (valid) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] WebP magic bytes in test required VP8 chunk marker**
- **Found during:** Task 1 GREEN phase
- **Issue:** Initial test used `RIFF....WEBP` (12 bytes); filetype requires `RIFF....WEBPVP8 ` (16 bytes) to detect WebP
- **Fix:** Corrected WEBP_MAGIC constant in test to `b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 245`
- **Files modified:** `tests/messaging/test_attachment_mime.py`
- **Commit:** included in `test(92-01): add failing tests for magic-byte MIME guard`

**2. [Rule 1 - Bug] Unused type: ignore comments in mime.py and s3.py**
- **Found during:** mypy strict check
- **Issue:** `# type: ignore[import-untyped]` and `# type: ignore[union-attr]` were unnecessary because pyproject.toml already has the mypy override for filetype/aioboto3/botocore
- **Fix:** Removed unused ignore comments; refactored s3.py ensure_bucket dict access to avoid any mypy concerns
- **Commit:** included in feat(92-01) commits

**3. [Rule 1 - Bug] Unused `aioboto3` and `StorageSettings` imports in s3.py**
- **Found during:** ruff check
- **Issue:** s3.py imported aioboto3 directly (session is created in factory.py) and StorageSettings (only needed in factory.py)
- **Fix:** Removed both unused imports; factory.py correctly imports aioboto3 + StorageSettings
- **Commit:** included in feat(92-01): migration 0066 commit

## Known Stubs

None — this plan creates infrastructure only (no HTTP endpoints). No stubs that affect achievability of plan goal.

## Threat Flags

None — all surfaces in this plan are covered by the plan's threat model (T-92-01 through T-92-04).

## Self-Check: PASSED
