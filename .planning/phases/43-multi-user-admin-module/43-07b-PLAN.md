---
phase: 43-multi-user-admin-module
plan: 07b
type: execute
wave: 3
depends_on: [6, 7]
files_modified:
  - apps/backend/tests/integration/users/__init__.py
  - apps/backend/tests/integration/users/conftest.py
autonomous: true
requirements: [USERS-02, USERS-04, USERS-06]
must_haves:
  truths:
    - "Per checker blocker (revision): shared conftest.py is a single-owner file authored before Wave 4 so the parallel test plans (43-08..43-12) do not race-write it"
    - "All cross-plan fixtures live here: authed_client_owner pairs already from clients/conftest.py — this users/conftest.py adds USERS-specific fixtures (seeded_active_reception_email, fresh_authed_reception_client, sandbox_email_client, refresh_client_*, deactivated_user_id, current_owner_user_id, single_active_owner_id, etc.)"
    - "Conftest.py imports cleanly under pytest --collect-only — no NameError, no missing-symbol regressions"
  artifacts:
    - path: "apps/backend/tests/integration/users/conftest.py"
      provides: "All shared fixtures for tests in tests/integration/users/*"
      contains: "async def seeded_active_reception_email"
    - path: "apps/backend/tests/integration/users/__init__.py"
      provides: "Empty package marker so pytest treats users/ as a package"
      contains: ""
  key_links:
    - from: "tests/integration/users/conftest.py"
      to: "tests/integration/clients/conftest.py (analog)"
      via: "mirror authed_client_owner / authed_client_reception construction + SAVEPOINT db_session usage"
      pattern: "ASGITransport.*AsyncClient.*_login"
---

<objective>
Land `tests/integration/users/conftest.py` (+ empty `__init__.py`) as a single-owner file BEFORE Wave 4 plans land. Wave 4 plans (43-08, 43-09, 43-10, 43-11, 43-12) all assume a rich set of shared fixtures (authed clients, seeded users in various states, sandbox email client, refresh-client pairs for the anti-oracle test). Authoring this file once — in Wave 3 — eliminates the race condition the checker flagged: 5 parallel plans previously implied to write the same conftest.py.

This plan creates ALL fixtures used by 43-08..43-12. Each Wave 4 plan then declares `depends_on: [..., 7b]` and consumes the fixtures by name — no plan re-defines them.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/43-multi-user-admin-module/43-CONTEXT.md
@.planning/phases/43-multi-user-admin-module/43-PATTERNS.md
@apps/backend/tests/integration/clients/conftest.py
@apps/backend/tests/integration/auth/conftest.py
@apps/backend/app/modules/auth/models.py
@apps/backend/app/modules/auth/service.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create users/__init__.py + users/conftest.py with all shared fixtures</name>
  <files>apps/backend/tests/integration/users/__init__.py, apps/backend/tests/integration/users/conftest.py</files>
  <read_first>
    - apps/backend/tests/integration/clients/conftest.py (PRIMARY analog — mirror its structure: OWNER_EMAIL constants, _seed_user/_login helpers, redis_clean, _client_app_overrides dependency-override fixture, authed_client_owner/reception)
    - apps/backend/tests/integration/auth/conftest.py (logger-cache autouse fixture; consider mirroring for users.service if it uses a structlog proxy)
    - apps/backend/app/modules/auth/models.py (User model column names: status, deactivated_at, deleted_at, password_hash, email_verified, is_active)
    - apps/backend/app/modules/auth/service.py (issue_refresh_pair or equivalent — fixtures that need refresh-token cookies call into this)
    - apps/backend/app/integrations/email/client.py (SandboxEmailClient capture API — `.sent_emails`/`.envelopes`)
    - apps/backend/app/core/permissions.py (Role enum)
    - .planning/phases/43-multi-user-admin-module/43-CONTEXT.md (D-43-13, D-43-16, D-43-18, D-43-20, D-43-26, D-43-28, D-43-29, D-43-33, D-43-34)
    - .planning/phases/43-multi-user-admin-module/43-PATTERNS.md (lines 700-790 — fixture conventions, sandbox email capture)
  </read_first>
  <action>
Create two files:

1. `apps/backend/tests/integration/users/__init__.py` — empty file (package marker so pytest discovers the subdirectory and conftest.py applies).

2. `apps/backend/tests/integration/users/conftest.py` — mirror `tests/integration/clients/conftest.py` structurally, then add the USERS-specific fixtures consumed by 43-08..43-12.

Top of file: docstring naming the source plan (43-07b) and the consumer plans (43-08..43-12). State explicitly: "This file is the single owner of users-module test fixtures — Wave 4 test plans MUST NOT modify it."

Required helpers / constants (mirror clients/conftest.py):
- `OWNER_EMAIL = "users-owner@example.com"` + `OWNER_PASSWORD = "hunter22hunter22"` (>=12 chars, noqa S105 comment)
- `RECEPTION_EMAIL = "users-reception@example.com"` + `RECEPTION_PASSWORD = "hunter22hunter22"`
- `_seed_user(db_session, *, role, email, password, full_name, status="active", is_active=True, deleted_at=None, deactivated_at=None) -> User` — INSERT a User via the SAVEPOINT-rolled session. Adds support for status / deactivated_at / deleted_at columns so deactivated/soft-deleted variants reuse the same helper.
- `_login(client, *, email, password) -> None` — POSTs `/api/v1/auth/login`, asserts 200.
- `_csrf_headers(client) -> dict[str, str]` — returns `{"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}`. Re-exported here so test modules need not redefine.

Required fixtures (use `pytest_asyncio.fixture` for all async ones; mark sync helpers with `@pytest.fixture`):

A. **Core authed clients (mirrors clients/conftest.py):**
   - `redis_clean(app) -> Redis` — flush Redis between tests.
   - `_client_app_overrides(app, db_session) -> AsyncIterator[FastAPI]` — install `get_db` + `get_redis` overrides, yield app, clear on teardown. Mirror clients/conftest.py exactly.
   - `seeded_owner(db_session, redis_clean) -> User` — seeds the users-test owner row.
   - `seeded_reception(db_session, redis_clean) -> User` — seeds the users-test reception row.
   - `authed_client_owner(_client_app_overrides, seeded_owner) -> AsyncIterator[AsyncClient]` — fresh ASGITransport + AsyncClient, performs `_login` with OWNER_EMAIL/PASSWORD, yields client with cookie jar populated.
   - `authed_client_reception(_client_app_overrides, seeded_reception) -> AsyncIterator[AsyncClient]` — analogous for reception.

B. **Owner-introspection fixtures (consumed by 43-09):**
   - `current_owner_user_id(authed_client_owner, db_session) -> UUID` — SELECT the active owner row by `OWNER_EMAIL` and return its id (NOT a generic owner SELECT — pin the row by email to keep deterministic ids across tests).
   - `single_active_owner_id(db_session) -> UUID` — ensure exactly one active+non-deleted owner exists; if multiple, soft-deactivate the extras (UPDATE is_active=False, deactivated_at=datetime.now(tz=UTC)). Return the surviving owner's id. Use the seeded owner pinned by `OWNER_EMAIL` as the survivor.

C. **Active-existing email fixture (consumed by 43-08):**
   - `seeded_active_reception_email(db_session) -> str` — INSERT a `User(email="active-existing@example.com", role=RECEPTION, status="active", is_active=True, email_verified=True, password_hash="$argon2id$dummy", full_name="Seeded Active")`. Flush; return the email string.

D. **Deactivated / soft-deleted user fixtures (consumed by 43-09 + 43-10 + 43-12):**
   - `deactivated_user(db_session) -> User` — INSERT reception user with `status="deactivated"`, `is_active=False`, `deactivated_at=now()`. Return the User instance.
   - `deactivated_user_id(deactivated_user) -> UUID` — return `deactivated_user.id` (used by 43-12 anti-oracle audit assertion).
   - `soft_deleted_user(db_session) -> User` — INSERT reception user with `deleted_at=now()`, `is_active=False`. Return the User instance.

E. **Session-pair fixtures (consumed by 43-10):**
   - `_make_authed_client_for_user(_client_app_overrides, db_session, *, email: str, password: str = "hunter22hunter22") -> AsyncIterator[AsyncClient]` — INTERNAL async-generator helper (NOT a pytest fixture — a callable used by the four fresh_authed_* fixtures below). Seeds the user if missing via `_seed_user`, performs `_login`, yields the AsyncClient.
   - `fresh_authed_reception_client(_client_app_overrides, db_session) -> AsyncIterator[tuple[AsyncClient, UUID]]` — seed a NEW reception user "`fresh-reception-1@example.com`" via `_seed_user`, login, yield `(client, user_id)`. NOTE: the existing 43-10 plan signature treats this as just `AsyncClient` — to avoid forcing 43-10 to be re-edited, expose TWO fixtures:
     - `fresh_authed_reception_user_id(db_session) -> UUID` — seeds the row and returns the id (no client).
     - `fresh_authed_reception_client(_client_app_overrides, fresh_authed_reception_user_id, db_session) -> AsyncIterator[AsyncClient]` — uses the same email/password as the id fixture, performs `_login`, yields the AsyncClient.
   - `fresh_authed_reception_user_id_2(db_session) -> UUID` + `fresh_authed_reception_client_2(_client_app_overrides, fresh_authed_reception_user_id_2, db_session) -> AsyncIterator[AsyncClient]` — second pair (email `fresh-reception-2@example.com`) for the soft-delete branch test.

F. **Sandbox email fixture (consumed by 43-11):**
   - `sandbox_email_client(app) -> SandboxEmailClient` — pull the SandboxEmailClient instance from `app.state` / dependency overrides. Reference Phase 42 plan 7 / 11 — mirror the exact resolution path (likely `app.state.email_client` or `app.integrations.email.client._client`). Assert isinstance, return.

G. **Refresh-token 4-case fixtures (consumed by 43-12):**
   - `refresh_client_active(_client_app_overrides, db_session) -> AsyncIterator[AsyncClient]` — seed active reception, login, yield client (cookies include `sz_refresh`).
   - `refresh_client_deactivated(_client_app_overrides, db_session) -> AsyncIterator[AsyncClient]` — seed active reception, login to issue the refresh cookie, THEN mutate the user row directly via db_session (UPDATE is_active=False, status='deactivated', deactivated_at=now()). Yield the client with the stale cookie still valid by structure but invalid by user-row predicate. The `deactivated_user_id` for the audit assertion is the same row — provide overlap via `pytest_asyncio.fixture` chaining or attach the id to the client via `client.user_id` attribute (document the pattern in the docstring).
   - `refresh_client_soft_deleted(_client_app_overrides, db_session) -> AsyncIterator[AsyncClient]` — analogous, mutate `deleted_at=now()` after login.
   - `refresh_client_unknown_token(_client_app_overrides) -> AsyncIterator[AsyncClient]` — create a bare AsyncClient with a syntactically valid but never-issued `sz_refresh` cookie (e.g. `secrets.token_urlsafe(48)`) + a matching CSRF cookie if the route requires it. Login is NOT performed. Yield the client.

H. **Logger-cache reset (optional, mirror auth/conftest.py if users.service uses structlog proxy):**
   - `_reset_users_service_logger_cache()` autouse fixture if `app.modules.users.service` exposes `_log` as a BoundLoggerLazyProxy. Pattern lifted from `tests/integration/auth/conftest.py:27-33`. Skip if the module does not have such a proxy (check before adding to avoid noise).

Imports at top of file:
- `from __future__ import annotations`
- stdlib: `import secrets`, `from collections.abc import AsyncIterator`, `from datetime import UTC, datetime`, `from typing import Any`, `from uuid import UUID`
- third-party: `import pytest`, `import pytest_asyncio`, `from fastapi import FastAPI`, `from httpx import ASGITransport, AsyncClient`, `from redis.asyncio import Redis`, `from sqlalchemy import select, update`, `from sqlalchemy.ext.asyncio import AsyncSession`
- app: `from app.core.database import get_db`, `from app.core.permissions import Role`, `from app.core.redis import get_redis`, `from app.core.security import hash_password`, `from app.modules.auth.models import User`, `from app.integrations.email.client import SandboxEmailClient` (or wherever the sandbox class actually lives — confirm via read_first)

Do NOT define `SandboxEmailClient` here — only resolve+return the instance. Do NOT define any test functions in this file — fixtures only.

If `app.modules.auth.models.User` does not expose the `status` / `deactivated_at` / `deleted_at` columns expected by the fixtures, fall back to the canonical model path (consult 43-04 / 43-05 plans for the exact import). The fixture must compile against the Wave 1 model definitions.
  </action>
  <verify>
    <automated>cd apps/backend && uv run python -c "import ast; tree = ast.parse(open('tests/integration/users/conftest.py').read()); fn_count = sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))); print(f'function_count={fn_count}'); assert fn_count >= 13, fn_count" && cd apps/backend && uv run pytest tests/integration/users/ --collect-only -q 2>&1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - File `apps/backend/tests/integration/users/__init__.py` exists (empty)
    - File `apps/backend/tests/integration/users/conftest.py` exists
    - `grep -cE '^(async )?def ' apps/backend/tests/integration/users/conftest.py` returns >= 13 (helpers + all required fixtures)
    - `grep -c 'authed_client_owner\|authed_client_reception\|seeded_active_reception_email\|deactivated_user\|soft_deleted_user\|fresh_authed_reception_client\|sandbox_email_client\|refresh_client_active\|refresh_client_deactivated\|refresh_client_soft_deleted\|refresh_client_unknown_token\|deactivated_user_id\|current_owner_user_id\|single_active_owner_id' apps/backend/tests/integration/users/conftest.py` returns >= 13 (all 13 fixture names referenced as definitions)
    - `cd apps/backend && uv run pytest tests/integration/users/ --collect-only -q` exits 0 (no ImportError, no collection errors — proves the conftest.py imports cleanly even before Wave 4 test files land)
    - `cd apps/backend && uv run ruff check tests/integration/users/conftest.py` exits 0
    - `cd apps/backend && uv run mypy tests/integration/users/conftest.py` exits 0 (strict mode per repo policy)
  </acceptance_criteria>
  <done>conftest.py + __init__.py committed; pytest --collect-only succeeds (empty collection or zero failures); ruff + mypy clean.</done>
</task>

</tasks>

<verification>
- conftest.py imports cleanly under `pytest --collect-only`.
- All 13 fixture names + helpers + login/seed primitives are present.
- No test functions are defined in this file (fixtures-only invariant).
- ruff + mypy strict pass.
</verification>

<success_criteria>
Shared test fixture surface for Phase 43 USERS tests is in place — Wave 4 plans (43-08..43-12) can now be implemented in parallel without race-writing conftest.py.
</success_criteria>

<output>
After completion, create `.planning/phases/43-multi-user-admin-module/43-07b-SUMMARY.md` listing:
- Final list of fixture names exported.
- The exact `SandboxEmailClient` resolution path used (app.state attribute vs module singleton).
- Any deviations from the clients/conftest.py analog and rationale.
</output>
