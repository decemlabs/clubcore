---
phase: 107-admin-fe-completion-on-existing-backend
verified: 2026-06-14T17:30:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Owner opens PlanFormModal for membership-plan create — fill all fields, submit, observe success toast and modal close"
    expected: "POST /api/v1/membership-plans fires, modal closes, Sonner toast 'Тариф создан' appears"
    why_human: "Mutation call wiring and toast flow are only verifiable against a running stack"
  - test: "Owner opens PlanFormModal for membership-plan edit — verify durationDays, priceKopecks, freezeDaysLimit fields are disabled with the hint «Нельзя изменить после создания»"
    expected: "Fields visually disabled; submit sends only name+active; 422 field errors surface inline"
    why_human: "Visual disable state, field-error rendering, and PATCH payload shape require browser + running backend"
  - test: "Owner opens PlanFormModal for PT-package-plan create and edit — verify name is editable on edit, other fields disabled"
    expected: "On edit only «Название» is editable; POST/PATCH /api/v1/pt-package-plans fires correctly"
    why_human: "Visual state + network call verification requires running stack"
  - test: "Staff clicks «Продать пакет» from TrainingsTab — selects a plan, sees locked amount, submits"
    expected: "POST /api/v1/pt-packages fires with amountKopecks locked to plan price; sell modal closes; hook's own success toast appears"
    why_human: "Live hook call, amount locking, and hook-owned toast require running stack"
  - test: "Trigger an amount_mismatch 422 from the sell modal (e.g. price changed between page load and submit)"
    expected: "Warn Callout «Стоимость пакета изменилась. Обновите страницу и попробуйте снова.» renders — no crash"
    why_human: "Requires orchestrated backend state manipulation to trigger the specific error code"
  - test: "Owner cancels a PT-package from TrainingsTab kebab — verify «Отменить пакет» is hidden for reception role"
    expected: "Reception: only «Вернуть оплату» visible in kebab. Owner: both items visible."
    why_human: "Role-switching and visual menu content require browser testing"
  - test: "Owner submits PtPackageCancelDialog with empty reason — verify submit is blocked; then submit with valid reason"
    expected: "Danger button disabled when reason is empty; after valid reason, DELETE mutation fires, dialog closes, hook's toast appears"
    why_human: "Required-reason guard + mutation flow require running stack"
  - test: "Staff (reception+owner) submits PtPackageRefundDialog — verify reason required, amount displayed, refund hook called"
    expected: "Required reason validated; «К возврату» StatRow shows correct amount; hook fires and toast appears"
    why_human: "Full refund flow requires running stack"
  - test: "Owner deletes a client from the hero — confirm dialog → delete fires, navigates to clients list"
    expected: "POST DELETE /api/v1/clients/{id} fires (204); navigate to /clients; 'Клиент удалён' toast"
    why_human: "Navigation + API call require running stack"
  - test: "Reception does NOT see «Удалить клиента» dropdown item in ProfileHeroReal"
    expected: "Item and its separator are invisible for reception role"
    why_human: "Role-based conditional rendering requires browser testing with role switching"
---

# Phase 107: Admin FE Completion on Existing Backend — Verification Report

**Phase Goal:** Every remaining staff toast-stub in apps/admin-app becomes a real, reachable action against an already-shipped endpoint — membership-plan create/edit, PT-package-plan create/edit, PT-package sell/cancel/refund, and client delete from the hero — with no backend or contract change.
**Verified:** 2026-06-14T17:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Owner can create AND edit a membership plan from a real form modal with Zod validation, immutable-field rules, and 422 field-error mapping — toast stub gone | VERIFIED | `PlanFormModal.tsx` (527 lines): all 4 CRUD hooks wired (`useCreatePlan`, `useUpdatePlan`, `useCreatePtPackagePlan`, `useUpdatePtPackagePlan`); `safeParse()` at 5 call-sites; `disabled={isPending \|\| isEditMode}` on immutable membership fields; `immutableHint = 'Нельзя изменить после создания'`; 422 → `setServerFieldErrors` per-field; `PlansPage.tsx` has zero plan create/edit toast stubs |
| 2 | Owner can create AND edit a PT-package plan from a real form modal with name editable + other fields immutable — toast stub gone | VERIFIED | Same `PlanFormModal.tsx` handles `kind='pt-package'`; PT edit mode disables `sessionCount`, `priceKopecks`, `validityDays`; only `ptName` editable on edit; `PtPackagePlanUpdateSchema` (name-only) used on edit path |
| 3 | Staff can sell a PT-package from reachable UI — cash, per-attempt Idempotency-Key — amount_mismatch 422 surfaces as clear state, not crash | VERIFIED | `PtPackageSellModal.tsx` (165 lines): `useSellPtPackage` + `usePtPackagePlans({ includeArchived: false })` wired; `amountKopecks: selectedPlan.priceKopecks` locked; `amount_mismatch` → warn `Callout`; `<PtPackageSellModal>` rendered in `TrainingsTab`; sell button in `CardHead action` prop (visible empty + data states) |
| 4 | Staff can cancel (owner-only) and refund (both roles) a PT-package from reachable TrainingsTab kebab actions (required reason) | VERIFIED | `PtPackageActionDialogs.tsx` (264 lines): `PtPackageCancelDialog` + `PtPackageRefundDialog` both require `reasonTrimmed` (10 occurrences); danger button disabled when `reasonTrimmed.length === 0`; `TrainingsTab` kebab: «Отменить пакет» gated by `can(role, 'cancel', 'pt-packages')` (line 107); «Вернуть оплату» always rendered; both dialogs rendered at bottom of component tree |
| 5 | Staff can delete a client from hero — real owner-gated soft-delete behind confirm — toast.info stub gone | VERIFIED | `ProfileHeroReal.tsx`: `useDeleteClient` + `useSession` + `can` imported; `deleteClient.mutate(client.id, { onSuccess: () => { navigate(ROUTES.clients); toast.success('Клиент удалён') }, onError: () => toast.error('Не удалось удалить клиента') })`; delete item gated by `can(role, 'delete', 'clients')` at line 156; old `toast.info('Удаление доступно из карточки редактирования')` string absent from file |

**Score:** 5/5 truths verified

### Note on ROADMAP SC-4 wording

ROADMAP SC-4 states "refund owner-only" — this is incorrect ROADMAP wording. `apps/admin-app/src/shared/session/can.ts` line 31 comment explicitly lists `{refund, pt-packages}` as reception-retained (NOT in OWNER_ONLY). The implementation correctly surfaces «Вернуть оплату» to both roles and «Отменить пакет» owner-only. The PLAN 02 and CONTEXT.md document this correctly. No implementation gap.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/admin-app/src/components/modals/PlanFormModal.tsx` | Shared kind×mode plan form modal | VERIFIED | 527 lines; `export function PlanFormModal`; all 4 CRUD hooks; `safeParse`; immutable-on-edit; no `@hookform` import |
| `apps/admin-app/src/pages/plans/PlansPage.tsx` | Plan CRUD handlers open PlanFormModal (stubs removed) | VERIFIED | `planFormModal` page-scoped state; `<PlanFormModal>` renders once; 4 toast stubs gone; promo toast preserved |
| `apps/admin-app/src/pages/plans/components/TariffCard.tsx` | Deleted — orphaned dead code | VERIFIED | File absent; zero references in codebase |
| `apps/admin-app/src/components/modals/PtPackageSellModal.tsx` | PT-package sell modal | VERIFIED | 165 lines; `useSellPtPackage` + `usePtPackagePlans`; `amountKopecks` locked; `amount_mismatch` handled; no `@/api/client` import |
| `apps/admin-app/src/components/modals/PtPackageActionDialogs.tsx` | Cancel + refund dialogs | VERIFIED | 264 lines; exports `PtPackageCancelDialog` + `PtPackageRefundDialog`; `useCancelPtPackage` + `useRefundPtPackage`; no `toast.success` (hooks own toasts); no `@/api/client` import |
| `apps/admin-app/src/pages/client/components/TrainingsTab.tsx` | Sell button + kebab + dialogs wired | VERIFIED | `useSession` + `can` imported; `sellOpen`/`cancelTarget`/`refundTarget` state; kebab with `aria-label="Действия с пакетом"`; owner-gate on cancel; sell uses `can(role,'create','pt-packages')`; all 3 dialogs rendered |
| `apps/admin-app/src/pages/client/components/ProfileHeroReal.tsx` | Real delete replacing toast stub | VERIFIED | `useDeleteClient` + `useSession` + `can` imported; `deleteClient.mutate`; navigate + toast on success; error toast on failure; `can(role,'delete','clients')` gate wraps separator + delete item |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `PlansPage.tsx` | `PlanFormModal.tsx` | page-scoped `planFormModal` state + `<PlanFormModal/>` render | WIRED | Import at line 36; rendered at lines 471-477 fed by modal state |
| `PlanFormModal.tsx` | `useCreatePlan`/`useUpdatePlan`/`useCreatePtPackagePlan`/`useUpdatePtPackagePlan` | TanStack Query hooks from features/plans + features/pt-packages | WIRED | All 4 hooks called; `activeMutation` selector wires correct hook per kind×mode |
| `TrainingsTab.tsx` | `PtPackageSellModal.tsx` | `sellOpen` state + `<PtPackageSellModal/>` | WIRED | Import at line 36; render at lines 188-193 |
| `TrainingsTab.tsx` | `PtPackageActionDialogs.tsx` | `cancelTarget`/`refundTarget` state + dialog renders | WIRED | Import at lines 38-41; dialogs render at lines 194-208 |
| `PtPackageSellModal.tsx` | `useSellPtPackage`/`usePtPackagePlans` | TanStack Query hooks from features/pt-packages | WIRED | Both hooks called; `mutate({ clientId, planId, amountKopecks: selectedPlan.priceKopecks })` |
| `ProfileHeroReal.tsx` | `useDeleteClient` → `DELETE /api/v1/clients/{id}` | `deleteClient.mutate(client.id, ...)` in confirm `onConfirm` | WIRED | Mutation call at line 169; `navigate(ROUTES.clients)` at line 171 |

### Data-Flow Trace (Level 4)

All new components call pre-existing TanStack Query hooks against the already-shipped backend. No new API routes were created. Data flows from real backend endpoints through existing hooks into the new modal/dialog components. The sell modal locks `amountKopecks` to `selectedPlan.priceKopecks` (fetched from `usePtPackagePlans`) — no operator-typed amount, no hollow prop. All dynamic data rendered in new components comes from existing query results.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `PlanFormModal.tsx` | `plan` prop (prefill) | passed from `PlansPage` state (from `usePlans`/`usePtPackagePlans`) | Yes — real API-backed data | FLOWING |
| `PtPackageSellModal.tsx` | `plans` | `usePtPackagePlans({ includeArchived: false })` | Yes | FLOWING |
| `PtPackageActionDialogs.tsx` | `item: PtPackageData` | passed from `TrainingsTab` (from `usePtPackagesByClient`) | Yes | FLOWING |
| `ProfileHeroReal.tsx` | `client: ClientData` | passed from client detail page (from `useClient`) | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| TariffCard.tsx deleted | `test ! -f apps/admin-app/src/pages/plans/components/TariffCard.tsx` | exit 0 | PASS |
| No TariffCard references | `grep -rn "TariffCard" apps/admin-app/src/` | no output | PASS |
| Plan create/edit toast stubs gone from PlansPage | `grep "toast.*Создание тарифа\|toast.*Редактирование тарифа" PlansPage.tsx` | no output | PASS |
| PlanFormModal renders once in PlansPage | `grep -c "<PlanFormModal" PlansPage.tsx` | 1 | PASS |
| Promo deferred toast intact | `grep -c "Создание акции" PlansPage.tsx` | 1 | PASS |
| No bogus edit/plans resource string | `grep "'edit', 'plans'" PlansPage.tsx` | no output | PASS |
| Sell amount locked to plan price | `grep "amountKopecks: selectedPlan" PtPackageSellModal.tsx` | line 86 | PASS |
| amount_mismatch handled | `grep -c "amount_mismatch" PtPackageSellModal.tsx` | 4 | PASS |
| No success toasts in action dialogs | `grep -c "toast.success" PtPackageActionDialogs.tsx` | 0 | PASS |
| No bogus sell action string | `grep "'sell', 'pt-packages'" TrainingsTab.tsx` | no output | PASS |
| Kebab aria-label present | `grep "Действия с пакетом" TrainingsTab.tsx` | line 99 | PASS |
| Old delete stub gone from ProfileHeroReal | `grep "Удаление доступно из карточки редактирования"` | no output (confirmed by file read) | PASS |
| Delete navigates to clients list | `grep -c "navigate(ROUTES.clients)" ProfileHeroReal.tsx` | 1 | PASS |
| Owner gate on delete item | `grep "can(role, 'delete', 'clients')" ProfileHeroReal.tsx` | line 156 | PASS |
| TypeScript typecheck | `pnpm -F @clubcore/admin-app typecheck` | exit 0, no errors | PASS |
| ESLint | `pnpm -F @clubcore/admin-app lint` | exit 0, no errors | PASS |
| Test suite | `pnpm -F @clubcore/admin-app test` | 340/340 passed (26 files) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| PLAN-01 | 107-01 | Membership-plan create/edit real form modal | SATISFIED | `PlanFormModal.tsx` membership branch; `handleCreatePlan`/`handleEditPlan` open modal; toast stubs removed |
| PLAN-02 | 107-01 | PT-package-plan create/edit real form modal | SATISFIED | `PlanFormModal.tsx` pt-package branch; `handleCreatePtPlan`/`handleEditPtPlan` open modal |
| PTPKG-01 | 107-02 | PT-package sell UI with Idempotency-Key + amount_mismatch | SATISFIED | `PtPackageSellModal.tsx`; Idempotency-Key built into `useSellPtPackage` hook (unchanged); amount locked; mismatch handled |
| PTPKG-02 | 107-02 | PT-package cancel (owner) + refund (both) with required reason | SATISFIED | `PtPackageActionDialogs.tsx`; cancel gated; refund both roles; required reason validated in both |
| CLI-04 | 107-03 | Client delete from hero — real owner-gated soft-delete | SATISFIED | `ProfileHeroReal.tsx`; `useDeleteClient.mutate`; navigate + toast; owner gate added |

All 5 requirements for Phase 107 are satisfied. No orphaned requirements.

### Anti-Patterns Found

No TBD/FIXME/XXX debt markers found in the new or modified files.

The pre-existing `toast('Создание акции')` at `PlansPage.tsx:392` is a documented deferred stub (out-of-scope promos feature) — not introduced by this phase, not a blocker.

The `usePtPackagePlans({ includeArchived: false })` call in `PtPackageSellModal.tsx` deviates from the plan acceptance criterion (which expected no-args call) but is an intentional, correct improvement documented in SUMMARY-02 (defense-in-depth against archived plan leakage, WR-04). The hook supports this parameter. This is not an anti-pattern.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| No blockers found | — | — | — | — |

### Human Verification Required

All 5 success criteria are verified at the code level. The following items require a running stack + browser to confirm the full end-to-end flows:

#### 1. Membership-plan create/edit full flow

**Test:** As owner, open PlansPage → «Добавить тариф» → fill form → submit. Then edit an existing plan and verify immutable fields are disabled.
**Expected:** POST /api/v1/membership-plans fires; modal closes with success toast; on edit, durationDays/priceKopecks/freezeDaysLimit are visually disabled with hint «Нельзя изменить после создания»; PATCH sends only mutable fields; 422 field errors surface inline.
**Why human:** Visual disable state, HTTP call inspection, and 422 error rendering require browser + running backend.

#### 2. PT-package-plan create/edit full flow

**Test:** As owner, open PlansPage → «Добавить услугу» → fill form → submit. Then edit an existing PT-package plan.
**Expected:** POST /api/v1/pt-package-plans fires; on edit only «Название» editable; PATCH sends only name.
**Why human:** Visual field states + HTTP calls require running stack.

#### 3. PT-package sell flow including amount_mismatch

**Test:** Navigate to any client → TrainingsTab → «Продать пакет» → select plan → submit. Also test: engineer a plan price change between page load and sell attempt.
**Expected:** POST /api/v1/pt-packages fires with amountKopecks = plan.priceKopecks; hook's success toast appears; on price mismatch, warn Callout appears.
**Why human:** Amount locking + engineered 422 scenario + hook toast require running stack.

#### 4. PT-package cancel and refund from TrainingsTab kebab

**Test:** As reception: confirm «Отменить пакет» not in kebab menu. As owner: cancel with empty reason (blocked), then valid reason. Both roles: refund with empty reason (blocked), then valid reason.
**Expected:** RBAC menu gating correct; required reason validation blocks empty submit; mutations fire and close dialogs; hook toasts appear.
**Why human:** Role switching + visual menu content + mutation flow require browser.

#### 5. Client delete from hero

**Test:** As reception: confirm «Удалить клиента» item is absent from dropdown. As owner: click «Удалить клиента» → confirm → verify navigation and toast.
**Expected:** DELETE /api/v1/clients/{id} fires; navigate to /clients; «Клиент удалён» toast appears.
**Why human:** HTTP DELETE + navigation + role-switch visibility require running stack.

### Gaps Summary

No automated gaps found. All 5 success criteria are code-verified. The 5/5 score reflects complete codebase implementation. Status is `human_needed` because 10 browser/live-stack verification items remain — standard for a wire-only FE phase where all mutation flows, visual states, and role-switching must be confirmed against the running stack.

---

_Verified: 2026-06-14T17:30:00Z_
_Verifier: Claude (gsd-verifier)_
