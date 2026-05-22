---
phase: 50-webhook-fsm-fiscal-foundation
plan: 03
subsystem: payments
tags: [yookassa, webhook, fsm, payment-recorder, activator, protocol, alembic, audit, blocker-resolution]

# Dependency graph
requires:
  - phase: 47-bedrock
    provides: MembershipActivator + PtPackageActivator Protocol slots (declared)
  - phase: 49-online-sales-orchestrator
    provides: OnlinePayment ORM + Phase 49 activator stub wiring + PaymentRecorder Protocol baseline
  - phase: 50-webhook-fsm-fiscal-foundation/50-01
    provides: Alembic 0035 fiscal_receipts table (chain anchor for 0036)
  - phase: 50-webhook-fsm-fiscal-foundation/50-02
    provides: 2 new LOCKED audit events (membership_activated_online + pt_package_activated_online) + payload schemas
provides:
  - MembershipActivator + PtPackageActivator Protocols with `online_payment_id` kwarg (Blocker #3 resolved)
  - PaymentRecorder Protocol widened to accept Optional audit_actor + Optional received_by_user_id (Blocker #2 resolved)
  - activate_membership_from_webhook + activate_pt_package_from_webhook bodies (D-50-22, D-50-24)
  - record_payment body that handles None audit_actor + None received_by_user_id
  - Alembic 0036: payments.received_by_user_id nullable
  - PaymentRecordedPayload.received_by_user_id widened to UUID | None
affects: [50-04 webhook-router-and-handlers, 51-fiscal-receipts-dispatch, 52-notifications]

# Tech tracking
tech-stack:
  added: []  # no new libraries — purely Protocol-shape + body + migration work
  patterns:
    - "Activator Protocol kwarg naming: `online_payment_id` carries the OnlinePayment seed UUID (activator CREATES Membership/PtPackage; no pre-INSERT pending row)"
    - "Optional-widening for anonymous flows: Protocol kwargs default to None, body guards `audit_actor.id` access, audit emit becomes system emit"
    - "Caller-owns-txn discipline preserved across new activator bodies — only flush() to populate id; no commit() or session.begin() inside activator"
    - "Cross-module narrow read pattern: activator SELECTs OnlinePayment via raw SQL `text()` to respect modules-independent importlinter contract (D-49-13 lineage)"

key-files:
  created:
    - apps/backend/tests/unit/test_activator_protocol_kwargs.py
    - apps/backend/tests/unit/test_payment_recorder_widened.py
    - apps/backend/tests/integration/online_payments/test_activate_from_webhook.py
    - apps/backend/tests/integration/online_payments/test_record_payment_handles_none.py
    - apps/backend/alembic/versions/0036_payments_received_by_user_id_nullable.py
  modified:
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/app/modules/memberships/service.py
    - apps/backend/app/modules/pt_packages/service.py
    - apps/backend/app/modules/payments/models.py
    - apps/backend/app/modules/payments/repository.py
    - apps/backend/app/modules/payments/service.py
    - .planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md

key-decisions:
  - "Blocker #1 — reused existing `InvalidTransitionError` rather than declaring new `IllegalTransitionError`; activator path does not raise it (that's Plan 50-04's handler scope), but the import-stable choice avoids new exception surface"
  - "Blocker #2 option (b) — widened PaymentRecorder Protocol with additive None defaults instead of synthesising a system actor; Alembic 0036 flips the column to nullable to match; PaymentRecordedPayload.received_by_user_id widened to UUID | None (Rule 2 add — without payload widening Pydantic validation would reject the None case)"
  - "Blocker #3 — renamed activator kwarg to `online_payment_id` in BOTH activators; the kwarg carries the OnlinePayment row UUID and the activator CREATES the Membership/PtPackage from the seed (Phase 49 sell flow never pre-INSERTs because Membership.status CHECK has no 'pending' value)"
  - "Cross-module read in activator uses raw SQL text() instead of importing OnlinePayment ORM — preserves modules-independent contract without adding a new importlinter ignore line"
  - "audit_correlation_id cast to str for JSONB-serialisability (mirror create_membership pattern at memberships/service.py:759)"

patterns-established:
  - "Activator body shape: SELECT seed (narrow raw SQL) -> resolve plan -> compute dates -> INSERT instance with status='active' + snapshots -> flush -> emit single LOCKED event (system emit, no actor) -> return row; caller owns commit"
  - "Anonymous Protocol widening: default to None + guard every attribute access; audit payload schema must also accept None to avoid Pydantic ValidationError at emit time"
  - "Blocker #6 enforcement: exactly ONE canonical emit per locked event — activator emits only `*_activated_online`, NEVER `*_created` / `*_sold` (those locked events are reserved for in-person sell flow)"
  - "TDD RED/GREEN per task: failing test commit first, then implementation commit; each task's commits stay atomic and the per-task tests cover the regression surface"

requirements-completed: [WH-05]

# Metrics
duration: 23min
completed: 2026-05-22
---

# Phase 50 Plan 03: Activator Kwarg Rename + PaymentRecorder Widening + Activator Body Fills Summary

**Renamed activator Protocol kwargs to `online_payment_id`, widened `PaymentRecorder` to accept Optional audit_actor + received_by_user_id with backing Alembic 0036 + ORM + payload schema, and filled the Phase 49 `activate_*_from_webhook` stubs so the webhook handler (Plan 50-04) has a working activation surface.**

## Performance

- **Duration:** 23 min
- **Started:** 2026-05-22T16:55:57Z
- **Completed:** 2026-05-22T17:18:51Z
- **Tasks:** 3 (each TDD: RED test commit -> GREEN impl commit)
- **Files modified:** 8 (+ 5 created)

## Accomplishments

- **Blocker #2 resolved:** `PaymentRecorder.__call__` widened so both `audit_actor: CurrentUser | None = None` and `received_by_user_id: UUID | None = None`. `record_payment` body guards `audit_actor.id` access; emit becomes system emit (actor_user_id=None per INFRA-39) when no operator is present. Alembic 0036 flips `payments.received_by_user_id` to nullable; ORM column + repository signature + `PaymentRecordedPayload.received_by_user_id` widened to match. 31 existing in-person sell/create integration tests still green — widening is purely additive.
- **Blocker #3 resolved:** `MembershipActivator` + `PtPackageActivator` Protocols renamed kwarg from `membership_id`/`pt_package_id` to `online_payment_id`. The activator now correctly receives the OnlinePayment row UUID and CREATES the Membership/PtPackage from that seed (Phase 49 sell flow does not pre-INSERT either; Membership.status CHECK has no 'pending' staging value).
- **Activator bodies filled (D-50-22, D-50-24):** Both `activate_membership_from_webhook` and `activate_pt_package_from_webhook` shipped functional bodies. Each SELECTs the OnlinePayment row via narrow raw SQL (`text()`) so the modules-independent importlinter contract is preserved without adding a new ignore line, resolves the plan via the existing repository, server-computes dates in Europe/Moscow, INSERTs the instance row with `status='active'` and full snapshot suite, flushes, and emits the new LOCKED audit event with `actor_user_id=None`. Blocker #6 honored: only `*_activated_online` is emitted, NEVER `*_created` / `*_sold`.
- **Blocker #7 verified:** Composition root (`app/main.py`) and worker startup (`app/workers/__init__.py`) UNCHANGED across the entire plan — Phase 49 already wired the registrations; Plan 50-03 only fills bodies and adjusts Protocol shape.

## Task Commits

Each task committed atomically with TDD RED before GREEN:

1. **Task 1 RED** — `d3626ac` (test: failing tests for activator kwarg rename + PaymentRecorder widening)
2. **Task 1 GREEN** — `954c0fd` (feat: rename activator kwarg + widen PaymentRecorder; W-1 sell/create sweep clean)
3. **Task 2 RED** — `5ad8053` (test: failing integration tests for activator body fills)
4. **Task 2 GREEN** — `9b39b1d` (feat: fill activator bodies D-50-22 + D-50-24)
5. **Task 3 RED** — `42203bd` (test: failing tests for record_payment None handling)
6. **Task 3 GREEN** — `27325d2` (feat: record_payment handles None audit_actor + None received_by_user_id; Alembic 0036)

## Files Created/Modified

### Created

- `apps/backend/tests/unit/test_activator_protocol_kwargs.py` — 5 tests asserting `online_payment_id` kwarg + UUID typing + composition-root smoke (Blocker #7 confirmation)
- `apps/backend/tests/unit/test_payment_recorder_widened.py` — 5 tests asserting both audit_actor + received_by_user_id widened to Optional with None defaults; backward-compat shape check
- `apps/backend/tests/integration/online_payments/test_activate_from_webhook.py` — 5 integration tests covering happy path + missing OnlinePayment + subject-kind mismatch for both activators (T-50-03-06 defense in depth)
- `apps/backend/tests/integration/online_payments/test_record_payment_handles_none.py` — 3 integration tests covering None handling + system emit + backward-compat
- `apps/backend/alembic/versions/0036_payments_received_by_user_id_nullable.py` — flips `payments.received_by_user_id` to nullable; round-trip verified

### Modified

- `apps/backend/app/core/dependencies.py` — MembershipActivator + PtPackageActivator kwarg rename; PaymentRecorder Protocol widening + docstring updates citing Blocker #2/#3
- `apps/backend/app/core/audit_payloads.py` — `PaymentRecordedPayload.received_by_user_id: UUID | None` (Rule 2 add — required so Pydantic validation accepts None case from the webhook flow)
- `apps/backend/app/modules/memberships/service.py` — `activate_membership_from_webhook` body filled (D-50-22): narrow OnlinePayment SELECT via raw SQL, plan resolve, INSERT Membership('active'), emit `membership_activated_online` system emit
- `apps/backend/app/modules/pt_packages/service.py` — `activate_pt_package_from_webhook` body filled (D-50-24): mirror against PtPackage + PtPackagePlan; emit `pt_package_activated_online`
- `apps/backend/app/modules/payments/models.py` — Payment.received_by_user_id flipped to `Mapped[UUIDType | None]`, `nullable=True`
- `apps/backend/app/modules/payments/repository.py` — `insert_payment` `received_by_user_id` widened to `UUID | None`
- `apps/backend/app/modules/payments/service.py` — `record_payment` widened to `audit_actor: CurrentUser | None = None`, `received_by_user_id: UUID | None = None`; guards `audit_actor.id` access; emits actor_user_id=None when audit_actor is None
- `.planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md` — logged 2 pre-existing out-of-scope failures (audit_payloads.py:541 E501 + test_freeze_resolver fixture mismatch)

## Decisions Made

1. **Reused `InvalidTransitionError`** instead of declaring new `IllegalTransitionError` per Blocker #1. Activator doesn't raise it in this plan (that's Plan 50-04 handler scope), but the import-stable choice avoids new exception surface for Plan 50-04.
2. **Cross-module read pattern: raw SQL `text()` against `online_payments`** rather than importing OnlinePayment ORM into memberships/pt_packages service. Mirrors D-49-13 lineage and preserves the modules-independent contract without touching `.importlinter`.
3. **Direct `session.add(Membership(...))` / `session.add(PtPackage(...))` constructors** instead of routing through `repository.insert_membership` / `repository.insert_pt_package`. The repository constructors require `MembershipCreateRequest` / `PtPackageCreateRequest` Pydantic objects; the activator has the OnlinePayment seed (UUID-first), and constructing a request DTO just to thread through the repository would be ceremonial noise. The flat constructor still emits identical snapshot fields.
4. **`PaymentRecordedPayload.received_by_user_id` widened to `UUID | None`** — Rule 2 add not explicitly listed in plan but required for correctness. Without this widening, `record_payment(received_by_user_id=None, audit_actor=None)` would pass `None` into the audit emit payload kwargs and `schema.model_validate(payload)` would reject with a Pydantic ValidationError. The widening is additive: existing in-person callers pass non-None UUIDs which still validate.
5. **`audit_correlation_id` cast to `str` for JSONB serialisability** — mirrors the existing `create_membership` pattern at memberships/service.py:759 where UUIDs are cast to str because the JSON encoder rejects raw UUID instances. Discovered during Task 2 GREEN — initial commit had a UUID round-trip bug that surfaced when the audit row INSERT hit the JSONB encoder.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing Critical] PaymentRecordedPayload.received_by_user_id widened to Optional**
- **Found during:** Task 3 (record_payment body update)
- **Issue:** Plan's Task 3 action specified widening Protocol + ORM + migration but did NOT list the audit payload schema. `PaymentRecordedPayload.received_by_user_id: UUID` (non-Optional) would have rejected the None value at `audit.emit()` validation, causing the webhook-side record_payment call to fail with `pydantic.ValidationError` despite the Protocol shape allowing None. Plan must have intended this widening but listed it implicitly.
- **Fix:** Widened `PaymentRecordedPayload.received_by_user_id: UUID | None` with updated docstring citing Phase 50 Plan 50-03 / Blocker #2.
- **Files modified:** `apps/backend/app/core/audit_payloads.py`
- **Verification:** Integration test `test_record_payment_with_none_audit_actor_and_none_received_by` passes (would have failed on Pydantic ValidationError without this); 31 existing sell/create tests still green (existing UUID values still validate against `UUID | None`).
- **Committed in:** `27325d2` (Task 3 commit)

**2. [Rule 1 — Bug] audit_correlation_id UUID-not-JSON-serialisable**
- **Found during:** Task 2 GREEN (running activator integration tests)
- **Issue:** First Task 2 GREEN commit passed `audit_correlation_id=audit_correlation_id` (raw UUID) into `audit.emit()` payload kwargs. The audit row INSERT serialises the payload to JSONB, and the JSON encoder rejects raw UUID instances with `TypeError: Object of type UUID is not JSON serializable`. Tests 1 + 4 failed with sqlalchemy.exc.StatementError wrapping the TypeError.
- **Fix:** Cast to `str(audit_correlation_id) if audit_correlation_id is not None else None` — mirrors the existing pattern in `create_membership` at memberships/service.py:759-763. Applied identically to both activators.
- **Files modified:** `apps/backend/app/modules/memberships/service.py`, `apps/backend/app/modules/pt_packages/service.py`
- **Verification:** All 5 activator integration tests pass.
- **Committed in:** `9b39b1d` (Task 2 GREEN commit — fixed before commit, no fix-up commit)

**3. [Rule 3 — Blocking] Test placement: created `tests/integration/online_payments/test_activate_from_webhook.py` instead of `tests/integration/test_activate_from_webhook.py`**
- **Found during:** Task 2 (test collection)
- **Issue:** Plan listed `apps/backend/tests/integration/test_activate_from_webhook.py` as the file path, but `make_user` / `make_client_with_email` / `make_pt_package_plan` fixtures are defined in `tests/integration/online_payments/conftest.py`. Test at top-level couldn't find the fixtures.
- **Fix:** Moved file into `tests/integration/online_payments/` subdirectory where the fixtures are visible. Same fix applied to Task 3's test file.
- **Files modified:** `apps/backend/tests/integration/online_payments/test_activate_from_webhook.py` (relocated from top-level), `apps/backend/tests/integration/online_payments/test_record_payment_handles_none.py` (relocated)
- **Verification:** Both test files collect + run green; broader sweep unaffected.
- **Committed in:** `5ad8053` + `42203bd` (RED commits already in correct location after move)

---

**Total deviations:** 3 auto-fixed (1 missing critical, 1 bug, 1 blocking)
**Impact on plan:** All three additions were necessary for correctness. The PaymentRecordedPayload widening + the audit_correlation_id str-cast are direct prerequisites for the plan's Tests-1-of-Task-3 + the activator integration tests passing. No scope creep — every line is in service of the plan's stated must-haves.

## Issues Encountered

- **Pre-existing test failure** `tests/integration/memberships/test_freeze_resolver.py::test_telegram_checkin_frozen_oracle_safe_dm`: fails on base commit `9b271764ad2639c69b90726a5adecf49b867a7dc` with `TypeError: HandlerContext.__new__() missing 2 required positional arguments`. Unrelated to Plan 50-03 surface area; verified by re-running on stashed working tree. Logged to `deferred-items.md`.
- **Pre-existing ruff E501** at `apps/backend/app/core/audit_payloads.py:541` — line length 148 > 100. Not introduced by this plan (line is `is_invitation_pending` docstring from earlier phase). Logged to `deferred-items.md`.
- **`alembic upgrade head` env requirement** — initial `uv run alembic upgrade head` failed because `.env` was absent in the worktree. Created `.env` from `.env.example` to apply migration 0036; round-trip verified clean.

## User Setup Required

None — purely structural Python changes + one DB migration (auto-applied via alembic upgrade head).

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: data-shape | apps/backend/app/modules/payments/models.py | `payments.received_by_user_id` now nullable. Future readers of the ledger MUST handle NULL (e.g., the receipt email fanout helper assumes a non-None operator UUID — Plan 50-04+ may need to gate on `received_by_user_id IS NOT NULL` or fan-out only sale-flow rows). Phase 51 / 52 should re-verify their ledger consumers. |
| threat_flag: audit-shape | apps/backend/app/core/audit_payloads.py | `PaymentRecordedPayload.received_by_user_id` now `UUID \| None`. Downstream consumers iterating audit payloads (forensic exports, BI ETL) MUST accept the None branch. The widening is documented in the payload class docstring. |

## Next Phase Readiness

- **Plan 50-04 unblocked:** the webhook handler now has a working `record_payment(method='online', audit_actor=None, received_by_user_id=None)` call shape AND functional `activate_membership_from_webhook(online_payment_id=op.id, ...)` / `activate_pt_package_from_webhook(...)` accessors. Plan 50-04 does NOT need to touch `app/core/dependencies.py` (no Wave 2 file overlap — the entire dependencies.py surface for v1.7 Phase 50 is now landed in this plan).
- **Threat T-50-03-06 mitigated:** activator-side precondition checks reject subject-kind mismatches (memberships activator called with PT-package OnlinePayment row -> ConflictError; vice versa). Defense in depth on top of Plan 50-04's `if row.membership_plan_id is not None` dispatch.
- **Threat T-50-03-07 mitigated:** W-1 sell/create regression sweep ran clean both immediately after Task 1 (Protocol widening alone) and after Task 3 (full record_payment + payload widening). Backward-compat verified at two distinct points in the plan, not just at the end.

## Self-Check: PASSED

- Created files (all verified to exist):
  - `apps/backend/tests/unit/test_activator_protocol_kwargs.py` — FOUND
  - `apps/backend/tests/unit/test_payment_recorder_widened.py` — FOUND
  - `apps/backend/tests/integration/online_payments/test_activate_from_webhook.py` — FOUND
  - `apps/backend/tests/integration/online_payments/test_record_payment_handles_none.py` — FOUND
  - `apps/backend/alembic/versions/0036_payments_received_by_user_id_nullable.py` — FOUND
- Modified files (all verified in `git diff HEAD~6..HEAD --stat`):
  - `apps/backend/app/core/dependencies.py` — FOUND
  - `apps/backend/app/core/audit_payloads.py` — FOUND
  - `apps/backend/app/modules/memberships/service.py` — FOUND
  - `apps/backend/app/modules/pt_packages/service.py` — FOUND
  - `apps/backend/app/modules/payments/models.py` — FOUND
  - `apps/backend/app/modules/payments/repository.py` — FOUND
  - `apps/backend/app/modules/payments/service.py` — FOUND
- All 6 commit hashes verified via `git log --oneline 9b271764..HEAD`:
  - d3626ac — FOUND
  - 954c0fd — FOUND
  - 5ad8053 — FOUND
  - 9b39b1d — FOUND
  - 42203bd — FOUND
  - 27325d2 — FOUND
- Blocker #1 (zero IllegalTransitionError refs): VERIFIED via `grep -rn "IllegalTransitionError" apps/backend/app/` returning 0
- Blocker #2 (PaymentRecorder widened): VERIFIED via `grep -c "audit_actor: CurrentUser | None" apps/backend/app/core/dependencies.py` returning 1
- Blocker #3 (online_payment_id rename): VERIFIED via `grep -c "online_payment_id: UUID" apps/backend/app/core/dependencies.py` returning 2
- Blocker #6 (single canonical emit): VERIFIED — `membership_activated_online` appears in mem svc; NO new `membership_created` / `pt_package_sold` callsites
- Blocker #7 (composition root untouched): VERIFIED via `git diff apps/backend/app/main.py apps/backend/app/workers/__init__.py` returning empty
- W-1 (sell/create regression sweep): VERIFIED twice — once after Task 1 GREEN, once after Task 3 GREEN; 31 tests passing both times

---
*Phase: 50-webhook-fsm-fiscal-foundation*
*Completed: 2026-05-22*
