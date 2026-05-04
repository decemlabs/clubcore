---
phase: 10-admin-web-auth-clients-wiring
plan: "06"
subsystem: clients
tags: [admin-web, clients, datagrid, optimistic-mutations, url-state, rbac, react-hook-form, zod]

# Dependency graph
requires:
  - phase: 10-admin-web-auth-clients-wiring-01
    provides: ReUI DataGrid, Button, Input, Skeleton, Dialog, AlertDialog in shared/ui
  - phase: 10-admin-web-auth-clients-wiring-02
    provides: clientsKeys factory, clientCreateSchema, clientsListQuerySchema, ClientsService contract
  - phase: 10-admin-web-auth-clients-wiring-03
    provides: mock clients service (list/get/create/update/remove)
  - phase: 10-admin-web-auth-clients-wiring-04
    provides: RoleGate, useCurrentRole, can()
  - phase: 10-admin-web-auth-clients-wiring-05
    provides: _protected/clients.tsx placeholder, _protected layout

provides:
  - Full /clients route with validateSearch(q, page, pageSize) + loaderDeps + ensureQueryData
  - Five TanStack Query hooks: useClientsList, useClient, useCreateClient, useUpdateClient, useDeleteClient
  - Optimistic delete with cache snapshot/rollback + onSettled invalidate (FE-04)
  - Optimistic update with list+detail snapshot/rollback (FE-04)
  - ClientsPage orchestrator: search toolbar, DataGrid, create/edit/delete dialog state
  - ClientsTable: ReUI DataGrid manualPagination + URL-driven pagination via onPaginationChange->navigate
  - ClientsTableSkeleton: 8 fake rows while query.isPending
  - ClientForm: RHF + zodResolver(clientCreateSchema), mode=create|edit, server error field mapping
  - ClientFormDialog: Dialog wrapper max-w-md, D-09 headings
  - ClientDeleteDialog: AlertDialog destructive confirm, мягкое удаление body, Не удалять cancel
  - useDebounceValue utility (shared/lib/hooks)
  - features/clients barrel index

affects:
  - 10-07 (final plan — verifier pass against all Phase 10 SC)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "validateSearch + z.coerce.number() for URL search params (Pitfall 6 fix)"
    - "loaderDeps({ search }) + ensureQueryData with clientsKeys.list(search) — same-key invariant (FE-04)"
    - "useReactTable must be called before early returns to comply with react-hooks/rules-of-hooks"
    - "vi.hoisted() for mock factories referenced in vi.mock() factories (Vitest hoisting)"
    - "Optimistic delete: getQueriesData snapshots all list cache pages, filter out deleted item, rollback onError"

key-files:
  created:
    - apps/admin-web/src/routes/_protected/clients.tsx (replaced Plan 05 placeholder)
    - apps/admin-web/src/features/clients/api/hooks.ts
    - apps/admin-web/src/features/clients/api/hooks.delete.test.tsx
    - apps/admin-web/src/shared/lib/hooks/useDebounceValue.ts
    - apps/admin-web/src/features/clients/components/ClientsPage.tsx
    - apps/admin-web/src/features/clients/components/ClientsTable.tsx
    - apps/admin-web/src/features/clients/components/ClientsTableSkeleton.tsx
    - apps/admin-web/src/features/clients/components/ClientsTable.rbac.test.tsx
    - apps/admin-web/src/features/clients/components/ClientForm.tsx
    - apps/admin-web/src/features/clients/components/ClientFormDialog.tsx
    - apps/admin-web/src/features/clients/components/ClientDeleteDialog.tsx
    - apps/admin-web/src/features/clients/index.ts
  modified:
    - apps/admin-web/src/routes/_protected/clients.tsx (Plan 05 placeholder replaced)

key-decisions:
  - "useReactTable called unconditionally before early-returns to satisfy react-hooks/rules-of-hooks; data?.items ?? [] passed as empty array for skeleton/empty states"
  - "vi.hoisted() used for removeMock in hooks.delete.test.tsx — vi.mock factory is hoisted before const declarations, so normal const mock = vi.fn() fails with 'Cannot access before initialization'"
  - "Phone field uses plain <Input type=tel> — phone mask deferred per plan (Claude's Discretion in CONTEXT.md)"
  - "ClientsPage uses Route.useSearch() bound via Route import from _protected/clients — same pattern as LoginPage in Plan 05"

patterns-established:
  - "URL-driven search: debounce 300ms → navigate({search: prev => ({...prev, q, page: 1})})"
  - "Optimistic list mutations use getQueriesData(lists()) to snapshot all paginated pages"
  - "DataGrid manualPagination: pageCount derived from total/pageSize; state.pagination from URL search params"

requirements-completed: [FE-04]

# Metrics
duration: 4min
completed: "2026-05-04"
---

# Phase 10 Plan 06: Clients Feature — Full CRUD + DataGrid + Dialogs Summary

**Full /clients feature: URL-driven search/pagination via validateSearch + z.coerce, ReUI DataGrid with manualPagination, optimistic mutations with rollback, RHF+Zod form dialogs, RoleGate-wrapped delete, UI-SPEC RU copy verbatim**

## Performance

- **Duration:** 4 min
- **Started:** 2026-05-04T13:45:52Z
- **Completed:** 2026-05-04T13:50:07Z
- **Tasks:** 3 (+ 1 auto-approved checkpoint at 1.5)
- **Files modified:** 12 (11 created, 1 replaced)

## Accomplishments

- `/clients` route ships with `validateSearch` + `z.coerce.number()` (Pitfall 6) + `loaderDeps` + `ensureQueryData` using `clientsKeys.list(search)` — same-key invariant (FE-04)
- Five hooks exported: `useClientsList`, `useClient`, `useCreateClient`, `useUpdateClient`, `useDeleteClient`
- `useDeleteClient`: full `onMutate` snapshot (all paginated pages via `getQueriesData`), `onError` rollback, `onSettled` invalidate
- `useUpdateClient`: `onMutate` snapshots list pages + detail entry with optimistic partial diff; `onError` restores all
- `useCreateClient`: `onSettled` invalidates lists (no optimistic insert — pagination position unknown)
- `ClientsPage` toolbar: 300ms debounced search → URL nav, "Новый клиент" → create dialog
- `ClientsTable`: ReUI DataGrid with `manualPagination: true`, URL-driven `state.pagination`, `onPaginationChange → navigate`, `RoleGate action="delete"` wraps trash button
- `ClientsTableSkeleton`: 8 fake rows while `query.isPending && !query.data` (WARNING #9 + RESEARCH Open Question #2)
- `ClientForm`: RHF + `zodResolver(clientCreateSchema)`, mode=create|edit, server error field mapping via `err.fields`, root error fallback
- `ClientFormDialog`: Dialog max-w-md, "Добавить клиента"/"Редактировать клиента" headings
- `ClientDeleteDialog`: AlertDialog, "мягкое удаление" body, "Не удалять" cancel, destructive "Удалить" confirm
- All 11 clients feature tests pass; typecheck 0 errors; lint 0 errors

## Task Commits

1. **Task 1: Route + hooks + delete test + useDebounceValue** - `c14b81e` (feat)
2. **Task 1.5: Structural gate** - auto-approved (auto_advance=true)
3. **Task 2: ClientsPage + ClientsTable + RBAC test + barrel** - `982cc2a` (feat)
4. **Task 3: ClientForm + ClientFormDialog + ClientDeleteDialog** - `59883a1` (feat)

## Files Created/Modified

- `apps/admin-web/src/routes/_protected/clients.tsx` - Full route (replaces Plan 05 placeholder) with validateSearch + loaderDeps + ensureQueryData
- `apps/admin-web/src/features/clients/api/hooks.ts` - 5 TanStack Query hooks with optimistic mutations
- `apps/admin-web/src/features/clients/api/hooks.delete.test.tsx` - 3 tests: optimistic remove, rollback on error, total decrement
- `apps/admin-web/src/shared/lib/hooks/useDebounceValue.ts` - Generic debounce hook
- `apps/admin-web/src/features/clients/components/ClientsPage.tsx` - Toolbar + DataGrid orchestrator + dialog state
- `apps/admin-web/src/features/clients/components/ClientsTable.tsx` - ReUI DataGrid + columns + RoleGate delete
- `apps/admin-web/src/features/clients/components/ClientsTableSkeleton.tsx` - 8 skeleton rows
- `apps/admin-web/src/features/clients/components/ClientsTable.rbac.test.tsx` - RBAC D-11 tests
- `apps/admin-web/src/features/clients/components/ClientForm.tsx` - RHF + Zod form, create/edit modes
- `apps/admin-web/src/features/clients/components/ClientFormDialog.tsx` - Dialog wrapper max-w-md
- `apps/admin-web/src/features/clients/components/ClientDeleteDialog.tsx` - AlertDialog destructive confirm
- `apps/admin-web/src/features/clients/index.ts` - Barrel export

## Decisions Made

- **useReactTable before early returns**: ESLint `react-hooks/rules-of-hooks` forbids calling hooks after conditional returns. Moved `useReactTable` to top of component body; empty array passed as data for skeleton/empty states.
- **vi.hoisted() for test mock**: `vi.mock` factory is hoisted to top of file before `const` declarations. `removeMock = vi.fn()` at module scope fails with "Cannot access before initialization". Fixed with `vi.hoisted(() => ({ removeMock: vi.fn() }))`.
- **Phone input**: plain `<Input type="tel">` — phone mask deferred per plan (Claude's Discretion in CONTEXT.md). Zod E.164 regex enforces the contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] vi.mock hoisting causes ReferenceError for removeMock**
- **Found during:** Task 1 delete test run
- **Issue:** `const removeMock = vi.fn()` declared after `vi.mock(...)` factory — Vitest hoists `vi.mock` to top of file, making `removeMock` inaccessible before initialization
- **Fix:** Changed to `const { removeMock } = vi.hoisted(() => ({ removeMock: vi.fn() }))` so the mock is defined in the hoisted scope
- **Files modified:** `apps/admin-web/src/features/clients/api/hooks.delete.test.tsx`
- **Verification:** All 3 delete tests pass

**2. [Rule 1 - Bug] react-hooks/rules-of-hooks: useReactTable called after conditional returns**
- **Found during:** Task 2 lint check
- **Issue:** `useReactTable` was called after early-return guards (`if (query.isError)`, `if (!data)`, etc.) — React Hooks must be called unconditionally
- **Fix:** Moved `useReactTable` and `columns` definition to the top of `ClientsTable` before any conditional returns; passed `data?.items ?? []` as empty array for non-ready states
- **Files modified:** `apps/admin-web/src/features/clients/components/ClientsTable.tsx`
- **Verification:** `pnpm lint` exits 0; RBAC tests still pass

---

**Total deviations:** 2 auto-fixed (1 test mock hoisting, 1 hooks rules fix)
**Impact on plan:** Both are required for correctness; no scope creep.

## Issues Encountered

- **Pre-existing test failure**: `src/shared/ui/components-json.test.ts` expects `style: 'new-york'` but finds `base-nova`. Introduced in Plan 03; not caused by Plan 06.

## Known Stubs

- **Phone mask**: `ClientForm` phone field uses plain `<Input type="tel" placeholder="+79991234567">`. PhoneInput component with `+7 (XXX) XXX-XX-XX` masking is deferred per Plan 06 CONTEXT.md "Claude's Discretion". Zod E.164 regex validates format. Future plan: install ReUI PhoneInput or implement mask.

## Threat Flags

None — all features match the plan's threat model. `validateSearch` + `z.coerce.number().max(100)` clamps `pageSize` (T-10-22 mitigated). `RoleGate` wraps delete (T-10-23 accepted as UI advisory).

## Self-Check: PASSED

All created files verified:
- `apps/admin-web/src/routes/_protected/clients.tsx` ✓ (contains validateSearch, loaderDeps, ensureQueryData, z.coerce.number())
- `apps/admin-web/src/features/clients/api/hooks.ts` ✓ (5 hooks, 2 onMutate, 2 onError, 3 onSettled)
- `apps/admin-web/src/features/clients/api/hooks.delete.test.tsx` ✓ (3 tests pass)
- `apps/admin-web/src/shared/lib/hooks/useDebounceValue.ts` ✓
- `apps/admin-web/src/features/clients/components/ClientsPage.tsx` ✓
- `apps/admin-web/src/features/clients/components/ClientsTable.tsx` ✓
- `apps/admin-web/src/features/clients/components/ClientsTableSkeleton.tsx` ✓
- `apps/admin-web/src/features/clients/components/ClientsTable.rbac.test.tsx` ✓ (3 tests pass)
- `apps/admin-web/src/features/clients/components/ClientForm.tsx` ✓
- `apps/admin-web/src/features/clients/components/ClientFormDialog.tsx` ✓
- `apps/admin-web/src/features/clients/components/ClientDeleteDialog.tsx` ✓
- `apps/admin-web/src/features/clients/index.ts` ✓

All 3 task commits verified: c14b81e, 982cc2a, 59883a1

---
*Phase: 10-admin-web-auth-clients-wiring*
*Completed: 2026-05-04*
