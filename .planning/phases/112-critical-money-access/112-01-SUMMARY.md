---
phase: 112-critical-money-access
plan: "01"
subsystem: backend/payments
tags: [refund, rbac, ledger, audit, money, payments]
dependency_graph:
  requires: []
  provides:
    - POST /api/v1/payments/{payment_id}/refund (owner-only manual ledger refund)
    - PaymentRefundRequest schema (amount_kopecks gt=0, reason min 3)
    - OverRefundError (code=over_refund, 409)
    - CannotRefundRefundError (code=cannot_refund_refund, 409)
    - refund_arbitrary_payment service function
  affects:
    - apps/backend/app/modules/payments/schemas.py
    - apps/backend/app/modules/payments/service.py
    - apps/backend/app/modules/payments/router.py
    - apps/backend/app/core/exceptions.py
tech_stack:
  added: []
  patterns:
    - FastAPI require_permission before verify_csrf (RBAC-04)
    - Service owns UoW (flush+commit) for standalone endpoints
    - IntegrityError discriminated to AlreadyRefundedError via constraint name
    - Audit emit with flat kwargs (refund_issued event)
    - ASGITransport integration tests with membership-sale seeding
key_files:
  created:
    - apps/backend/tests/integration/payments/test_payments_arbitrary_refund.py
  modified:
    - apps/backend/app/modules/payments/schemas.py
    - apps/backend/app/modules/payments/service.py
    - apps/backend/app/modules/payments/router.py
    - apps/backend/app/core/exceptions.py
decisions:
  - "D-112-01-APPROACH-B: Keep frozen uq_payments_refund_of_alive UNIQUE constraint; support single partial refund per original of any amount 1<=amount<=original; zero Alembic migration"
  - "D-112-01-SERVICE-OWNS-UOW: refund_arbitrary_payment calls flush+commit itself (unlike issue_refund which uses caller-owns-txn noqa); router is thin pass-through"
  - "D-112-01-AMOUNT-FIELD: PaymentRefundRequest has amount_kopecks gt=0 + reason min_length=3 per D-112 decision"
metrics:
  duration: "~4 minutes"
  completed: "2026-06-15"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 4
---

# Phase 112 Plan 01: Arbitrary Payment Refund Backend Summary

**One-liner:** Backend ledger refund endpoint (POST /payments/{id}/refund) with partial-amount support, OWNER_ONLY RBAC, CSRF, and refund_issued audit — backed by 8 ASGITransport integration tests covering all error paths.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Refund schema + exception classes | 583d0198 | schemas.py, exceptions.py |
| 2 | refund_arbitrary_payment service fn + router endpoint | f026a72d | service.py, router.py |
| 3 | ASGITransport integration tests | 10f480a0 | test_payments_arbitrary_refund.py |

## What Was Built

### Task 1: Schema + Exceptions

`PaymentRefundRequest(BackendSchemaBase)` added to `payments/schemas.py`:
- `amount_kopecks: int = Field(gt=0, ...)` — Pydantic blocks zero/negative at schema layer
- `reason: str = Field(min_length=3, max_length=500)` — per D-112 decision
- `extra='forbid'` inherited from `BackendSchemaBase`

Two new exception classes in `core/exceptions.py`:
- `CannotRefundRefundError(ConflictError)` — code=`cannot_refund_refund`, status_code=409
- `OverRefundError(ConflictError)` — code=`over_refund`, status_code=409

### Task 2: Service Function + Router Endpoint

`refund_arbitrary_payment` in `payments/service.py`:
1. Fetch original via `repository.get_payment_by_id` → 404 if missing
2. Reject `subject_kind == SUBJECT_KIND_REFUND` → `CannotRefundRefundError` (409)
3. Reject `amount_kopecks > original.amount_kopecks` → `OverRefundError` (409)
4. Insert refund row: negative amount, `refund_of=original.id`, `subject_kind='refund'`
5. `session.flush()` → catch `IntegrityError` discriminated by `_is_refund_of_uniqueness_conflict` → `AlreadyRefundedError` (409)
6. Emit `refund_issued` audit with full flat-kwargs field set (original hash)
7. `session.flush()` + `session.commit()` — service owns the UoW

`POST /{payment_id}/refund` endpoint in `payments/router.py`:
- `require_permission(Action.REFUND, Resource.FINANCE)` declared BEFORE `verify_csrf` (RBAC-04)
- Returns `ResponseEnvelope[PaymentResponse]` with `status.HTTP_201_CREATED`
- No try/except in router — global AppError handler maps exceptions

### Task 3: Integration Tests

8 test scenarios in `test_payments_arbitrary_refund.py` — all green:
1. `test_arbitrary_refund_full_amount_201` — owner full refund, DB invariant checked
2. `test_arbitrary_refund_partial_amount_201` — owner half-amount refund
3. `test_arbitrary_refund_over_amount_409` — over-refund → 409 over_refund
4. `test_arbitrary_refund_double_409` — second refund → 409 already_refunded
5. `test_arbitrary_refund_of_refund_409` — refund row targeted → 409 cannot_refund_refund
6. `test_arbitrary_refund_reception_403` — RBAC gate: reception → 403
7. `test_arbitrary_refund_csrf_missing_403` — no X-CSRF-Token → 403 csrf_mismatch
8. `test_arbitrary_refund_missing_payment_404` — random UUID → 404 original_payment_not_found

## Decisions Made

- **D-112-01-APPROACH-B:** Kept frozen `uq_payments_refund_of_alive` UNIQUE constraint (approach b from CONTEXT.md); supports single partial refund per original (any amount 1≤amount≤original); zero Alembic migration needed.
- **D-112-01-SERVICE-OWNS-UOW:** `refund_arbitrary_payment` calls `flush()+commit()` itself (unlike `issue_refund` which uses `# noqa: SVC001 caller-owns-txn`). This is a standalone endpoint with no cross-module orchestration.
- **D-112-01-NO-NOQA-SVC001:** Per plan instructions, the `# noqa: SVC001 caller-owns-txn` marker is NOT added because the service OWNS the commit for this endpoint.

## Deviations from Plan

None — plan executed exactly as written. The `# noqa: SVC001` warning in PATTERNS.md was correctly identified as stale (the plan explicitly says "do NOT add the SVC001 noqa marker here").

## Verification Results

- `uv run ruff check app/modules/payments/` → clean
- `uv run mypy app/modules/payments/` → "Success: no issues found in 9 source files"
- `uv run pytest tests/integration/payments/test_payments_arbitrary_refund.py -x -q` → 8 passed in ~3s
- Refund route registered: `any(rt.path.endswith('/{payment_id}/refund') for rt in router.routes)` → True

## Requirements Fulfilled

- REF-01: Owner can POST /payments/{id}/refund with amount + reason → 201 + new refund row ✓
- Reception → 403 RBAC before CSRF ✓
- Partial amount ≤ original accepted; amount > original → 409 over_refund ✓
- Second refund of same original → 409 already_refunded (unique constraint) ✓
- Refunding a refund row → 409 cannot_refund_refund ✓
- Every successful refund emits refund_issued audit row ✓

## Self-Check: PASSED

All created/modified files found on disk. All 3 task commits verified in git log:
- 583d0198 — Task 1: schema + exceptions
- f026a72d — Task 2: service fn + router endpoint
- 10f480a0 — Task 3: integration tests
