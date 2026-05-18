---
phase: 41-infra-bedrock-anti-oracle-scaffold
plan: 09
subsystem: database
tags: [alembic, postgres, sqlalchemy, password-reset, partial-unique, eager-import]

requires:
  - phase: 41-infra-bedrock-anti-oracle-scaffold
    provides: Migration 0024 (down_revision target), User ORM hoist to app.core.models (FK target), CONTEXT D-41-03/04/05/29 decisions
provides:
  - Alembic migration 0025_password_reset_tokens (unified table per D-41-04)
  - Partial UNIQUE (user_id, purpose) WHERE consumed_at IS NULL (D-41-05)
  - PasswordResetToken ORM model at app.modules.auth.password_reset_token_model
  - Eager-import in app/workers/__init__.py (REG-29-04 / D-41-29 mirror)
  - tests/unit/test_workers_eager_import.py asserting password_reset_tokens visibility from worker root
  - Pre-existing alembic-check drift catalogued in deferred-items.md (out-of-scope per SCOPE BOUNDARY)
affects: ["44-invitation-reset", "45-email-notifications"]

tech-stack:
  added: []
  patterns:
    - "Per-table eager-import discipline in workers/__init__.py (REG-29-04 mirror) — new ORM tables that any cron one-shot may indirectly touch get explicit module-load side effects"
    - "Partial-UNIQUE name parity between Alembic migration op.create_index() and ORM __table_args__ Index (mirrors uq_bookings_slot_confirmed pattern from 0017)"
    - "Test pins eager-import discipline as code — REG-29-04 regression class can no longer recur silently"

key-files:
  created:
    - "apps/backend/alembic/versions/0025_password_reset_tokens.py"
    - "apps/backend/app/modules/auth/password_reset_token_model.py"
    - "apps/backend/tests/unit/test_workers_eager_import.py"
    - ".planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md"
  modified:
    - "apps/backend/app/workers/__init__.py"
    - "apps/backend/alembic/env.py"

key-decisions:
  - "Phase 41 Plan 09: INFRA-38 closed — Alembic 0025 ships unified password_reset_tokens with purpose discriminator + partial UNIQUE per (user_id, purpose) WHERE consumed_at IS NULL + non-unique ix_password_reset_tokens_token_hash for Phase 44 atomic-consume path. Round-trip clean (0024 ↔ 0025). Live partial-UNIQUE verified (one NULL + one NOT NULL coexist; two NULL rejected; cross-purpose NULL coexists)."
  - "PasswordResetToken ORM declares Index/CheckConstraint name letter-identical to migration so alembic check on the new table is clean. Pre-existing v1.5/v1.6 drift (users.deleted_at, users.email global UNIQUE, notification.channel) remains catalogued in deferred-items.md and is owned by Phases 43/45 per D-41-07."
  - "REG-29-04 discipline pinned as code in tests/unit/test_workers_eager_import.py — no such test existed before this plan (grep'd tests for 'Base.metadata.tables' returned zero results); two assertions: password_reset_tokens visibility + v1.5 critical-tables smoke (memberships / membership_notifications / bookings / booking_notifications)."

patterns-established:
  - "ORM ↔ migration name-parity rule for partial-UNIQUE: literal name appears in both op.create_index() and Index(__table_args__) declaration — no name in NAMING_CONVENTION skiplist needed because SQLAlchemy round-trips postgresql_where text byte-identically"
  - "Eager-import block in workers/__init__.py uses # noqa: F401 with a contextual trailing comment (`# Phase NN <REQ> / <D-NN-NN> — <table-name>`); ruff sort places the new line alphabetically by module path"
  - "Test enforcement of eager-import discipline lives in tests/unit/test_workers_eager_import.py with TWO assertions per new table: contract-pin + v1.5 critical-tables smoke — guards against accidental import-order regression"

requirements-completed: [INFRA-38]

duration: ~12min
completed: 2026-05-18
---

# Phase 41 Plan 09: INFRA-38 closeout — password_reset_tokens unified table Summary

**Alembic 0025 + PasswordResetToken ORM + workers eager-import + REG-29-04 test — completing the fourth and final v1.6 INFRA-bedrock migration so Phase 44 ships zero migrations.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-18T19:16:00Z
- **Completed:** 2026-05-18T19:28:16Z
- **Tasks:** 3 / 3
- **Files modified:** 5 (4 created + 1 modified + 1 modified env.py for autogenerate registration; 1 deferred-items.md doc artefact)

## Accomplishments

- Migration 0025 lands `password_reset_tokens` (9 columns + 2 indexes) — fourth and final v1.6 schema bedrock migration; Phase 44 RESET-01 now ships zero migrations per D-41-03.
- Partial UNIQUE `uq_password_reset_tokens_active` on `(user_id, purpose) WHERE consumed_at IS NULL` (D-41-05) live-verified: one NULL + one NOT NULL coexist; two NULL rejected with constraint-named IntegrityError; cross-purpose NULL coexist.
- Non-UNIQUE `ix_password_reset_tokens_token_hash` supports Phase 44's atomic-consume `UPDATE … WHERE token_hash = ? AND purpose = ? AND consumed_at IS NULL RETURNING …` path.
- PasswordResetToken ORM (`app/modules/auth/password_reset_token_model.py`) mirrors migration letter-for-letter; `alembic check` is clean for this table (the broader pre-existing v1.5/v1.6 drift remains catalogued in `deferred-items.md`).
- REG-29-04 discipline pinned as code: `app/workers/__init__.py` eager-imports `PasswordResetToken`; `tests/unit/test_workers_eager_import.py` (newly created — no prior eager-import test existed under any name) asserts both `password_reset_tokens` visibility AND v1.5 critical-tables smoke (memberships, membership_notifications, bookings, booking_notifications) so future import-order regressions fail at unit test time, not at the 06:05 cron tick.

## Task Commits

1. **Task 1: Author Alembic migration 0025_password_reset_tokens.py** — `951cb52` (feat)
2. **Task 2: ORM model PasswordResetToken + alembic/env.py registration** — `f6787b5` (feat)
3. **Task 3: Eager-import in workers + extend eager-import test** — `d2642f1` (feat)

## Files Created/Modified

- `apps/backend/alembic/versions/0025_password_reset_tokens.py` — Migration 0025 (revision id `0025_password_reset_tokens`, down_revision `0024_notif_channel_discriminator`). Long docstring cites D-41-03/04/05 and explains the four design pillars: DB-table over itsdangerous, hash-at-rest, atomic-consume semantics, deferred cleanup cron.
- `apps/backend/app/modules/auth/password_reset_token_model.py` — PasswordResetToken ORM class with 6 declared columns + UUIDPkMixin + TimestampMixin; `__table_args__` carries the CheckConstraint + partial Index + non-unique hash Index; no `relationship()` to User per D-41-04 footnote.
- `apps/backend/app/workers/__init__.py` — Adds eager-import block with header comment documenting REG-29-04 rule. Ruff sorted the new import alphabetically before `app.workers.scheduled.*`.
- `apps/backend/tests/unit/test_workers_eager_import.py` — NEW. Two tests: `test_password_reset_tokens_eager_imported` (contract pin) + `test_v15_critical_tables_still_visible` (regression smoke).
- `apps/backend/alembic/env.py` — Registers `import app.modules.auth.password_reset_token_model` so autogenerate sees the model. Mechanical one-line addition to the existing registration block.
- `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md` — Catalogues pre-existing `alembic check` drift (users.email global UNIQUE still on ORM, users.deleted_at missing from ORM, notification.channel missing from ORM) — all owned by later phases per D-41-07 / 41-05 SUMMARY / 41-08 SUMMARY.

## Decisions Made

- **Migration docstring as load-bearing context.** The 0025 file carries a ~60-line docstring covering: (a) why DB-table over stateless tokens — `password_changed_at` collision with USERS-03; (b) hash-at-rest discipline + T-41-09-01 threat mitigation; (c) `consumed_at` carries both redeem AND revoke semantics (single column keeps the atomic-consume SQL a single literal predicate); (d) cleanup cron explicitly deferred to Phase 44. Future maintainers reading 0025 should not need to cross-reference 41-CONTEXT.md to understand the shape.
- **Partial-UNIQUE round-trip via ORM `Index` not `UniqueConstraint`.** Followed the bookings precedent (`uq_bookings_slot_confirmed` in `apps/backend/app/modules/bookings/models.py:165`) — `Index(..., unique=True, postgresql_where=text(...))` declared in `__table_args__` matches the migration's `op.create_index(..., unique=True, postgresql_where=text(...))` byte-for-byte; SQLAlchemy compares the `postgresql_where` SQL text and `alembic check` is clean WITHOUT needing to add the constraint name to `env.py:_include_object` skiplist. This is the v1.4+ pattern for partial-UNIQUE round-trip.
- **env.py registration was Rule 2 deviation.** Plan did not call out the `alembic/env.py` ORM-registration block, but without it `alembic check` reports `Detected removed table 'password_reset_tokens'` — the entire point of the ORM model failing-loud parity is undermined. Added the one-line `import app.modules.auth.password_reset_token_model` in alphabetical position alongside the other model registrations. Logged as Rule 2 in the Deviations section below.
- **Pre-existing alembic drift documented separately, not fixed here.** `alembic check` after Plan 41-09 still reports drift on `users.email` (global UNIQUE removed in 41-05 migration 0022 but ORM `User.email` still has `unique=True`), `users.deleted_at` (added in 0022 but absent from ORM), and the channel-discriminator columns on `booking_notifications` / `membership_notifications` (added in 0024 but absent from those ORMs). All three drift sources are out-of-scope per the SCOPE BOUNDARY rule — they are not caused by 41-09's changes — and are catalogued in `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md` for the appropriate owning phases (43 / 43 / 45 respectively per D-41-07 and the 41-08 SUMMARY note).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Register new ORM module in alembic/env.py**

- **Found during:** Task 2 (ORM model creation)
- **Issue:** After authoring the PasswordResetToken ORM and running `alembic check`, autogenerate reported `Detected removed table 'password_reset_tokens'` because `alembic/env.py` enumerates each ORM module by explicit `import` (see lines 24-35), and the new module was not yet in that list. Without registration, the entire point of ORM↔migration parity — failing loud when an ORM mapping drifts from the schema — is silently undermined for this table.
- **Fix:** Added `import app.modules.auth.password_reset_token_model  # Phase 41 INFRA-38 / 0025 — D-41-04` to the registration block, alphabetically grouped with the other `app.modules.auth.*` import.
- **Files modified:** `apps/backend/alembic/env.py`
- **Verification:** `alembic check` no longer reports drift on `password_reset_tokens` (other pre-existing drift unchanged — see deferred-items.md). Ruff + mypy strict clean.
- **Committed in:** `f6787b5` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 missing critical)
**Impact on plan:** The env.py registration was implicit in "ORM must be importable and parity must hold." Adding it ensured the ORM↔migration parity is actually enforceable for `password_reset_tokens` going forward. No scope creep.

## Issues Encountered

- **Initial live partial-UNIQUE test had transaction-scope bug.** First run used a single `e.connect()` with implicit transaction management; the IntegrityError from the case-2 assertion-of-rejection rolled back the seed user along with the failed INSERT, breaking case 3's FK lookup. Fixed by switching to explicit `async with e.begin()` blocks per case so each transaction commits/rolls back independently. The schema itself was correct from the first invocation; only the live-verify harness needed adjusting.

- **`alembic check` reports broader drift unrelated to this plan.** The remaining drift (users.email global UNIQUE, users.deleted_at, booking_notifications.channel, membership_notifications.channel) is pre-existing from plans 41-05 (D-41-07 — Phase 43 owns User ORM) and 41-08 (channel column ORM addition deferred to Phase 45). Catalogued in deferred-items.md to prevent re-discovery; explicitly out-of-scope per the SCOPE BOUNDARY rule.

## User Setup Required

None — purely schema + Python infrastructure; no external services touched. The database migration `0025_password_reset_tokens` applied cleanly against the running Postgres 16 instance via `uv run alembic upgrade head`.

## Next Phase Readiness

- **INFRA-38 closed.** All four v1.6 schema migrations (0022, 0023, 0024, 0025) are in. ROADMAP Success Criterion 4 GREEN for Phase 41.
- **Plan 41-10 (SVC001 scope extension) unblocked.** SVC001 walker scope extension references `app/modules/auth/password_reset_service.py` (D-41-28) — that future file will operate on the `password_reset_tokens` table this plan provides. The walker treats "expected target file absent at Phase 41 commit time" as a hard fail per D-41-28, which is the intended anti-silent-drop discipline.
- **Phase 44 has zero migrations remaining.** RESET-01 / RESET-03 / RESET-05 ship pure application code against the schema delivered here. The atomic-consume `UPDATE … WHERE token_hash = ? AND purpose = ? AND consumed_at IS NULL RETURNING …` predicate matches the (partial-UNIQUE + hash-Index + check-constraint) shape committed in 0025; threat T-41-09-02 (token replay) is structurally mitigated.
- **REG-29-04 discipline now testable as code.** Phases 42 (`email_send_log`) and 45 (`payment_receipts`) will add their own eager-import lines + extend `test_v15_critical_tables_still_visible` with their own table assertions, following the pattern this plan establishes.

## Self-Check: PASSED

- `apps/backend/alembic/versions/0025_password_reset_tokens.py` — FOUND
- `apps/backend/app/modules/auth/password_reset_token_model.py` — FOUND
- `apps/backend/tests/unit/test_workers_eager_import.py` — FOUND
- `apps/backend/app/workers/__init__.py` — modified (eager-import block + header comment), FOUND
- `apps/backend/alembic/env.py` — modified (one-line ORM registration), FOUND
- `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md` — FOUND
- Commits `951cb52`, `f6787b5`, `d2642f1` — all FOUND in `git log --oneline --all`
- Live database state: `alembic current` reports `0025_password_reset_tokens (head)`; `password_reset_tokens` table exists with 9 columns + 2 indexes (verified via async inspector and live INSERT round-trip)
- `uv run pytest tests/unit/test_workers_eager_import.py -x -q` → 2 passed in 0.02s

---
*Phase: 41-infra-bedrock-anti-oracle-scaffold*
*Completed: 2026-05-18*
