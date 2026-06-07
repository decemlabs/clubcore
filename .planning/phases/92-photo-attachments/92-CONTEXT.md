# Phase 92: Photo Attachments - Context

**Gathered:** 2026-06-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 92 adds photo attachments to client messages: a server-side validated upload endpoint, an
S3-compatible storage backend behind an `app/integrations/storage/` abstraction, an authenticated
IDOR-safe serve endpoint with stored-XSS guards, and the `message_attachments` table (migration 0066)
wiring `messages.attachment_id`.

Covers requirements ATT-01 (client attaches a photo), ATT-02 (magic-byte allowlist + size cap,
Content-Type header NOT trusted), ATT-03 (authenticated IDOR-safe serve with
`Content-Disposition: attachment` + `X-Content-Type-Options: nosniff`).

**In scope:** `integrations/storage/` seam + `S3Storage` impl (aioboto3), upload endpoint (magic-byte
validation server-side), serve endpoint (authenticated proxy-stream), migration 0066, `POST /messages`
extended to accept `attachmentId`, `MessageItem` attachment sub-object, `filetype` dependency,
local-dev S3-compatible docker service.

**Out of scope:** Telegram photo forwarding (Phase 93), PWA photo picker + full-screen viewer
(Phase 94, PWA-03), EXIF stripping / re-encoding (deferred), orphaned-file cleanup cron (out of scope
per research).

</domain>

<decisions>
## Implementation Decisions

### Storage Backend — S3-compatible from day one (USER OVERRIDE)
- **User chose S3-compatible now** (overriding the research-recommended local filesystem). Backend is
  S3-compatible object storage via the already-pinned `aioboto3 (>=13,<14)`.
- Abstraction: `app/integrations/storage/` protocol (mirrors the email/yookassa/telegram integration
  pattern) with an `S3Storage` implementation. Endpoint, region, bucket, access key, secret are
  env-driven via `Settings` (like YooKassa creds).
- **Upload is server-side validated, NOT presigned PUT:** the client POSTs the file to the backend;
  the backend validates magic-bytes + size, then `put_object` to S3. (Presigned PUT cannot enforce
  the magic-byte allowlist — server-side upload is required for ATT-02.)
- **Serve is an authenticated proxy-stream, NOT presigned GET:** `GET /client/messages/attachments/{id}`
  runs `require_client` + IDOR check, then streams the object from S3 through the backend with the
  anti-XSS headers. (Presigned GET would bypass `require_client` and the IDOR/nosniff guarantees.)
- On-disk/object key: UUID4-based object key (no enumeration); store key + mime + size in DB.
- **Local dev:** add an S3-compatible service to docker-compose (MinIO-compatible / SeaweedFS — any
  S3 endpoint works via env-driven `S3_ENDPOINT_URL`). Bucket auto-created on startup if absent.
  Local creds are dev defaults; live/prod S3 creds are operator-provided (an operator-pending item).

### Upload Validation & Limits (ATT-01, ATT-02)
- MIME validation via the `filetype` lib magic-byte allowlist — **JPEG / PNG / WebP only**. SVG and
  all `text/*` explicitly rejected. The `Content-Type` request header is NOT trusted (read ≤261 bytes).
- Size cap: **5 MB**; larger uploads rejected with 413.
- Two-step flow: `POST /client/messages/attachments` (multipart) → `{attachmentId, previewUrl}`, then
  `POST /client/messages` with `attachmentId`.
- Store image **as-is** (no re-encode / EXIF strip) — rely on magic-byte allowlist + `nosniff` +
  `Content-Disposition: attachment`. Re-encoding deferred.

### Serve Endpoint & Anti-Stored-XSS (ATT-03)
- `GET /client/messages/attachments/{id}` — `require_client`, streams from S3 (FileResponse/StreamingResponse).
- IDOR: ownership via `attachment.client_id == principal.client_id`; **404-collapse** on non-owned
  (never 403 — no existence leak), consistent with MSG-02.
- Anti-XSS headers: `Content-Disposition: attachment` + `X-Content-Type-Options: nosniff`;
  `Content-Type` set from the **stored validated mime**, never from user input.
- `previewUrl` is a relative path to the serve endpoint; the PWA fetches it with credentials (P94).
  (Time-limited presigned URLs deliberately NOT used — auth/IDOR stays server-side.)

### Schema Integration & Scope
- Migration **0066** `message_attachments`: id UUID PK, thread_id FK, client_id FK (IDOR ownership),
  mime_type TEXT, file_path/object_key TEXT, size_bytes INT, created_at TIMESTAMPTZ. Add nullable
  `attachment_id` FK to `messages`.
- `POST /client/messages` accepts optional `attachmentId`; message validity becomes **body OR
  attachment** required (relaxes the Phase 90 empty-body 422 when an attachment is present).
- `MessageItem` gains an attachment sub-object: `{id, mimeType, sizeBytes, url}`.
- New dependency: `filetype >=1.2,<2` (pure-Python magic-byte, no libmagic). `aioboto3` already pinned.
- `attachment_uploaded` audit event already pre-registered in Phase 90 (INFRA-15) — reuse it.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `aioboto3 (>=13,<14)` already pinned in pyproject.toml (mypy override for aioboto3/botocore present).
- `app/integrations/{email,telegram,yookassa}/` — established integration-module pattern to mirror
  for `app/integrations/storage/` (protocol + impl + env-driven config).
- `app/modules/messaging/` — module from Phase 90/91 to extend (models, repository, service, router,
  schemas). `attachment_uploaded` audit pair pre-registered in `audit.py` (Phase 90).
- `app/core/dependencies.py` — `require_client` / `ClientPrincipal` for the serve endpoint auth + IDOR.
- `app/core/config.py` — Settings pattern (YooKassa creds are the analog for env-driven S3 creds).

### Established Patterns
- Caller-owns-transaction; raw-SQL `text()` cross-module reads (D-54-08); camelCase wire via
  `BackendSchemaBase`; 404-collapse on IDOR (MSG-02 precedent).
- DB-first: persist the attachment row + message before publishing any WS `new_message` (P90 CR-02 fix).
- Migrations chain sequentially; latest is 0065 → new is **0066**.
- No existing `UploadFile` endpoint anywhere — file upload handling is novel; use FastAPI `UploadFile`.

### Integration Points
- `messaging/router.py` — add `POST /messages/attachments` + `GET /messages/attachments/{id}`.
- `messaging/service.py` — attachment create/serve service fns calling the storage adapter.
- docker-compose.yml — add S3-compatible local service + env wiring (S3_ENDPOINT_URL, bucket, creds).
- No `.importlinter` change for the messaging module (added P90); `integrations/` is already exempt-ish
  per the integrations contract — verify the storage integration doesn't import modules.

</code_context>

<specifics>
## Specific Ideas

- Magic-byte allowlist via `filetype.guess()` on the first ≤261 bytes; map to a strict
  {image/jpeg, image/png, image/webp} set; reject everything else (incl. image/svg+xml).
- Storage protocol: `put(key, data, content_type) -> None`, `open_stream(key) -> AsyncIterator[bytes]`
  (or `get_object` body), `delete(key)`. `S3Storage` uses aioboto3 session with env-driven endpoint.
- Serve streams via StreamingResponse/FileResponse with explicit headers; never `inline`.
- Bucket bootstrap: on startup (or first use), create the bucket if missing (idempotent) for local dev.
- LOCKED INVARIANTS (research P7/P8/P17): magic-byte allowlist is the only ground truth; SVG banned;
  Content-Disposition attachment + nosniff on serve; 5MB cap; UUID keys; IDOR ownership 404-collapse.

</specifics>

<deferred>
## Deferred Ideas

- Telegram photo forwarding (client photo → staff Telegram) — Phase 93.
- PWA photo picker (`<input capture>`) + full-screen viewer — Phase 94 (PWA-03).
- EXIF stripping / image re-encoding — deferred (store as-is in v2.5).
- Orphaned-file cleanup cron — out of scope (research).
- Presigned PUT/GET URLs — deliberately not used (server-side validation + auth/IDOR proxy chosen).
- Live/prod S3 credentials provisioning — operator-pending (env-driven; local dev uses a dev S3 service).

</deferred>
