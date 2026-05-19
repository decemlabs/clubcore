---
phase: 43-multi-user-admin-module
plan: 04
subsystem: api
tags: [users, repository, sqlalchemy, async, password_reset_tokens, invitation, soft-delete]

# Dependency graph
requires:
  - phase: 41-infra-bedrock-anti-oracle-scaffold
    provides: "User ORM hoist (D-41-01), password_reset_tokens table + partial UNIQUE (D-41-04/05), Role/Resource permissions"
  - phase: 43/01
    provides: "Migration 0030 + User ORM lifecycle columns (is_active, status, deactivated_at, deactivated_by_user_id), password_hash nullable"
  - phase: 43/02
    provides: "users/schemas.py (UserListQuery, UserListItemResponse, UserCreateRequest), users/constants.py (INVITATION_TOKEN_TTL)"
provides:
  - "apps/backend/app/modules/users/repository.py — pure-SQL chokepoints for users module (12 async functions)"
  - "get_alive / list_alive partition pattern (mirror clients/repository.py)"
  - "Invitation-token CRUD: insert / consume-by-user / consume-by-id / get-by-id, all UPDATE...RETURNING race-tight"
  - "Last-owner guard: count_active_owners_excluding with SELECT...FOR UPDATE serial-arbiter"
  - "Stable signature surface that 43-05 (service) orchestrates against"
affects: [43-05-service, 43-06-router, 43-07-refresh-extension, 44-invite-accept]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Repository owns no commit/flush — service owns transactional moment (D-03 / D-43-09)"
    - "LEFT JOIN subquery (MAX over GROUP BY) to populate computed columns on list responses"
    - "Atomic-consume via UPDATE...RETURNING for race-tight token consumption (mirrors v1.1 refresh rotation)"
    - "SELECT count(*) ... FOR UPDATE as last-owner serial-arbiter (mirrors v1.2 freeze-period guard)"

key-files:
  created:
    - "apps/backend/app/modules/users/repository.py — 12 async functions, 0 commit/flush"
  modified: []

key-decisions:
  - "Used GROUP BY MAX(expires_at) subquery for invitation_expires_at (LEFT JOIN-safe vs DISTINCT ON which would require PG-specific syntax)"
  - "Confirmed PasswordResetToken import path: app.modules.auth.password_reset_token_model (matches D-41-04 / Phase 41 plan 09)"
  - "_now_utc() helper centralises tz=UTC writes (Pitfall 6 mitigation; one call site per timestamped UPDATE)"
  - "PaginatedData.model_construct used (mirrors clients repo pattern — items are already validated Pydantic instances)"

patterns-established:
  - "Two-tier consume primitive: consume-by-user-id (re-invite path) + consume-by-token-id (owner revoke path) — both UPDATE...RETURNING"
  - "Hash helper _hash_token() colocated with token INSERT — keeps the SHA-256 contract (D-41-04) in one file"

requirements-completed: [USERS-01, USERS-02, USERS-03]

# Metrics
duration: 6min
completed: 2026-05-19
---

# Phase 43 Plan 04: Users Repository Summary

**Pure-SQL users repository: list_alive with active-invitation LEFT JOIN, get_alive partition, idempotent re-invite via UPDATE...RETURNING, last-owner FOR UPDATE guard — zero commit/flush per D-43-09.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-19T14:06:00Z
- **Completed:** 2026-05-19T14:12:09Z
- **Tasks:** 1
- **Files modified:** 1 (created)

## Accomplishments
- Landed `apps/backend/app/modules/users/repository.py` with exactly 12 async functions covering the full users + invitation-token surface.
- `list_alive` constructs a LEFT JOIN subquery against `password_reset_tokens` (purpose='invitation', consumed_at IS NULL, expires_at > now()) aggregated via `MAX(expires_at)`, populating `invitation_expires_at` on every list item (D-43-10).
- `count_active_owners_excluding` uses `.with_for_update()` to serialise concurrent deactivate attempts on the last owner (D-43-16).
- Both atomic-consume primitives (`consume_active_invitation_for_user`, `atomic_consume_invitation_token_by_id`) use `UPDATE ... RETURNING` — race-tight against parallel `POST /users` (re-invite) and `POST /invitations/{id}/revoke` (owner revoke).
- `soft_delete_user` uses `COALESCE(User.deactivated_at, now())` so the column-consistency CHECK constraint (migration 0030) holds for both delete-after-deactivate and pure-delete paths.
- ruff + mypy --strict green.

## Function Inventory

| Function | Purpose | Decision |
|---|---|---|
| `get_alive` | Lookup alive user by id | D-43-09 |
| `get_by_email_for_create` | Lookup alive user by lowercased email (re-invite branching) | D-43-13 |
| `list_alive` | Paginated list + LEFT JOIN invitation_expires_at | D-43-10/15 |
| `insert_user_pending_invitation` | INSERT new pending_invitation user | D-43-13 1st branch |
| `insert_invitation_token` | INSERT password_reset_tokens row purpose='invitation' | D-43-13 / D-41-04 |
| `consume_active_invitation_for_user` | Atomic-consume active invitation by user_id (re-invite path) | D-43-13 2nd branch |
| `deactivate_user` | Flip is_active=false + set deactivated_at/by | D-43-16 |
| `reactivate_user` | Flip is_active=true + clear deactivated_* | D-43-17 |
| `soft_delete_user` | Set deleted_at=now() + is_active=false + COALESCE deactivated_at | D-43-18 |
| `get_invitation_token_by_id` | Lookup token by id (purpose='invitation' filter) | D-43-19 |
| `atomic_consume_invitation_token_by_id` | Atomic-consume by token id (owner revoke) | D-43-19 |
| `count_active_owners_excluding` | Last-owner guard with FOR UPDATE | D-43-16 |

## Task Commits

1. **Task 1: Create apps/backend/app/modules/users/repository.py** — `b1dd309` (feat)

**Plan metadata commit:** _(pending after this summary)_

## Files Created/Modified
- `apps/backend/app/modules/users/repository.py` — 12 async functions, 0 commit/flush, atomic-consume primitives, FOR UPDATE last-owner guard.

## Decisions Made

- **LEFT JOIN subquery (GROUP BY MAX) for `invitation_expires_at` over DISTINCT ON**: portable across SQLAlchemy backends; matches the aggregate semantics the schema requires (one expires_at per user) without locking the implementation into PG-specific `DISTINCT ON` syntax. Subquery is fine performance-wise (single index lookup on the small `password_reset_tokens` table; partial UNIQUE on `(user_id, purpose) WHERE consumed_at IS NULL` already constrains the row count per user to ≤1).
- **PasswordResetToken import path confirmed**: `from app.modules.auth.password_reset_token_model import PasswordResetToken` (matches D-41-04 + Phase 41 plan 09 STATE entry — `password_reset_token_model.py` is the canonical module name).
- **`_now_utc()` helper centralises tz=UTC writes** (Pitfall 6) — single audit point if the timezone discipline ever changes.
- **`PaginatedData.model_construct` over `PaginatedData(...)`** — mirrors clients/repository.py pattern; items are already-validated Pydantic instances (we just built them above) so re-validation is wasted work.
- **`get_by_email_for_create` filters `deleted_at IS NULL`** — soft-deleted rows are intentionally invisible to the create-path branching logic; the partial UNIQUE on `lower(email) WHERE deleted_at IS NULL` (Phase 41 0022) then permits the new INSERT for an email reclaimed after soft-delete (D-43-13 4th bullet / Pitfall 4 INSERT-only invariant).

## D-03 Invariant Verified

`grep -c 'session.commit()' repository.py` → 0
`grep -c 'session.flush()' repository.py` → 0
`grep -c '.returning(' repository.py` → 2 (consume-by-user + consume-by-id)
`grep -c 'with_for_update' repository.py` → 1 (last-owner guard)

## Deviations from Plan

None - plan executed exactly as written, with one cosmetic adjustment:

### Auto-fixed Issues

**1. [Rule 3 - Blocking] mypy `no-any-return` on `session.scalar(...)` direct return**
- **Found during:** Task 1 verification
- **Issue:** `mypy --strict` flagged 3 returns of `Any` from functions declared `User | None` / `PasswordResetToken | None`. SQLAlchemy 2.0's `session.scalar()` returns `Any` so a direct `return await session.scalar(stmt)` cannot satisfy `--strict`.
- **Fix:** Bound the result to a typed local (`result: User | None = await session.scalar(stmt); return result`) — mirrors the existing pattern in `apps/backend/app/modules/clients/repository.py:53-54`.
- **Files modified:** apps/backend/app/modules/users/repository.py (3 functions)
- **Verification:** `uv run mypy --strict app/modules/users/repository.py` → `Success: no issues found in 1 source file`.
- **Committed in:** b1dd309 (task commit)

**2. [Rule 3 - Blocking] ruff E501 on docstring line**
- **Found during:** Task 1 verification
- **Issue:** `reactivate_user` docstring carried the full CHECK constraint on one line (104 chars > 100 limit).
- **Fix:** Wrapped the CHECK expression across two lines inside the docstring.
- **Files modified:** apps/backend/app/modules/users/repository.py
- **Verification:** `uv run ruff check` → `All checks passed!`
- **Committed in:** b1dd309 (task commit)

**3. [Rule 1 - Bug] Docstring literal "session.commit()" / "session.flush()" tripped acceptance grep**
- **Found during:** Task 1 acceptance criteria grep
- **Issue:** Plan acceptance criteria require `grep -c 'session.commit()'` → 0 and `grep -c 'session.flush()'` → 0. Two docstring references to "session.commit()" and one to "session.flush()" failed the literal check.
- **Fix:** Reworded the docstring references to "commit"/"flush" without parens so the spirit (no actual calls) and the literal grep both pass.
- **Files modified:** apps/backend/app/modules/users/repository.py (module + 1 function docstring)
- **Verification:** Both `grep -c` checks now return 0.
- **Committed in:** b1dd309 (task commit)

---

**Total deviations:** 3 auto-fixed (2 Rule 3 blocking — type/lint hygiene; 1 Rule 1 — docstring matching plan acceptance grep)
**Impact on plan:** All three were minor — needed to land mypy --strict + ruff + grep-acceptance green. No design changes; no scope creep.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Self-Check: PASSED

Verification commands run post-write:

- `[ -f apps/backend/app/modules/users/repository.py ]` → FOUND
- `git log --oneline --all | grep -q b1dd309` → FOUND (b1dd309 feat(43-04): add users repository)
- `uv run ruff check app/modules/users/repository.py` → PASS
- `uv run mypy --strict app/modules/users/repository.py` → PASS
- 12/12 async functions verified via inspect.iscoroutinefunction
- 14 of 14 acceptance grep checks pass (10 function presence + 1 with_for_update + 2 returning + 1 each commit/flush absence)

## Next Phase Readiness

- **43-05 (service.py) is unblocked**: can now `from app.modules.users import repository` and orchestrate the 6 endpoint workflows (create / list / deactivate / reactivate / soft-delete / revoke-invitation) against the stable signatures.
- **No new ORM tables introduced** — REG-29-04 eager-import discipline (D-43-32) confirmed clean; no changes needed to `tests/unit/test_workers_eager_import.py`.
- **D-43-OWNER-COPY-LOCK** (Plan 02) and **D-43-RUNTIME-WIRING** (Plan 03) already landed — Wave 2 plan 43-05 has all its dependencies in place.

---
*Phase: 43-multi-user-admin-module*
*Completed: 2026-05-19*
