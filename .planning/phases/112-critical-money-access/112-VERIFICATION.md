---
phase: 112-critical-money-access
verified: 2026-06-15T12:00:00Z
status: human_needed
score: 8/8
overrides_applied: 0
human_verification:
  - test: "Refund flow — Cashbox (owner). Log in as owner@clubcore.dev. Open Касса. On a non-refund payment row, open the «...» menu. Confirm «Оформить возврат» is present. Enter a partial amount and a reason >=3 chars, confirm."
    expected: "Success toast «Возврат оформлен» + new «Возврат» row (red, −amount) appears. Trying to refund the same row again shows «Этот платёж уже был возвращён» and the modal stays open."
    why_human: "Live render of modal fields, default amount value, Sonner toast appearance, and ledger row re-render cannot be verified statically."
  - test: "Refund flow — Finance table (owner). Open Финансы → Онлайн-платежи. Confirm «Оформить возврат» action is present on a non-refund row."
    expected: "Same modal opens and works; success toast + new refund row after invalidation."
    why_human: "Finance page role threading and modal render require browser verification."
  - test: "Role-change flow (owner). Open Настройки → Команда. On an active non-self user, open «...» → «Изменить роль». Pick the other role, confirm."
    expected: "Toast «Роль изменена → {fullName} → {newRoleLabel}» + team list re-renders with new role badge. Info callout «Роль вступит в силу при следующем входе сотрудника.» is visible in the modal."
    why_human: "ChipGroup selection, info callout visibility, and team-list re-render require browser verification."
  - test: "Reception gate. Log in as reception. Open Касса, Финансы, Настройки → Команда."
    expected: "NO «Оформить возврат» action anywhere in Cashbox/Finance, and NO «Изменить роль» action in the Team list. Actions are HIDDEN (not disabled — zero DOM render for the trigger)."
    why_human: "RBAC gating on the UI layer (hidden vs. disabled) and absence of DOM elements requires browser verification."
---

# Phase 112: Critical Money Access — Verification Report

**Phase Goal:** Owner can refund any recorded payment (not just membership/PT) and can change a staff user's role — the two P0 operational gaps that block daily gym management.
**Verified:** 2026-06-15T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Owner can POST `/api/v1/payments/{payment_id}/refund` with amount + reason and get 201 + new refund row | VERIFIED | `refund_arbitrary_payment` in service.py:249; `refund_payment_endpoint` in router.py:116; spot-check test_arbitrary_refund_full_amount_201 PASSED (0.47s) |
| 2 | Reception calling the refund endpoint gets 403 (RBAC) before CSRF | VERIFIED | `require_permission(Action.REFUND, Resource.FINANCE)` at router.py:119 before `verify_csrf` at line 120; spot-check test_arbitrary_refund_reception_403 PASSED (0.53s) |
| 3 | A partial amount <= original is accepted; amount > original is rejected 409 over_refund | VERIFIED | Service enforces `amount_kopecks > original.amount_kopecks` → `OverRefundError`; `OverRefundError.code='over_refund'`, status_code=409; Python import check OK |
| 4 | A second refund of the same original is rejected 409 already_refunded (unique constraint) | VERIFIED | `uq_payments_refund_of_alive` UNIQUE constraint → `AlreadyRefundedError`; test_arbitrary_refund_double_409 + test_arbitrary_refund_partial_then_second_partial_409 both collected (9 tests) |
| 5 | Refunding a refund row is rejected 409 cannot_refund_refund | VERIFIED | Service checks `original.subject_kind == SUBJECT_KIND_REFUND` → `CannotRefundRefundError`; code='cannot_refund_refund', status_code=409; import check OK |
| 6 | Every successful refund emits a refund_issued audit row | VERIFIED | `audit.emit("refund_issued", ...)` at service.py:303; committed in same UoW as insert |
| 7 | Owner can PATCH `/api/v1/users/{user_id}/role` and get 204; role persisted; audited | VERIFIED | `change_user_role` at service.py:336; `change_user_role_endpoint` in router.py:156; PATCH route registered (import check OK); `user_role_changed` in LOCKED_AUDIT_EVENTS; spot-check test_successful_role_change_writes_audit_row PASSED (0.41s) |
| 8 | Reception calling the role endpoint gets 403; self-change → 409; last-owner demotion → 409; current sessions keep old role (no invalidation) | VERIFIED | `require_permission(Action.UPDATE, Resource.USERS)` BEFORE `verify_csrf` in router.py:159-160; `CannotChangeOwnRoleError`+`CannotChangeLastOwnerRoleError` in service guard chain; no session invalidator call (confirmed by code read); spot-check test_reception_cannot_change_role_returns_403 PASSED (0.41s) |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/modules/payments/schemas.py` | `PaymentRefundRequest` (amount_kopecks gt=0, reason min 3) | VERIFIED | `class PaymentRefundRequest(BackendSchemaBase)` at line 82; Pydantic validation spot-check passed |
| `apps/backend/app/modules/payments/service.py` | `refund_arbitrary_payment(payment_id, amount_kopecks, reason, audit_actor)` | VERIFIED | `async def refund_arbitrary_payment` at line 249; 209-line impl with all guards |
| `apps/backend/app/modules/payments/router.py` | POST `/{payment_id}/refund` endpoint, REFUND+FINANCE gated, CSRF | VERIFIED | `refund_payment_endpoint` at line 116; RBAC-04 ordering confirmed |
| `apps/backend/app/core/exceptions.py` | `CannotRefundRefundError` + `OverRefundError` | VERIFIED | Lines 480, 491; codes and status_codes confirmed |
| `apps/backend/tests/integration/payments/test_payments_arbitrary_refund.py` | 8+ ASGITransport tests covering all paths | VERIFIED | 9 tests collected: full, partial, over, double, partial-then-partial, refund-of-refund, reception-403, csrf-403, 404 |
| `apps/backend/app/core/audit.py` | `('user_role_changed','user')` in LOCKED_AUDIT_EVENTS | VERIFIED | Line 407; import check confirmed |
| `apps/backend/app/core/audit_payloads.py` | `UserRoleChangedPayload` | VERIFIED | Line 1416; registered in AUDIT_PAYLOAD_SCHEMAS at line 1552; includes `audit_correlation_id: UUID | None` |
| `apps/backend/app/modules/users/repository.py` | `update_user_role(target_user_id, new_role)` | VERIFIED | `async def update_user_role` at line 389 |
| `apps/backend/app/modules/users/service.py` | `change_user_role` with self + last-owner guards + audit | VERIFIED | Line 336; guard chain: get_alive → self-guard → last-owner-lock → update → audit emit |
| `apps/backend/app/modules/users/schemas.py` | `UserRoleChangeRequest{role}` | VERIFIED | `class UserRoleChangeRequest` at line 89 |
| `apps/backend/app/modules/users/router.py` | PATCH `/{user_id}/role` endpoint (UPDATE,USERS) + CSRF, 204 | VERIFIED | `change_user_role_endpoint` at line 156; RBAC-04 ordering confirmed |
| `apps/backend/tests/integration/users/test_users_role_change.py` | 6+ ASGITransport tests | VERIFIED | 10 tests collected: promote, demote, persist, reception-403, csrf-403, self-409, last-owner-409, audit-row, inactive-409 (WR-03), no-op-409 (WR-04) |
| `apps/admin-app/src/features/payments/api.ts` | `useRefundPayment` mutation hook | VERIFIED | Exported at line 100; `mutationFn` POSTs to `/api/v1/payments/{payment_id}/refund`; `onSettled` invalidates `paymentsKeys.lists()` |
| `apps/admin-app/src/features/users/api.ts` | `useChangeUserRole` mutation hook | VERIFIED | Exported at line 146; `mutationFn` PATCHes to `/api/v1/users/{user_id}/role`; `onSettled` invalidates `usersKeys.lists()` |
| `apps/admin-app/src/components/modals/RefundModal.tsx` | Refund confirmation dialog (amount + reason) | VERIFIED | 209 lines; `AdaptiveModal` with `IconChip tone="warn"`, amount + reason fields, `handleRefundError` maps 3 distinct codes; WR-01 fix: `already_refunded` → «Этот платёж уже был возвращён» (distinct message); WR-02 fix: single-refund contract documented in-code |
| `apps/admin-app/src/components/modals/ChangeRoleModal.tsx` | Staff role-change dialog | VERIFIED | 159 lines; `AdaptiveModal` with `IconChip tone="indigo"`, ChipGroup, info callout; maps `cannot_change_last_owner_role` (no dead `cannot_demote_last_owner` alias after fix) |
| `apps/admin-app/src/pages/cashbox/components/TransactionsCard.tsx` | Refund row action (owner-gated) replacing FAKEREFUND stub | VERIFIED | `RefundModal` imported at line 31; `can(role, 'refund', 'finance')` at line 82; T-103-03-FAKEREFUND stub comment removed (grep confirms zero matches in entire codebase) |
| `apps/admin-app/src/pages/settings/components/SectionsBottom.tsx` | «Изменить роль» dropdown item + ChangeRoleModal | VERIFIED | `ChangeRoleModal` imported at line 10; `can(role, 'update', 'users')` at line 821; «Изменить роль» text at line 831 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `payments/router.py` | `payments.service.refund_arbitrary_payment` | router calls service inside request | WIRED | Pattern `refund_arbitrary_payment` confirmed in router |
| `payments/router.py` | `require_permission(Action.REFUND, Resource.FINANCE)` | FastAPI dependency before verify_csrf | WIRED | Line 119 before line 120 confirmed |
| `users/router.py` | `users.service.change_user_role` | router calls service | WIRED | `change_user_role` confirmed in router at line 156+ |
| `users/service.py` | `audit.emit user_role_changed` | audit emitted in same UoW as UPDATE | WIRED | `audit.emit("user_role_changed", ...)` at service.py:398 |
| `users/service.py` | `repository.count_active_owners_excluding` | last-owner demotion guard | WIRED | `count_active_owners_excluding` at service.py:381 |
| `RefundModal.tsx` | `features/payments/api.ts useRefundPayment` | mutation call on confirm | WIRED | `useRefundPayment` imported and called in `handleSubmit` |
| `TransactionsCard.tsx` | `RefundModal` | row action opens modal, owner-gated by `can(role, 'refund', 'finance')` | WIRED | `can(role, 'refund', 'finance')` at line 82; `<RefundModal` rendered at line 231 |
| `ChangeRoleModal.tsx` | `features/users/api.ts useChangeUserRole` | mutation call on confirm | WIRED | `useChangeUserRole` imported and called in `handleSubmit` |
| `SectionsBottom.tsx` | `ChangeRoleModal` | dropdown item opens modal, owner-gated | WIRED | `can(role, 'update', 'users')` at line 821; `<ChangeRoleModal` at line 880 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `RefundModal.tsx` | `payment` prop (id, amountKopecks, etc.) | Passed from `TransactionsCard`/`OnlinePaymentsTable` via `usePaymentsLedger` real query | Yes — TanStack Query from live backend | FLOWING |
| `ChangeRoleModal.tsx` | `user` prop (id, fullName, role) | Passed from `SectionsBottom` via users list query | Yes — TanStack Query from live backend | FLOWING |
| `useRefundPayment` | Mutation result (PaymentResponse) | POSTs to `/api/v1/payments/{payment_id}/refund` → `refund_arbitrary_payment` → DB insert | Yes — real DB insert + audit | FLOWING |
| `useChangeUserRole` | Mutation result (204 No Content) | PATCHes to `/api/v1/users/{user_id}/role` → `change_user_role` → DB UPDATE | Yes — real DB UPDATE + audit | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Owner can refund full amount (201) | `pytest test_arbitrary_refund_full_amount_201 -x -q` | 1 passed in 0.47s | PASS |
| Reception gets 403 on refund | `pytest test_arbitrary_refund_reception_403 -x -q` | 1 passed in 0.53s | PASS |
| Reception gets 403 on role change | `pytest test_reception_cannot_change_role_returns_403 -x -q` | 1 passed in 0.41s | PASS |
| Audit row written on role change | `pytest test_successful_role_change_writes_audit_row -x -q` | 1 passed in 0.41s | PASS |
| PaymentRefundRequest validation (amount>0, reason>=3) | `uv run python -c "..."` import/validation check | OK | PASS |
| Refund route + role route registered | `uv run python -c "..."` route registry check | OK | PASS |

### Probe Execution

No probe scripts found — phase does not declare probes. Step 7c: SKIPPED (no probe scripts).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| REF-01 | 112-01, 112-03 | Owner can refund an arbitrary recorded payment (cash / non-membership / non-PT) from Cashbox or Finance, with a reason; the refund is recorded and the ledger/cashbox reflects it (removes T-103-03-FAKEREFUND stub) | SATISFIED | Backend endpoint + service + tests (9 tests) + FE modal wired in Cashbox + Finance; FAKEREFUND stub removed |
| TEAM-01 | 112-02, 112-03 | Owner can change the role (owner ↔ reception) of an existing staff user from the Team/Settings screen, with the change persisted and audited; reception cannot | SATISFIED | Backend endpoint + service + repository + audit + tests (10 tests) + FE modal wired in Settings Team list |

No orphaned requirements — REQUIREMENTS.md maps only REF-01 and TEAM-01 to Phase 112.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| No blockers found | — | No TBD/FIXME/XXX debt markers in any modified file | Info | — |

All 6 WARNINGs and 4 INFO items from the code review (15dda17f..1e00bcb7) were resolved:

- WR-01 (already_refunded misleading toast): FIXED — maps to «Этот платёж уже был возвращён» (distinct from over_refund)
- WR-02 (single-shot refund honesty): FIXED — UI single-refund contract documented in-code; `alreadyRefundedKopecks` stub removed
- WR-03 (inactive user guard): FIXED — `CannotChangeInactiveUserRoleError` added; service rejects inactive target; test added
- WR-04 (no-op role change audit pollution): FIXED — `RoleUnchangedError` 409 before mutate/emit; test added
- WR-05 (already_inactive code mismatch): FIXED — `user_already_inactive` (correct code) in SectionsBottom handle409
- WR-06 (received_by_user_id nullable): FIXED — backend `UUID | None = None`; FE `z.string().nullable()`
- IN-01 (redundant flush): FIXED — commit 22a34e06
- IN-02 (dead cannot_demote_last_owner branch): FIXED — removed from ChangeRoleModal
- IN-03 (dead test parameter): FIXED — commit f87c9937
- IN-04 (missing partial-then-partial test): FIXED — `test_arbitrary_refund_partial_then_second_partial_409` added (9th test)

### Human Verification Required

The following items require live browser UAT against the running dev stack (`docker compose up` in `apps/backend` + `pnpm -F @clubcore/admin-app dev` on http://localhost:5173). These were auto-deferred from Plan 03 Task 4 per the operator-pending-verify memory.

### 1. Refund Flow — Cashbox (Owner)

**Test:** Log in as owner@clubcore.dev / ownerpass12345. Open Касса. On a non-refund payment row, open the «...» menu. Confirm «Оформить возврат» action is present. Enter a partial amount and a reason >=3 chars, confirm. Then attempt to refund the same row again.

**Expected:** Success toast «Возврат оформлен» (with formatted amount) + new «Возврат» row (red, negative amount) appears in ledger. Second attempt shows «Этот платёж уже был возвращён» and the modal stays open (no close on error).

**Why human:** Live render of modal fields (default amount = full original in rubles), Sonner toast appearance, ledger row re-render after `paymentsKeys.lists()` invalidation — cannot be verified statically.

### 2. Refund Flow — Finance (Owner)

**Test:** Open Финансы → Онлайн-платежи. Confirm «Оформить возврат» is present on a non-refund row. Trigger a refund.

**Expected:** Same RefundModal opens; success toast + new refund row after invalidation.

**Why human:** Finance page role threading (FinancePage → OnlineTab → OnlinePaymentsTable) and modal render in the Finance context require browser verification.

### 3. Role-Change Flow (Owner)

**Test:** Open Настройки → Команда. On an active non-self user, open «...» → «Изменить роль». Pick the other role and confirm.

**Expected:** Toast «Роль изменена» with «{fullName} → {newRoleLabel}» description. Team list re-renders with the new role badge. Info callout «Роль вступит в силу при следующем входе сотрудника. Текущая сессия продолжается с прежними правами.» is visible in the ChangeRoleModal.

**Why human:** ChipGroup selection UI, info callout visibility, and team-list re-render after `usersKeys.lists()` invalidation require browser verification.

### 4. Reception RBAC Gate (UI Hidden — Not Disabled)

**Test:** Log in as reception. Open Касса, Финансы, Настройки → Команда.

**Expected:** No «Оформить возврат» action in Cashbox or Finance (row «...» menus do not exist at all for reception, or the refund item is absent). No «Изменить роль» item in the Settings Team list for any user.

**Why human:** Verifying that actions are HIDDEN (zero DOM render) vs. merely disabled is a visual/DOM inspection task; grep shows `can(role, ...)` is used correctly, but absence of render in the actual browser requires visual confirmation.

### Gaps Summary

No automated gaps found. All 8 observable truths verified across 3 plans. All code review findings (6 WARNINGs, 4 INFO) resolved and confirmed by commit history. The 4 items above are browser UAT deferrals — automated verification is complete and passing.

---

_Verified: 2026-06-15T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
