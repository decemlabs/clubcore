---
phase: 112-critical-money-access
reviewed: 2026-06-15T00:00:00Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - apps/admin-app/src/components/modals/ChangeRoleModal.tsx
  - apps/admin-app/src/components/modals/RefundModal.tsx
  - apps/admin-app/src/features/payments/api.ts
  - apps/admin-app/src/features/users/api.ts
  - apps/admin-app/src/pages/cashbox/CashboxPage.tsx
  - apps/admin-app/src/pages/cashbox/components/TransactionsCard.tsx
  - apps/admin-app/src/pages/finance/FinancePage.tsx
  - apps/admin-app/src/pages/finance/components/OnlinePaymentsTable.tsx
  - apps/admin-app/src/pages/settings/components/SectionsBottom.tsx
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/core/exceptions.py
  - apps/backend/app/modules/payments/router.py
  - apps/backend/app/modules/payments/schemas.py
  - apps/backend/app/modules/payments/service.py
  - apps/backend/app/modules/users/repository.py
  - apps/backend/app/modules/users/router.py
  - apps/backend/app/modules/users/schemas.py
  - apps/backend/app/modules/users/service.py
  - apps/backend/tests/integration/payments/test_payments_arbitrary_refund.py
  - apps/backend/tests/integration/users/test_users_role_change.py
  - apps/backend/tests/unit/test_audit_taxonomy.py
  - packages/api-client/src/schema.d.ts
findings:
  critical: 0
  warning: 6
  info: 4
  total: 10
status: issues_found
---

# Phase 112: Code Review Report

**Reviewed:** 2026-06-15
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

P0 money + access-control phase: arbitrary-payment refund (partial allowed) + staff
role change. The core security properties hold up under adversarial inspection:

- **RBAC** — both endpoints map to `OWNER_ONLY` pairs (`(REFUND, FINANCE)` and
  `(UPDATE, USERS)`); `require_permission` is declared BEFORE `verify_csrf` in both
  signatures so 401 fires before 403 (RBAC-04 ordering). Reception-403 is covered by tests.
- **CSRF** — `verify_csrf` Depends present on both mutating routes; missing-token-403
  covered by tests.
- **Refund amount validation** — `amount_kopecks` has `Field(gt=0)` (422 on ≤0);
  service enforces `> original → over_refund` (409); duplicate refund blocked by the
  partial-UNIQUE `uq_payments_refund_of_alive` → `already_refunded` (409); refund-of-refund
  blocked by `subject_kind == 'refund'` guard → `cannot_refund_refund` (409). Negative
  amounts impossible (model CHECK forces refund rows negative; service inserts `-amount`).
- **Privilege escalation / lockout** — `cannot_change_own_role` self-guard and
  `cannot_change_last_owner_role` (row-locking `count_active_owners_excluding`) both
  present and tested.
- **Audit completeness** — `refund_issued` (RefundIssuedPayload) and `user_role_changed`
  (UserRoleChangedPayload) are locked + schema-validated with `extra='forbid'`; emit
  kwargs match the payload fields; old_role captured before the bulk UPDATE.
- **Money in kopecks** — integer math throughout; FE `Math.round(amountNum * 100)`.
- **Wire-shape alignment** — generated `schema.d.ts` confirms camelCase `{ amountKopecks,
  reason }` and `{ role }` request bodies match the FE hooks.

No BLOCKER-class defects found. The findings below are robustness / correctness-margin
issues (mostly error-mapping drift and missing server-side guards that the UI happens
to mask), plus a few quality items.

## Warnings

### WR-01: `already_refunded` over-refund toast misleads the operator

**File:** `apps/admin-app/src/components/modals/RefundModal.tsx:60-61`
**Issue:** `handleRefundError` maps `already_refunded` to the SAME message as
`over_refund` ("сумма превышает доступный остаток" / amount exceeds available remainder).
But `already_refunded` means the payment was already refunded once (the partial-UNIQUE
fired) — it has nothing to do with amount. An operator who issues a second partial refund
(allowed conceptually — partial refunds are advertised) gets a wrong explanation and no
indication that the original is already fully closed for refunds. This is a money-flow
UX defect on a P0 path.
**Fix:**
```ts
} else if (err.code === 'already_refunded') {
  toast.error('Этот платёж уже был возвращён');
}
```

### WR-02: Partial refund is single-shot but UI implies cumulative top-ups

**File:** `apps/backend/app/modules/payments/service.py:277,291-297` and
`apps/admin-app/src/components/modals/RefundModal.tsx:88-92,167`
**Issue:** The schema/UI present partial refunds ("Частичный возврат разрешён — не более
доступного остатка" / "доступно к возврату") as if an operator can refund 50% now and the
remaining 50% later. The DB partial-UNIQUE on `refund_of` permits **exactly one** refund
row per original, so a second partial refund of the same payment fails with
`already_refunded` regardless of how much was refunded the first time. After a 50% partial
refund the other 50% is permanently unrecoverable through this endpoint. `alreadyRefundedKopecks`
is hardcoded to `0` (RefundModal.tsx:90) so "Доступно к возврату" always shows the full
amount even after a partial refund already happened. This is a latent money-correctness gap:
operators will believe funds are still refundable when they are not.
**Fix:** Either (a) document/limit the UI to full-only refunds for Phase 112, or (b) track
prior refunds (sum existing `refund_of` rows for the original) and validate cumulative
`Σ refunds + new ≤ original`, dropping the single-row UNIQUE in favor of a cumulative check.
At minimum, surface the real remaining amount instead of hardcoding `alreadyRefundedKopecks = 0`.

### WR-03: `change_user_role` does not verify target is active

**File:** `apps/backend/app/modules/users/service.py:355-368`
**Issue:** The guard chain uses `get_alive` (only `deleted_at IS NULL`) and never checks
`target.is_active`. A deactivated (but not deleted) user's role can be changed. The FE only
exposes the «Изменить роль» action for `status === 'active'` rows (SectionsBottom.tsx:801,821),
so the UI masks this — but the endpoint is the security boundary and a crafted PATCH will
silently mutate a deactivated user's role. Combined with the role taking effect on next login
(no session invalidation), an owner could pre-stage a privilege change on an account they
intend to reactivate, with no `is_active` gate. Behaviorally low-severity (a deactivated user
has no session and cannot log in), but it diverges from the documented guard set and from the
deactivate/soft-delete siblings which DO branch on state.
**Fix:** Add an explicit state decision: either reject role change on inactive users
(`if not target.is_active: raise UserNotActive...`) or document that role change is
intentionally allowed regardless of `is_active` (mirror the soft_delete_user docstring rationale).

### WR-04: No-op role change passes all guards and emits a spurious audit row

**File:** `apps/backend/app/modules/users/service.py:360,377-389`
**Issue:** A PATCH with `role` equal to the target's current role is not rejected. It runs
the UPDATE (no-op) and emits a `user_role_changed` audit row with `old_role == new_role`.
The `UserRoleChangedPayload` regex accepts it. The FE blocks this via `sameRole` (ChangeRoleModal.tsx:88),
but a direct API call pollutes the forensic audit trail with phantom role changes that never
happened. On a money/access audit surface, false "role changed" entries are a forensic-integrity
problem.
**Fix:** Short-circuit before mutate/emit:
```python
if target.role == new_role:
    return  # no-op; or raise a 409 "role_unchanged" if the contract prefers
```

### WR-05: `handle409` checks `already_inactive` but backend emits `user_already_inactive`

**File:** `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx:767`
**Issue:** `UserAlreadyInactiveError.code = "user_already_inactive"`
(exceptions.py:383), but `handle409` branches on `err.code === 'already_inactive'`. The
specific Russian toast ("Пользователь уже неактивен") never fires; the deactivate flow falls
through to the generic "Не удалось выполнить действие" message. Pre-existing Phase-104 drift,
but it lives in a Phase-112 reviewed file and degrades the team-management error UX.
**Fix:**
```ts
} else if (err.code === 'user_already_inactive') {
  toast.error('Пользователь уже неактивен');
}
```

### WR-06: `PaymentResponse.received_by_user_id` non-nullable vs. nullable column / FE schema

**File:** `apps/backend/app/modules/payments/schemas.py:54` and
`apps/admin-app/src/features/payments/schemas.ts:28`
**Issue:** `PaymentResponse.received_by_user_id: UUID` (required) and FE
`PaymentSchema.receivedByUserId: z.string()` (required) both assume a non-null operator.
But the `payments.received_by_user_id` column is nullable (Alembic 0036 — ЮKassa-webhook
rows are anonymous, `received_by_user_id IS NULL`, per record_payment docstring). The Finance
«Онлайн-платежи» table (OnlinePaymentsTable) renders exactly these online rows. A webhook-
originated online payment row will (a) fail `PaymentResponse.model_validate` on the GET list,
or (b) fail the FE `z.string()` parse — breaking the very table from which the refund action
is launched. Not introduced by Phase 112, but Phase 112 wires the refund action onto that
table, making the latent drift load-bearing for this phase.
**Fix:** Make both nullable: backend `received_by_user_id: UUID | None = None`; FE
`receivedByUserId: z.string().nullable()`.

## Info

### IN-01: Redundant flush before commit in `refund_arbitrary_payment`

**File:** `apps/backend/app/modules/payments/service.py:316-317`
**Issue:** `await session.flush()` immediately followed by `await session.commit()`. The
commit flushes implicitly; the extra flush is dead work. Harmless but noise on a function
that already flushes inside the try block (line 292).
**Fix:** Drop the line 316 `flush()`; keep only `commit()`.

### IN-02: Dead `cannot_demote_last_owner` branch in role-change error handler

**File:** `apps/admin-app/src/components/modals/ChangeRoleModal.tsx:51-53`
**Issue:** The handler maps both `cannot_change_last_owner_role` (the code the backend
actually emits) and `cannot_demote_last_owner` (never emitted by the backend — see
exceptions.py:518-526). The defensive double-mapping is fine but the second literal is dead
and the comment admits it is speculative.
**Fix:** Remove `cannot_demote_last_owner` once confirmed no other code path emits it, or
keep with a clearer "legacy alias" comment.

### IN-03: `amount_override` parameter is documented as a no-op in test helper

**File:** `apps/backend/tests/integration/payments/test_payments_arbitrary_refund.py:57-65`
**Issue:** `_seed_sale_payment` declares `amount_override: int | None = None` and the docstring
states it is "not supported … but we keep the parameter slot for clarity." A never-used
parameter that cannot affect behavior is misleading test scaffolding.
**Fix:** Remove the parameter; it is never passed by any caller.

### IN-04: No test covers partial-then-second-partial refund rejection

**File:** `apps/backend/tests/integration/payments/test_payments_arbitrary_refund.py`
**Issue:** `test_arbitrary_refund_double_409` issues a full refund then a second full refund.
There is no test for the partial-refund-then-partial-refund case, which is the exact scenario
WR-02 describes (operator does 50%, then tries the remaining 50% and is blocked). Given the UI
advertises partial refunds, this is the missing-coverage that would have surfaced WR-02.
**Fix:** Add a test: partial refund (amount < original) → 201, then second partial of the same
original → 409 `already_refunded`, asserting the remaining balance is unrecoverable.

---

_Reviewed: 2026-06-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
