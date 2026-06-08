---
phase: 92-photo-attachments
plan: "02"
subsystem: messaging/attachments + integrations/storage
tags: [storage, s3, attachments, upload, magic-bytes, idor, audit, tdd]
dependency_graph:
  requires:
    - app.integrations.storage (Storage Protocol, guess_allowed_mime, build_storage) — Plan 01
    - migration-0066 (message_attachments table) — Plan 01
    - MessageAttachment ORM model — Plan 01
  provides:
    - POST /api/v1/client/messages/attachments (multipart upload endpoint)
    - service.create_attachment (5MB cap + magic-byte allowlist + S3 put + DB row + audit)
    - repository.insert_attachment (raw-SQL INSERT...RETURNING id)
    - AttachmentUploadResponse schema (attachmentId/previewUrl camelCase wire)
    - app.state.storage lifespan wiring + get_storage() FastAPI dependency
    - PayloadTooLargeError (413) + UnsupportedMediaTypeError (415) in exceptions.py
  affects:
    - apps/backend/app/main.py
    - apps/backend/app/integrations/storage/__init__.py
    - apps/backend/app/modules/messaging/schemas.py
    - apps/backend/app/modules/messaging/repository.py
    - apps/backend/app/modules/messaging/service.py
    - apps/backend/app/modules/messaging/router.py
    - apps/backend/app/core/exceptions.py
    - apps/backend/pyproject.toml (python-multipart added)
tech_stack:
  added:
    - python-multipart==0.0.32 (required for FastAPI UploadFile/multipart form support)
  patterns:
    - get_storage() dependency in integrations/storage/__init__.py (mirrors get_redis pattern; avoids app.main circular import)
    - Bounded file.read(5MB+1) before service call (P17 — never unbounded await file.read())
    - TDD RED/GREEN cycle for service layer (stub Storage, patched repo/audit)
key_files:
  created:
    - apps/backend/tests/messaging/test_attachment_service.py
  modified:
    - apps/backend/app/main.py (build_storage + ensure_bucket in lifespan)
    - apps/backend/app/integrations/storage/__init__.py (get_storage dep function added)
    - apps/backend/app/modules/messaging/schemas.py (AttachmentUploadResponse added)
    - apps/backend/app/modules/messaging/repository.py (insert_attachment added)
    - apps/backend/app/modules/messaging/service.py (create_attachment added)
    - apps/backend/app/modules/messaging/router.py (POST /messages/attachments added)
    - apps/backend/app/core/exceptions.py (PayloadTooLargeError + UnsupportedMediaTypeError added)
    - apps/backend/pyproject.toml (python-multipart dep)
decisions:
  - "get_storage() placed in app/integrations/storage/__init__.py, not app/main.py — avoids circular import (main→api→messaging.router→main)"
  - "AttachmentUploadResponse uses attachment_id (Python) → attachmentId (wire) via to_camel alias_generator — consistent with plan contract"
  - "python-multipart added as explicit dep (FastAPI requires it for UploadFile; not auto-installed by fastapi)"
  - "Duplicate size cap check in both router (bounded read + 413 guard) and service (PayloadTooLargeError) — defense in depth; router guard prevents buffering, service guard is the authoritative validation layer"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-07"
  tasks_completed: 3
  files_created: 1
  files_modified: 8
---

# Phase 92 Plan 02: Upload Endpoint + Service + Repository + Schema + Lifespan Wiring Summary

**One-liner:** Authenticated multipart upload endpoint with magic-byte validation, 5MB cap, S3 put, IDOR-owned DB row, audit emission, and lifespan storage wiring.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Lifespan storage wiring + ensure_bucket + get_storage dep | `43f4091f` | app/main.py, app/integrations/storage/__init__.py |
| 2 (TDD) | AttachmentUploadResponse + insert_attachment + create_attachment | `2cfbbaa0` (RED), `783e5881` (GREEN) | schemas.py, repository.py, service.py, tests/messaging/test_attachment_service.py, exceptions.py |
| 3 | POST /messages/attachments endpoint | `125f0874` | router.py, pyproject.toml |

## What Was Built

### Lifespan Storage Wiring (`app/main.py` + `app/integrations/storage/__init__.py`)
- `combined_lifespan` now calls `build_storage(StorageSettings())` and stores the adapter at `app.state.storage`
- `await app.state.storage.ensure_bucket()` bootstraps the local-dev S3 bucket on startup (idempotent; no teardown needed — aioboto3 sessions are factories)
- `get_storage(request) -> Storage` dependency function added to `app/integrations/storage/__init__.py` (reads `request.app.state.storage` lazily, mirroring `get_redis` discipline). NOT in `app/main.py` to avoid a circular import chain (`main → api → messaging.router → main`).

### New Error Types (`app/core/exceptions.py`)
- `PayloadTooLargeError` (HTTP 413, code `payload_too_large`) — upload exceeds 5MB cap
- `UnsupportedMediaTypeError` (HTTP 415, code `unsupported_media_type`) — magic-byte allowlist rejection

### Schema (`app/modules/messaging/schemas.py`)
- `AttachmentUploadResponse(ResponseData)`: fields `attachment_id: UUID` → wire alias `attachmentId`, `preview_url: str` → wire alias `previewUrl` via `alias_generator=to_camel` on the base class

### Repository (`app/modules/messaging/repository.py`)
- `insert_attachment(session, *, thread_id, client_id, mime_type, object_key, size_bytes) -> UUID`
- Raw-SQL `text()` INSERT INTO message_attachments ... RETURNING id (D-54-08 discipline)
- Caller-owns-txn; no `session.commit()`

### Service (`app/modules/messaging/service.py`)
- `create_attachment(session, storage, *, client_id, raw_bytes, claimed_content_type) -> AttachmentUploadResponse`
- Step 1: `len(raw_bytes) > 5MB` → `PayloadTooLargeError` (T-92-06)
- Step 2: `guess_allowed_mime(raw_bytes[:261])` → None → `UnsupportedMediaTypeError` (T-92-05 LOCKED; claimed_content_type NEVER trusted)
- Step 3: `get_or_create_thread`
- Step 4: `object_key = f"attachments/{uuid4()}"` (server-generated, no user filename — T-92-08)
- Step 5: `await storage.put(key, raw_bytes, content_type=validated_mime)`
- Step 6: `insert_attachment(...)` with IDOR-owned client_id (T-92-07)
- Step 7: `audit.emit("attachment_uploaded", actor_user_id=None, resource_type="message", ...)` (T-92-09)
- Step 8: returns `AttachmentUploadResponse` with `preview_url = /api/v1/client/messages/attachments/{id}`

### Router Endpoint (`app/modules/messaging/router.py`)
- `POST /api/v1/client/messages/attachments` (operation_id `client_upload_attachment`, tags `Client-Portal`)
- RBAC-04 ordering: `require_client()` → `verify_client_csrf` → `get_storage` / `get_db`
- Bounded read: `raw = await file.read(5*1024*1024 + 1)`; if `len(raw) > 5MB` → 413 BEFORE calling service (P17)
- Calls `service.create_attachment(...)` → `await session.commit()` → `envelope(result)`
- No idempotency wrapper (fresh-object create, not financial mutation)
- No try/except — AppError bubbles to `_app_error_handler`
- Placed before `POST /messages` to respect route ordering; does not conflict with `/messages/read` literal

## Verification Results

All gates green:

| Gate | Result |
|------|--------|
| `uv run pytest tests/messaging/test_attachment_service.py` | 5/5 PASSED |
| `uv run mypy --strict app/main.py app/modules/messaging/` | Success: no issues in 8 source files |
| `uv run ruff check app/modules/messaging/` | All checks passed |
| `uv run python -c "import app.main"` | Success (no output) |
| `uv run lint-imports` | No new violations (pre-existing ignored-import warnings only) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Circular import: get_storage in app/main.py**
- **Found during:** Task 3 implementation
- **Issue:** Plan specified `get_storage` in `app/main.py`. However, `app/modules/messaging/router.py` is loaded via `app.api.router` which is imported by `app/main.py` at module level. Importing `app.main.get_storage` from the router creates a cycle: `main → api → messaging.router → main`.
- **Fix:** Moved `get_storage()` to `app/integrations/storage/__init__.py` — the integration layer has no dependency on `app.modules` or `app.main`, cleanly breaking the cycle. Updated `__all__` and docstring. The `app/main.py` function was removed.
- **Files modified:** `app/integrations/storage/__init__.py`, `app/main.py`, `app/modules/messaging/router.py`
- **Commit:** `125f0874`

**2. [Rule 3 - Blocking] python-multipart missing dependency**
- **Found during:** Task 3 verification (`import app.main`)
- **Issue:** FastAPI's `UploadFile` / multipart form support requires `python-multipart`. This package is NOT auto-installed as a FastAPI dependency and was absent from `pyproject.toml`. At import time, decorating the route with `UploadFile` raises `RuntimeError: Form data requires python-multipart`.
- **Fix:** `uv add "python-multipart>=0.0.9"` — package is well-established (official FastAPI docs dep). Package verified as legitimate (python-multipart on PyPI, widely used).
- **Files modified:** `apps/backend/pyproject.toml`, `apps/backend/uv.lock`
- **Commit:** `125f0874`

## Known Stubs

None — the upload endpoint is fully wired. `previewUrl` points to the serve endpoint (`/api/v1/client/messages/attachments/{id}`) which is implemented in Plan 03. The URL is correct and functional once Plan 03 delivers the serve handler.

## Threat Flags

None — all new surfaces are covered by the plan's threat model (T-92-05 through T-92-09 mitigated as planned).

## Self-Check: PASSED
