---
phase: 32-payment-ledger-sale-flow-refund
plan: 03
subsystem: backend/memberships+payments
tags: [refund-flow, status-guard-ordering, partial-unique-race, audit-chain, protocol-slot-consumer, modules-independent]
requires:
  - 32-01 PaymentRefunder Protocol slot + get_payment_refunder defensive accessor
  - 32-01 payments.service.issue_refund caller-owns-txn (loads original via subject_kind/subject_id; emits refund_issued audit + AlreadyRefundedError / OriginalPaymentNotFoundError mapping)
  - 32-01 payments.repository.has_refund_of_uniqueness_conflict + uq_payments_refund_of_alive partial UNIQUE
  - 32-01 CANCELLATION_REASON_REFUNDED sentinel + memberships.cancellation_reason column
  - 32-02 PAYMENT_SUBJECT_KIND_MEMBERSHIP literal in memberships.constants (modules-independent workaround)
  - Phase 30 LOCKED_AUDIT_EVENTS ('refund_issued', 'payment') + ('membership_refunded', 'membership')
  - Phase 30 AUDIT_PAYLOAD_SCHEMAS RefundIssuedPayload + MembershipRefundedPayload
provides:
  - POST /api/v1/memberships/{id}/refund endpoint (RBAC-04 ordering, NO Idempotency-Key)
  - memberships.service.refund_membership orchestrator with D-32-11 status-guard ordering
  - memberships.repository.has_renewal_descendants single-row EXISTS query (REF-04 / B-09)
  - 2 new ConflictError subclasses: MustUnfreezeFirstError + CannotRefundRenewedSourceError
  - MembershipRefundRequest schema in memberships.schemas (parallel to payments.schemas — modules-independent)
  - cancellation_reason field surfaced through MembershipResponse projection
  - 15 happy/conflict/422 refund integration tests + REF-TEST-01 race + 3 REF-07 audit chain tests
affects:
  - memberships.service.refund_membership orchestrator (NEW); _build_membership_response + list bulk projection extended with cancellation_reason field
  - memberships.repository.has_renewal_descendants helper (NEW)
  - memberships.router POST /{id}/refund endpoint (NEW)
  - memberships.schemas MembershipRefundRequest (NEW — parallel to payments.schemas for modules-independent contract)
  - tests/integration/memberships/conftest.py db_session_real_commit TRUNCATE list adds `payments`
  - tests/integration/payments/conftest.py re-exports db_session_real_commit
tech-stack:
  added: []
  patterns:
    - "Refund orchestrator status-guard ordering: frozen-specific FIRST (must_unfreeze_first B-08), renewed-source SECOND (cannot_refund_renewed_source B-09), generic _assert_can_transition THIRD (invalid_transition) — Phase 25 D-25-07 invariant preserved"
    - "Modules-independent contract preserved via parallel schema definition (MembershipRefundRequest in memberships.schemas mirrors payments.schemas field-for-field; same wire shape for admin-web FE-13 in Phase 35)"
    - "Refunder Protocol slot consumed with (subject_kind, subject_id) — D-32-14 amended signature so orchestrator never imports payments.repository or payments.models"
    - "Caller-owns-txn discipline: refund_membership owns the UoW; refunder is caller-owns-txn and internally flushes + emits refund_issued audit, but does NOT commit"
    - "DB partial UNIQUE uq_payments_refund_of_alive is the race winner (mirrors v1.3 freeze partial UNIQUE pattern); REF-TEST-01 asserts [200] + [409]*4 across 5 concurrent POSTs"
key-files:
  created:
    - apps/backend/tests/integration/payments/test_payments_refund.py
    - apps/backend/tests/integration/payments/test_payments_refund_race.py
    - apps/backend/tests/integration/payments/test_payments_refund_audit_chain.py
  modified:
    - apps/backend/app/modules/memberships/service.py
    - apps/backend/app/modules/memberships/router.py
    - apps/backend/app/modules/memberships/repository.py
    - apps/backend/app/modules/memberships/schemas.py
    - apps/backend/tests/integration/memberships/conftest.py
    - apps/backend/tests/integration/payments/conftest.py
decisions:
  - "D-32-11 applied verbatim: status-guard ordering frozen → renewed-source → generic transition. Specific 409 codes (must_unfreeze_first, cannot_refund_renewed_source) win over generic invalid_transition; operator UI surfaces actionable error."
  - "MembershipRefundRequest defined in memberships.schemas instead of imported from payments.schemas. Rationale: importlinter modules-independent contract forbids `app.modules.memberships → app.modules.payments`. Same shape, both extend BackendSchemaBase, both inherit extra='forbid'. Same lesson as Phase 32-02 deviation #4 (PAYMENT_SUBJECT_KIND_MEMBERSHIP literal)."
  - "MembershipResponse projection extended with cancellation_reason field (Rule 1 bug fix): column existed since Plan 32-01 ALTER but was never surfaced through _build_membership_response or list_memberships bulk projection. Without this fix, REF-01 acceptance criterion `data.cancellation_reason == 'refunded'` fails at the API boundary even though the DB column is correctly populated by the orchestrator."
  - "test_refund_already_refunded_409 manually re-flips status to 'active' on the SAVEPOINT-mode session after the first successful refund. Production behaviour: after refund completes the membership is cancelled, so a second POST hits 409 invalid_transition (transition guard fires before the DB write). The manual re-flip drives the flow PAST the transition guard so we can exercise the uq_payments_refund_of_alive partial UNIQUE specifically. REF-TEST-01 (race test, separate file) is where the partial UNIQUE actually wins a real concurrent race; this unit-style test pins the 409 → already_refunded translation."
metrics:
  duration_minutes: 27
  tasks_completed: 3
  files_created: 3
  files_modified: 6
  integration_tests_added: 19
  completed_date: "2026-05-15"
---

# Phase 32 Plan 03: Refund Flow Summary

**One-liner:** Lands the refund flow as the third and final Phase 32 deliverable —
POST /api/v1/memberships/{id}/refund endpoint with D-32-11 status-guard ordering
(frozen → renewed-source → generic transition), refund_membership orchestrator
consuming the PaymentRefunder Protocol slot via `get_payment_refunder()` (NO
direct payments.repository import — modules-independent contract preserved),
2 new ConflictError subclasses for the 409 mapping, has_renewal_descendants
EXISTS query, and 19 integration tests covering 15 endpoint cases + REF-TEST-01
concurrent race (partial UNIQUE wins) + 3 REF-07 audit chain traceability cases.

## has_renewal_descendants repository helper

`apps/backend/app/modules/memberships/repository.py:614-633` —
```python
async def has_renewal_descendants(
    session: AsyncSession, membership_id: UUID
) -> bool:
    stmt = (
        select(Membership.id)
        .where(Membership.previous_membership_id == membership_id)
        .limit(1)
    )
    result = await session.scalar(stmt)
    return result is not None
```
Single-row EXISTS-style read; no soft-delete filter (memberships have no
`deleted_at` per Phase 25/26 invariant). Any descendant row blocks the refund
of the source.

## Two New ConflictError Subclasses

`apps/backend/app/modules/memberships/service.py:167-192`:

| Class | Code | Status | Trigger |
|-------|------|--------|---------|
| `MustUnfreezeFirstError` | `must_unfreeze_first` | 409 | source `status == 'frozen'` (B-08) |
| `CannotRefundRenewedSourceError` | `cannot_refund_renewed_source` | 409 | `has_renewal_descendants(...)` returns True (B-09) |

Both subclass `ConflictError`; both raised by `refund_membership` BEFORE the
generic `_assert_can_transition` so specific codes win.

## refund_membership Orchestrator

`apps/backend/app/modules/memberships/service.py:707-781` — 11-step sequence
per D-32-11:

| # | Step | File:Line |
|---|------|-----------|
| 1 | Load membership (404 membership_not_found) | service.py:744-746 |
| 2 | Frozen guard — 409 must_unfreeze_first (B-08, specific-first) | service.py:750-751 |
| 3 | Renewed-source guard — 409 cannot_refund_renewed_source (B-09) | service.py:754-755 |
| 4 | Generic transition guard — 409 invalid_transition (already cancelled / expired) | service.py:758 |
| 5 | Call `get_payment_refunder()` Protocol slot (subject_kind, subject_id, refund_user_id, reason, audit_actor) — refunder loads ORIGINAL sale row + INSERTs refund + emits refund_issued audit | service.py:764-771 |
| 6 | Transition status='cancelled' + set cancellation_reason=CANCELLATION_REASON_REFUNDED + cancelled_at=now(UTC) | service.py:774-779 |
| 7 | `await session.flush()` | service.py:782 |
| 8 | Emit `membership_refunded` audit row (LOCKED name; NOT `payment_refunded`) | service.py:788-797 |
| 9 | Refresh `updated_at` for response | service.py:800 |
| 10 | `await session.commit()` (SVC001 gate) | service.py:803 |
| 11 | Return via `_build_membership_response` | service.py:807 |

The 409 mapping at the boundary:

| App error | Source | HTTP |
|-----------|--------|------|
| `MustUnfreezeFirstError` | orchestrator step 2 | 409 must_unfreeze_first |
| `CannotRefundRenewedSourceError` | orchestrator step 3 | 409 cannot_refund_renewed_source |
| `InvalidTransitionError` | `_assert_can_transition` step 4 | 409 invalid_transition |
| `AlreadyRefundedError` | issue_refund (uq_payments_refund_of_alive race) | 409 already_refunded |
| `OriginalPaymentNotFoundError` | issue_refund (legacy membership) | 404 original_payment_not_found |
| `MembershipNotFoundError` | step 1 | 404 membership_not_found |

## POST /api/v1/memberships/{id}/refund Endpoint

`apps/backend/app/modules/memberships/router.py:514-559` — handler signature:
```python
async def refund_membership(
    membership_id: UUID,
    payload: MembershipRefundRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.REFUND, Resource.MEMBERSHIPS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
```

RBAC-04 ordering preserved: `require_permission(REFUND, MEMBERSHIPS)` BEFORE
`verify_csrf`. NO `Depends(verify_idempotency)` — refund flow uses DB partial
UNIQUE for natural idempotency per D-32-20.

`(REFUND, MEMBERSHIPS)` is NOT in OWNER_ONLY per B-07 — reception+owner
uniform; admin-web AlertDialog + H-13 confirmation lands in Phase 35 FE-13.

## MembershipRefundRequest schema

Defined verbatim in BOTH `app.modules.payments.schemas` (Plan 32-01) AND
`app.modules.memberships.schemas` (this plan). The orchestrator imports from
the memberships side to honour the importlinter `modules-independent`
contract. Same wire shape:
```python
class MembershipRefundRequest(BackendSchemaBase):
    reason: str = Field(min_length=1, max_length=200)
    # `extra='forbid'` inherited from BackendSchemaBase — rejects
    # amountKopecks et al. per REF-05.
```

## Integration Tests

### `test_payments_refund.py` — 15 cases (all green)

| # | Test | Asserts |
|---|------|---------|
| 1 | `test_refund_happy_path` | 200 + status='cancelled' + cancellationReason='refunded' + exactly 1 negative-amount Payment row with refund_of pointing at the sale |
| 2 | `test_refund_must_unfreeze_first_409` | freeze first → POST /refund → 409 must_unfreeze_first; no refund row inserted |
| 3 | `test_refund_cannot_refund_renewed_source_409` | renew source first → POST /refund on source → 409 cannot_refund_renewed_source |
| 4 | `test_refund_invalid_transition_409_when_already_cancelled` | admin cancel first → POST /refund → 409 invalid_transition |
| 5 | `test_refund_already_refunded_409` | first refund success → DB-direct status re-flip → second refund → 409 already_refunded; exactly 1 refund row |
| 6 | `test_refund_membership_not_found_404` | random UUID → 404 membership_not_found |
| 7 | `test_refund_legacy_membership_no_payment` | DB-direct seeded membership without sale → 404 original_payment_not_found |
| 8 | `test_refund_rejects_amount_kopecks_field_422` | `{"reason":"x","amountKopecks":1000}` → 422 (REF-05); no refund row |
| 9 | `test_refund_rejects_unknown_field_422` | `{"reason":"x","foo":"bar"}` → 422 (extra='forbid') |
| 10 | `test_refund_reason_min_length_validation` | `{"reason":""}` → 422 (Field min_length=1) |
| 11 | `test_refund_reason_max_length_validation` | `{"reason":"x"*201}` → 422 (Field max_length=200) |
| 12 | `test_refund_reception_allowed` | reception POST /refund → 200 (B-07) |
| 13 | `test_refund_owner_allowed` | owner POST /refund → 200 |
| 14 | `test_refund_anonymous_returns_401` | unauth → 401 (RBAC-04 ordering: auth fires first) |
| 15 | `test_refund_csrf_missing_returns_403` | missing X-CSRF-Token → 403 csrf_mismatch |

### `test_payments_refund_race.py` — REF-TEST-01 (green)

`test_concurrent_refund_loses_at_db_layer` — uses `db_session_real_commit`
fixture (not SAVEPOINT-isolated), seeds owner + plan + client + membership +
ORIGINAL sale Payment row, then `asyncio.gather` of 5 parallel POST /refund
requests. Asserts:
- `statuses == [200] + [409] * 4`
- All 4 × 409 bodies have `code == "already_refunded"`
- Exactly 1 refund Payment row persists (uq_payments_refund_of_alive
  serialised the concurrent INSERTs)
- Exactly 1 `membership_refunded` audit row + 1 `refund_issued` audit row
  (losing tasks rollback BEFORE both audit emits)

### `test_payments_refund_audit_chain.py` — REF-07 (3 cases, all green)

| Test | Asserts |
|------|---------|
| `test_refund_audit_chain_order` | All 4 LOCKED events present: payment_recorded (sale UoW) + membership_created (sale UoW) + refund_issued (refund UoW, payment-side) + membership_refunded (refund UoW, subject-side); resource_id linkage consistent |
| `test_refund_issued_payload_includes_payment_row_hash` | payload['payment_row_hash'] matches `^sha256:[0-9a-f]{64}$`; recomputed hash from 8 stable columns of ORIGINAL sale row equals stored value |
| `test_membership_refunded_payload_links_refund_payment` | payload['refund_payment_id'] == str(refund.id); payload['reason'] == operator_input; payload['membership_id'] + payload['client_id'] are well-formed UUID strings |

## Cross-Module Contract Preserved

`grep -E 'from app\.modules\.payments\.(repository|models)' apps/backend/app/modules/memberships/service.py apps/backend/app/modules/memberships/router.py | wc -l`
returns **0** — the orchestrator and router never import payments
repository or ORM. Only consumed: `get_payment_refunder()` Protocol slot
accessor (from `app.core.dependencies`) + locally-defined constants
(`PAYMENT_SUBJECT_KIND_MEMBERSHIP` lives in memberships.constants).

`uv run lint-imports` confirms all 3 contracts kept (core ⊥ modules,
modules ⊥ each other, integrations ⊥ modules).

## B-07 Reception+Owner Uniformity Evidence

`(Action.REFUND, Resource.MEMBERSHIPS)` not in `OWNER_ONLY` set
(`app/core/permissions.py` line 67-76 reception-scoping comment confirms).
Both `test_refund_reception_allowed` and `test_refund_owner_allowed` return
200 with `data.status == 'cancelled'`. No 403 path documented for
reception on this endpoint.

## Locked Event Names Verified

| Audit event | Used here | Stale alternative (NOT used) |
|-------------|-----------|------------------------------|
| `refund_issued` | ✓ (payments.service.issue_refund, Phase 32-01) | `payment_refunded` ✗ — ROADMAP SC #5 terminology drift |
| `membership_refunded` | ✓ (memberships.service.refund_membership, line 791) | — |
| `payment_recorded` | ✓ (sale-side, existing from Plan 32-02) | — |
| `membership_created` | ✓ (sale-side, existing from Plan 32-02) | `membership_sold` ✗ — ROADMAP terminology drift |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] MembershipRefundRequest cannot be imported from payments.schemas**

- **Found during:** Task 1 planning of imports for service.py.
- **Issue:** Plan §action 2 instructs
  `from app.modules.payments.schemas import MembershipRefundRequest`, but the
  importlinter `modules-independent` contract forbids
  `app.modules.memberships → app.modules.payments`. This is the same lesson
  Phase 32-02 hit (deviation #4) and resolved via a parallel local constant
  in memberships.constants.
- **Fix:** Defined `MembershipRefundRequest` in
  `app.modules.memberships.schemas` field-for-field identical to the one in
  `app.modules.payments.schemas` (Plan 32-01). Both extend `BackendSchemaBase`
  and inherit `extra='forbid'`. The router imports from memberships side;
  payments-side schema preserved for the Phase 33 pt_packages consumer.
- **Files modified:** `apps/backend/app/modules/memberships/schemas.py`.
- **Commit:** `ddbaf3d`.

**2. [Rule 1 - Bug] MembershipResponse projection missing cancellation_reason field**

- **Found during:** Task 3 first integration test run —
  `test_refund_happy_path` asserted
  `data.cancellation_reason == 'refunded'` but got `None`.
- **Issue:** `_build_membership_response` (single-row projector,
  service.py:265-288) constructs the payload dict from explicit ORM
  attributes but **OMITTED `cancellation_reason`** even though the column
  has existed since Plan 32-01's ALTER. The bulk projection in
  `list_memberships` (service.py:1192-1206) had the same omission. Result:
  the DB column was correctly populated by the orchestrator
  (`UPDATE memberships SET cancellation_reason='refunded'` confirmed in SQL
  log), but never surfaced through the API.
- **Fix:** Added
  `"cancellation_reason": membership.cancellation_reason` to both projection
  dicts. Already-correct schema field `cancellation_reason: str | None = None`
  (Plan 32-01) wires through `MembershipResponse.model_validate(payload)`.
- **Files modified:** `apps/backend/app/modules/memberships/service.py`
  (two locations).
- **Commit:** `42576b7`.

**3. [Rule 3 - Blocking] db_session_real_commit fixture not exported into payments package**

- **Found during:** Task 3 first run of `test_payments_refund_race.py`.
- **Issue:** The race test requires `db_session_real_commit` (real
  BEGIN/COMMIT per request — required for concurrent-INSERT serialisation
  testing); the fixture lives in
  `tests/integration/memberships/conftest.py:307` but
  `tests/integration/payments/conftest.py` only re-exports a subset.
- **Fix:** Added `db_session_real_commit` to the re-export list in payments
  conftest. Also extended the TRUNCATE list in the fixture cleanup to
  include `payments` so REF-TEST-01 leaves no residue between race-test runs
  (CASCADE handles FKs but explicit-table listing is safer).
- **Files modified:**
  `apps/backend/tests/integration/payments/conftest.py`,
  `apps/backend/tests/integration/memberships/conftest.py`.
- **Commit:** `42576b7`.

### Pre-existing Failures Out of Scope

- 4 stale `tests/integration/test_rbac_parity.py` failures (Phase 30 INFRA-19
  expanded OWNER_ONLY to 26 entries; fixture not refreshed). Already
  documented in Plan 32-01 `deferred-items.md`. Phase 32 Plan 03 did not
  touch the OWNER_ONLY set; ran with `--deselect` to confirm the rest of the
  suite is regression-free.

## REF-02 & REF-06 Out-of-Scope Confirmation

- **REF-02** — POST /api/v1/pt-packages/{id}/refund router lands in Phase 33
  alongside the pt_packages module. The PaymentRefunder Protocol slot
  signature is already frozen by Plan 32-01 + 32-03; pt-packages consumer
  extends the `NotImplementedError` branch in
  `payments.service.issue_refund` to handle `subject_kind='pt_package'`.
- **REF-06** — admin-web AlertDialog + H-13 "Понимаю, что возврат
  необратим" checkbox + client/plan/amount/date display land in Phase 35
  FE-13. Current phase delivers the backend REST endpoint only;
  full-amount-only refund (B-02) and reason ≤200 chars are enforced
  server-side via `MembershipRefundRequest`.

## Threat Surface — Coverage Confirmation

Every entry in the plan's `<threat_model>` (T-32-03-01 through T-32-03-08)
maps to a passing test:

| Threat ID | Mitigation Test |
|-----------|-----------------|
| T-32-03-01 — amountKopecks tampering | `test_refund_rejects_amount_kopecks_field_422` |
| T-32-03-02 — concurrent refund race | `test_concurrent_refund_loses_at_db_layer` (REF-TEST-01) |
| T-32-03-03 — refund of frozen | `test_refund_must_unfreeze_first_409` |
| T-32-03-04 — refund of renewed source | `test_refund_cannot_refund_renewed_source_409` |
| T-32-03-05 — refund-of-refund cycle | Defended by issue_refund WHERE amount > 0 + CHECK ck_payments_amount_sign_matches_subject_kind (Plan 32-01) — refund row cannot match the sale-side filter |
| T-32-03-06 — repudiation / no chain | `test_refund_audit_chain_order` + `test_refund_issued_payload_includes_payment_row_hash` |
| T-32-03-07 — reception bypass | `test_refund_reception_allowed` + `test_refund_owner_allowed` (B-07 documented uniform) |
| T-32-03-08 — refund of admin-cancelled | `test_refund_invalid_transition_409_when_already_cancelled` |

No new threat flags discovered.

## Verification Evidence

- **mypy --strict**: clean on `memberships/service.py`, `memberships/router.py`,
  `memberships/repository.py`, `memberships/schemas.py` (4 source files).
- **lint-imports**: 3/3 contracts kept (core ⊥ modules, modules ⊥ each other,
  integrations ⊥ modules).
- **AST commit-gate (SVC001)**: green — `refund_membership` owns its
  `await session.commit()` literally; walker accepts.
- **AST append-only (test_payments_appendonly)**: green — no new
  `update(Payment)` / `delete(Payment)` callsites.
- **AST audit-taxonomy**: green — `"membership_refunded"` is a literal string
  at the emit callsite (line 791), `"membership"` is a literal at
  `resource_type`.
- **Wider unit suite**: 428/428 green.
- **payments + memberships integration**: 212/212 green.
- **Wider integration suite**: 481/481 green (4 pre-existing `rbac_parity`
  failures deselected — Plan 32-01 `deferred-items.md`).

## Self-Check: PASSED

**Files verified to exist:**
- FOUND: apps/backend/app/modules/memberships/service.py
- FOUND: apps/backend/app/modules/memberships/router.py
- FOUND: apps/backend/app/modules/memberships/repository.py
- FOUND: apps/backend/app/modules/memberships/schemas.py
- FOUND: apps/backend/tests/integration/payments/test_payments_refund.py
- FOUND: apps/backend/tests/integration/payments/test_payments_refund_race.py
- FOUND: apps/backend/tests/integration/payments/test_payments_refund_audit_chain.py
- FOUND: apps/backend/tests/integration/memberships/conftest.py (modified)
- FOUND: apps/backend/tests/integration/payments/conftest.py (modified)

**Commits verified:**
- FOUND: ddbaf3d — Task 1 (has_renewal_descendants + 2 ConflictError subclasses + refund_membership orchestrator + MembershipRefundRequest schema)
- FOUND: 7261a81 — Task 2 (POST /api/v1/memberships/{id}/refund endpoint)
- FOUND: 42576b7 — Task 3 (15 integration tests + REF-TEST-01 race + 3 REF-07 audit chain tests + cancellation_reason projection bug fix)
