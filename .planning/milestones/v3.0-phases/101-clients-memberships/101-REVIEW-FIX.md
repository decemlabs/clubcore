---
phase: 101-clients-memberships
fixed_at: 2026-06-13T15:30:00Z
review_path: .planning/phases/101-clients-memberships/101-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 101: Code Review Fix Report

**Fixed at:** 2026-06-13T15:30:00Z
**Source review:** .planning/phases/101-clients-memberships/101-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (CR-01, WR-02, WR-03, WR-04, WR-05, IN-01, IN-02, IN-03, IN-04)
- Fixed: 9
- Skipped: 0

WR-01 (Plans create/edit UI stubs) excluded per scope instructions — intentionally deferred.

Post-fix verification: `pnpm -F @clubcore/admin-app typecheck && lint && test && build` — all green. 190/190 tests passing.

---

## Fixed Issues

### CR-01: Freeze/Unfreeze `onSettled` fires success toast on error

**Files modified:** `apps/admin-app/src/features/memberships/api.ts`
**Commit:** b0cfe8d1
**Applied fix:** Added `onSuccess` callbacks to `useFreezeMembership` and `useUnfreezeMembership` containing `toast.success(...)`. Removed `toast.success(...)` from `onSettled` in both mutations. `onSettled` now contains only cache invalidation calls. This ensures success toasts are shown only when the mutation actually succeeds, not on error.

---

### WR-02: `useRefundMembership.onSuccess` missing `byClient` invalidation

**Files modified:** `apps/admin-app/src/features/memberships/api.ts`
**Commit:** 8340cc34
**Applied fix:** Changed `mutationFn` to parse the refund response via `MembershipSchema.parse((raw as { data: unknown }).data)` (matching the pattern of all other lifecycle mutations). Updated `onSuccess` to use `data.id` and `data.clientId` from the parsed response, and added `qc.invalidateQueries({ queryKey: membershipsKeys.byClient(data.clientId) })` so `ClientPage` `MembershipsSection` refreshes immediately after a refund.

---

### WR-03: Forbidden detection relies on `err.message` string-sniffing

**Files modified:** `apps/admin-app/src/features/memberships/api.ts`, `apps/admin-app/src/features/pt-packages/api.ts`
**Commit:** b326c9d3
**Applied fix:** Removed the `|| err.message.toLowerCase().includes('forbidden')` fallback from `useCancelMembership.onError` and `useCancelPtPackage.onError`. Both now rely exclusively on `err.code === 'forbidden'` for the 403 gate — the `ApiError` always carries a stable machine-readable `code` field from the backend, independent of the localised message body.

---

### WR-04: `EditClientModal` form re-syncs on every background refetch

**Files modified:** `apps/admin-app/src/components/modals/EditClientModal.tsx`
**Commit:** e28ecc2c
**Applied fix:** Added `const initialised = useRef(false)` and wrapped the `useEffect` form sync behind `if (client && !initialised.current)` so the form is populated only on the first client load. Background revalidations triggered by TanStack Query now have no effect on the form state. Also added `useRef` to the React import.

---

### WR-05: Cancel gate returns `null` instead of closed-state modal

**Files modified:** `apps/admin-app/src/components/modals/SubscriptionModal.tsx`
**Commit:** c081f88d
**Applied fix:** Replaced the bare `return null` in the `'cancel'` case of the SubscriptionModal dispatcher with `return <AdaptiveModal open={false} onOpenChange={onOpenChange} title="" footerActions={null}><></></AdaptiveModal>`. This allows the portal/backdrop cleanup animations to run normally, consistent with how all other screens handle their closed state.

---

### IN-01: Redundant `sort as SortPreset` cast in `ClientsPage`

**Files modified:** `apps/admin-app/src/pages/clients/ClientsPage.tsx`
**Commit:** d517d766 (included in IN-04 prettier commit, then individually applied as IN-01)
**Applied fix:** Changed `sort: sort as SortPreset` to plain `sort` — the variable is already typed `SortPreset` from `useState<SortPreset>` and `ClientsListQuery.sort` accepts the same union type. No cast needed.

---

### IN-02: `HistoryScreen` renders hardcoded fake events

**Files modified:** `apps/admin-app/src/components/modals/SubscriptionModal.tsx`
**Commit:** 1f8d0741
**Applied fix:** Removed the `HISTORY` array (4 fabricated freeze/renewal records), the `TL_DOT` map, and the timeline rendering code. Replaced with a simple `py-8 text-center` paragraph reading «История появится позже — эта функция будет доступна в следующей версии.» The export-to-PDF stub button was also removed since there is nothing to export. Cleaned up now-unused imports: `ReactNode`, `LucideIcon`, `toast`, `Check`, `Wallet`.

---

### IN-03: Russian grammar — «появятся» → «появится» in `PaymentsTab`

**Files modified:** `apps/admin-app/src/pages/client/components/PaymentsTab.tsx`
**Commit:** 3a182598
**Applied fix:** Changed `message="История платежей клиента появятся здесь."` to `message="История платежей клиента появится здесь."` — «История» is singular feminine; verb must agree in number.

---

### IN-04: Semicolon style inconsistency across Phase 101 files

**Files modified:** 25 files — all Phase 101 feature/page/modal source files listed in `files_reviewed_list`
**Commit:** 9c1c173f
**Applied fix:** Ran `prettier --write` with `apps/admin-app/.prettierrc` (`semi: true, singleQuote: true, trailingComma: all, printWidth: 100`) over all 32 Phase 101 source files. 25 files were reformatted; 7 were already conformant. Subsequent `prettier --check` passes cleanly for all files.

---

_Fixed: 2026-06-13T15:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
