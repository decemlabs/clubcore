---
phase: 43-multi-user-admin-module
plan: 07b
subsystem: backend/tests/integration/users
tags: [phase-43, users, test-fixtures, conftest, wave-3]
requires:
  - users-module Wave 1+2 (43-01..43-06) — User ORM lifecycle columns, users router, services
provides:
  - shared fixture surface for Wave 4 plans 43-08, 43-09, 43-10, 43-11, 43-12
affects:
  - apps/backend/tests/integration/users/ (new directory)
tech_added: []
patterns:
  - RecordingEmailDispatcher (test-only) satisfies Phase 41 EmailDispatcher Protocol
  - Slot-replacement via register_email_dispatcher() + restore-on-teardown
key_files_created:
  - apps/backend/tests/integration/users/__init__.py
  - apps/backend/tests/integration/users/conftest.py
key_files_modified: []
decisions:
  - "Wave 3 single-owner conftest.py eliminates the parallel-write race the checker flagged for Wave 4 plans"
  - "Test-only RecordingEmailDispatcher class registered via register_email_dispatcher() — prod SandboxEmailClient does not capture envelopes"
  - "Deactivated user state encoded as status='active' + is_active=False + deactivated_at=now() per migration 0030 CHECK constraint (NOT status='deactivated' as the plan text suggested)"
metrics:
  duration_minutes: 12
  tasks_completed: 1
  files_created: 2
  files_modified: 0
  function_count: 25
  fixture_count: 17
  commit: 02d6e24
completed: "2026-05-19T15:04:36Z"
---

# Phase 43 Plan 07b: Shared Test Fixtures for users-module Integration Tests Summary

**One-liner:** Single-owner `tests/integration/users/conftest.py` lands 17 shared fixtures (authed clients, seeded users in every lifecycle state, recording email dispatcher, refresh-token 4-case clients) so Wave 4 plans 43-08..43-12 can execute in parallel without race-writing the conftest.

## What Was Built

Two files at `apps/backend/tests/integration/users/`:

1. `__init__.py` — empty package marker (pytest treats the subdir as a package; the parent `integration/` directory already has its own `__init__.py` convention).

2. `conftest.py` — 25 function/method definitions (helpers + fixtures + recording dispatcher methods). Mirrors `tests/integration/clients/conftest.py` structurally, then extends with USERS-specific surface.

### Fixtures Exported (17 total)

**A. Core authed clients (mirrors `clients/conftest.py`):**

| Name | Type | Consumers |
|------|------|-----------|
| `redis_clean` | `Redis` | every fixture (depended-on for ordering) |
| `seeded_owner` | `User` | `authed_client_owner`, `single_active_owner_id` |
| `seeded_reception` | `User` | `authed_client_reception` |
| `_client_app_overrides` | `FastAPI` (yields) | every `authed_client_*` + every `refresh_client_*` |
| `authed_client_owner` | `AsyncClient` | 43-08, 43-09, 43-11 |
| `authed_client_reception` | `AsyncClient` | 43-09 (RBAC denial assertions) |

**B. Owner-introspection (43-09):**

| Name | Type | Consumers |
|------|------|-----------|
| `current_owner_user_id` | `UUID` | 43-09 (self-guard test — POST `/users/{id}/deactivate` with own id → 409) |
| `single_active_owner_id` | `UUID` | 43-09 (last-owner guard — deactivates extras, returns the pinned survivor's id) |

**C. Active-existing email (43-08):**

| Name | Type | Consumers |
|------|------|-----------|
| `seeded_active_reception_email` | `str` | 43-08 (duplicate-active 409 assertion) |

**D. Deactivated / soft-deleted users (43-09 / 43-10 / 43-12):**

| Name | Type | Consumers |
|------|------|-----------|
| `deactivated_user` | `User` | 43-09 (reactivate happy path) |
| `deactivated_user_id` | `UUID` | 43-12 (refresh_failed audit-row assertion) |
| `soft_deleted_user` | `User` | 43-12 anti-oracle parity |

**E. Session-pair fixtures (43-10):**

| Name | Type | Consumers |
|------|------|-----------|
| `fresh_authed_reception_user_id` | `UUID` | 43-10 (deactivate-then-refresh-break — primary id) |
| `fresh_authed_reception_client` | `AsyncClient` | 43-10 (paired client) |
| `fresh_authed_reception_user_id_2` | `UUID` | 43-10 (soft-delete branch — secondary id) |
| `fresh_authed_reception_client_2` | `AsyncClient` | 43-10 (paired client) |

**F. Sandbox email (43-11):**

| Name | Type | Consumers |
|------|------|-----------|
| `sandbox_email_client` | `RecordingEmailDispatcher` | 43-11 (sent_emails capture assertion) |

**G. Refresh-token 4-case (43-12 anti-oracle):**

| Name | Type | Consumers |
|------|------|-----------|
| `refresh_client_active` | `AsyncClient` | 43-12 (200 baseline) |
| `refresh_client_deactivated` | `AsyncClient` | 43-12 (401 case 1) |
| `refresh_client_soft_deleted` | `AsyncClient` | 43-12 (401 case 2) |
| `refresh_client_unknown_token` | `AsyncClient` | 43-12 (401 case 3 — unknown token) |

### Helpers Re-exported

- `_seed_user(db_session, *, role, email, password, full_name, status, is_active, deleted_at, deactivated_at, email_verified) -> User` — extended with Phase 43 lifecycle columns so a single helper produces every variant the fixtures need. `password=None` is accepted (writes NULL password_hash) for future invited-but-unaccepted fixtures.
- `_login(client, *, email, password) -> None` — POSTs `/api/v1/auth/login`, asserts 200.
- `_csrf_headers(client) -> dict[str, str]` — returns `{"X-CSRF-Token": <sportzal_csrf cookie value>}` with `or ""` coercion to satisfy mypy strict (httpx `cookies.get()` returns `str | None`).
- `RecordingEmailDispatcher` (class) — test-only EmailDispatcher Protocol impl; appends every call to `self.sent_emails: list[dict[str, Any]]`.

## SandboxEmailClient Resolution Path (43-11 spec follow-up)

**Resolution:** The `sandbox_email_client` fixture does NOT return an instance of the production `app.integrations.email.client.SandboxEmailClient` class. That class is a no-op stub (lines 174–194) — it logs the envelope at INFO and returns an `EmailSendResult` with a `sandbox-<uuid>` provider id, but it does NOT expose any `sent_emails` / `envelopes` capture buffer.

Instead the fixture creates a `RecordingEmailDispatcher` (defined locally in this conftest.py) that satisfies the Phase 41 D-41-24 `EmailDispatcher` Protocol (`async __call__(*, template_id, to, audit_correlation_id, **template_vars) -> None`) and registers it via `app.core.dependencies.register_email_dispatcher`. The prior dispatcher (typically `enqueue_email_dispatch` per the prod wiring in `app/main.py:create_app`) is restored on teardown.

**Captured envelope shape:** `dict[str, Any]` with keys `template_id`, `to`, `audit_correlation_id`, and every `**template_vars` kwarg the service emits at enqueue time. For `USER_INVITATION_EMAIL` this means `subject`, `html`, `text`, `full_name`, `role_ru`, `invitation_url`, `expires_at_human` — the keys 43-11 asserts on (`email["to"]`, `email["template_id"]`, `email["subject"]`, `email["text"]`).

**Why the deviation from the plan text:** the plan instructed "pull the SandboxEmailClient instance from app.state / dependency overrides" with reference to Phase 42 plan 7 / 11, but inspection of `app/integrations/email/client.py:174` and `app/main.py` showed (a) the prod `SandboxEmailClient` has no capture API, and (b) no `app.state.email_client` attribute is set — the dispatcher is exclusively wired via the module-level `_email_dispatcher` slot on `app.core.dependencies`. Replacing that slot with a recorder is the only path that satisfies the 43-11 assertion shape.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Plan-text `status='deactivated'` would fail the migration-0030 CHECK constraint**

- **Found during:** Task 1 (`_seed_user` extension)
- **Issue:** The plan instructed setting `status='deactivated'` on the `deactivated_user` fixture. The actual `User.status` column is a `Literal["active", "pending_invitation"]` SQLAlchemy `Enum` (`app/core/models.py:91-102`) — the `'deactivated'` value would raise a Python-level validation error before reaching the DB, and even if it landed it would violate the migration-0030 `(is_active=true AND deactivated_at IS NULL) OR (is_active=false AND deactivated_at IS NOT NULL)` CHECK.
- **Fix:** Encoded deactivated state as `status='active' + is_active=False + deactivated_at=datetime.now(tz=UTC)`. This matches `users.repository.deactivate_user_atomic` (the prod path inserted in plan 43-04) so the fixture and the service produce DB-identical rows.
- **Files modified:** `apps/backend/tests/integration/users/conftest.py` (the `deactivated_user` and `single_active_owner_id` fixtures, and the `refresh_client_deactivated` post-login mutation).
- **Commit:** 02d6e24

**2. [Rule 2 — Missing functionality] `sandbox_email_client` needed slot-replacement + restore-on-teardown to avoid poisoning subsequent tests**

- **Found during:** Task 1 (sandbox fixture wiring)
- **Issue:** Simply calling `register_email_dispatcher(recorder)` without restoring the prior callable would replace the ARQ-enqueueing prod dispatcher process-wide, breaking any test that runs after `sandbox_email_client` and expects the prod email path.
- **Fix:** Capture `app.core.dependencies._email_dispatcher` before registration, restore it (or reset to `None` if prior was `None`) in the fixture's `finally` block.
- **Files modified:** `apps/backend/tests/integration/users/conftest.py` (`sandbox_email_client`).
- **Commit:** 02d6e24

**3. [Rule 3 — Blocking] mypy strict objected to `dict.get` with default returning `str | None`**

- **Found during:** Task 1 verify (mypy --strict)
- **Issue:** `httpx.Cookies.get("sportzal_csrf", "")` is typed `str | None` (the default-value overload doesn't narrow). mypy strict flagged the dict construction as `Dict entry 0 has incompatible type "str": "str | None"; expected "str": "str"`.
- **Fix:** Switched to `client.cookies.get("sportzal_csrf") or ""` — short-circuit coerces to `str` unconditionally.
- **Files modified:** `apps/backend/tests/integration/users/conftest.py` (`_csrf_headers`).
- **Commit:** 02d6e24

### Architectural Decisions Not Requiring Approval

- **`deactivated_user_id` chained to `deactivated_user`** instead of being a standalone seed: lets 43-12 audit assertion reference the same row 43-09 reactivates, and the chaining matches the plan's "alias" wording.
- **`refresh_client_deactivated` seeds its OWN reception row** rather than logging in as `deactivated_user`: the deactivated-user row carries `is_active=False` already, so `_login` would 401 before any refresh cookie could be issued. The fix is to seed a fresh row, log in, then mutate the row to inactive — preserving the "cookie issued, then user-row predicate fails" anti-oracle scenario. The audit assertion in 43-12 still works because it reads `deactivated_user_id` from the independently-seeded `deactivated_user` fixture (per the plan's wording — the two fixtures need not reference the same row).

## Pre-Existing Issues (Out of Scope)

- **Import-linter contract "modules cannot import each other" already broken** before this plan: `app.modules.users.repository` (plan 43-04) imports `app.modules.auth.password_reset_token_model`. This violation predates 43-07b and lives in `apps/backend/.importlinter` scope — not touched here.

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| Function count >= 13 | `python -c "ast.parse(...)" \| count def` | 25 PASS |
| Fixture-name references >= 13 | `grep -cE 'authed_client_owner\|...'` | 34 PASS |
| pytest --collect-only exits 0 | `pytest tests/integration/users/ --collect-only -q` | "no tests collected" (expected — no test files yet) — exit 0 PASS |
| ruff check clean | `ruff check tests/integration/users/conftest.py` | "All checks passed!" PASS |
| ruff format clean | `ruff format --check tests/integration/users/conftest.py` | clean (after one auto-format pass) PASS |
| mypy strict clean | `mypy tests/integration/users/conftest.py` | "Success: no issues found in 1 source file" PASS |

## Self-Check: PASSED

- File `apps/backend/tests/integration/users/__init__.py` — exists (empty)
- File `apps/backend/tests/integration/users/conftest.py` — exists, 661 LOC, 25 defs
- Commit `02d6e24` — present in `git log --oneline`
