---
phase: 92-photo-attachments
verified: 2026-06-07T12:31:10Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
---

# Phase 92: Photo Attachments Verification Report

**Phase Goal:** Клиент прикрепляет фото к сообщению; вложения хранятся сервером и отдаются через аутентифицированный IDOR-safe endpoint с защитой от stored XSS.
**Requirements:** ATT-01, ATT-02, ATT-03
**Verified:** 2026-06-07T12:31:10Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Client can upload JPEG/PNG/WebP (up to 5MB) via POST /client/messages/attachments; server validates by magic bytes (not Content-Type), rejects SVG/HTML with 4xx, rejects >5MB with 413 | VERIFIED | `service.create_attachment`: `guess_allowed_mime` on first 261 bytes (never trusts `claimed_content_type`); `_MAX_UPLOAD_BYTES=5*1024*1024` check; `UnsupportedMediaTypeError`/`PayloadTooLargeError` raised. Tests: `test_upload_svg_with_fake_content_type_rejected` (415), `test_upload_six_mb_returns_413` (413), 9 mime-unit tests with real bytes — all pass in 106/106 suite. |
| 2 | Client can retrieve their own attachment via GET /client/messages/attachments/{id}; another client's UUID returns 404 (IDOR-safe); response carries Content-Disposition: attachment and X-Content-Type-Options: nosniff | VERIFIED | `serve_attachment` in service.py calls `get_owned_attachment` (client_id predicate is the IDOR gate); `None` → `NotFoundError` (404, never 403). StreamingResponse with `"Content-Disposition": "attachment"`, `"X-Content-Type-Options": "nosniff"`, `media_type=mime_type` (from DB, never client-derived). Tests: `test_serve_own_attachment_returns_200_with_anti_xss_headers`, `test_serve_other_clients_attachment_returns_404_idor_collapse`, `test_serve_unauthenticated_returns_401`, `test_serve_nonexistent_attachment_returns_404`. |
| 3 | Client can include attachment_id in POST /client/messages; photo appears in thread history | VERIFIED | `send_client_message` accepts `payload.attachment_id`, IDOR-checks via `get_owned_attachment` before inserting, passes `attachment_id` to `insert_message`. `list_thread_history` LEFT JOINs `message_attachments` and builds `MessageAttachmentItem`. End-to-end test: `test_end_to_end_upload_send_list_serve` covers full round-trip (upload → send → list → serve). |

**Score:** 3/3 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/integrations/storage/mime.py` | Magic-byte allowlist guard | VERIFIED | `guess_allowed_mime(head)` → `str\|None`; `ALLOWED_MIMES = frozenset({"image/jpeg","image/png","image/webp"})`; `MAGIC_BYTE_READ_LEN=261`. SVG/HTML/GIF/empty all return None. 9 unit tests with real bytes pass. |
| `apps/backend/app/integrations/storage/types.py` | Storage Protocol | VERIFIED | `@runtime_checkable class Storage(Protocol)` with `put`, `open_stream`, `ensure_bucket` async methods. No aioboto3 types at boundary. |
| `apps/backend/app/integrations/storage/s3.py` | S3Storage adapter | VERIFIED | `class S3Storage` with `put`, `open_stream` (async generator, keeps client open for stream lifetime), `ensure_bucket` (idempotent: head_bucket → create, swallows BucketAlreadyOwnedByYou). Session-as-factory (fresh `async with session.client("s3",...)` per operation). |
| `apps/backend/app/integrations/storage/settings.py` | StorageSettings env_prefix=S3_ | VERIFIED | `class StorageSettings(BaseSettings)` with `env_prefix="S3_"`; `secret_access_key: SecretStr`; dev-safe defaults. |
| `apps/backend/app/integrations/storage/factory.py` | build_storage factory | VERIFIED | `build_storage(settings) -> S3Storage`; no app.modules imports. |
| `apps/backend/alembic/versions/0066_message_attachments.py` | Migration 0066 | VERIFIED | Creates `message_attachments` (id, thread_id FK RESTRICT, client_id FK RESTRICT NOT NULL, mime_type TEXT, object_key TEXT, size_bytes INTEGER, created_at/updated_at). Adds nullable `messages.attachment_id` FK. `down_revision="0065_messaging_messages"`. Reversible: downgrade drops column+FK then drops table. |
| `apps/backend/app/modules/messaging/models.py` | MessageAttachment ORM + Message.attachment_id | VERIFIED | `class MessageAttachment(Base, UUIDPkMixin, TimestampMixin)` with all columns. `Message.attachment_id: Mapped[UUIDType\|None]` replaces "deferred to Phase 92" comment. |
| `apps/backend/app/modules/messaging/router.py` | POST + GET attachment endpoints | VERIFIED | `POST /messages/attachments` (RBAC-04 order: require_client→CSRF→get_storage→get_db; bounded read 5MB+1; 413 guard before service call). `GET /messages/attachments/{attachment_id}` (require_client, no CSRF, returns StreamingResponse directly). |
| `apps/backend/app/modules/messaging/service.py` | create_attachment + serve_attachment | VERIFIED | `create_attachment`: 5-step validation→UUID key→S3 put→insert→audit. `serve_attachment`: get_owned_attachment IDOR check→404-collapse→StreamingResponse with anti-XSS triad. |
| `apps/backend/app/modules/messaging/repository.py` | get_owned_attachment + insert_attachment + list join | VERIFIED | `get_owned_attachment`: raw-SQL WHERE id=:aid AND client_id=:cid. `insert_attachment`: INSERT...RETURNING id. `list_thread_history`: LEFT JOIN message_attachments projecting att_id/att_mime/att_size. |
| `apps/backend/app/modules/messaging/schemas.py` | MessageAttachmentItem + body-OR-attachment | VERIFIED | `class MessageAttachmentItem(ResponseData)` with id/mime_type/size_bytes/url (camelCase). `MessageItem.attachment: MessageAttachmentItem\|None`. `SendMessageRequest.body` now optional; `attachment_id: UUID\|None`; `@model_validator(mode='after')` enforces body-OR-attachment + whitespace guard. |
| `apps/backend/app/main.py` | lifespan storage wiring | VERIFIED | `app.state.storage = build_storage(StorageSettings())` + `await app.state.storage.ensure_bucket()` in `combined_lifespan`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `router.py POST /messages/attachments` | `integrations/storage (get_storage)` | `Depends(get_storage)` in signature | WIRED | `storage: Annotated[Storage, Depends(get_storage)]` confirmed in router; `get_storage` in `app/integrations/storage/__init__.py` reads `request.app.state.storage` (no circular import). |
| `service.create_attachment` | `mime.guess_allowed_mime` | magic-byte call on raw_bytes[:261] | WIRED | Line `validated_mime = guess_allowed_mime(raw_bytes[:MAGIC_BYTE_READ_LEN])` in service.py; claimed_content_type passed but never used for validation. |
| `app/main.py lifespan` | `factory.build_storage` | `app.state.storage = build_storage(StorageSettings())` | WIRED | Confirmed at lines 382-383 of main.py. |
| `serve_attachment` | `repository.get_owned_attachment` | IDOR ownership lookup | WIRED | `row = await repository.get_owned_attachment(session, attachment_id, client_id=client_id)` then `if row is None: raise NotFoundError`. |
| `serve_attachment` | `storage.open_stream` | `StreamingResponse(storage.open_stream(object_key), ...)` | WIRED | object_key read from owned DB row only (T-92-12: no path traversal). StreamingResponse returned directly (FastAPI cannot override headers). |
| `migration 0066` | `0065_messaging_messages` | `down_revision="0065_messaging_messages"` | WIRED | Chain confirmed in migration file. |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `serve_attachment` StreamingResponse | `object_key` from `row["object_key"]` | `repository.get_owned_attachment` → raw-SQL SELECT from `message_attachments` WHERE id AND client_id | Yes — DB row, server-stored object key | FLOWING |
| `list_thread_history` attachment sub-object | `att_id`, `att_mime`, `att_size` from JOIN | LEFT JOIN `message_attachments ma ON ma.id = m.attachment_id` | Yes — real DB join columns | FLOWING |
| `create_attachment` S3 put | `object_key = f"attachments/{uuid4()}"`, `raw_bytes` | Router bounded read from UploadFile | Yes — actual multipart bytes | FLOWING |

---

### Security Invariants Verified

| Invariant | Location | Test Assertion |
|-----------|----------|----------------|
| Magic-byte only (Content-Type never trusted) | `service.create_attachment`: `guess_allowed_mime(raw_bytes[:261])` — `claimed_content_type` argument is passed but never used for validation or S3 ContentType | `test_upload_svg_with_fake_content_type_rejected`: SVG bytes with `Content-Type: image/png` header → 415 |
| JPEG/PNG/WebP allowlist; SVG/GIF/HTML rejected | `mime.py ALLOWED_MIMES = frozenset({"image/jpeg","image/png","image/webp"})` | 9 unit tests with real magic bytes (JPEG SOI, PNG sig, WebP RIFF VP8, SVG text, HTML, GIF, empty) |
| 5MB cap | Router bounded read `file.read(5*1024*1024 + 1)` + service `_MAX_UPLOAD_BYTES` check | `test_upload_six_mb_returns_413`: 6MB → 413 |
| IDOR 404-collapse (never 403) | `get_owned_attachment`: WHERE client_id predicate; None → `NotFoundError` (maps to 404) | `test_serve_other_clients_attachment_returns_404_idor_collapse`: client B → 404, not 403 |
| Content-Disposition: attachment | `StreamingResponse(headers={"Content-Disposition": "attachment", ...})` | `test_serve_own_attachment_returns_200_with_anti_xss_headers`: asserts `"attachment" in response.headers["content-disposition"]` |
| X-Content-Type-Options: nosniff | `StreamingResponse(headers={..., "X-Content-Type-Options": "nosniff"})` | Same test asserts `response.headers["x-content-type-options"] == "nosniff"` |
| Content-Type from stored validated mime (never client-derived) | `StreamingResponse(media_type=mime_type)` where `mime_type = str(row["mime_type"])` from DB | Same test asserts `response.headers["content-type"] == "image/jpeg"` |
| UUID object key (no user filename) | `object_key = f"attachments/{uuid4()}"` — no user input in key | T-92-08: IDOR gate + InMemoryStorage stub proves key is server-generated |
| client_id from principal only (never from body/URL) | `require_client()` → `client.id` passed to service; SendMessageRequest has no client_id field; `extra="forbid"` | T-92-07: `client_id=client.id` in router; test confirms foreign attachment rejected via `get_owned_attachment` |
| Unauthenticated → 401 | `require_client()` as first dependency | `test_serve_unauthenticated_returns_401`: no auth cookie → 401 |
| Send with foreign attachmentId → 404, no message written | `send_client_message` calls `get_owned_attachment` before `insert_message`; raises `NotFoundError` if None | `test_send_client_message_with_foreign_attachment_raises_not_found`: `pytest.raises(NotFoundError)` |

---

### Behavioral Spot-Checks

Full HTTP security suite executed via `uv run pytest tests/messaging/ -q -p no:cacheprovider`:

| Behavior | Test | Result | Status |
|----------|------|--------|--------|
| JPEG upload → 200 + {attachmentId, previewUrl} | `test_serve_own_attachment_returns_200_with_anti_xss_headers` (upload step) | 200 | PASS |
| SVG with fake Content-Type: image/png → 415 | `test_upload_svg_with_fake_content_type_rejected` | 415 | PASS |
| 6MB upload → 413 | `test_upload_six_mb_returns_413` | 413 | PASS |
| Own attachment GET → 200 + anti-XSS header triad | `test_serve_own_attachment_returns_200_with_anti_xss_headers` | 200, headers verified | PASS |
| Client B GET of client A's attachment → 404 | `test_serve_other_clients_attachment_returns_404_idor_collapse` | 404 | PASS |
| Unauthenticated GET → 401 | `test_serve_unauthenticated_returns_401` | 401 | PASS |
| End-to-end upload→send→list→serve round-trip | `test_end_to_end_upload_send_list_serve` | All 4 steps pass | PASS |
| IDOR lookup returns None for non-owner (DB-level) | `test_get_owned_attachment_returns_none_for_non_owner` | None returned | PASS |
| Foreign attachmentId in send → NotFoundError | `test_send_client_message_with_foreign_attachment_raises_not_found` | NotFoundError raised | PASS |

**Full suite result:** 106/106 passed in 25.35s (includes all pre-existing messaging tests from Phase 90/91 — no regressions).

---

### Probe Execution

No explicit `scripts/*/tests/probe-*.sh` probes were declared for Phase 92. Static gates verified below.

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ATT-01 | 92-01, 92-02 | Клиент прикрепляет фото к сообщению (upload) | SATISFIED | POST /client/messages/attachments endpoint fully implemented; `create_attachment` service wired; REQUIREMENTS.md checked `[x]` since 92-01 docs commit. |
| ATT-02 | 92-01, 92-02 | Magic-byte allowlist (JPEG/PNG/WebP) + size cap; Content-Type header NOT trusted | SATISFIED | `mime.py ALLOWED_MIMES`, `guess_allowed_mime`, `_MAX_UPLOAD_BYTES=5MB`; 9 unit tests + service tests with real bytes; REQUIREMENTS.md checked `[x]`. |
| ATT-03 | 92-03 | Authenticated IDOR-safe serve; Content-Disposition: attachment + X-Content-Type-Options: nosniff | SATISFIED | `serve_attachment` + `GET /messages/attachments/{id}` implemented; 7-test HTTP security suite passes; **NOTE: REQUIREMENTS.md still shows `[ ]` for ATT-03** — documentation gap, not an implementation gap. The code, git history (73d76d20), and all tests confirm full implementation. |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/modules/messaging/service.py` | 194 | `TODO Phase 93:` | Info | Explicit phase-referenced forward seam for Telegram bridge. Does NOT trigger debt gate (has "Phase 93" as formal follow-up reference). |

No `TBD`, `FIXME`, or `XXX` markers found in any Phase 92-modified files.

---

### Static Gate Results

| Gate | Result |
|------|--------|
| `uv run pytest tests/messaging/ -q -p no:cacheprovider` | **106/106 PASSED in 25.35s** |
| `uv run mypy --strict app/modules/messaging/ app/integrations/storage/` | **Success: no issues in 13 source files** |
| `uv run lint-imports` | **3 contracts kept, 0 broken** (`integrations must not import modules` — KEPT) |

---

### Human Verification Required

None. All security invariants are mechanically verifiable and confirmed by the automated test suite with real bytes and real DB rows.

---

## Gaps Summary

No gaps found. All three ROADMAP Success Criteria are implemented and verified:

1. Upload validated by magic bytes with correct rejection codes — confirmed by 9 mime unit tests + 5 service tests + 2 HTTP tests.
2. Serve endpoint enforces IDOR 404-collapse + full anti-XSS header triad — confirmed by 7-test HTTP security suite with two real clients.
3. Two-step flow (upload → send with attachmentId → appears in history) — confirmed by end-to-end test + 6 IDOR tests.

**Documentation note (non-blocking):** `REQUIREMENTS.md` line 36 still shows `[ ] ATT-03` instead of `[x] ATT-03`. This is a missing checkbox update — the implementation is complete and the ROADMAP.md, STATE.md, and all commits correctly reflect Phase 92 as complete. The REQUIREMENTS.md update was omitted from the wave-3 docs commit (8003a385 updated only ROADMAP.md and STATE.md).

---

_Verified: 2026-06-07T12:31:10Z_
_Verifier: Claude (gsd-verifier)_
