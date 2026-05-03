---
phase: 08-clients-module-audit-log
plan: 05
subsystem: auth
tags: [audit, async, sqlalchemy-async, transactions, telegram, rbac, csrf]

requires:
  - phase: 08-clients-module-audit-log
    provides: async `audit.emit(session, event, *, actor_user_id, resource_type, resource_id=None, **payload)` signature (Plan 02)
provides:
  - "All 13 originally-enumerated audit emit call-sites in auth/service.py, auth/router.py, telegram_service.py, integrations/telegram/handlers.py migrated to new async signature"
  - "2 additional Rule-3 fixes in app/core/dependencies.py (`rbac_forbidden`, `csrf_mismatch`) so the codebase compiles under mypy --strict"
  - "Pitfall 2 fix: every `await audit.emit(...)` call sits BEFORE its `await session.commit()` (or before the `async with session.begin():` block exits) so the audit row commits atomically with the business mutation"
  - "Pitfall 3 fix: 4 telegram handler events (telegram_unknown_start, telegram_replay_attempt, telegram_dm_blocked, telegram_dm_failed) converted from `logger.warning/info` to `await audit_emit(session, ...)` inside the existing `async with ctx.session_factory() as session:` block — they now write rows to audit_log instead of structlog-only"
affects:
  - "08-08 (tests) — DB-row visibility tests now have all 15+ events writing rows"
  - "08-06 (clients router) — confirms the audit migration pattern is in place"

tech-stack:
  added: []
  patterns:
    - "Co-transactional audit emit BEFORE caller's session.commit() (Pitfall 2)"
    - "Audit emit inside `async with session.begin():` block (rotate_refresh branch C) — row enrolls in DB tx that auto-commits at block exit"
    - "Audit emit inside `async with ctx.session_factory() as session:` block (telegram handlers) — row enrolls in session that commits on clean __aexit__"
    - "FastAPI signature-dep injection of `session: AsyncSession = Depends(get_db)` into `_checker` and `verify_csrf` to give them the session needed by the new async signature"

key-files:
  created: []
  modified:
    - "apps/backend/app/modules/auth/service.py — 7 call-sites: login_failed×2, login_success, family_reuse_detected (moved INSIDE begin block), session_revoked (emit before commit), session_revoked_all (emit before commit), password_changed_revokes_sessions (emit before commit added). Import `from app.core.audit import emit` → `from app.core import audit`."
    - "apps/backend/app/modules/auth/router.py — 1 call-site: telegram_verify login_success. Import swap."
    - "apps/backend/app/modules/auth/telegram_service.py — 3 call-sites: telegram_deep_link_issued (emit before commit), otp_issued (emit before commit), otp_consumed (emit before commit, restructured order: load user → emit → commit). Import swap."
    - "apps/backend/app/integrations/telegram/handlers.py — 4 call-sites converted from logger.warning/info → await audit_emit. New import `from app.core.audit import emit as audit_emit` (permitted by importlinter)."
    - "apps/backend/app/core/dependencies.py — Rule 3 fix: 2 call-sites (rbac_forbidden, csrf_mismatch) needed migration too because mypy --strict on app/ would have failed otherwise. Injected `session: Annotated[AsyncSession, Depends(get_db)]` into `_checker` and `verify_csrf`. Import swap."

key-decisions:
  - "Rule 3 deviation: 2 additional call-sites in app/core/dependencies.py NOT in plan's enumeration migrated, because the plan's must_have truth #1 ('All ... emit call-sites use new async signature') and the requirement that mypy --strict on app/ stays green forced inclusion. Without them: 10 mypy errors and the codebase would not compile."
  - "rbac_forbidden mapped to actor_user_id=user.id, resource_type=resource.value (the Resource enum value of the route the caller tried to access). resource_id=None (no specific resource UUID at the dep layer)."
  - "csrf_mismatch mapped to actor_user_id=None (CSRF runs before the auth dep so user identity is not yet resolved per D-23), resource_type='csrf', resource_id=None."
  - "consume() in telegram_service.py: re-ordered to load user BEFORE final commit, so emit-then-commit can be done in a single atomic block. Original had commit between consumed_at-stamp and user load; new order is consumed_at-stamp → load user → emit → commit. Equivalent semantics for callers; better Pitfall 2 alignment."

requirements-completed: [AUDIT-02]

duration: ~10min
completed: 2026-05-03
---

# Phase 08 Plan 05: Migrate audit emit call-sites to async signature — Summary

**13 enumerated call-sites + 2 Rule-3 fixes (15 total) migrated to `await audit.emit(session, ...)`; Pitfall 2 enforced (emit BEFORE commit) and Pitfall 3 closed (4 telegram handler events now write to audit_log).**

## Per-File Call-Site Counts

| File | Old `emit(` (unqualified) | New `await audit.emit(` | New `await audit_emit(` |
|---|---:|---:|---:|
| `apps/backend/app/modules/auth/service.py` | 0 | 7 | 0 |
| `apps/backend/app/modules/auth/router.py` | 0 | 1 | 0 |
| `apps/backend/app/modules/auth/telegram_service.py` | 0 | 3 | 0 |
| `apps/backend/app/integrations/telegram/handlers.py` | 0 | 0 | 4 |
| `apps/backend/app/core/dependencies.py` (Rule 3) | 0 | 2 | 0 |
| **Total** | **0** | **13** | **4** |

Verification (final state):

```
$ grep -rEn "^\s*emit\(" app/modules/auth app/integrations/telegram app/core
(no matches)

$ grep -rE 'logger\.(warning|info)\("telegram_(unknown_start|replay_attempt|dm_blocked|dm_failed)"' app/integrations/telegram/handlers.py
(no matches)
```

## D-04 Mapping — Per-Event Confirmation

| Event | actor_user_id | resource_type | resource_id | Where |
|---|---|---|---|---|
| `login_failed` (×2) | `None` | `'login_attempt'` | (omitted) | service.py authenticate |
| `login_success` (email_password) | `user.id` | `'session'` | `None` | service.py authenticate |
| `login_success` (telegram) | `user.id` | `'session'` | `None` | router.py telegram_verify |
| `family_reuse_detected` | `row.user_id` | `'session'` | `row.family_id` | service.py rotate_refresh branch C |
| `session_revoked` | `user_id` | `'session'` | `family_id` | service.py revoke_session |
| `session_revoked_all` | `user_id` | `'user'` | `user_id` | service.py revoke_all_sessions |
| `password_changed_revokes_sessions` | `user_id` | `'user'` | `user_id` | service.py revoke_sessions_on_password_change |
| `telegram_deep_link_issued` | `None` | `'otp'` | (omitted) | telegram_service.py start_deep_link |
| `otp_issued` | `user.id` | `'otp'` | (omitted) | telegram_service.py commit_otp |
| `otp_consumed` | `user.id` | `'otp'` | (omitted) | telegram_service.py consume |
| `telegram_unknown_start` | `None` | `'otp'` | (omitted) | handlers.py start_handler |
| `telegram_replay_attempt` | `None` | `'otp'` | (omitted) | handlers.py start_handler |
| `telegram_dm_blocked` | `None` | `'otp'` | (omitted) | handlers.py start_handler |
| `telegram_dm_failed` | `None` | `'otp'` | (omitted) | handlers.py start_handler |
| **(Rule 3)** `rbac_forbidden` | `user.id` | `resource.value` (route's Resource enum) | (omitted) | dependencies.py require_permission._checker |
| **(Rule 3)** `csrf_mismatch` | `None` | `'csrf'` | (omitted) | dependencies.py verify_csrf |

## Pitfall 2 Compliance (emit BEFORE commit)

| Function | Pre-emit-vs-commit before plan | After plan |
|---|---|---|
| `authenticate` (service.py) | emit had no commit (route owns commit via get_db) | unchanged — emit happens; route's get_db lifecycle commits |
| `rotate_refresh` branch (C) | emit was OUTSIDE the `async with session.begin():` block (would never commit because the block already closed and the function then raises) | emit moved INSIDE the begin block, BEFORE the implicit commit on block exit |
| `revoke_session` | emit was AFTER `await session.commit()` (audit row never committed in same tx) | emit moved BEFORE commit |
| `revoke_all_sessions` | emit was AFTER `await session.commit()` | emit moved BEFORE commit |
| `revoke_sessions_on_password_change` | emit was AFTER inner commit (no outer commit) | emit + new explicit commit added; emit precedes commit |
| `start_deep_link` (telegram_service.py) | emit was AFTER commit | emit moved BEFORE commit |
| `commit_otp` | emit was AFTER commit | emit moved BEFORE commit |
| `consume` | emit was AFTER commit | restructured: stamp → load user → emit → commit |
| `handlers.py` (4 sites) | logger calls had no DB write | audit_emit inside `async with ctx.session_factory()` block — session auto-commits on clean exit |
| `require_permission._checker` (Rule 3) | emit had no commit | emit happens; FastAPI dep `get_db` lifecycle owns commit |
| `verify_csrf` (Rule 3) | emit had no commit | emit happens; `get_db` lifecycle owns commit |

Lexical inspection confirmed for every function that calls `await session.commit()`: the most recent `await audit.emit(...)` (or `await audit_emit(...)`) within the same function body lexically precedes the commit.

## Verification Results

| Check | Status |
|---|---|
| `grep -rEn "^\s*emit\(" app/modules/auth app/integrations/telegram app/core` | PASS (no matches) |
| `grep -rE 'logger\.(warning|info)\("telegram_(unknown_start|replay_attempt|dm_blocked|dm_failed)"'` | PASS (no matches) |
| `grep "from app.core import audit"` in service.py / router.py / telegram_service.py / dependencies.py | PASS (4 files) |
| `grep "from app.core.audit import emit as audit_emit"` in handlers.py | PASS |
| `cd apps/backend && uv run ruff check` (full project) | PASS |
| `cd apps/backend && uv run mypy --strict app/` (54 source files) | PASS |
| `cd apps/backend && uv run lint-imports` (3 contracts) | PASS — 3 KEPT, 0 broken |

## Task Commits

1. **Task 1** — `41dfdb2` — `refactor(08-05): migrate auth/service.py emit() to async audit.emit + Pitfall 2 reorder`
2. **Task 2** — `7aacb56` — `refactor(08-05): migrate auth/router.py + telegram_service.py + dependencies.py to async audit.emit`
3. **Task 3** — `bdbe3f7` — `refactor(08-05): convert 4 logger.warning/info to await audit_emit in handlers.py (Pitfall 3)`

## Decisions Made

- **Rule 3 (auto-fix blocking issue) — `dependencies.py` migration not in plan.** The plan enumerates 13 call-sites (5 service + 1 router + 3 telegram_service + 4 handlers). However, `app/core/dependencies.py` had 2 additional `emit(...)` calls (`rbac_forbidden`, `csrf_mismatch`) that used the OLD sync signature. After Plan 02 (which made `emit` async), these failed mypy with 10 errors. Without fixing them, `mypy --strict app/` would not be GREEN — violating the plan's verification block (`uv run mypy --strict app/` MUST exit 0). The fix:
  - Injected `session: Annotated[AsyncSession, Depends(get_db)]` into `_checker` (require_permission factory) and `verify_csrf` — both are FastAPI deps so signature-dep injection is the canonical wiring.
  - Mapped `rbac_forbidden` → `actor_user_id=user.id, resource_type=resource.value` (the Resource enum value of the gated route).
  - Mapped `csrf_mismatch` → `actor_user_id=None, resource_type='csrf'` (CSRF runs before auth dep per D-23, so caller identity is not yet resolved).
- **`consume()` flow re-ordering.** Original: `consumed_at = now → user_id check → commit → load user`. New: `consumed_at = now → user_id check → load user → emit → commit`. The user load happens before the final commit; this is correct because `User` row was set during a prior commit (in `commit_otp`) — we are reading committed data via the same session. Pitfall 2 alignment is the win: emit and consumed_at-stamp now commit atomically.
- **`family_reuse_detected` emit moved INSIDE `async with session.begin():` block.** Original code had emit AFTER the begin block exited — meaning the audit row would never have committed (the block already closed). Moving it inside ensures the AuditLog INSERT enrolls in the same transaction as the family revocation UPDATE, and both commit atomically when the block exits cleanly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] Migrate `app/core/dependencies.py` emit call-sites**
- **Found during:** Task 2 (running `mypy --strict app/modules/auth/router.py app/modules/auth/telegram_service.py` triggered errors in dependencies.py too)
- **Issue:** Plan enumerated 13 call-sites; 2 more existed in `app/core/dependencies.py` (`rbac_forbidden` line 131, `csrf_mismatch` line 196) using the old sync signature. Plan 02 made `emit` async, so these 2 calls produced 10 mypy errors — codebase would not compile.
- **Fix:** Migrated both to `await audit.emit(session, ...)`. Added `session: Annotated[AsyncSession, Depends(get_db)]` to `_checker` (require_permission factory closure) and to `verify_csrf` signature so the new async signature has its required first arg. Updated import.
- **D-04 mapping invented for these 2 events** (not in plan's interfaces table — out-of-scope additions): `rbac_forbidden → user.id / resource.value`; `csrf_mismatch → None / 'csrf'`.
- **Files modified:** `apps/backend/app/core/dependencies.py`
- **Commit:** `7aacb56` (folded into Task 2 commit)

**2. [Rule 3 — Blocking issue] `consume()` ordering refactor in telegram_service.py**
- **Found during:** Task 2 emit insertion
- **Issue:** Original `consume()` did `consumed_at-stamp → commit → load user → emit`. The plan requires emit BEFORE commit, but the only commit was BEFORE the user lookup needed for `actor_user_id=user.id`.
- **Fix:** Re-ordered to `consumed_at-stamp → load user → emit (with user.id) → commit`. Kept the defensive `user_id is None` branch's commit (it returns early). Equivalent semantics; emit now precedes the consumed_at commit.
- **Files modified:** `apps/backend/app/modules/auth/telegram_service.py`
- **Commit:** `7aacb56` (folded into Task 2)

**3. [Rule 3 — Blocking issue] `family_reuse_detected` emit needed to move INSIDE begin block**
- **Found during:** Task 1 implementation
- **Issue:** Original code had `emit("family_reuse_detected", ...)` AFTER the `async with session.begin():` block had already exited. Under the new co-transactional contract, the AuditLog row enrolls in the session's transaction — but if the begin block has already auto-committed, the row sits in a NEW autobegun tx that will be discarded when the function raises `InvalidAccessToken`.
- **Fix:** Moved the `await audit.emit(...)` inside the begin block, after the family-revocation UPDATE and before the implicit commit on block exit. The two writes now commit atomically.
- **Files modified:** `apps/backend/app/modules/auth/service.py`
- **Commit:** `41dfdb2`

## Issues Encountered

- **Tests for `dependencies.py` audit emit will need updating in Plan 08-08.** `tests/unit/test_dependencies_require_authenticated.py` exists and asserts on the emit behaviour. It is out of scope for this plan (test migration is Plan 08-08 territory). Behaviour change: `_checker` and `verify_csrf` now require an extra signature dep (`session`), so any test that constructs them without FastAPI dep injection will fail. Plan 08-08 owns those test updates.

## Threat Surface Scan

No new security-relevant surface introduced. The 2 Rule-3 events (`rbac_forbidden`, `csrf_mismatch`) were already structlog-emitted; this plan promotes them to DB rows but does not add any new ingress/egress, schema change, or trust boundary.

The `from app.core.audit import emit as audit_emit` import in `app/integrations/telegram/handlers.py` was an explicit threat in T-08-28 — verified by `lint-imports` GREEN (3 contracts KEPT). `app.integrations → app.core` is permitted; `app.integrations → app.modules` is forbidden — neither is violated.

## Self-Check: PASSED

- `apps/backend/app/modules/auth/service.py` — `await audit.emit` present; old `from app.core.audit import emit` removed; old `emit(` call-sites zero. Verified via grep + ruff/mypy.
- `apps/backend/app/modules/auth/router.py` — same. Verified.
- `apps/backend/app/modules/auth/telegram_service.py` — same. Verified.
- `apps/backend/app/integrations/telegram/handlers.py` — `await audit_emit` present (4 sites); old `logger.warning/info` for the 4 telegram audit events removed. Verified via grep.
- `apps/backend/app/core/dependencies.py` — `await audit.emit` present (2 sites); session injected into both deps. Verified.
- Commits `41dfdb2`, `7aacb56`, `bdbe3f7` all present in `git log --oneline -5` of this worktree branch. Verified.
- `cd apps/backend && uv run ruff check && uv run mypy --strict app/ && uv run lint-imports` exits 0 across the board. Verified.

---
*Phase: 08-clients-module-audit-log*
*Plan: 05*
*Completed: 2026-05-03*
