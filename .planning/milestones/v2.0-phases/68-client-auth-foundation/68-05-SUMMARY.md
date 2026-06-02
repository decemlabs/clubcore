---
phase: 68-client-auth-foundation
plan: "05"
subsystem: backend/client-auth
tags: [client-auth, otp, session, cookies, fastapi, pydantic, openapi]
dependency_graph:
  requires: [68-03, 68-04]
  provides: [client-auth-http-surface]
  affects: [app/api/v1/router.py, app/main.py]
tech_stack:
  added: []
  patterns:
    - ResponseEnvelope + envelope() for all 6 handlers
    - RBAC-04 dep ordering (require_client before verify_client_csrf)
    - Composition-root slot pattern for client loader and OTP sender
    - inline PHONE_REGEX to respect importlinter modules-cannot-import-each-other
key_files:
  created:
    - apps/backend/app/modules/client_auth/schemas.py
    - apps/backend/app/modules/client_auth/router.py
  modified:
    - apps/backend/app/api/v1/router.py
    - apps/backend/app/main.py
decisions:
  - "D-05: ClientMeResponse exposes core identity only (8 fields: id/phone/email/first_name/last_name/middle_name/birthday/gender)"
  - "D-04: ClientMePatchRequest accepts email only"
  - "D-08: register_client_loader(load_client_by_id) wired in create_app()"
  - "D-01: register_client_otp_sender telegram DM closure wired in create_app()"
  - "Dev-68-05-01: PHONE_REGEX inlined in schemas.py (not imported from clients.schemas) to satisfy importlinter"
metrics:
  duration: "~4m"
  completed: "2026-05-29"
  tasks: 2
  files: 4
---

# Phase 68 Plan 05: Client Auth HTTP Surface Summary

Client auth HTTP surface exposed via Pydantic v2 schemas + 6-handler FastAPI router mounted
under `/api/v1/client`, with composition-root wiring of `register_client_loader` and the real
Telegram DM OTP sender in `create_app()`.

## What Was Built

**schemas.py** — four Pydantic v2 models extending BackendSchemaBase (camelCase wire):
- `ClientOtpRequestBody` — E.164 phone (CAUTH-03)
- `ClientOtpVerifyBody` — E.164 phone + 6-digit code
- `ClientMeResponse` — core identity only: id/phone/email/first_name/last_name/middle_name/birthday/gender (D-05)
- `ClientMePatchRequest` — email-only (D-04)

**router.py** — 6 handlers under `APIRouter(tags=["Client"])`:
1. `POST /otp/request` (202, public) — anti-oracle fixed response (T-68-22/CAUTH-02)
2. `POST /otp/verify` (public) — issues cc_client_* session cookies
3. `POST /session/refresh` — rotates refresh token, reissues cookies
4. `POST /session/logout` — RBAC-04 dep order: require_client BEFORE verify_client_csrf (T-68-25)
5. `GET /me` — core identity response
6. `PATCH /me` — email-only update, 409 on duplicate (D-06)

**api/v1/router.py** — `client_auth_router` mounted at prefix `/client` before `/_internal`.

**main.py** — composition root additions:
- `register_client_loader(load_client_by_id)` — D-08 client principal slot
- `register_client_otp_sender(_send_client_otp_dm)` — D-01 real Telegram DM sender via `build_bot()`
- `"client_otp_request"` and `"client_otp_verify"` added to `PUBLIC_ENDPOINT_OPERATION_IDS`
- `"Client"` tag added to `OPENAPI_TAGS`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Inlined PHONE_REGEX to satisfy importlinter**
- **Found during:** Task 1 verification (lint-imports)
- **Issue:** `schemas.py` imported `PHONE_REGEX` from `app.modules.clients.schemas`, violating the `modules cannot import each other` importlinter contract
- **Fix:** Declared `_PHONE_REGEX: str = r"^\+[1-9]\d{1,14}$"` locally in `client_auth/schemas.py` with a comment noting it mirrors clients/schemas.py and must be kept in sync
- **Files modified:** `apps/backend/app/modules/client_auth/schemas.py`
- **Commit:** included in 5d53cc00

## Self-Check

### Commits exist
- 37ab8fec — feat(68-05): add client auth schemas + 6-handler router
- 5d53cc00 — feat(68-05): mount /client router + register client loader + mark OTP ops public

### Files exist
- apps/backend/app/modules/client_auth/schemas.py
- apps/backend/app/modules/client_auth/router.py
- apps/backend/app/api/v1/router.py (modified)
- apps/backend/app/main.py (modified)

### Verifications passed
- `uv run mypy --strict app/modules/client_auth/ app/main.py app/api/v1/router.py` — 0 issues
- `uv run ruff check` — all passed
- `uv run lint-imports` — 3 contracts kept, 0 broken
- `create_app()` boots; `/api/v1/client/me`, `/api/v1/client/otp/request` paths confirmed present
- `register_client_loader` grep confirms wiring
- `register_client_otp_sender` grep confirms wiring
- `PUBLIC_ENDPOINT_OPERATION_IDS` contains `client_otp_request` and `client_otp_verify`

## Self-Check: PASSED
