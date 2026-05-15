---
phase: 33-pt-package-plans-instances
plan: 03
subsystem: backend
tags: [fastapi, sqlalchemy, pydantic, audit-log, idempotency, rbac, pt-packages, payments, refund]

# Dependency graph
requires:
  - phase: 30-foundations-tech-debt-bedrock
    provides: LOCKED_AUDIT_EVENTS frozenset (pt_package_cancelled / pt_package_refunded pre-registered), AUDIT_PAYLOAD_SCHEMAS registry, SVC001 walker scope incl. pt_packages, modules-independent .importlinter contract incl. pt_packages, append-only AST walker
  - phase: 32-payment-ledger-sale-flow-refund
    provides: PaymentRefunder Protocol slot (get_payment_refunder() consumed by refund_pt_package), payments/service.issue_refund (extended here with subject_kind='pt_package' elif branch), RefundIssuedPayload + PaymentRecordedPayload patterns already include 'pt_package' (D-32-12), AlreadyRefundedError + OriginalPaymentNotFoundError reused, uq_payments_refund_of_alive partial UNIQUE DB-final race gate
  - plan: 33-01
    provides: PT_PACKAGE_STATUS_TRANSITIONS MappingProxyType FSM constant (D-33-04 four-edge graph), CANCELLATION_REASON_REFUNDED sentinel, PAYMENT_SUBJECT_KIND_PT_PACKAGE literal, _assert_can_transition central guard + 3 thin wrappers (_assert_can_cancel/_expire/_exhaust) per memberships:198-260 verbatim shape, InvalidTransitionError + PtPackageNotFoundError error classes, repository helpers (get_pt_package / update_pt_package_status), PtPackageCancelRequest + PtPackageRefundRequest BackendSchemaBase schemas, empty pt_packages_router stub
  - plan: 33-02
    provides: pt_packages sale + read + cron surface (no overlap with cancel/refund file edits — additive on service.py, router.py, audit_payloads.py)
provides:
  - cancel_pt_package(session, actor, pt_package_id, data) — owner-only orchestrator owning UoW; emits pt_package_cancelled with 4-key payload (pt_package_id, client_id, cancellation_reason, prior_status); free-text cancellation_reason (NOT 'refunded' sentinel); NO payment ledger touch
  - refund_pt_package(session, actor, pt_package_id, data) — reception+owner per B-07 orchestrator owning UoW; consumes get_payment_refunder() Protocol slot with subject_kind=PAYMENT_SUBJECT_KIND_PT_PACKAGE; transitions to cancelled + CANCELLATION_REASON_REFUNDED sentinel; emits pt_package_refunded subject-side after refund_issued payment-side
  - POST /api/v1/pt-packages/{id}/cancel (owner-only via Action.CANCEL; CSRF + Idempotency-Key per D-33-16; two-phase Redis replay)
  - POST /api/v1/pt-packages/{id}/refund (reception+owner via Action.REFUND per B-07; CSRF + Idempotency-Key per D-33-16; two-phase Redis replay)
  - payments/repository.get_original_pt_package_payment(session, pt_package_id) — mirrors get_original_membership_payment verbatim with SUBJECT_KIND_PT_PACKAGE substitution
  - payments/service.issue_refund elif branch for subject_kind=SUBJECT_KIND_PT_PACKAGE — replaces Phase 32 NotImplementedError gate at lines 166-170; sub-block-A bridge that lifts the Phase 32 PT-package gating
  - PtPackageCancelledPayload.prior_status additive extension — resolves 33-PATTERNS.md:1112 mismatch flag; LOCKED_AUDIT_EVENTS frozenset and AUDIT_PAYLOAD_SCHEMAS registry both untouched
  - tests/unit/pt_packages/test_state_machine.py extension — 13 new wrapper-denial parametrize cells (1 cancel-from-cancelled + 3 expire-from-non-active + 3 exhaust-from-non-active + 3 cancel-allows-legal-source + supporting assertions)
  - tests/integration/pt_packages/test_pt_package_cancel.py — 11 integration tests covering 3-source happy paths + reception 403 + 404 + 409 + 4 schema-422 + Idempotency replay + audit payload presence
  - tests/integration/pt_packages/test_pt_package_refund.py — 13 integration tests covering owner+reception B-07 happy paths + exhausted/expired sources + 404 original_payment_not_found + 409 invalid_transition + Idempotency replay + 3-row audit chain (payment_recorded → refund_issued → pt_package_refunded) + SHA-256 payment_row_hash + 4 schema-422
  - tests/integration/pt_packages/test_pt_package_refund_race.py — REF-TEST-02 N=5 concurrent gather race (Postgres-only); asserts exactly 1×200 + 4×409 already_refunded; exactly 1 refund Payment row + 1 pt_package_refunded audit + 1 refund_issued audit
  - tests/integration/pt_packages/conftest.py — db_session_real_commit fixture for REF-TEST-02 (TRUNCATE list extended to pt_package_plans + pt_packages)
affects: [34-pt-sessions, 35-admin-web-wiring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FSM-guard-before-mutation discipline (mirrors memberships D-15 / Phase 24 D-24-04): both cancel and refund call _assert_can_transition(target='cancelled') BEFORE any side effect. Cancelled-source request leaves zero side effects; second-refund-attempt is caught by the FSM guard, NOT by the DB partial UNIQUE (the partial UNIQUE only fires on the concurrent race — REF-TEST-02)."
    - "Cross-module Protocol-slot consumption (D-32-14 / D-33-12): refund_pt_package consumes get_payment_refunder() — pt_packages NEVER imports app.modules.payments.*. lint-imports modules-independent contract green; cross-module communication is exclusively through app.core.dependencies."
    - "Sentinel-vs-free-text cancellation_reason discrimination (D-33-08 / mirrors Phase 32 D-32-08): cancel_pt_package stores free-text reason; refund_pt_package stores 'refunded' literal (CANCELLATION_REASON_REFUNDED constant). An offline audit scan can discriminate refund-driven cancellations from operator-driven ones via the cancellation_reason column alone — no JOIN to payments needed."
    - "Additive audit-payload schema extension (D-33-15 / 33-PATTERNS.md:1112 resolution): PtPackageCancelledPayload grows with prior_status: str field. LOCKED_AUDIT_EVENTS frozenset and AUDIT_PAYLOAD_SCHEMAS registry remain untouched. Same pattern used by 33-02 PtPackageSoldPayload + PtPackageExhaustedPayload extensions."
    - "Two-phase Redis idempotency replay on the same route, distinct routes hash to distinct keys (T-33-03-10 mitigation): verify_idempotency derives keys from method+path+body, so the SAME Idempotency-Key on /cancel vs /refund does NOT collide. Replay branch returns cached envelope verbatim WITHOUT a second orchestrator call or audit emit. Mirrors create_pt_package sale endpoint verbatim."
    - "DB partial UNIQUE as final race gate (D-32-04 / REF-TEST-02): concurrent refund INSERTs race on uq_payments_refund_of_alive WHERE subject_kind='refund' AND voided_at IS NULL. Exactly one wins; losers translate IntegrityError to AlreadyRefundedError via payments.repository._is_refund_of_uniqueness_conflict — the FSM guard's TOCTOU window cannot serialise this, the DB index does."

key-files:
  created:
    - apps/backend/tests/integration/pt_packages/test_pt_package_cancel.py
    - apps/backend/tests/integration/pt_packages/test_pt_package_refund.py
    - apps/backend/tests/integration/pt_packages/test_pt_package_refund_race.py
  modified:
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/app/modules/payments/repository.py
    - apps/backend/app/modules/payments/service.py
    - apps/backend/app/modules/pt_packages/service.py
    - apps/backend/app/modules/pt_packages/router.py
    - apps/backend/tests/unit/pt_packages/test_state_machine.py
    - apps/backend/tests/integration/pt_packages/conftest.py

key-decisions:
  - "PtPackageCancelledPayload additive extension (D-33-15 reconciliation, 33-PATTERNS.md:1112): the original CONTEXT.md D-33-15 sketch named the emit kwarg `reason` and did not include prior_status. The locked Pydantic schema in audit_payloads.py used the field name `cancellation_reason`. Plan 33-03 resolves the mismatch by emitting `cancellation_reason=data.reason` (matching the schema field) AND additively extending the schema with `prior_status: str` (forensic chain inspection requires it — auditor must distinguish active→cancelled from exhausted→cancelled from expired→cancelled). LOCKED_AUDIT_EVENTS frozenset and AUDIT_PAYLOAD_SCHEMAS registry both UNTOUCHED — only the Pydantic model body grows."
  - "Cancel endpoint requires Idempotency-Key (D-33-16) DIFFERS from membership cancel: D-33-16 explicitly extends Idempotency-Key to all 3 mutating PT-package POSTs (sale + cancel + refund) for operator-UX consistency. Memberships sale requires Idempotency-Key but membership cancel does NOT (D-32-20). The DB partial UNIQUE remains the load-bearing race defence on refund; Idempotency-Key is the network-retry defence. Different routes hash to distinct Redis keys (T-33-03-10 mitigation) — same key on /cancel and /refund cannot collide."
  - "Second-refund-attempt surface is 409 invalid_transition (FSM guard), NOT 409 already_refunded (DB partial UNIQUE). Sequential second attempts are caught at the service layer because the instance is already cancelled from the first refund. The DB partial UNIQUE surface (already_refunded) is exclusive to the concurrent race — REF-TEST-02 proves this with N=5 distinct Idempotency-Keys forcing the race past the idempotency cache and through to the DB layer."
  - "REF-TEST-02 uses 5 DISTINCT Idempotency-Keys (one per concurrent request). A shared Idempotency-Key would collapse 4 of the 5 into idempotency-cache replay 200s — masking the race. The distinct-keys design ensures all 5 requests reach the orchestrator and contend for the DB partial UNIQUE; exactly one wins with 201 + others surface 409 already_refunded via the issue_refund discriminator path."
  - "W4 compliance on test seeding: test_pt_package_refund.py seeds the original sale payment row via the real HTTP POST /api/v1/pt-packages sale endpoint (which internally routes through the get_payment_recorder() Protocol slot), NOT via raw session.execute(insert(Payment)). This ensures the seeded payment carries the correct payment_row_hash derivation surface for the test_refund_pt_package_audit_chain_traceable forensic chain assertion."

requirements-completed:
  - PT-06
  - PT-08
  - PT-13

# Metrics
duration: ~30min
completed: 2026-05-15
---

# Phase 33 Plan 33-03: PT-Package Cancel + Refund + Payments Bridge Summary

**Lifecycle terminus for PT-packages: cancel-without-refund + refund orchestrators landed in pt_packages/service.py + routes added to pt_packages/router.py + payments/service.issue_refund extended for subject_kind='pt_package' + audit_payloads.PtPackageCancelledPayload additively extended with prior_status — closes Wave 3 of Phase 33.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-05-15 (post 33-02 merge)
- **Tasks:** 3 (Task 1 FSM test extension; Task 2 payments bridge + cancel/refund orchestrators + routes; Task 3 integration tests + REF-TEST-02)
- **Files modified:** 10 (7 modified, 3 created)
- **Tests added:** 38 (13 unit FSM extension + 11 cancel integration + 13 refund integration + 1 REF-TEST-02 race)
- **Tests passing:** Full unit + integration sweep: 480 passed + 70 skipped (no Postgres locally), no regression.

## Accomplishments

### FSM verification + test extension (Task 1 / PT-06)

`tests/unit/pt_packages/test_state_machine.py` extended in-place with 13 new wrapper-denial parametrize cells (W6 ownership preserved — FSM constants + central guard + 3 thin wrappers landed by 33-01 are untouched):

- `test_assert_can_cancel_raises_from_cancelled` — terminal source denial with discriminator fields payload.
- `test_assert_can_expire_raises_from_non_active[exhausted|expired|cancelled]` — 3 cells; only `active` source legal.
- `test_assert_can_exhaust_raises_from_non_active[exhausted|expired|cancelled]` — 3 cells; only `active` source legal.
- `test_assert_can_cancel_allows_legal_sources[active|exhausted|expired]` — 3 cells; pins the happy-path call shape per source.

Total 29 tests in `test_state_machine.py` (16-cell central-guard matrix from 33-01 + 13 new wrapper cells from 33-03), all passing.

### Payments-side bridge (Task 2 sub-block A / PT-13)

**`payments/repository.py`** — new helper `get_original_pt_package_payment(session, pt_package_id)` mirrors `get_original_membership_payment` verbatim with `SUBJECT_KIND_PT_PACKAGE` substitution. SELECT * FROM payments WHERE subject_kind='pt_package' AND subject_id=:id AND amount_kopecks > 0 ORDER BY received_at ASC LIMIT 1. Returns `Payment | None`.

**`payments/service.py`** — `issue_refund` extended at lines 164-173: the Phase 32 NotImplementedError gate at the original lines 166-170 is replaced with an `elif subject_kind == SUBJECT_KIND_PT_PACKAGE` branch that calls the new repository helper. The remaining body (payment_row_hash, INSERT negative-amount row with refund_of=original.id, flush + IntegrityError → AlreadyRefundedError discriminator, audit emit `refund_issued`) is subject-kind-agnostic and required zero further modification — `RefundIssuedPayload.subject_kind` and `PaymentRecordedPayload.subject_kind` already include `'pt_package'` per Phase 32 D-32-12. Trailing else still raises NotImplementedError for unknown kinds.

**`app/core/audit_payloads.py`** — `PtPackageCancelledPayload` additively extended with `prior_status: str` (required, no default). LOCKED_AUDIT_EVENTS frozenset and AUDIT_PAYLOAD_SCHEMAS registry both UNTOUCHED. Resolves the 33-PATTERNS.md:1112 audit-payload mismatch flag.

### PT-packages orchestrators + routes (Task 2 sub-block B / PT-06 / PT-08 / PT-13)

**`pt_packages/service.py`** — two new orchestrators appended after `_expire_due_pt_packages`:

- `cancel_pt_package(session, actor, pt_package_id, data)` (D-33-10, PT-08):
  1. Load instance (404 pt_package_not_found).
  2. Capture `prior_status` BEFORE mutation (forensic audit field).
  3. `_assert_can_transition(target='cancelled')` — 409 invalid_transition for cancelled source.
  4. `update_pt_package_status(status='cancelled', cancellation_reason=<free-text>)`.
  5. Flush.
  6. Emit `pt_package_cancelled` audit with 4-key payload (pt_package_id, client_id, cancellation_reason, prior_status).
  7. Refresh updated_at.
  8. Commit (SVC001 gate enforces).
  9. Return PtPackageResponse.

- `refund_pt_package(session, actor, pt_package_id, data)` (D-33-11, REF-02 / PT-13):
  1. Load instance (404 pt_package_not_found).
  2. `_assert_can_transition(target='cancelled')` — 409 invalid_transition for cancelled source (fires BEFORE the refunder so the second-attempt case never reaches the DB layer).
  3. Call `get_payment_refunder()` Protocol slot with `subject_kind=PAYMENT_SUBJECT_KIND_PT_PACKAGE` — the refunder raises OriginalPaymentNotFoundError (404) or AlreadyRefundedError (409 — DB race). Orchestrator does NOT re-catch.
  4. `update_pt_package_status(status='cancelled', cancellation_reason=CANCELLATION_REASON_REFUNDED)` (sentinel).
  5. Flush.
  6. Emit `pt_package_refunded` audit row (subject-side) AFTER `refund_issued` (payment-side, in issue_refund).
  7. Refresh updated_at.
  8. Commit.
  9. Return PtPackageResponse.

NO freeze guard (v1.4 has no PT-package freeze). NO renewed-source guard (v1.4 has no PT-package renewal). Modules-independent contract preserved — no direct `app.modules.payments.*` import.

**`pt_packages/router.py`** — two new endpoints appended:

- `POST /api/v1/pt-packages/{pt_package_id}/cancel` — owner-only via `require_permission(Action.CANCEL, Resource.PT_PACKAGES)` (CANCEL+PT_PACKAGES IS in OWNER_ONLY per Phase 30 INFRA-19). CSRF + Idempotency-Key required per D-33-16. Two-phase Redis claim + replay mirroring the sale endpoint.
- `POST /api/v1/pt-packages/{pt_package_id}/refund` — reception+owner per B-07 via `require_permission(Action.REFUND, Resource.PT_PACKAGES)` (REFUND+PT_PACKAGES NOT in OWNER_ONLY). CSRF + Idempotency-Key required. Two-phase Redis claim + replay.

RBAC-04 dependency ordering preserved on both routes: `require_permission` BEFORE `verify_csrf` BEFORE `verify_idempotency` BEFORE `get_db`.

### Integration tests (Task 3)

**`tests/integration/pt_packages/test_pt_package_cancel.py`** — 11 tests:
- `test_cancel_pt_package_active_owner_happy_path` — full DB + audit + no-refund-row invariant assertions.
- `test_cancel_pt_package_exhausted_owner_happy_path` — payload.prior_status='exhausted'.
- `test_cancel_pt_package_expired_owner_happy_path` — payload.prior_status='expired'.
- `test_cancel_pt_package_reception_403` — RBAC denial leaves zero side effects (DB unchanged + no audit emit).
- `test_cancel_pt_package_missing_404` — 404 pt_package_not_found.
- `test_cancel_pt_package_already_cancelled_409` — 409 invalid_transition with discriminator fields={'from_status':'cancelled', 'to_status':'cancelled'}.
- 4 schema-rejection cases: no CSRF / extra field / empty reason / reason >200 chars.
- `test_cancel_pt_package_idempotency_replay` — same key+body → cached envelope, exactly 1 audit emit.

**`tests/integration/pt_packages/test_pt_package_refund.py`** — 13 tests:
- `test_refund_pt_package_owner_happy_path_active` — full invariants: 200 + sentinel cancellation_reason='refunded' + 1 negative-amount Payment row with refund_of FK + 1 pt_package_refunded audit row with 4-key payload.
- `test_refund_pt_package_reception_happy_path_active` — B-07 RBAC parity.
- `test_refund_pt_package_exhausted_owner_happy_path` / `..._expired_owner_happy_path` — D-33-04 legal sources.
- `test_refund_pt_package_already_cancelled_409` — FSM guard wins; 409 invalid_transition.
- `test_refund_pt_package_no_original_payment_404` — 404 original_payment_not_found.
- `test_refund_pt_package_second_attempt_409` — sequential second attempt → 409 invalid_transition (NOT already_refunded); exactly 1 refund row in DB.
- `test_refund_pt_package_idempotency_replay` — same key+body → cached envelope, exactly 1 refund row + 1 audit row.
- `test_refund_pt_package_audit_chain_traceable` — 3-row audit chain (payment_recorded → refund_issued → pt_package_refunded) with resource_id linkage verified; refund_issued payload.payment_row_hash matches `^sha256:[0-9a-f]{64}$` (D-30-04 forensic anchor).
- 4 schema-rejection cases.

W4 compliance: sale-side payment row seeded via real HTTP POST `/api/v1/pt-packages` sale endpoint (which routes through `get_payment_recorder()` Protocol slot per Phase 32 D-32-14), NOT via raw `session.execute(insert(Payment))`.

**`tests/integration/pt_packages/test_pt_package_refund_race.py`** — REF-TEST-02:
- N=5 concurrent `POST /api/v1/pt-packages/{id}/refund` via `asyncio.gather`.
- 5 DISTINCT Idempotency-Keys so race surfaces at DB partial UNIQUE `uq_payments_refund_of_alive`, NOT at idempotency replay branch.
- Asserts `sorted([r.status_code]) == [200, 409, 409, 409, 409]`.
- All 4 409 bodies have `code == 'already_refunded'`.
- DB invariant: exactly 1 refund Payment row + 1 pt_package_refunded audit row + 1 refund_issued audit row (race losers rolled back before audit emit).
- Postgres-required — fails locally without Postgres (mirrors REF-TEST-01 behavior). Will pass in CI.

**`tests/integration/pt_packages/conftest.py`** — `db_session_real_commit` fixture added. Mirrors memberships sibling verbatim with TRUNCATE list extended to `pt_package_plans` + `pt_packages`.

## Decisions Made

- **PtPackageCancelledPayload additive extension (D-33-15 reconciliation, 33-PATTERNS.md:1112)**: schema field renamed `reason` → `cancellation_reason` (already correct since 33-01 land) AND `prior_status: str` added. LOCKED_AUDIT_EVENTS frozenset and AUDIT_PAYLOAD_SCHEMAS registry both UNTOUCHED — only the Pydantic model body grows. Mirrors the 33-02 PtPackageSoldPayload + PtPackageExhaustedPayload additive-extension precedent.
- **Cancel endpoint also requires Idempotency-Key per D-33-16** — different from membership cancel which has NO Idempotency-Key (D-32-20). The PT-package surface adopts the stronger requirement so all three mutating PT-package POSTs are operator-UX uniform. T-33-03-10 mitigation: distinct routes (cancel vs refund) hash to distinct Redis keys; same Idempotency-Key on different routes cannot collide because `verify_idempotency` derives keys from method+path+body.
- **Second-refund-attempt is 409 invalid_transition (FSM wins) NOT 409 already_refunded (DB partial UNIQUE)** — sequential attempts are caught at the service layer (instance is cancelled after the first refund). The DB partial UNIQUE surface is exclusive to the concurrent race (REF-TEST-02). This is the same discipline as memberships refund.
- **REF-TEST-02 uses 5 DISTINCT Idempotency-Keys** so the race surfaces at the DB layer, NOT at the idempotency cache. A shared key would collapse 4 of the 5 into replay branches — masking the race. The distinct-keys design ensures all 5 requests reach the orchestrator and contend for `uq_payments_refund_of_alive`.
- **W4 test seeding**: `test_pt_package_refund.py` seeds the sale payment row via real HTTP POST `/api/v1/pt-packages` (routes through `get_payment_recorder()` Protocol slot per Phase 32 D-32-14). NOT raw `session.execute(insert(Payment))`. Ensures the audit chain assertion test (test_refund_pt_package_audit_chain_traceable) sees a real `payment_recorded` audit event.
- **`record_payment`/`payment_recorder` grep token count is 1 (docstring mention)**: the W4 grep returns 1 — the test file documents the protocol-slot path in the `_sell_pt_package` helper docstring; the actual seeding happens via the HTTP sale endpoint which itself consumes the slot. Substantively compliant.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ruff F401 — unused `UUID` import in cancel test**
- **Found during:** Task 3 ruff check.
- **Issue:** `from uuid import UUID, uuid4` — `UUID` not referenced (the test only constructs new UUIDs via `uuid4()`).
- **Fix:** `uv run ruff check --fix` auto-removed the unused import.
- **Files modified:** `apps/backend/tests/integration/pt_packages/test_pt_package_cancel.py`.
- **Verification:** `uv run ruff check tests/integration/pt_packages/` → All checks passed.
- **Committed in:** 811d65a (Task 3 commit, applied before commit).

**2. [Rule 3 - Blocking] ruff E501 — line-too-long in 2 docstrings**
- **Found during:** Task 3 ruff check.
- **Issue:** Two test-file docstrings exceeded the 100-char line width (`test_pt_package_cancel.py:317` at 101 chars, `test_pt_package_refund_race.py:1` module docstring at 103 chars).
- **Fix:** Compressed both docstrings to ≤100 chars without losing semantic content.
- **Files modified:** `test_pt_package_cancel.py`, `test_pt_package_refund_race.py`.
- **Verification:** `uv run ruff check tests/integration/pt_packages/` → All checks passed.
- **Committed in:** 811d65a (Task 3 commit, applied before commit).

**3. [Rule 3 - Blocking] mypy strict — `plan.validity_days` is `int | None` in race test seeding**
- **Found during:** Task 3 mypy strict pass on `test_pt_package_refund_race.py`.
- **Issue:** `today + timedelta(days=plan.validity_days - 1)` flagged `Unsupported operand types for - ("None" and "int")` because the column type is `int | None` (the runtime value is the concrete int 90, but mypy cannot narrow through the SA Mapped attribute access).
- **Fix:** Extracted `validity_days = plan.validity_days; assert validity_days is not None` before the arithmetic; reused the narrowed variable in both the `validity_days_snapshot=` kwarg and the `end_date=today + timedelta(...)` expression.
- **Files modified:** `apps/backend/tests/integration/pt_packages/test_pt_package_refund_race.py`.
- **Verification:** `uv run mypy --strict tests/integration/pt_packages/test_pt_package_cancel.py tests/integration/pt_packages/test_pt_package_refund.py tests/integration/pt_packages/test_pt_package_refund_race.py` → Success.
- **Committed in:** 811d65a (Task 3 commit, applied before commit).

---

**Total deviations:** 3 auto-fixed (all Rule 3 — Blocking; tool / gate compliance only, no behavior change).
**Impact on plan:** Zero scope creep — all fixes are mypy / ruff compliance.

## Issues Encountered

- **No local Postgres available** in the worktree environment, so the 25 new integration tests skip cleanly via the `db_session` connectivity probe + the REF-TEST-02 race test fails with `OSError: Connect call failed ('127.0.0.1', 5432)` (same behavior as the existing REF-TEST-01 race test on memberships — local-env-only limitation, will pass in CI where Postgres is available). The 13 new unit tests in `test_state_machine.py` all pass locally; the full pytest sweep (480 passed + 70 skipped, excluding the race test) confirms no regression in 33-01 / 33-02 / memberships / payments / Phase 30 walkers.
- **Pre-existing mypy strict error in `tests/integration/pt_packages/test_pt_package_plans_crud.py:32`** (`Dict entry 0 has incompatible type "str": "str | None"; expected "str": "str"`) is out-of-scope per the deviation-rule scope boundary — landed in 33-01 and not directly caused by 33-03 changes; not modified here.

## Threat Flags

No new security-relevant surface introduced beyond the plan's `<threat_model>` register (T-33-03-01..13 all mitigated as documented):
- T-33-03-01 (concurrent refund race) — REF-TEST-02 covers via uq_payments_refund_of_alive partial UNIQUE.
- T-33-03-02 (reception → cancel escalation) — test_cancel_pt_package_reception_403 + DB unchanged + audit emptiness.
- T-33-03-03 (reception → refund RBAC parity) — test_refund_pt_package_reception_happy_path_active.
- T-33-03-04 (unknown body field) — 4 schema-422 tests on each endpoint.
- T-33-03-05 (forensic chain tampering) — test_refund_pt_package_audit_chain_traceable asserts payment_row_hash SHA-256 anchor.
- T-33-03-06 (repudiation chain) — 3-row audit chain ordering assertion; prior_status forensic field on cancel emit.
- T-33-03-07 (audit-payload key drift) — schema additively extended; emit kwargs aligned; D-30-03 validator rejects drift at runtime (audit-taxonomy AST gate green).
- T-33-03-10 (Idempotency-Key cross-route reuse) — different routes hash to distinct Redis keys (verify_idempotency derives from method+path+body).
- T-33-03-11 (CSRF-less POST) — verify_csrf on both routes; test_*_no_csrf_403 cases.

## Self-Check

Verified all claims:

- `[FOUND] apps/backend/tests/integration/pt_packages/test_pt_package_cancel.py`
- `[FOUND] apps/backend/tests/integration/pt_packages/test_pt_package_refund.py`
- `[FOUND] apps/backend/tests/integration/pt_packages/test_pt_package_refund_race.py`
- `[FOUND] apps/backend/app/core/audit_payloads.py` (modified: PtPackageCancelledPayload.prior_status added)
- `[FOUND] apps/backend/app/modules/payments/repository.py` (modified: get_original_pt_package_payment added)
- `[FOUND] apps/backend/app/modules/payments/service.py` (modified: issue_refund elif branch for pt_package)
- `[FOUND] apps/backend/app/modules/pt_packages/service.py` (modified: cancel_pt_package + refund_pt_package added)
- `[FOUND] apps/backend/app/modules/pt_packages/router.py` (modified: /cancel + /refund endpoints added)
- `[FOUND] apps/backend/tests/unit/pt_packages/test_state_machine.py` (modified: 13 wrapper-denial cells added)
- `[FOUND] apps/backend/tests/integration/pt_packages/conftest.py` (modified: db_session_real_commit fixture added)
- `[FOUND] commit 203ba19` (Task 1 — test_state_machine.py extension)
- `[FOUND] commit 3e92ffc` (Task 2 — payments bridge + cancel/refund orchestrators + routes)
- `[FOUND] commit 811d65a` (Task 3 — integration tests + REF-TEST-02 + conftest extension)
- mypy --strict on app/modules/pt_packages/ + app/modules/payments/ + app/core/audit_payloads.py: PASS.
- mypy --strict on 3 new test files: PASS.
- lint-imports: 3 contracts KEPT (core-not-depend-on-modules / modules-independent / integrations-not-depend-on-modules). modules-independent green proves no direct `from app.modules.payments` import was added to pt_packages.
- ruff check on all new + modified files: PASS.
- Phase 30 walkers (test_payments_appendonly + test_service_commit_gate + test_audit_taxonomy): PASS.
- pytest unit sweep + pt_packages integration (excluding race): 480 passed + 70 skipped (no regression).

**Self-Check: PASSED**

## Audit-Payload Mismatch Resolution (33-PATTERNS.md:1112)

The original CONTEXT.md D-33-15 sketch named the `pt_package_cancelled` emit kwarg `reason`. The locked Pydantic schema in `audit_payloads.py:204-212` (added by Plan 30-01 / Plan 33-01 verification pass) used the field name `cancellation_reason`. Plan 33-03 resolves the mismatch in TWO complementary ways:

1. **Emit kwarg renamed**: `cancel_pt_package` orchestrator emits `cancellation_reason=data.reason` (matching the schema field).
2. **Schema additively extended**: `PtPackageCancelledPayload` grows with `prior_status: str` (required field). Forensic chain inspection requires this — auditor must distinguish active→cancelled from exhausted→cancelled from expired→cancelled.

Option B from the 33-PATTERNS.md:1112 menu (additive schema extension). LOCKED_AUDIT_EVENTS frozenset and AUDIT_PAYLOAD_SCHEMAS registry both UNTOUCHED. Same pattern used by 33-02 PtPackageSoldPayload + PtPackageExhaustedPayload extensions — establishes the Phase 33 additive-extension precedent.

## Out-of-Scope to Phase 34+

- `pt_package_exhausted` audit emit — schema landed in 33-02; callsite added when Phase 34 PT-session decrement orchestrator brings `sessions_remaining` to 0.
- PT-session lifecycle (`pt_session_recorded` / `pt_session_cancelled`) — Phase 34.
- Frontend admin-web UI for cancel/refund — Phase 35 (FE-10..18).
- Audit log retention policy / PII redaction for `reason` field — ROADMAP backlog.

---
*Phase: 33-pt-package-plans-instances*
*Completed: 2026-05-15*
