# Phase 107: Admin FE Completion on Existing Backend - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Every remaining staff toast-stub in `apps/admin-app` becomes a real, reachable action against an **already-shipped** endpoint — membership-plan create/edit, PT-package-plan create/edit, PT-package instance sell/cancel/refund, and client delete from the client-page hero. **No backend or contract change** (D-V31-SCOPE — first phase of v3.1; all hooks + endpoints already exist from v3.0 Phase 101). FE-only wiring + form/modal UI on top of ready TanStack Query mutation hooks.

Covers: PLAN-01, PLAN-02, PTPKG-01, PTPKG-02, CLI-04.

Out of scope (deferred / other phases): promo/«акции» create-edit (still a toast stub, not a v3.1 requirement); Settings persistence (Phase 108); profile/password (Phase 109); any new endpoint.
</domain>

<decisions>
## Implementation Decisions

### Plan create/edit forms (PLAN-01, PLAN-02)
- **One shared `PlanFormModal`** with a `kind: 'membership' | 'pt-package'` discriminator — both kinds reuse the same field primitives (`ModalInput`/`Field`/`FieldRow`/`ModalButton`) and manual `Schema.safeParse()` validation (no `@hookform/resolvers` in admin-app, per D-101-01-NOHOOKFORM).
- **One component, `mode: 'create' | 'edit'`** — create vs edit differ only by initial values (prefill on edit) and immutable-field handling. Mirrors the single-component-per-concern pattern of the SubscriptionModal lifecycle screens.
- **Immutable fields on EDIT are visible but disabled** with a hint («нельзя изменить после создания»). For membership plans: `durationDays` + `freezeDaysLimit`. For PT-package plans: everything except `name` (only `name` editable per D-101-02-PTUPDATE-NAMEONLY). The update schemas already omit/forbid the immutable fields client-side (D-101-02-DURATIONIMMUTABLE); backend `extra='forbid'` is the 422 authority.
- **422 field-error mapping:** map `fields[]` from the `{code, message, fields}` error envelope to per-field inline errors under the relevant inputs; fall back to the shared `ErrorCallout` (tone="danger") for non-field errors. The known membership 422 surfaces as «Длительность тарифа нельзя изменить после создания».
- **Modal placement:** local component state on `PlansPage.tsx` (page-scoped), NOT the global `ModalsProvider` (which is reserved for cross-page actions like checkin/new-client/extend). Wire the existing stub handlers (`PlansPage.tsx` create/edit Тариф at ~234/239, create/edit Услуга at ~258/262, and the `TariffCard`/`PtPackagePlanRow` edit triggers) to open the modal.

### PT-package sell (PTPKG-01)
- **Dedicated `PtPackageSellModal`** (NOT a new screen inside `SubscriptionModal`) — `SubscriptionModal`'s payload type and `CreateScreen` are membership-shaped; a separate modal keeps concerns clean while reusing `AdaptiveModal` + `fields.tsx` building blocks. (Roadmap text said "PtPackageScreen in SubscriptionModal or equivalent" — "equivalent" chosen.)
- **Entry point:** a «Продать пакет» button in the `TrainingsTab` header on the client page (the PT-package surface; mirrors how the membership-sell entry was added to the client page in quick task 260614-j2d).
- **Charged amount is locked to the plan price** — shown read-only as a «К оплате» `StatRow`, and `amountKopecks` is sent equal to the selected plan's `priceKopecks`. The `amount_mismatch` 422 is handled defensively as a clear inline state (e.g., plan price changed under the operator → show callout + offer refetch), not a crash — satisfies SC#3 without letting staff fat-finger a mismatch.
- **Plan selection** via a `<select>` populated by `usePtPackagePlans()` (active only); prefill the amount from the selected plan. Mirrors the membership `CreateScreen` select pattern.
- Uses the ready `useSellPtPackage()` hook — per-attempt `Idempotency-Key` (`crypto.randomUUID()`) and success/error toasts are already built into the hook.

### PT-package cancel/refund in TrainingsTab (PTPKG-02)
- **Per-row kebab (⋯) overflow menu** using the existing `DropdownMenu` primitive (already used in `ProfileHeroReal`) — keeps the read-only rows clean and scales. `TrainingsTab` is currently read-only ("No lifecycle actions here"); this adds the actions.
- **Cancel is OWNER_ONLY → hidden for reception** via `can(role, 'cancel', 'pt-packages')` (consistent with SubscriptionModal CancelScreen hide pattern, D-101-03-CANCEL-GATE). Refund is reception+owner (B-07) → visible to both.
- **Reason is REQUIRED (1–200 chars) for BOTH cancel and refund** — note PT-package cancel reason is required (unlike membership cancel where reason is optional). Both dialogs validate the reason before enabling submit.
- **Dedicated PT-package cancel/refund dialogs** mirroring the membership `CancelScreen`/`RefundScreen` UX (AdaptiveModal, required-reason textarea with counter, inline `ErrorCallout`, spinner on submit), co-located with the sell modal as a small pt-package modal family. Wire the ready `useCancelPtPackage()` (owner-only, reason required) + `useRefundPtPackage()` (reception+owner, reason required, carries Idempotency-Key) hooks.

### Client delete from hero (CLI-04)
- **Plain danger confirm** — the hero dropdown (`ProfileHeroReal.tsx:~152-166`) already opens a `ConfirmPayload` (tone='danger', title «Удалить клиента?», message warning that active memberships will be voided). Keep it plain (NOT type-to-confirm) — it's an owner-gated soft-delete with an explicit warning. Replace only the stubbed `onConfirm` (currently `toast.info('Удаление доступно из карточки редактирования')`) with the real mutation.
- **After successful 204:** navigate to the clients list (`ROUTES.clients`) + success toast — the current client page would be empty/stale after a soft-delete.
- **Reception gating:** the «Удалить клиента» dropdown item is **hidden for reception** via `can(role, 'delete', 'clients')` (clients delete is OWNER_ONLY).
- **Failure (403/409/etc.):** `toast.error` (confirm modal closes), matching the existing mutation error pattern. Uses the ready `useDeleteClient()` hook (DELETE /api/v1/clients/{client_id} → 204).

### Claude's Discretion
- Exact file/component naming, where the shared dialog helpers live, and skeleton/empty-state copy — at Claude's discretion, following existing admin-app conventions (`AdaptiveModal`, `fields.tsx`, `lib/format.ts` Russian helpers, semantic Tailwind tokens).
- Whether the PT-package sell/cancel/refund dialogs share one dispatcher component or are separate files — planner's call, as long as they reuse the membership-dialog UX patterns.
</decisions>

<canonical_refs>
## Canonical References (full paths — downstream agents MUST read)

- `.planning/ROADMAP.md` — Phase 107 goal + 5 success criteria (lines ~280-291).
- `.planning/REQUIREMENTS.md` — PLAN-01/02, PTPKG-01/02, CLI-04 (lines ~14-31).
- `.planning/STATE.md` — v3.1 Architecture Context (D-V31-SCOPE, D-V31-CONTRACT-ADDITIVE), Phase 101 Decisions (D-101-01..04), cookie-naming reminder.
- `apps/admin-app/CLAUDE.md` — admin-app architecture, layered component model, modal system, styling tokens, formatting/i18n. (NOTE: its "no real API yet / mock" prose is stale post-v3.0 — hooks now use `staffRequest`.)
- No external specs/ADRs beyond the above — this is a wire-only FE-completion phase against already-documented v3.0 endpoints.
</canonical_refs>

<code_context>
## Existing Code Insights

### The 5 stubs to replace
- **PLAN-01:** `apps/admin-app/src/pages/plans/PlansPage.tsx:234,239` — `toast('Создание/Редактирование тарифа')`. Also `pages/plans/components/TariffCard.tsx:103,111` (edit/duplicate toast stubs).
- **PLAN-02:** `apps/admin-app/src/pages/plans/PlansPage.tsx:258,262` (Услуги = pt-package plans), `handleEditPtPlan` at ~261 → toast. The «Доп. услуги» section + `PtPackagePlanRow` already render real data with `canEdit`/`canDelete` gating (~402-457).
- **PTPKG-01:** no UI today — `SubscriptionModal` is membership-only; `SubscriptionScreen` enum has no pt-package screen.
- **PTPKG-02:** `apps/admin-app/src/pages/client/components/TrainingsTab.tsx` — read-only rows, explicitly "No lifecycle actions here".
- **CLI-04:** `apps/admin-app/src/pages/client/components/ProfileHeroReal.tsx:161` — `toast.info('Удаление доступно из карточки редактирования')` inside an already-wired danger confirm.

### Ready hooks (no backend work)
- `features/plans/api.ts` — `useCreatePlan` / `useUpdatePlan` (durationDays omitted client-side) / `useDeletePlan`. `ApiError` re-exported.
- `features/pt-packages/api.ts` — plan CRUD (`useCreatePtPackagePlan` / `useUpdatePtPackagePlan` [name-only] / `useDeletePtPackagePlan`) + instance lifecycle (`useSellPtPackage` [Idempotency-Key + toasts built in], `useCancelPtPackage` [owner-only, reason required], `useRefundPtPackage` [reception+owner, reason required, Idempotency-Key]). `usePtPackagesByClient(clientId)`. `ApiError` re-exported.
- `features/clients/api.ts:114` — `useDeleteClient()` (DELETE /clients/{client_id} → 204).

### Reusable assets / patterns (the analogs to mirror)
- **`components/modals/SubscriptionModal.tsx`** — the membership lifecycle screen-dispatcher. CreateScreen (plan `<select>` + StatRow «К оплате»), CancelScreen (optional reason), RefundScreen (required reason 1–200 + counter + touched-validation), `ErrorCallout`, spinner-on-submit, close+toast on success, `can()`-hide for owner-only. **Direct template for the PT-package sell/cancel/refund dialogs.**
- **`components/modals/fields.tsx`** — `Section`, `FieldRow`, `Field`, `ModalInput`, `ModalSelect`, `ModalTextarea`, `ChipGroup`, `PlanCards`, `ModalButton`, `IconChip`, `StatRow`, `ToggleRow`, `ToggleSwitch`. Form-modal exemplars that already use text/number inputs: `ExtendModal.tsx`, `CashModal.tsx`.
- **`components/modals/AdaptiveModal.tsx`** — modal shell (title/description/icon/footerActions/size).
- **`components/modals/modals-context.ts`** — `ModalsProvider` + `ModalKey` union + `ConfirmPayload` (supports `requireText` type-to-confirm, `tone`, `onConfirm`). `useModals().open('confirm', {...})`.
- `shared/session/can.ts` — `can(role, action, resource)`; `lib/format.ts` — `formatKopecks`/`formatDateRu` (Russian). `components/icons` — lucide re-exports.

### Integration points
- PlansPage create/edit handlers + TariffCard/PtPackagePlanRow edit triggers → open `PlanFormModal`.
- TrainingsTab header → «Продать пакет» button → `PtPackageSellModal`; TrainingsTab rows → kebab → cancel/refund dialogs.
- ProfileHeroReal `onConfirm` → `useDeleteClient` + navigate to `ROUTES.clients`.
</code_context>

<specifics>
## Specific Ideas

- Reuse the membership lifecycle dialog UX verbatim for PT-package sell/cancel/refund (AdaptiveModal + fields + ErrorCallout + spinner + close-on-success-toast). Consistency over novelty.
- The PT-package sell amount is display-only (locked to plan price) — the operator never types it; this is the deliberate guard that makes `amount_mismatch` a defensive-only state.
</specifics>

<deferred>
## Deferred Ideas

- Promo / «акции» create-edit modals (`PlansPage.tsx:388` `toast('Создание акции')`, `PromoCard` action toasts) — still stubs, but NOT a v3.1 requirement (promo admin CRUD remains deferred). Do not wire in Phase 107.
- Membership-plan duplicate action (`TariffCard.tsx:111` `toast.success('Тариф продублирован')`) — cosmetic stub, no backend duplicate endpoint; leave as-is unless trivially in scope.
- Membership "edit" screen (`SubscriptionModal` default/edit case) stays a placeholder — no backend membership-instance edit endpoint; out of scope.
</deferred>
