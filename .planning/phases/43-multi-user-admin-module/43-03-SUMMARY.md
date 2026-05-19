---
phase: 43-multi-user-admin-module
plan: 03
subsystem: auth

tags: [auth, audit, fastapi, sqlalchemy, redis, pydantic, mypy]

# Dependency graph
requires:
  - phase: 41-infra-bedrock-anti-oracle-scaffold
    provides: UserSessionInvalidator Protocol slot (D-41-25); EmailDispatcher slot precedent (REG-29-03 double-wire reference); LOCKED_AUDIT_EVENTS frozenset + AST taxonomy gate; 6 pre-registered user-lifecycle Pydantic payloads with extra='forbid'
  - phase: 42-email-transport-layer-email-otp-fallback
    provides: register_email_dispatcher composition-root precedent (immediate neighbour for Phase 43 single-wire registration); 70-entry LOCKED_AUDIT_EVENTS frozenset baseline (Phase 42 plan 09 added otp_requested/otp)
provides:
  - invalidate_all_families_for_user async function in app/modules/auth/service.py — Phase 41 D-41-25 UserSessionInvalidator Protocol implementation (wraps revoke_all_sessions with reason logging)
  - set_redis_factory closure-injection setter (D-43-26 composition discipline) — lazy Redis client lookup via app.state.redis
  - UserInvitedPayload.link_copied: bool field — Phase 43 D-43-14 escape-hatch tracking (?include_invite_link=true)
  - RefreshFailedPayload class with reason Literal['account_inactive','invalid_session','expired','revoked'] — Phase 43 D-43-20 anti-oracle forensic payload
  - ('refresh_failed', 'session') pair registered in LOCKED_AUDIT_EVENTS AND AUDIT_PAYLOAD_SCHEMAS — cardinality 70 → 71
  - register_user_session_invalidator(invalidate_all_families_for_user) call in app/main.py:create_app() — D-43-27 single-wire (no worker registration)
  - test_user_session_invalidator_registered_single_wire integration test — asserts both positive registration AND anti-double-wire negative (AST walk of workers/__init__.py)
affects: [43-05 users-service-create-deactivate-reactivate (consumes get_user_session_invalidator), 43-07 auth-refresh-is-active-guard (emits refresh_failed/session via the new payload), 43-08 audit-payloads-link-copied (already-shipped here as part of 43-03 scope per plan frontmatter), 44-RESET-02 password-reset-confirm (reuses UserSessionInvalidator slot with reason='password_reset')]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Composition-root single-wire (D-43-27): Protocol slot consumed only by FastAPI HTTP flows → registered ONLY in create_app(); worker untouched. Asymmetric vs EmailDispatcher REG-29-03 double-wire."
    - "Lazy Redis closure (D-43-26): module-level _redis_factory callable accepts a no-arg lambda that reads app.state.redis at invocation time (the lifespan populates state.redis AFTER create_app() returns)."
    - "Anti-oracle forensic emit (D-43-20): identical HTTP response across failure reasons; only the audit row's discriminating reason field tells deactivated-account from generic invalid-session at the dashboard layer."

key-files:
  created:
    - apps/backend/.planning/phases/43-multi-user-admin-module/43-03-SUMMARY.md
  modified:
    - apps/backend/app/modules/auth/service.py (added set_redis_factory + invalidate_all_families_for_user; Callable added to collections.abc import)
    - apps/backend/app/core/audit_payloads.py (UserInvitedPayload.link_copied field; new RefreshFailedPayload class; AUDIT_PAYLOAD_SCHEMAS registry entry)
    - apps/backend/app/core/audit.py (LOCKED_AUDIT_EVENTS gains ('refresh_failed', 'session'))
    - apps/backend/app/main.py (set_auth_redis_factory + register_user_session_invalidator calls; new imports from app.modules.auth.service)
    - apps/backend/tests/integration/test_app_wiring.py (extended all-slots test + new single-wire parity test)
    - apps/backend/tests/unit/test_audit_taxonomy.py (cardinality assertion 70 → 71)

key-decisions:
  - "Used Approach A (closure injection via set_redis_factory + lambda: app.state.redis) — keeps auth.service surface clean of FastAPI request scope; the lambda is the only place that knows about app.state."
  - "Cardinality assertion updated to 71 (not 70 as plan claimed) — pre-existing drift: Phase 42 plan 09 added ('otp_requested', 'otp') after the 41-01 plan header was written. Documented in test_audit_taxonomy.py docstring continuation."
  - "Worker/__init__.py left untouched per D-43-27 — anti-double-wire AST assertion pins it."
  - "RefreshFailedPayload registered next to password_reset entries in AUDIT_PAYLOAD_SCHEMAS (auth/session domain grouping); single LOCKED_AUDIT_EVENTS insertion next to family_reuse_detected (session-resource lineage)."

patterns-established:
  - "Single-wire Protocol slot pattern (D-43-27): for any future Protocol whose consumers are exclusively HTTP-bound, register ONLY in create_app() and pin the asymmetry with a negative-AST assertion against workers/__init__.py. Distinguishes from REG-29-03 double-wire where both FastAPI and ARQ consume the slot."
  - "Lazy lifespan-aware factory (D-43-26): when a Protocol implementation needs a runtime resource only populated by the lifespan (Redis client, ARQ pool), accept a no-arg factory at registration time and resolve the resource at invocation time."

requirements-completed: [USERS-04, USERS-06, USERS-07]

# Metrics
duration: 35min
completed: 2026-05-19
---

# Phase 43 Plan 03: Cross-cutting Runtime Bedrock Summary

**UserSessionInvalidator Protocol implementation + audit payload extensions enabling Wave 2 users/service.py and Wave 3 /auth/refresh to emit and consume cross-cutting events without further plumbing.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-05-19T13:52:00Z (approx — picked up after 43-01 SUMMARY commit)
- **Completed:** 2026-05-19T14:03:19Z
- **Tasks:** 5
- **Files modified:** 6

## Accomplishments

- `invalidate_all_families_for_user` async function (D-41-25 Protocol-conformant signature) ships in `app/modules/auth/service.py`, wrapping the existing `revoke_all_sessions` and pulling Redis through a composition-root-injected factory
- `UserInvitedPayload.link_copied: bool` + new `RefreshFailedPayload` (with `account_inactive` reason) extend the audit substrate so Wave 2's `users/service.py` and Wave 3's `rotate_refresh` modifications can emit without ValidationError
- `('refresh_failed', 'session')` registered in both LOCKED_AUDIT_EVENTS (cardinality 70 → 71) AND AUDIT_PAYLOAD_SCHEMAS — Wave 3's anti-oracle deactivated-account branch has its forensic emit path ready
- `register_user_session_invalidator(invalidate_all_families_for_user)` wired in `create_app()` adjacent to the Phase 42 `register_email_dispatcher` call — **single-wire** per D-43-27 (worker untouched)
- New `test_user_session_invalidator_registered_single_wire` integration test pins BOTH halves of the asymmetry (positive registration + anti-double-wire AST assertion against `workers/__init__.py`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add invalidate_all_families_for_user** — `8921059` (feat)
2. **Task 2: Extend audit_payloads (link_copied + RefreshFailedPayload)** — `e68fd3e` (feat)
3. **Task 3: Register ('refresh_failed', 'session') in LOCKED_AUDIT_EVENTS** — `7bd0c4e` (feat)
4. **Task 4: Wire register_user_session_invalidator in create_app()** — `b101e11` (feat)
5. **Task 5: Add single-wire parity test** — `340f01e` (test)

_Note: Two unrelated 43-02 commits (`69921cc` USER_INVITATION_EMAIL template, `07109c2` snapshot test) landed between Task 3 and Task 4 from a parallel execution thread. They belong to 43-02, not 43-03._

## Files Created/Modified

- `apps/backend/app/modules/auth/service.py` — `Callable` added to `collections.abc` import; new `_redis_factory` module-level slot; `set_redis_factory(factory)` setter; `invalidate_all_families_for_user(session, *, user_id, reason)` Protocol-conformant async function (logs reason via `_log`, delegates to `revoke_all_sessions`)
- `apps/backend/app/core/audit_payloads.py` — `UserInvitedPayload.link_copied: bool` field added (extra='forbid' preserved); new `RefreshFailedPayload` class with `reason: Literal['account_inactive','invalid_session','expired','revoked']` and nullable `user_id`/`audit_correlation_id`; AUDIT_PAYLOAD_SCHEMAS gains `('refresh_failed', 'session'): RefreshFailedPayload`
- `apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` frozenset gains `('refresh_failed', 'session')` next to `('family_reuse_detected', 'session')` with a Phase 43 D-43-20 comment block
- `apps/backend/app/main.py` — imports `register_user_session_invalidator` from dependencies and `invalidate_all_families_for_user` + `set_redis_factory as set_auth_redis_factory` from auth.service; new registration block immediately after `register_email_dispatcher(...)` with `set_auth_redis_factory(lambda: app.state.redis)` + `register_user_session_invalidator(invalidate_all_families_for_user)`
- `apps/backend/tests/integration/test_app_wiring.py` — `test_create_app_registers_all_protocol_slots` extended with Phase 43 slot assertion; new `test_user_session_invalidator_registered_single_wire` covers both positive registration and the negative anti-double-wire AST walk
- `apps/backend/tests/unit/test_audit_taxonomy.py` — cardinality docstring extended with Phase 43 Plan 03 paragraph; assertion updated from `== 70` to `== 71` (13 v1.6 pairs total)

## Decisions Made

- **Approach A (closure) over Approach B (request-scope coupling):** the plan recommended Approach A and the recommendation held — the auth.service surface stays free of FastAPI imports, and the closure receives `app` via the `create_app()` body so it can read `app.state.redis` lazily (the lifespan populates state.redis AFTER `create_app()` returns).
- **Cardinality 70 → 71 (not 69 → 70 as plan claimed):** pre-existing drift. Phase 41 plan 01 added 11 v1.6 pairs taking the set to 69; Phase 42 plan 09 added `('otp_requested', 'otp')` taking it to 70. My addition brings it to 71. The `test_audit_taxonomy.py` cardinality assertion was already at `== 70` (Phase 42 had updated it), so I updated to `== 71` and extended its docstring with the Phase 43 Plan 03 paragraph documenting the chain.
- **Registry placement:** `('refresh_failed', 'session')` in AUDIT_PAYLOAD_SCHEMAS placed between the password-reset entries and the payment-receipt-email entry — auth/session domain grouping. In LOCKED_AUDIT_EVENTS placed right after `('family_reuse_detected', 'session')` to keep session-resource pairs adjacent.
- **`app.state.redis` confirmed via grep** as the canonical attribute name (set in `app/core/redis.py:50` inside `redis_lifespan`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in plan against current state] Cardinality assertion corrected to 71**
- **Found during:** Task 3 (Add ('refresh_failed', 'session') to LOCKED_AUDIT_EVENTS)
- **Issue:** Plan claimed PRIOR cardinality was 69 and post-task should be 70. Actual prior cardinality was 70 because Phase 42 plan 09 added `('otp_requested', 'otp')` after the plan was written. Also, `tests/unit/test_audit_taxonomy.py` already had `assert len(LOCKED_AUDIT_EVENTS) == 70` which would have failed at the post-task value of 71.
- **Fix:** Updated assertion `== 70 → == 71`, updated docstring count breakdown `12 v1.6 → 13 v1.6`, added a paragraph documenting Phase 43 Plan 03's contribution.
- **Files modified:** `apps/backend/tests/unit/test_audit_taxonomy.py`
- **Verification:** `pytest tests/unit/test_audit_taxonomy.py -x -q` → 7 passed.
- **Committed in:** `7bd0c4e` (Task 3 commit; staged together with the audit.py change since the test file is the AST gate for the same frozenset).

**2. [Rule 3 - Blocking ruff import-sort] Auto-sorted import block in main.py**
- **Found during:** Task 4 (Wire register_user_session_invalidator in main.py)
- **Issue:** Ruff isort flagged the new combined `from app.modules.auth.service import (...)` block as un-sorted because `invalidate_all_families_for_user` and `load_user_by_id` are non-aliased while `set_redis_factory as set_auth_redis_factory` is aliased — ruff isort splits them into two adjacent import statements.
- **Fix:** Ran `uv run ruff check --fix app/main.py`; the auto-fix produced two `from app.modules.auth.service import (...)` blocks (one for non-aliased symbols, one for the aliased import).
- **Files modified:** `apps/backend/app/main.py`
- **Verification:** `uv run ruff check app/main.py` exits 0.
- **Committed in:** `b101e11` (Task 4 commit).

**3. [Rule 3 - Blocking mypy unused-ignore] Removed unnecessary `type: ignore[attr-defined]` in test**
- **Found during:** Task 5 (parity test)
- **Issue:** Plan template included `# type: ignore[attr-defined]` on the `deps._user_session_invalidator = None` reset line. Mypy `--strict` rejected it with `Unused "type: ignore" comment [unused-ignore]` — the `_user_session_invalidator` attribute is fully typed in dependencies.py.
- **Fix:** Removed the trailing `# type: ignore[attr-defined]` comment.
- **Files modified:** `apps/backend/tests/integration/test_app_wiring.py`
- **Verification:** `uv run mypy --strict tests/integration/test_app_wiring.py` no longer flags the test file (3 errors remain in unrelated `app/modules/auth/*` files — pre-existing, see Issues Encountered).
- **Committed in:** `340f01e` (Task 5 commit).

---

**Total deviations:** 3 auto-fixed (1 Rule 1 plan-vs-state correctness, 2 Rule 3 tooling-blocking).
**Impact on plan:** All three were necessary to keep the tree green. No scope creep — every fix maps directly to one of the five planned tasks; no architectural changes.

## Issues Encountered

**Pre-existing mypy errors (NOT introduced by this plan, NOT auto-fixed per scope boundary):**

- `app/modules/auth/service.py:45` and `app/modules/auth/telegram_service.py:45` and `app/modules/auth/router.py:45` — `Module "app.modules.auth.models" does not explicitly export attribute "User"` — Phase 41 D-41-01/02 User hoist created a one-milestone shim in `app/modules/auth/models.py` that re-exports `User` without an explicit `__all__`. Tracked as `DEFER-41-shim` (v1.7 removal).
- `app/modules/auth/service.py:141` — `Argument 2 to "verify_password" has incompatible type "str | None"; expected "str"` — Phase 43 Plan 01 dropped `users.password_hash NOT NULL` so the column type is now `Mapped[str | None]`; the `_authenticate_password` callsite needs an `if password_hash is None: raise InvalidCredentials` guard before calling `verify_password`. This is **owned by a later Phase 43 plan (43-04 or 43-05 users-module integration; the plan explicitly says "auth.service updates are scoped tightly to that single SELECT in `_authenticate_password` (Plan 43-XX to be sized by planner)")**. NOT within 43-03's scope; logged to deferred-items if a tracking file exists.

These were verified to exist BEFORE this plan started (Phase 43-01 SUMMARY notes the `Mapped[str | None]` change). The Phase 43-03 plan scope is strictly limited to the 5 enumerated tasks; the inactive-account guard at `_authenticate_password` belongs to a later plan.

## User Setup Required

None — no external service configuration required.

## Threat Flags

None — Plan 43-03 adds no new network endpoints, auth paths, or trust-boundary surface. The new function is an internal Protocol implementation consumed only by composition-root-registered slots; the new audit pair tightens forensic visibility on an existing surface (`/auth/refresh`).

## Next Phase Readiness

- **Wave 2 unblocked:** `app/modules/users/service.py:deactivate_user` can now call `get_user_session_invalidator()(session, user_id=..., reason='deactivated')` and route to `revoke_all_sessions` via the closure-injected Redis client.
- **Wave 3 unblocked:** `auth.service.rotate_refresh` can extend its user-row SELECT with `is_active=true AND deleted_at IS NULL` (D-43-20) and emit `audit.emit("refresh_failed", actor_user_id=..., resource_type="session", reason="account_inactive", audit_correlation_id=None)` without `AuditEventNotLockedError` or `pydantic.ValidationError`.
- **Wave 2's invitation flow** can pass `link_copied=True|False` to `audit.emit("user_invited", ..., link_copied=...)` without ValidationError (D-43-14).
- **Single-wire parity pinned in CI:** the new integration test guards against accidental future double-wiring of `UserSessionInvalidator` in the worker.
- **Pre-existing 4-mypy-error backlog in `app/modules/auth/*`** is unchanged by this plan; it is owned by a later 43-* plan that integrates the new users module with `_authenticate_password`.

## Self-Check: PASSED

Verified after writing this SUMMARY:

- `apps/backend/app/modules/auth/service.py` — FOUND (modified, contains `invalidate_all_families_for_user`, `set_redis_factory`, `_redis_factory`)
- `apps/backend/app/core/audit_payloads.py` — FOUND (modified, contains `link_copied: bool`, `class RefreshFailedPayload`, registry entry)
- `apps/backend/app/core/audit.py` — FOUND (modified, contains `("refresh_failed", "session")`)
- `apps/backend/app/main.py` — FOUND (modified, contains `register_user_session_invalidator(invalidate_all_families_for_user)`)
- `apps/backend/tests/integration/test_app_wiring.py` — FOUND (modified, contains `test_user_session_invalidator_registered_single_wire`)
- `apps/backend/tests/unit/test_audit_taxonomy.py` — FOUND (cardinality assertion updated to 71)
- Commit `8921059` (Task 1) — FOUND
- Commit `e68fd3e` (Task 2) — FOUND
- Commit `7bd0c4e` (Task 3) — FOUND
- Commit `b101e11` (Task 4) — FOUND
- Commit `340f01e` (Task 5) — FOUND

---
*Phase: 43-multi-user-admin-module*
*Completed: 2026-05-19*
