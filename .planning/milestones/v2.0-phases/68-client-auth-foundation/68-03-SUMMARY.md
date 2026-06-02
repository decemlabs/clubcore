---
phase: 68-client-auth-foundation
plan: "03"
subsystem: backend-client-auth
tags: [client-auth, composition-root, principal, csrf, security]
dependency_graph:
  requires: [68-02]
  provides: [ClientPrincipal, register_client_loader, get_current_client, require_client, verify_client_csrf, load_client_by_id]
  affects: [app.core.dependencies, app.modules.clients.service]
tech_stack:
  added: []
  patterns: [composition-root-loader-slot, protocol-structural-typing, double-submit-csrf]
key_files:
  created: []
  modified:
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/modules/clients/service.py
decisions:
  - "ClientPrincipal Protocol has no role field — clients have no RBAC role (D-07 / CISO-01)"
  - "get_current_client reads cc_client_access and routes through decode_client_token — staff tokens rejected at aud assertion (CISO-02)"
  - "verify_client_csrf reads clubcore_client_csrf (not clubcore_csrf) with secrets.compare_digest (T-68-12)"
  - "load_client_by_id filters deleted_at IS NULL — soft-deleted clients yield None (T-68-13)"
  - "permissions.py byte-unchanged; no Role.CLIENT added (CISO-01)"
metrics:
  duration: "~4 minutes"
  completed: "2026-05-29T17:09:14Z"
  tasks_completed: 2
  files_changed: 2
---

# Phase 68 Plan 03: Client Principal Composition Root Summary

Parallel client auth composition root: `ClientPrincipal` Protocol + `require_client()` + `load_client_by_id` — isolated from staff RBAC with `aud:"client"` token discrimination and separate CSRF cookie.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add load_client_by_id to clients/service.py | e119d775 | apps/backend/app/modules/clients/service.py |
| 2 | Add ClientPrincipal, loader slot, get_current_client, require_client, verify_client_csrf | ddea034a | apps/backend/app/core/dependencies.py |

## What Was Built

### Task 1: `load_client_by_id` in `clients/service.py`

Added `async def load_client_by_id(session: AsyncSession, client_id: UUID) -> Client | None` — the composition-root loader for `require_client()`. Filters `Client.deleted_at.is_(None)` so soft-deleted (revoked) members cannot authenticate (T-68-13 mitigation). Uses explicit `result: Client | None` annotation for mypy `--strict` compliance (mirrors `resolve_client_by_telegram_user_id` pattern).

### Task 2: Client auth composition root in `dependencies.py`

Five new symbols added at the end of the file:

- **`ClientPrincipal(Protocol)`** — structural type with `id: UUID`, `phone: str`, `email: str | None`. No `role` field (D-07 / CISO-01). `app.modules.clients.models.Client` satisfies it structurally.
- **`ClientLoader` type alias + `_client_loader` slot + `register_client_loader()`** — mirrors `UserLoader` / `_user_loader` / `register_user_loader` exactly (D-08 composition-root pattern). Slot is idempotent — test stubs can inject a replacement.
- **`get_current_client(request, session) -> ClientPrincipal`** — reads `cc_client_access` cookie → `decode_client_token(token)` (asserts `aud=="client"`) → `_client_loader(session, uid)`. CISO-02: staff tokens have no `aud` claim, so `MissingRequiredClaimError` inside PyJWT → `invalid_token` 401. Fail-closed on missing loader slot (T-68-14: `client_loader_not_registered`).
- **`require_client() -> Callable[..., Awaitable[ClientPrincipal]]`** — factory returning `_checker` closure over `get_current_client`. No RBAC gate (clients have no role). Mirrors `require_authenticated()`.
- **`verify_client_csrf(request, session) -> None`** — double-submit CSRF for client endpoints; reads `clubcore_client_csrf` cookie (distinct from staff `clubcore_csrf`), compares with `x-csrf-token` header using `secrets.compare_digest` (constant-time, T-68-12). Short-circuits safe HTTP methods.

The `decode_client_token` import was added to the existing `from app.core.security import ...` line.

## Verification Results

- `uv run mypy --strict app/core/dependencies.py app/modules/clients/service.py` — exits 0
- `uv run lint-imports` — exits 0 (3 contracts KEPT)
- `git diff --quiet app/core/permissions.py` — clean (byte-unchanged)
- `grep Role.CLIENT app/core/permissions.py` — no matches
- `grep -q "def require_client" app/core/dependencies.py` — FOUND
- `grep -q "def verify_client_csrf" app/core/dependencies.py` — FOUND
- `grep -q "clubcore_client_csrf" app/core/dependencies.py` — FOUND

## Deviations from Plan

None — plan executed exactly as written. The `result: Client | None` explicit annotation was needed for mypy `--strict` no-any-return compliance (auto-fix Rule 1, trivial — same pattern already used in the file at `resolve_client_by_telegram_user_id`).

## Threat Mitigations Implemented

| Threat ID | Mitigation |
|-----------|-----------|
| T-68-10 (Spoofing: staff token on client endpoint) | `get_current_client` routes through `decode_client_token` which requires `aud=="client"` — staff tokens have no `aud` → `invalid_token` 401 (CISO-02) |
| T-68-11 (Elevation: Role.CLIENT leaking into staff RBAC) | `ClientPrincipal` has no `role`; `permissions.py` byte-unchanged; no `Role.CLIENT` anywhere |
| T-68-12 (CSRF on PATCH /me + logout) | `verify_client_csrf` double-submit against `clubcore_client_csrf` with `secrets.compare_digest` |
| T-68-13 (Soft-deleted client authenticating) | `load_client_by_id` filters `deleted_at IS NULL` → revoked member yields None → 401 |
| T-68-14 (Loader slot unset in production) | `get_current_client` raises `InvalidAccessToken("client_loader_not_registered")` fail-closed |

## Self-Check: PASSED

- `apps/backend/app/modules/clients/service.py` — modified, commit e119d775 verified
- `apps/backend/app/core/dependencies.py` — modified, commit ddea034a verified
- `mypy --strict` on both files — 0 errors
- `lint-imports` — 0 broken contracts
- `permissions.py` — byte-unchanged
