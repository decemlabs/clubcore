---
phase: 107-admin-fe-completion-on-existing-backend
plan: "02"
subsystem: admin-app / pt-packages UI
tags: [frontend, pt-packages, modals, rbac, wire-only]
dependency_graph:
  requires:
    - 107-01 (PlanFormModal + fields.tsx building blocks established)
  provides:
    - PtPackageSellModal (PTPKG-01)
    - PtPackageCancelDialog (PTPKG-02)
    - PtPackageRefundDialog (PTPKG-02)
    - TrainingsTab lifecycle actions
  affects:
    - apps/admin-app/src/pages/client/components/TrainingsTab.tsx
tech_stack:
  added: []
  patterns:
    - AdaptiveModal + fields.tsx form modal with plan select + StatRow
    - Radix DropdownMenu kebab pattern from ProfileHeroReal
    - required-reason textarea with char counter + touched validation
    - amount_mismatch 422 defensive warn callout
key_files:
  created:
    - apps/admin-app/src/components/modals/PtPackageSellModal.tsx
    - apps/admin-app/src/components/modals/PtPackageActionDialogs.tsx
  modified:
    - apps/admin-app/src/pages/client/components/TrainingsTab.tsx
decisions:
  - "PtPackageSellModal is a standalone file (not a screen in SubscriptionModal) — membership payload type incompatible"
  - "PtPackageCancelDialog + PtPackageRefundDialog co-located in PtPackageActionDialogs.tsx family file"
  - "amountKopecks locked to selectedPlan.priceKopecks — operator never types it; amount_mismatch is defensive-only"
  - "onSuccess in all three modals ONLY closes — hooks own their own toasts"
  - "Sell button visible to both roles via can(role,'create','pt-packages') (NOT 'sell' — not a registered Action)"
  - "Cancel kebab item owner-gated via can(role,'cancel','pt-packages')"
  - "Sell button hoisted into CardHead action prop so it renders in empty state too"
metrics:
  duration: "4m"
  completed: "2026-06-14"
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 1
---

# Phase 107 Plan 02: PT-Package Instance Modal Family Summary

PT-package sell/cancel/refund UI built as a standalone modal family and wired into TrainingsTab — three new components closing the PTPKG-01/02 missing-UI gap against already-shipped hooks.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Build PtPackageSellModal (PTPKG-01) | 9c9ecae6 | PtPackageSellModal.tsx (new, 159 lines) |
| 2 | Build PtPackageCancelDialog + PtPackageRefundDialog (PTPKG-02) | 5acb14cc | PtPackageActionDialogs.tsx (new, 264 lines) |
| 3 | Wire sell button + kebab cancel/refund into TrainingsTab | f11a7e9a | TrainingsTab.tsx (modified) |

## What Was Built

**PtPackageSellModal** (`components/modals/PtPackageSellModal.tsx`):
- `AdaptiveModal size="wide"` with `IconChip tone="accent" icon={CreditCard}`
- Plan select populated by `usePtPackagePlans()` (no args — active only by default)
- Skeleton pulse while plans load
- `amountKopecks` locked to `selectedPlan.priceKopecks` — never typed by operator
- `amount_mismatch` 422 → warn `Callout` («Стоимость пакета изменилась…»), not a crash
- Optional «Заметка» textarea (display-only — sell hook has no notes field)
- `onSuccess` ONLY closes — `useSellPtPackage` owns its own toast
- `useEffect([open])` reset + `isPending` block on `onOpenChange`

**PtPackageCancelDialog** (`components/modals/PtPackageActionDialogs.tsx`):
- `AdaptiveModal size="default"` with `IconChip tone="danger" icon={CircleX}`
- Required reason (1–200 chars) with char counter + touched inline error
- Always-shown danger `Callout` irreversibility warning
- Danger footer button disabled when `isPending || reasonTrimmed.length === 0`
- `onSuccess` ONLY closes — `useCancelPtPackage` owns its own toast

**PtPackageRefundDialog** (co-located in same file):
- `AdaptiveModal size="default"` with `IconChip tone="danger" icon={ReceiptText}`
- Warn `Callout` + «К возврату» StatRow (accent) + «Дата покупки» StatRow
- Verbatim textarea classes from SubscriptionModal RefundScreen
- Footer CTA: `Вернуть {formatKopecks(item.amountKopecks)}`
- `onSuccess` ONLY closes — `useRefundPtPackage` owns its own toast

**TrainingsTab** (modified):
- Added `useSession` + `can()` imports; `const role = session.data?.role ?? 'reception'`
- `[sellOpen, setSellOpen]`, `[cancelTarget, setCancelTarget]`, `[refundTarget, setRefundTarget]` local state
- «Продать пакет» button via `can(role,'create','pt-packages')` in `CardHead action` prop (reachable in both empty and data states)
- `PtPackageRow` extended with kebab `DropdownMenu`: «Вернуть оплату» (both roles) + «Отменить пакет» owner-only
- Kebab trigger has `aria-label="Действия с пакетом"`, icon-only
- Grid widened to `grid-cols-[1fr_auto_auto]` to accommodate kebab column
- All three dialogs rendered at the bottom of the component tree

## RBAC Gating (correct)

| Action | Gate | Result |
|--------|------|--------|
| Sell button | `can(role,'create','pt-packages')` | Both roles — `create/pt-packages` NOT in OWNER_ONLY |
| «Вернуть оплату» kebab | Always rendered | Both roles — `refund/pt-packages` NOT in OWNER_ONLY |
| «Отменить пакет» kebab | `can(role,'cancel','pt-packages')` | Owner-only — `cancel/pt-packages` IS in OWNER_ONLY (line 43) |

## Verification Results

- `pnpm -F @clubcore/admin-app typecheck` — PASS (0 errors)
- `pnpm -F @clubcore/admin-app lint` — PASS (0 warnings)
- `pnpm -F @clubcore/admin-app test` — PASS (340 tests, 26 test files)

## Deviations from Plan

None — plan executed exactly as written.

The `can()` call uses a cast `role as Parameters<typeof can>[0]` — this is because `useSession().data?.role` returns the `Role` type but the nullish fallback `'reception'` is typed as `string`. The cast is safe because the fallback value is a valid `Role` value.

## Known Stubs

None. All three components wire to real TanStack Query mutation hooks against the existing backend.

## Threat Flags

No new threat surface. All mitigations from the plan's threat register are implemented:
- T-107-02-01 (Tampering / amountKopecks): locked to plan price in `handleSubmit`
- T-107-02-02 (Replay / double-charge): Idempotency-Key built into hooks (unchanged)
- T-107-02-03 (EoP / cancel owner-only): `can(role,'cancel','pt-packages')` gate in kebab

## Self-Check: PASSED

- `apps/admin-app/src/components/modals/PtPackageSellModal.tsx` — EXISTS
- `apps/admin-app/src/components/modals/PtPackageActionDialogs.tsx` — EXISTS
- `apps/admin-app/src/pages/client/components/TrainingsTab.tsx` — EXISTS (modified)
- Commit 9c9ecae6 — EXISTS
- Commit 5acb14cc — EXISTS
- Commit f11a7e9a — EXISTS
