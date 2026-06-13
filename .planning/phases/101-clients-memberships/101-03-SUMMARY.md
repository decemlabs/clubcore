---
phase: "101"
plan: "03"
subsystem: admin-app
tags: [memberships, pt-packages, lifecycle, optimistic-mutations, refund, tdd]
dependency_graph:
  requires: ["101-02"]
  provides: ["MEM-02", "MEM-03"]
  affects: ["features/memberships", "features/pt-packages", "components/modals/SubscriptionModal"]
tech_stack:
  added: []
  patterns:
    - "Optimistic mutation: onMutate→cancelQueries→snapshot→setQueryData→onError rollback→onSettled invalidate (freeze/unfreeze)"
    - "Per-attempt Idempotency-Key via crypto.randomUUID() inside mutationFn (T-101-08-DOUBLECHARGE)"
    - "Non-optimistic lifecycle mutations with invalidate+toast (sell/renew/cancel/refund)"
    - "TDD RED/GREEN cycle: failing test → schema implementation → 27 passing tests"
key_files:
  created:
    - apps/admin-app/src/features/memberships/keys.ts
    - apps/admin-app/src/features/memberships/schemas.ts
    - apps/admin-app/src/features/memberships/api.ts
    - apps/admin-app/src/features/memberships/schemas.test.ts
  modified:
    - apps/admin-app/src/features/pt-packages/api.ts
    - apps/admin-app/src/components/modals/SubscriptionModal.tsx
    - apps/admin-app/src/components/modals/modals-context.ts
    - apps/admin-app/src/components/modals/fields.tsx
    - apps/admin-app/src/components/icons/index.tsx
decisions:
  - "D-101-03-PATH-PARAMS: Backend paths use {membership_id} and {pt_package_id}, not {id} — matched to schema.d.ts before typing"
  - "D-101-03-RECEIPTX: lucide-react 0.469 has no ReceiptX icon; used ReceiptText as functional equivalent for RefundScreen"
  - "D-101-03-HISTORY-STUB: HistoryScreen remains on mock data (hardcoded HISTORY array); wiring to a history endpoint is deferred as no dedicated endpoint exists"
  - "D-101-03-EDIT-PLACEHOLDER: EditScreen replaced with a placeholder message; no backend edit endpoint for memberships is in scope for Phase 101"
  - "D-101-03-CANCEL-GATE: SubscriptionModal dispatcher returns null for 'cancel' screen when role is reception (can() gating before rendering)"
metrics:
  duration_seconds: 634
  completed_date: "2026-06-13"
  task_count: 2
  file_count: 9
---

# Phase 101 Plan 03: Memberships Lifecycle + SubscriptionModal Wiring Summary

**One-liner:** JWT-key-per-attempt membership sell/freeze/unfreeze/renew/cancel/refund lifecycle with optimistic freeze/unfreeze mutations and net-new RefundScreen; PT-package sell/cancel/refund hooks appended.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | memberships keys/schemas/api; pt-package instance hooks | b16289c7 | keys.ts, schemas.ts, api.ts, schemas.test.ts, pt-packages/api.ts |
| 2 | Wire SubscriptionModal lifecycle dialogs + net-new RefundScreen | b7ee57fd | SubscriptionModal.tsx, modals-context.ts, fields.tsx, icons/index.tsx |

## What Was Built

### Task 1: Memberships Feature Module + PT-Package Instance Hooks

**`features/memberships/keys.ts`** — query-key factory `membershipsKeys` with `all/lists()/list(filter)/details()/detail(id)/byClient(clientId)`.

**`features/memberships/schemas.ts`** — Zod contract layer:
- `FreezePeriodSchema` (id/startedAt/startedBy/endedAt/endedBy)
- `MembershipSchema` (embeds `MembershipPlanSchema` via planSnapshot; currentFreezePeriod nullable)
- `MembershipsListResponseSchema` (data-wrapped paginated list)
- `MembershipSellSchema` (clientId+planId required, paidAt/notes optional)
- `MembershipCancelSchema` (reason optional ≤500 chars)
- `MembershipRefundSchema` (reason required 1-200 chars, `«Причина обязательна для возврата»`)

**`features/memberships/schemas.test.ts`** — 27 TDD tests (RED/GREEN cycle) covering all schema validations per `<behavior>` block.

**`features/memberships/api.ts`** — full lifecycle hooks:
- `useMembershipsByClient(clientId)` — query with `enabled: !!clientId`
- `useMembership(id)` — single instance query
- `useSellMembership` — non-optimistic; `crypto.randomUUID()` inside mutationFn; invalidates lists+byClient on success
- `useFreezeMembership` — OPTIMISTIC: onMutate flips `status: 'frozen'` + injects placeholder `currentFreezePeriod`; onError rollback; onSettled invalidate
- `useUnfreezeMembership` — OPTIMISTIC: onMutate flips `status: 'active'` + clears `currentFreezePeriod: null`; same rollback pattern
- `useRenewMembership` — non-optimistic; `endDate`-based success toast via `formatDateRu`
- `useCancelMembership` — non-optimistic; OWNER_ONLY; 403 → specific toast `«Отмена абонемента доступна только владельцу»`
- `useRefundMembership` — non-optimistic; **NO Idempotency-Key** (per UI-SPEC §3.2); reason required 1-200

**PT-package instance hooks appended to `features/pt-packages/api.ts`:**
- `usePtPackagesByClient` — query
- `useSellPtPackage` — Idempotency-Key; `amountKopecks` required
- `useCancelPtPackage` — OWNER_ONLY; reason REQUIRED (unlike memberships cancel)
- `useRefundPtPackage` — Idempotency-Key (unlike memberships refund)

### Task 2: SubscriptionModal Wiring + RefundScreen

**`modals-context.ts`:**
- Added `'refund'` to `SubscriptionScreen` union
- Extended `subscription` payload with `membershipId?`, `clientId?`, `membership?` fields (backward-compatible — all optional)

**`SubscriptionModal.tsx`** — full rewrite preserving visual design:
- **CreateScreen** — wired to `useSellMembership` + `usePlans({ active: true })`; removed mock promo/discount UI; real plan select dropdown
- **RenewScreen** — wired to `useRenewMembership`; removed multi-period chip picker
- **FreezeScreen** — wired to `useFreezeMembership`; removed chip duration picker; displays `freezeDaysRemaining`
- **UnfreezeScreen** — wired to `useUnfreezeMembership`; displays `currentFreezePeriod` start date
- **CancelScreen** — wired to `useCancelMembership`; optional reason textarea ≤500 chars; irreversibility callout preserved
- **HistoryScreen** — unchanged (mock data stub; no history endpoint in scope)
- **RefundScreen (NET-NEW)** — `IconChip tone=danger icon=ReceiptText`, required reason textarea maxLength=200, char counter `{n}/200`, inline `«Причина обязательна для возврата»` error on submit, `«Вернуть {formatRub(…)}»` danger button, no amount field

All dialogs: submitting state (disabled buttons + Loader2 spinner), error state (inline `Callout tone=danger` below fields, dialog stays open), success (close + toast per Copywriting Contract).

Cancel dispatcher: returns `null` for reception via `can(role, 'cancel', 'memberships')` — defense-in-depth per T-101-09-CANCELPRIV.

**`fields.tsx`** — added `required` prop to `Field` (shows red asterisk `*`).

**`icons/index.tsx`** — added `ReceiptText` export (ReceiptX not available in lucide-react 0.469.0).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Path params use `{membership_id}` / `{pt_package_id}`, not `{id}`**
- **Found during:** Task 1 typecheck
- **Issue:** Initial `api.ts` used `{id}` in paths; TypeScript `staffRequest<P extends keyof paths>` flagged unknown keys
- **Fix:** Updated all membership paths to `{membership_id}` and pt-package paths to `{pt_package_id}` per `schema.d.ts`
- **Files modified:** `features/memberships/api.ts`, `features/pt-packages/api.ts`
- **Commit:** b16289c7

**2. [Rule 1 - Bug] `ReceiptX` icon not available in lucide-react 0.469.0**
- **Found during:** Task 2 typecheck
- **Issue:** `lucide-react@0.469.0` does not export `ReceiptX`; UI-SPEC referenced it but the installed version predates this icon
- **Fix:** Used `ReceiptText` as the refund icon (semantically close; visually appropriate for a receipt-based action)
- **Files modified:** `components/icons/index.tsx`, `SubscriptionModal.tsx`
- **Commit:** b7ee57fd
- **Note:** D-101-03-RECEIPTX

**3. [Rule 1 - Bug] `onMutate` context shape had `readonly unknown[]` vs `unknown[]` type mismatch**
- **Found during:** Task 1 typecheck
- **Issue:** TanStack Query's `getQueriesData` returns `[readonly unknown[], ...]` but the explicit context type expected `unknown[]`
- **Fix:** Used explicit `useMutation<unknown, Error, FreezeVars, OptimisticCtx>` type parameters with `readonly unknown[]` in the context type
- **Files modified:** `features/memberships/api.ts`
- **Commit:** b16289c7

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `HistoryScreen` uses hardcoded HISTORY array | `SubscriptionModal.tsx` | No backend membership-history endpoint in Phase 101 scope; deferred to Phase 103+ |
| EditScreen shows placeholder message | `SubscriptionModal.tsx` | No backend edit-membership endpoint in scope; edit UX deferred |

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `features/memberships/keys.ts` exists | FOUND |
| `features/memberships/schemas.ts` exists | FOUND |
| `features/memberships/api.ts` exists | FOUND |
| `features/memberships/schemas.test.ts` exists | FOUND |
| `101-03-SUMMARY.md` exists | FOUND |
| Commit `b16289c7` exists | FOUND |
| Commit `b7ee57fd` exists | FOUND |
| `crypto.randomUUID()` called 7 times in api.ts | PASS |
| `useRefundMembership` has NO Idempotency-Key header | PASS |
| `onMutate` present in freeze + unfreeze only | PASS |
| `RefundScreen` present in SubscriptionModal | PASS |
| typecheck PASS | ✓ |
| lint PASS | ✓ |
| tests 180/180 PASS | ✓ |
| build PASS | ✓ |
