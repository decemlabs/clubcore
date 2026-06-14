---
phase: 107-admin-fe-completion-on-existing-backend
plan: "01"
subsystem: admin-app
tags: [frontend, plans, modals, wire-only]
dependency_graph:
  requires: []
  provides: [PlanFormModal, PlansPage-plan-wiring]
  affects: [apps/admin-app/src/pages/plans/PlansPage.tsx, apps/admin-app/src/components/modals/]
tech_stack:
  added: []
  patterns: [manual-safeParse-validation, page-scoped-modal-state, 422-field-error-mapping]
key_files:
  created:
    - apps/admin-app/src/components/modals/PlanFormModal.tsx
  modified:
    - apps/admin-app/src/pages/plans/PlansPage.tsx
  deleted:
    - apps/admin-app/src/pages/plans/components/TariffCard.tsx
decisions:
  - "D-107-01-PLANFORM-SHARED: One PlanFormModal component handles all 4 permutations (membership/pt-package × create/edit) via kind+mode props — mirrors single-component-per-concern pattern from SubscriptionModal"
  - "D-107-01-PAGESTATE: Page-scoped planFormModal state on PlansPage (not ModalsProvider) per D-101 modal-placement decision for owner-domain actions"
  - "D-107-01-TARIFFCARD-DELETE: TariffCard.tsx deleted as dead code (zero importers; rendered mock Tariff design type superseded by inline MembershipPlanCard); its edit/duplicate toast stubs disappear with it"
  - "D-107-01-RBAC-UNCHANGED: Existing can(role,'edit','membership-plans') and can(role,'edit','pt-package-plans') gates on PlansPage already control create/edit button visibility; no new can() call needed"
metrics:
  duration: "~4 min"
  completed: "2026-06-14T13:58:06Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
  files_deleted: 1
---

# Phase 107 Plan 01: PlanFormModal + PlansPage Wiring Summary

**One-liner:** Real Zod-validated membership/PT-package plan create/edit form modal replacing four PlansPage toast stubs, plus deletion of the zero-importer orphan TariffCard.tsx.

## What Was Built

Replaced the v3.0 P101 WR-01 deferred stubs — membership plan and PT-package plan create/edit operations were previously toast-only placeholders. Now all four triggers open a real `PlanFormModal` with field validation and backend mutation wiring.

**PlanFormModal** (`apps/admin-app/src/components/modals/PlanFormModal.tsx`):
- Shared `kind: 'membership' | 'pt-package'` × `mode: 'create' | 'edit'` form component
- Manual `Schema.safeParse()` validation (no @hookform/resolvers — D-101-01-NOHOOKFORM)
- Membership fields: Название (editable both modes), Длительность + Стоимость + Дней заморозки (disabled on edit), Активен toggle
- PT-package fields: Название (editable both modes), Количество занятий + Стоимость + Срок действия (disabled on edit)
- Disabled-on-edit fields carry hint «Нельзя изменить после создания»
- 422 field-error mapping: `err.fields` distributed to per-field inline display; non-field errors → `ErrorCallout`
- All four CRUD hooks wired: `useCreatePlan` / `useUpdatePlan` / `useCreatePtPackagePlan` / `useUpdatePtPackagePlan`
- `ApiError` imported from feature api modules (not `@/api/client`) per ESLint boundary
- Reset-on-open `useEffect`, `isPending` onOpenChange block, spinner footer label
- Noun-anchored footer labels per UI-SPEC: «Создать тариф»/«Сохранить тариф»/«Создать услугу»/«Сохранить услугу» + «Не создавать»/«Не сохранять»

**PlansPage** (`apps/admin-app/src/pages/plans/PlansPage.tsx`):
- Added page-scoped `planFormModal` state (`open + kind + mode + plan?`)
- Replaced four toast-stub handlers (`handleCreatePlan`, `handleEditPlan`, `handleCreatePtPlan`, `handleEditPtPlan`) with `setPlanFormModal()` calls
- `<PlanFormModal>` rendered once at page bottom fed by modal state
- Promo «Создание акции» toast left unchanged (deferred, out of v3.1 scope)
- Existing RBAC gates (`can(role,'edit','membership-plans')`, `can(role,'edit','pt-package-plans')`) unchanged — already gate the create/edit buttons

**TariffCard.tsx deleted** (`apps/admin-app/src/pages/plans/components/TariffCard.tsx`):
- Confirmed zero importers before deletion
- Orphaned mock-data card carrying `Tariff` design type (superseded by inline `MembershipPlanCard`)
- Edit toast at line 103 (PLAN-01 stub, in scope) gone; duplicate toast at line 111 (deferred) gone for free

## Verification

- `pnpm -F @clubcore/admin-app typecheck` — PASS (0 errors)
- `pnpm -F @clubcore/admin-app lint` — PASS (0 errors)
- `pnpm -F @clubcore/admin-app test` — PASS (340/340 tests, router-smoke + unit)
- `test ! -f apps/admin-app/src/pages/plans/components/TariffCard.tsx` — PASS

## Deviations from Plan

None — plan executed exactly as written. TariffCard.tsx had zero importers as stated; the four stub handlers were at the exact lines indicated; RBAC gates were already correct in the file.

## Known Stubs

None introduced. Promo «Создание акции» toast at `PlansPage.tsx` line 389 is a pre-existing deferred stub (not a v3.1 requirement) — not modified.

## Threat Flags

None found. No new network endpoints, no new auth paths, no new file access patterns.

## Self-Check

- [x] `apps/admin-app/src/components/modals/PlanFormModal.tsx` exists — PASS
- [x] `apps/admin-app/src/pages/plans/PlansPage.tsx` modified — PASS
- [x] `apps/admin-app/src/pages/plans/components/TariffCard.tsx` deleted — PASS
- [x] Commit a1eded1c exists (Task 1: PlanFormModal) — PASS
- [x] Commit b9c5ef12 exists (Task 2: PlansPage wiring + TariffCard deletion) — PASS

## Self-Check: PASSED
