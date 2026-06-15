---
phase: 113-promo-codes-crud
plan: "03"
subsystem: frontend
tags: [promo-codes, tanstack-query, zod, owner-rbac, modal, real-data]

dependency_graph:
  requires:
    - "113-01 backend CRUD (GET/POST/PATCH /api/v1/promo-codes)"
    - "can.ts PROMO_CODES entries (45 entries from 113-01)"
    - "features/promoCodes/ directory (new)"
  provides:
    - "features/promoCodes/schemas.ts — Zod wire schemas + create/update input schemas"
    - "features/promoCodes/api.ts — promoCodesKeys + 4 hooks + ApiError re-export"
    - "PromoCodeModal.tsx — create/edit form with percent/kopecks conversion"
    - "PromoCard.tsx — real PromoCodeData with owner-gated actions"
    - "PlansPage.tsx — 'Скидки и акции' wired to real query, mock cards removed"
  affects:
    - "apps/admin-app/src/pages/plans/PlansPage.tsx (promo section wired)"
    - "apps/admin-app/src/shared/session/can.test.ts (count 42→45)"

tech_stack:
  added: []
  patterns:
    - "staffRequest path cast via 'as unknown as keyof paths' for pre-schema admin endpoints (Phase 117 regenerates schema)"
    - "PromoCodeModal: percent*100 / rubles*100 → wire discountValue; inverse for edit prefill"
    - "Deactivate via useModals().open('confirm', {confirm: {tone:'danger', onConfirm}}) — no new confirm component"
    - "promoCodesQuery enabled: can(role,'list','promo-codes') — both roles true, mirrors users pattern"

key_files:
  created:
    - apps/admin-app/src/features/promoCodes/schemas.ts
    - apps/admin-app/src/features/promoCodes/api.ts
    - apps/admin-app/src/components/modals/PromoCodeModal.tsx
  modified:
    - apps/admin-app/src/pages/plans/components/PromoCard.tsx
    - apps/admin-app/src/pages/plans/PlansPage.tsx
    - apps/admin-app/src/shared/session/can.test.ts

decisions:
  - "Path cast via 'as unknown as keyof paths' for /api/v1/promo-codes and sub-paths — admin promo endpoints not yet in schema.d.ts (Phase 117 will regenerate). Runtime safety ensured by Zod parse."
  - "ApiError.status does not exist on the class (code-only error model) — 422 detection uses err.code === 'validation_error' | 'unprocessable_entity' instead of err.status === 422"
  - "Deactivate uses useModals().open('confirm',...) consistent with other pages; PromoCodeModal is a local useState modal (not in global modals context) — same pattern as PlanFormModal"
  - "can.test.ts count test updated 42→45 (113-01 added 3 entries without updating FE test)"

metrics:
  duration: "~15 minutes"
  completed_date: "2026-06-15"
  tasks_completed: 3
  tasks_total: 3
  files_created: 3
  files_modified: 3
---

# Phase 113 Plan 03: Frontend Wiring — Promo Codes Management Summary

**One-liner:** Plans page «Скидки и акции» wired to real GET /api/v1/promo-codes with owner-gated create/edit/deactivate via PromoCodeModal + ConfirmModal, Zod seam matching real camelCase wire shapes, and percent/kopecks ↔ wire conversion.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | features/promoCodes — schemas.ts + api.ts | ea59c081 | schemas.ts, api.ts |
| 2 | PromoCodeModal (create/edit form) | 1a2bb386 | PromoCodeModal.tsx |
| 3 | Wire PromoCard + PlansPage section | 73ef307b | PromoCard.tsx, PlansPage.tsx, can.test.ts |

## What Was Built

### features/promoCodes/schemas.ts
- `PromoCodeSchema` — camelCase wire shape matching real PromoCodeListItemResponse (id, code, discountType, discountValue, maxUses, perClientLimit, validFrom, validUntil, isActive, applicableTo, description, usedCount, createdAt)
- `PromoCodesListResponseSchema` — paginated envelope `{data: {items, total, page, pageSize}}`
- `PromoCodeCreateSchema` — all required fields (code min(1) max(32), discountType enum, discountValue int min(1))
- `PromoCodeUpdateSchema` — `PromoCodeCreateSchema.partial()` for partial edit
- Exported `PromoCodeData`, `PromoCodeCreateInput`, `PromoCodeUpdateInput` inferred types

### features/promoCodes/api.ts
- `promoCodesKeys` factory (all/lists/list(filter)/detail(id))
- `usePromoCodes(opts, role)` — GET with `enabled: can(role,'list','promo-codes')`, staleTime 30_000
- `useCreatePromoCode()` — POST, onSettled invalidates lists()
- `useUpdatePromoCode()` — PATCH /{promo_id}, onSettled invalidates lists()
- `useDeactivatePromoCode()` — PATCH /{promo_id}/deactivate, onSettled invalidates lists()
- All paths cast via `as unknown as keyof paths` (pre-schema endpoints, Phase 117 regenerates)
- `ApiError` re-exported per D-100-03-APIERROR-REEXPORT

### PromoCodeModal.tsx
- `AdaptiveModal` size='default', `IconChip tone="accent" icon={Tag}` header
- Create mode: title "Создать промокод"; edit mode: "Редактировать промокод" + promo.code description
- Sections: Код и скидка / Ограничения / Срок действия / Дополнительно (per 113-UI-SPEC)
- `ChipGroup` for discount type toggle (Процент / Фикс. сумма)
- FE input in whole percent or rubles; convert to wire on submit (×100); inverse for edit prefill
- Inline validation: percent > 100 (text-danger hint), valid_until < valid_from (text-danger hint)
- Confirm button disabled when invalid or isPending; spinner during mutation
- `useEffect` reset-on-open: prefill from promo in edit mode
- Error mapping: `promo_code_already_exists` → toast.error, `validation_error` → toast.error("Проверьте..."), generic → toast.error("Не удалось сохранить...")

### PromoCard.tsx (rewritten)
- Props changed from `{ promo: Promo }` (mock type) to `{ promo: PromoCodeData; role: Role; onEdit?; onDeactivate? }`
- iconKind derived from `discountType` (percentage → 'percent', fixed → 'discount')
- `StatusPill` driven by `isActive` boolean (Активен/Неактивен)
- Stats: Скидка (discountValue/100 + % or formatKopecks), Использований (usedCount / maxUses??'∞'), Действует (validity window), Лимит на клиента
- `can(role,'edit','promo-codes')` gates «Изменить»; `can(role,'delete','promo-codes') && isActive` gates «Деактивировать»
- Old `Promo` mock type import removed

### PlansPage.tsx (updated)
- Added `usePromoCodes({}, role)`, `useDeactivatePromoCode()`, `useModals()`
- Added `promoModal` state (`{open, mode, promo?}`) for `PromoCodeModal`
- `handleCreatePromo` / `handleEditPromo` / `handleDeactivatePromo` handlers
- `handleDeactivatePromo` uses `openModal('confirm', {confirm: {tone:'danger', ...}})` with deactivate mutation
- 403 detection: `promoCodesForbidden` (error.code === 'forbidden') mirrors plansForbidden pattern
- Section renders: PageLoading / 403 EmptyState / PageError / empty EmptyState (with create CTA) / grid of PromoCard
- SectionHead action: `canCreatePromoCodes` gate on «Создать промокод» button
- `<PromoCodeModal>` mounted at page level
- Mock `mockData.promos.map` block removed; other mock sections (sales, KPIs, page head) unchanged

### can.test.ts (fixed)
- Count test updated 42→45 (113-01 added 3 promo-codes write pairs without updating FE test)
- Added promo-codes RBAC coverage test (owner: all 3 writes ✓; reception: all 3 writes ✗)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] can.test.ts expected 42 OWNER_ONLY pairs after 113-01 added 3**
- **Found during:** Task 3 verification (vitest run)
- **Issue:** 113-01 extended `can.ts` with 3 promo-codes write pairs (42→45) but did not update the FE `can.test.ts` count assertion or the "reception is denied all N pairs" test name.
- **Fix:** Updated count to 45 in both test names and assertions; added promo-codes RBAC tests.
- **Files modified:** `apps/admin-app/src/shared/session/can.test.ts`
- **Commit:** 73ef307b

**2. [Rule 1 - Bug] ApiError has no .status property**
- **Found during:** Task 2 verification (tsc)
- **Issue:** UI-SPEC says "422 → toast" but `ApiError` class only has `code` and `fields` (no `status`). Used `err.status === 422` which doesn't compile.
- **Fix:** Changed to check `err.code === 'validation_error' || err.code === 'unprocessable_entity'` — backend's BackendSchemaBase extra='forbid' raises these codes on 422.
- **Files modified:** `apps/admin-app/src/components/modals/PromoCodeModal.tsx`
- **Commit:** 1a2bb386

**3. [Rule 1 - Bug] PromoCodeCreateInput type narrowing required splitting mode branches**
- **Found during:** Task 2 verification (tsc)
- **Issue:** Using a single `schema.safeParse(raw)` and then calling `createMutation.mutate(result.data)` — TypeScript saw `result.data` as `PromoCodeCreateInput | PromoCodeUpdateInput` (union), incompatible with `mutate`'s narrower `PromoCodeCreateInput` parameter.
- **Fix:** Split into separate create/edit branches each calling their own `PromoCodeCreateSchema.safeParse` / `PromoCodeUpdateSchema.safeParse` — TypeScript narrows correctly.
- **Files modified:** `apps/admin-app/src/components/modals/PromoCodeModal.tsx`
- **Commit:** 1a2bb386

**4. [Rule 1 - Bug] Path cast required for pre-schema admin endpoints**
- **Found during:** Task 1 design analysis
- **Issue:** `/api/v1/promo-codes` admin paths not in `schema.d.ts` (Phase 117 regenerates). `staffRequest<P extends keyof paths>` would reject them.
- **Fix:** Used `'...' as unknown as keyof paths` cast pattern; runtime safety via Zod parse. Documented in api.ts docblock.
- **Files modified:** `apps/admin-app/src/features/promoCodes/api.ts`
- **Commit:** ea59c081

## Known Stubs

None — the plan goal is fully achieved: «Скидки и акции» renders real promo data, create/edit/deactivate functional, reception gated.

## Threat Surface Scan

No new threat surface beyond the plan's threat model:
- T-113-03-01: can() gates applied to all action buttons (PromoCard + SectionHead)
- T-113-03-02: staffRequest auto-attaches X-CSRF-Token (no manual header needed)
- T-113-03-03: Zod safeParse gates modal submit (backend is authoritative)
- T-113-03-04: Schemas match real camelCase wire from 113-01

## Self-Check: PASSED

All key files verified present on disk:
- FOUND: apps/admin-app/src/features/promoCodes/schemas.ts
- FOUND: apps/admin-app/src/features/promoCodes/api.ts
- FOUND: apps/admin-app/src/components/modals/PromoCodeModal.tsx
- FOUND: .planning/phases/113-promo-codes-crud/113-03-SUMMARY.md

All commits verified in git log:
- FOUND: ea59c081 (promoCodes Zod seam + TanStack Query hooks)
- FOUND: 1a2bb386 (PromoCodeModal — create/edit promo code form)
- FOUND: 73ef307b (wire PromoCard + PlansPage — mock → real promo codes)
