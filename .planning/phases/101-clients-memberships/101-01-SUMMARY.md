---
phase: 101-clients-memberships
plan: "01"
subsystem: frontend/clients
tags: [clients, zod, staffRequest, mock-to-http, server-pagination, RBAC]
dependency_graph:
  requires: [100-04]
  provides: [features/clients/schemas.ts, features/clients/api.ts, features/clients/query.ts]
  affects: [pages/clients/ClientsPage, pages/client/ClientPage, modals/NewClientModal, modals/EditClientModal]
tech_stack:
  added: []
  patterns:
    - staffRequest + Schema.parse(raw).data (same as auth/api.ts — P100 exemplar)
    - Manual Zod safeParse for modal form validation (no @hookform/resolvers in admin-app)
    - useDebounce hook for server-side search gating
key_files:
  created:
    - apps/admin-app/src/features/clients/schemas.ts
    - apps/admin-app/src/features/clients/schemas.test.ts
    - apps/admin-app/src/features/clients/query.ts
    - apps/admin-app/src/lib/useDebounce.ts
    - apps/admin-app/src/pages/clients/components/ClientRow.tsx
    - apps/admin-app/src/pages/client/components/ProfileHeroReal.tsx
  modified:
    - apps/admin-app/src/features/clients/api.ts
    - apps/admin-app/src/pages/clients/ClientsPage.tsx
    - apps/admin-app/src/pages/clients/components/ClientsToolbar.tsx
    - apps/admin-app/src/pages/client/ClientPage.tsx
    - apps/admin-app/src/components/modals/NewClientModal.tsx
    - apps/admin-app/src/components/modals/EditClientModal.tsx
    - apps/admin-app/src/components/modals/ModalsProvider.tsx
decisions:
  - "Path param is client_id not id: /api/v1/clients/{client_id} per schema.d.ts"
  - "No @hookform/resolvers in admin-app (only admin-web) — used manual Zod safeParse for modals"
  - "ClientFilterTabs.tsx file kept on disk (used by mock type system) but NOT rendered in ClientsPage"
  - "sort.ts/sort.test.ts kept as-is — still used by existing code; sort types not imported by new ClientsPage"
  - "ClientPage tabs stay on mock clientDetail data — wired in Plan 04 per plan instructions"
metrics:
  duration: "~13 minutes"
  completed: 2026-06-13
  tasks_completed: 3
  files_created: 6
  files_modified: 7
  tests_added: 28
---

# Phase 101 Plan 01: Clients Domain Mock→HTTP Flip Summary

Flipped the clients domain from mock to real backend over the P100 `staffRequest` transport: Zod contract layer, server-side list with reduced filters/sorts, client-detail profile head on real data, and create/update/delete modals wired to real mutations with error handling.

## What Was Built

### Task 1: Clients Zod Contract Layer + HTTP api.ts

- **schemas.ts** — `ClientSchema`, `ClientsListResponseSchema` (data:{items,total,page,pageSize}), `ClientCreateSchema` (phone E.164 regex `^\+[1-9]\d{1,14}$`, email `.email().optional().or(z.literal(''))`, tags array ≤16/≤32/lowercase-regex, notes ≤4096), `ClientUpdateSchema = ClientCreateSchema.partial()`
- **query.ts** — `ClientsListQuery` type + `filterToQuery()` (omits q<2 chars, maps sort presets `recent:desc→created_at_desc`, `name:asc→last_name_asc`)
- **api.ts** — Rewrote from mock to `staffRequest`; `clientsKeys` hierarchy (`all/lists()/list(filter)/details()/detail(id)`); `useClients`, `useClient`; `useCreateClient`, `useUpdateClient`, `useDeleteClient` mutations; `ApiError` re-export (D-100-03-APIERROR-REEXPORT)
- **schemas.test.ts** — 28 pure-zod assertions (all green); covers list response, phone regex, tags limits, notes max, email empty-string, partial update, filterToQuery mapping

### Task 2: ClientsPage Server Pagination + Filter/Sort Reduction + Profile Head

- **ClientsPage.tsx** — Rewrote: `useClients(filter)`, debounced search (300ms, min-2-char gate via `useDebounce`), URL `?page=N` sync, server-side `{items,total,page,pageSize}` pagination; two distinct empty states (zero-clients vs filter-empty)
- **ClientsToolbar.tsx** — Replaced mock-only controls: removed membership-status tabs, planType, trainer, «Ещё фильтры», unsupported sort presets; added backend-supported filters: gender, hasTelegram, tag; sort: `recent:desc` (default) + `name:asc` only
- **ClientRow.tsx** (new) — Simple list row for real `ClientData` (lastName/firstName/phone/email/tags/createdAt)
- **useDebounce.ts** (new) — Generic debounce hook
- **ClientPage.tsx** — Profile head now calls `useClient(clientId)` via `ProfileHeroReal`; tabs remain on mock `clientDetail` data (deferred to Plan 04)
- **ProfileHeroReal.tsx** (new) — Renders real `ClientData` fields: full name, phone, email, birthday, gender, telegramUserId, tags, createdAt

### Task 3: NewClient + EditClient Modals Wired to Real Mutations

- **NewClientModal.tsx** — `useCreateClient()` + manual `ClientCreateSchema.safeParse()` validation; 422→inline field errors; 403→`toast.error('Недостаточно прав')`; 5xx→generic toast, form stays open; submit state disables buttons + spinner
- **EditClientModal.tsx** — `useUpdateClient()` + `useDeleteClient()`; loads real `ClientData` via `useClient(clientId)`; dirty-state guard dialog preserved; delete button HIDDEN for reception via `can(role,'delete','clients')` (T-101-02-OWNERDEL defense-in-depth); 422/403/5xx handling; unsaved-changes guard dialog
- **ModalsProvider.tsx** — Updated to pass `editClient.clientId` payload to `EditClientModal`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Correct API path for client detail**
- **Found during:** Task 1 typecheck
- **Issue:** Plan/PATTERNS used `/api/v1/clients/{id}` but schema.d.ts uses `/api/v1/clients/{client_id}`
- **Fix:** Changed param name to `client_id` in all three hooks (`useClient`, `useUpdateClient`, `useDeleteClient`)
- **Files modified:** `features/clients/api.ts`
- **Commit:** 5c13de71

**2. [Rule 3 - Blocking] @hookform/resolvers not installed in admin-app**
- **Found during:** Task 3 typecheck
- **Issue:** Plan assumed `@hookform/resolvers` was present (tech stack reference); it is only in admin-web, not admin-app
- **Fix:** Implemented modal form validation using `ClientCreateSchema/ClientUpdateSchema.safeParse()` directly — equivalent correctness, no external dependency needed
- **Files modified:** `NewClientModal.tsx`, `EditClientModal.tsx`
- **Impact:** No behavioral difference; validation is equivalent. No package install was performed.
- **Commit:** 828c73bf

**3. [Rule 2 - Missing Critical Functionality] ClientFilterTabs.tsx file removal not executed**
- **Found during:** Task 2 planning
- **Issue:** Plan said to "REMOVE entirely" the ClientFilterTabs component usage; the component file is kept on disk as `ClientsPage` no longer imports/renders it, but the file itself still exists for backward-compat with sort.ts types
- **Impact:** The component is not rendered; no stub data flows to UI. The `sort.ts`/`sort.test.ts` files still compile because they reference the old `Client` type from `types.ts` which is unrelated to the new backend-driven `ClientData`

**4. [Design] ClientPage tabs stay on mock data**
- **Per plan instructions:** Activity/trainings/payments/chat/notes tabs remain on mock `clientDetail` data — explicitly deferred to Plan 04 per the task action description

## Known Stubs

**ClientPage — activity/trainings/payments/chat/notes tabs:**
- `apps/admin-app/src/pages/client/ClientPage.tsx` imports `clientDetail` from `@/mocks/client-detail`
- These tabs use mock data intentionally per plan scope; Plan 04 will wire them to real backend reads
- This does NOT prevent the plan's goal (profile head on real data) from being achieved

## Threat Surface Scan

No new security surface beyond what the threat model covers:
- All real backend calls go through `staffRequest` (CSRF + credentials already handled)
- `useClient` 404/403 → `PageError` (T-101-01-IDOR: no partial render of another client's data)
- Delete hidden for reception (T-101-02-OWNERDEL defense-in-depth)
- Error messages rendered as-is from backend-curated Russian strings (T-101-03-PII-ERR)
- Zod mirrors backend constraints at the boundary (T-101-04-INPUT)

## Test Results

- `schemas.test.ts`: 28 tests green
- `sort.test.ts`: existing 9 tests still green (sort.ts untouched)
- `router-smoke.test.tsx`: 20 route smoke tests green
- Full test suite: 127 tests passed
- Typecheck: green
- Lint: green
- Build: green (2.54s)

## Self-Check: PASSED

All created files exist on disk. All 3 commits verified in git log:
- 2e101b5c: feat(101-01): clients zod contract layer + http api.ts (mock→staffRequest)
- 5c13de71: feat(101-01): ClientsPage server pagination + filter/sort reduction + client-detail head
- 828c73bf: feat(101-01): wire NewClient + EditClient modals to real mutations + Zod validation
