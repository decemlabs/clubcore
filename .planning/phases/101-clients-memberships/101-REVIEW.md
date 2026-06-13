---
phase: 101-clients-memberships
reviewed: 2026-06-13T12:18:14Z
depth: standard
files_reviewed: 36
files_reviewed_list:
  - apps/admin-app/src/features/clients/api.ts
  - apps/admin-app/src/features/clients/query.ts
  - apps/admin-app/src/features/clients/schemas.ts
  - apps/admin-app/src/features/clients/schemas.test.ts
  - apps/admin-app/src/features/plans/api.ts
  - apps/admin-app/src/features/plans/schemas.ts
  - apps/admin-app/src/features/plans/schemas.test.ts
  - apps/admin-app/src/features/pt-packages/api.ts
  - apps/admin-app/src/features/pt-packages/schemas.ts
  - apps/admin-app/src/features/memberships/api.ts
  - apps/admin-app/src/features/memberships/keys.ts
  - apps/admin-app/src/features/memberships/schemas.ts
  - apps/admin-app/src/features/memberships/schemas.test.ts
  - apps/admin-app/src/features/visits/api.ts
  - apps/admin-app/src/features/visits/schemas.ts
  - apps/admin-app/src/features/visits/schemas.test.ts
  - apps/admin-app/src/features/payments/api.ts
  - apps/admin-app/src/features/payments/schemas.ts
  - apps/admin-app/src/lib/useDebounce.ts
  - apps/admin-app/src/components/modals/NewClientModal.tsx
  - apps/admin-app/src/components/modals/EditClientModal.tsx
  - apps/admin-app/src/components/modals/SubscriptionModal.tsx
  - apps/admin-app/src/components/modals/fields.tsx
  - apps/admin-app/src/components/modals/ModalsProvider.tsx
  - apps/admin-app/src/components/modals/modals-context.ts
  - apps/admin-app/src/components/icons/index.tsx
  - apps/admin-app/src/pages/clients/ClientsPage.tsx
  - apps/admin-app/src/pages/clients/components/ClientRow.tsx
  - apps/admin-app/src/pages/clients/components/ClientsToolbar.tsx
  - apps/admin-app/src/pages/client/ClientPage.tsx
  - apps/admin-app/src/pages/client/components/ActivityTab.tsx
  - apps/admin-app/src/pages/client/components/PaymentsTab.tsx
  - apps/admin-app/src/pages/client/components/ProfileHeroReal.tsx
  - apps/admin-app/src/pages/client/components/ProfileTabs.tsx
  - apps/admin-app/src/pages/client/components/TrainingsTab.tsx
  - apps/admin-app/src/pages/plans/PlansPage.tsx
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 101: Code Review Report

**Reviewed:** 2026-06-13T12:18:14Z
**Depth:** standard
**Files Reviewed:** 36
**Status:** issues_found

## Summary

Phase 101 wires the Clients, Plans, Memberships, Visits, and Payments domains to the real backend transport layer. The architecture is sound: idempotency-key placement (`crypto.randomUUID()` inside `mutationFn`) is correct for all sell/cancel/freeze/unfreeze/renew mutations; the refund asymmetry (memberships refund sends no key, pt-packages refund sends one) is intentional and documented. `can()` gating uses correct resource strings throughout. Zod schemas faithfully implement the contract (cancel optional/refund mandatory reason distinction, update schema omits immutable `durationDays`, PT-package plan update accepts only `name`).

One blocker exists: the `onSettled` handler in both optimistic freeze/unfreeze mutations fires `toast.success(...)` unconditionally — including on error — so every failed freeze/unfreeze produces a contradictory success toast alongside the error toast. Four warnings cover a logic gap in the Plans create/edit stub, a missing `byClient` invalidation in the refund path, loose error gating in membership cancel, and an uninitialised form race in `EditClientModal`. Four info items flag a redundant type cast, an empty `HistoryScreen` that renders hardcoded mock data despite the page being wired, a cosmetic grammar error in Russian copy, and the formatting inconsistency between the admin-app `.prettierrc` (`semi: true`) and feature files that use no semicolons.

---

## Critical Issues

### CR-01: Freeze/Unfreeze `onSettled` fires success toast on error (contradicts error UI)

**File:** `apps/admin-app/src/features/memberships/api.ts:178-183` (freeze); `:248-254` (unfreeze)

**Issue:** Both `useFreezeMembership` and `useUnfreezeMembership` place `toast.success(...)` inside `onSettled`, which TanStack Query calls on **both success and error**. When the backend returns an error, the flow is:

1. `onError` fires — optimistic state rolls back, `toast.error(...)` is shown.
2. `onSettled` fires — `toast.success('Абонемент заморожен')` is shown simultaneously.

The user sees two toasts with contradictory messages. The mutation is non-idempotent from the user's perspective (they don't know whether the freeze succeeded). This breaks the spec requirement that success toast appears only on success.

**Fix:** Move `toast.success` into `onSuccess` and keep only cache invalidation in `onSettled`:

```ts
// useFreezeMembership
onSuccess: () => {
  toast.success('Абонемент заморожен');
},
onError: (_err, vars, ctx) => {
  if (!ctx) return;
  for (const [key, data] of ctx.listSnapshots) {
    qc.setQueryData(key as readonly unknown[], data);
  }
  if (ctx.detailSnapshot) {
    qc.setQueryData(membershipsKeys.detail(vars.membershipId), ctx.detailSnapshot);
  }
  toast.error('Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.');
},
onSettled: (_data, _err, vars) => {
  void qc.invalidateQueries({ queryKey: membershipsKeys.lists() });
  void qc.invalidateQueries({ queryKey: membershipsKeys.detail(vars.membershipId) });
  void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(vars.clientId) });
},
```

Apply the same fix to `useUnfreezeMembership` (lines 248–254).

---

## Warnings

### WR-01: Plans create/edit CRUD path is stubbed — toast-only, not functional

**File:** `apps/admin-app/src/pages/plans/PlansPage.tsx:232-239`, `:257-262`

**Issue:** `handleCreatePlan` and `handleEditPlan` (both membership plans and PT-package plans) call `toast(...)` and return immediately. The mutation hooks `useCreatePlan`, `useUpdatePlan`, `useCreatePtPackagePlan`, `useUpdatePtPackagePlan` are defined and tested, but no modal or form is opened. The buttons are visible to owners (they pass `can()`) and appear functional. Users who click "Добавить тариф" or "Изменить" receive only a toast, with no way to actually submit data. If Phase 101 was meant to deliver functional create/edit for plans (per MEM-01 scope), this is a logic gap. If it is explicitly deferred, the stub should be hidden or clearly disabled rather than presenting an interactive button that silently fails.

**Fix (if deferral is intentional):** Either disable the button with a `title="Будет доступно в следующей версии"` tooltip, or hide it behind a feature flag, so it does not mislead the owner. If functional create/edit is in scope for Phase 101, wire the existing `useCreatePlan`/`useUpdatePlan` hooks to a modal (the schemas and hooks are complete; only the UI surface is missing).

---

### WR-02: `useRefundMembership.onSuccess` does not invalidate `byClient` — inconsistent with other lifecycle mutations

**File:** `apps/admin-app/src/features/memberships/api.ts:372-375`

**Issue:** On successful refund, the hook invalidates `membershipsKeys.detail(vars.membershipId)` and `membershipsKeys.lists()`, but NOT `membershipsKeys.byClient(vars.clientId)`. Every other lifecycle mutation (sell, freeze, unfreeze, renew, cancel) invalidates `byClient`. A refund changes membership status; the `MembershipsSection` in `ClientPage` queries via `useMembershipsByClient` (which uses the `byClient` key), so the membership card will not refresh after a refund until the stale time expires.

Notably, `vars.clientId` is not available in `onSuccess` because `mutationFn` accepts `{ membershipId, body }` — there is no `clientId` in the input. The parsed `data` returned from `mutationFn` is typed as `unknown` (the function returns `staffRequest(...)` without parsing), so `data.clientId` is not accessible.

**Fix:** Parse the refund response to get `clientId` (as all other mutations do), or add `clientId` to the mutation vars:

```ts
// Option A — add clientId to vars and parse response
mutationFn: async ({ membershipId, clientId, body }: {
  membershipId: string;
  clientId: string;
  body: MembershipRefundInput;
}) => {
  const raw = await staffRequest('post', '/api/v1/memberships/{membership_id}/refund', {
    params: { membership_id: membershipId },
    body,
  });
  return MembershipSchema.parse((raw as { data: unknown }).data);
},
onSuccess: (data) => {
  toast.success('Возврат оформлен', { description: 'Средства будут возвращены клиенту.' });
  void qc.invalidateQueries({ queryKey: membershipsKeys.detail(data.id) });
  void qc.invalidateQueries({ queryKey: membershipsKeys.lists() });
  void qc.invalidateQueries({ queryKey: membershipsKeys.byClient(data.clientId) });
},
```

---

### WR-03: Membership cancel forbidden detection relies on `err.message` string sniffing as fallback

**File:** `apps/admin-app/src/features/memberships/api.ts:330-334`

**Issue:** The `onError` handler checks for a 403 by inspecting `err.code === 'forbidden'` (correct) OR `err.message.toLowerCase().includes('forbidden')` (fragile). If the backend returns a 403 with a localised Russian message body (e.g. `"Недостаточно прав"`) that does not contain the English word "forbidden", the second branch fails silently and shows the generic error toast. This is defence-in-depth UX, not a security issue (backend enforces the rule), but it means the user-facing error message will be wrong in that case.

The `useCancelPtPackage` hook has the same pattern at `pt-packages/api.ts:207`.

**Fix:** Rely exclusively on `err.code`:

```ts
onError: (err) => {
  if (err instanceof ApiError && err.code === 'forbidden') {
    toast.error('Недостаточно прав', {
      description: 'Отмена абонемента доступна только владельцу.',
    });
  } else {
    const msg = err instanceof ApiError ? err.message : undefined;
    toast.error(
      msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
    );
  }
},
```

Apply the same fix to `useCancelPtPackage` in `pt-packages/api.ts:207`.

---

### WR-04: `EditClientModal` form may render stale data if `client` reloads after user has already edited fields

**File:** `apps/admin-app/src/components/modals/EditClientModal.tsx:89-102`

**Issue:** The `useEffect` that syncs `client` data into form state runs every time the `client` reference changes (lines 89–102). This is correct for the initial load, but if TanStack Query revalidates the `useClient(clientId)` query in the background while the modal is open (unlikely given `staleTime: 30_000` and `refetchOnWindowFocus: false`, but possible on retry after error), the form fields will be silently overwritten with server data, discarding any in-progress edits. The `dirty` guard (line 118) only prevents closing — it does not prevent the background sync from wiping edits.

**Fix:** Populate the form only on initial mount (when `form` is still at default empty state) or use a ref flag:

```ts
const initialised = useRef(false);

useEffect(() => {
  if (client && !initialised.current) {
    initialised.current = true;
    setForm({
      lastName: client.lastName,
      // ...
    });
  }
}, [client]);
```

---

### WR-05: `cancelMembership` `can()` gate inside `SubscriptionModal` dispatcher returns `null` instead of the closed-state modal

**File:** `apps/admin-app/src/components/modals/SubscriptionModal.tsx:772-773`

**Issue:** When `screen === 'cancel'` and the role is `'reception'`, the dispatcher returns `null` (line 772–773). This abruptly unmounts the modal entirely, rather than rendering `open={false}`. All other screens render their modal component with the passed `open` prop; only the cancel guard deviates. If the `ModalsProvider` opens the cancel screen for a reception user (which should not happen via normal UI, but could occur via URL manipulation or a bug in a calling screen), the abrupt `null` return means no modal close animation occurs and the backdrop may remain in a broken state depending on how `AdaptiveModal` handles parent unmounting.

This is defense-in-depth gating (backend enforces the real rule), but the implementation approach is inconsistent and potentially problematic for portal/backdrop cleanup.

**Fix:** Render the closed-state modal shell instead of `null`:

```ts
case 'cancel':
  if (!can(role, 'cancel', 'memberships')) {
    return (
      <AdaptiveModal open={false} onOpenChange={onOpenChange} title="" footerActions={null}>
        <></>
      </AdaptiveModal>
    );
  }
  return <CancelScreen {...props} />;
```

---

## Info

### IN-01: Redundant type cast `sort as SortPreset` in `ClientsPage`

**File:** `apps/admin-app/src/pages/clients/ClientsPage.tsx:52`

**Issue:** `sort` is already typed as `SortPreset` (from `useState<SortPreset>`) and `ClientsListQuery.sort` is `'recent:desc' | 'name:asc'` — the same union. The `as SortPreset` cast adds no information and suppresses the type checker for this field. Remove it.

**Fix:**
```ts
sort,  // no cast needed — already SortPreset
```

---

### IN-02: `HistoryScreen` renders hardcoded mock data on a page that is otherwise fully wired

**File:** `apps/admin-app/src/components/modals/SubscriptionModal.tsx:627-728`

**Issue:** The `HistoryScreen` function renders a hardcoded `HISTORY` array of four static records (lines 627–677). Since `ClientPage` and all lifecycle screens now use real backend data, opening the History screen shows fake freeze/renewal events that do not correspond to any real client. While the comment marks it "read-only, unchanged", the disconnect between real lifecycle data and fake history creates a confusing UX that could mislead staff.

**Fix:** Either remove the History tab from the modal dispatcher until the real endpoint is wired (return `null` or a "coming soon" placeholder), or add a prominent banner inside `HistoryScreen` noting the data is illustrative.

---

### IN-03: Russian copy typo in `PaymentsTab` empty state

**File:** `apps/admin-app/src/pages/client/components/PaymentsTab.tsx:99`

**Issue:** The empty state message reads `"История платежей клиента появятся здесь."` — this is grammatically incorrect. "История" is a singular feminine noun; the verb must agree: `"появится"` (not `"появятся"`, which is plural).

**Fix:**
```ts
message="История платежей клиента появится здесь."
```

---

### IN-04: Semicolon style inconsistency — feature `api.ts`/`schemas.ts` files omit semicolons despite `"semi": true` in admin-app `.prettierrc`

**File:** Multiple — `apps/admin-app/src/features/memberships/api.ts`, `apps/admin-app/src/features/clients/api.ts`, `apps/admin-app/src/features/plans/api.ts`, etc.

**Issue:** The admin-app `.prettierrc` specifies `"semi": true`. The feature files introduced in Phase 101 (`api.ts`, `schemas.ts`, `query.ts` etc.) consistently omit semicolons at statement ends, following the root-level `CLAUDE.md` convention ("No semicolons (ASI relied on)"). This creates a formatting split within the project: `fields.tsx`, `modals-context.ts`, and existing admin-app files use semicolons; the new Phase 101 files do not. Running `prettier --check` on the project will report formatting failures.

**Fix:** Standardise on the admin-app `.prettierrc` (add semicolons to all new feature files), or update the `.prettierrc` to remove the conflict with the root `CLAUDE.md` convention. The simplest fix that respects the admin-app config is to add semicolons to all Phase 101 feature files.

---

_Reviewed: 2026-06-13T12:18:14Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
