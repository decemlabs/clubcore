---
phase: 101-clients-memberships
verified: 2026-06-13T15:12:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open Clients list → search for a client by name (min 2 chars, 300ms debounce) → confirm server-side results change with real data from GET /api/v1/clients"
    expected: "Results filter in real time after 300ms; fewer than 2 chars typed → list unchanged; pagination controls driven by {total,page,pageSize}"
    why_human: "Requires live backend (docker compose) — cannot verify real network round-trip, debounce timing, or server-side search results programmatically"
  - test: "Open a client detail → view memberships / visits / payments tabs → confirm each tab loads independently; break one endpoint (e.g. visits) and confirm only the visits tab shows its inline error, not a full-page crash"
    expected: "Memberships tab shows MembershipsSection from useMembershipsByClient; Activity tab shows real visits; Payments tab shows read-only payments via /by-client/{id}; per-tab error isolation works"
    why_human: "Requires live backend and deliberate network error injection"
  - test: "Create a new client via the modal — submit with a duplicate phone number → verify backend 422 surfaces as inline field errors on the phone field"
    expected: "Zod rejects on client side for format; backend 422 with fields map produces inline error; success shows toast 'Клиент добавлен' and closes modal"
    why_human: "Requires live backend for 422 round-trip validation"
  - test: "As reception role → open Client list → confirm Delete button absent in EditClientModal; as owner role → confirm Delete button present and triggers ConfirmModal with 'Удалить клиента?' copy"
    expected: "Delete button hidden for reception (can() gate); visible for owner; soft-delete via DELETE /api/v1/clients/{client_id} → 204 → toast 'Клиент удалён'"
    why_human: "Role-based UI gating requires session state + live backend to confirm 204 round-trip"
  - test: "Open Plans screen as reception → confirm tariff/addon lists render but Add/Edit/Delete buttons absent; as owner → buttons present; delete a plan → confirm DELETE /membership-plans/{plan_id} round-trip"
    expected: "Reception sees read-only view; owner sees CRUD; 403 query → Lock EmptyState 'Недостаточно прав'; delete wired to real endpoint"
    why_human: "Role-based visibility requires live session + real backend delete to confirm 204"
  - test: "Sell a membership → confirm POST /memberships with Idempotency-Key header present; retry the same form (simulate network timeout) → confirm a NEW UUID is sent"
    expected: "Each form submit generates a fresh crypto.randomUUID() in the Idempotency-Key header; backend records the sale; toast 'Абонемент оформлен' with payment amount"
    why_human: "Header inspection requires browser DevTools + live backend; UUID freshness-per-attempt cannot be verified without manual retry simulation"
  - test: "Freeze a membership → observe optimistic status flip in the UI before backend responds; simulate backend error → confirm rollback to previous status"
    expected: "Status flips to 'frozen' immediately (optimistic); on error, status reverts; on success, invalidation re-fetches; toast 'Абонемент заморожен'"
    why_human: "Optimistic mutation rollback requires manual network throttling/error injection with live backend"
  - test: "Open RefundScreen → submit with empty reason → confirm inline error; submit with reason > 200 chars → confirm blocked; submit valid reason → confirm no Idempotency-Key header sent, full amount returned"
    expected: "Empty reason: 'Причина обязательна для возврата' inline; >200 chars: disabled button or Zod block; valid submit: NO Idempotency-Key header; toast 'Возврат оформлен'"
    why_human: "Header absence verification requires browser DevTools + live backend refund endpoint"
  - test: "Cancel a membership as reception → confirm cancel button not rendered; as owner → confirm cancel dialog with optional reason textarea (≤500 chars)"
    expected: "Reception sees no cancel option (can() returns null for 'cancel','memberships'); owner sees CancelScreen with optional reason; confirmation toast 'Абонемент отменён'"
    why_human: "Role-based rendering + backend cancel endpoint requires live session + docker backend"
---

# Phase 101: Clients + Memberships Verification Report

**Phase Goal:** Staff can manage the full client-membership lifecycle on real data — list, view, create, edit, delete clients; manage plans; sell, freeze, renew, and cancel memberships.
**Verified:** 2026-06-13T15:12:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Clients list renders real GET /api/v1/clients with server-side search and pagination envelope; loading, error, and empty states visible | VERIFIED | `ClientsPage.tsx` calls `useClients(filter)` with debounced search (300ms, min-2-char gate via `useDebounce`); `?page=N` URL sync; `PageLoading`/`PageError`/two distinct `EmptyState` renders confirmed in source |
| 2 | Client detail shows profile, memberships, visits, and payments from real backend; mock queryFns removed | VERIFIED | `ClientPage.tsx` has `MembershipsSection` via `useMembershipsByClient`; `ActivityTab` uses `useClientVisits`; `TrainingsTab` uses `usePtPackagesByClient`; `PaymentsTab` uses `usePaymentsByClient` (scoped `/by-client/{client_id}` path); no mock imports remain in wired tab code |
| 3 | Create/edit client forms validate via Zod, submit to POST/PATCH /api/v1/clients, soft-delete via DELETE; owner-only actions gated | VERIFIED | `NewClientModal` uses `useCreateClient` + `ClientCreateSchema.safeParse()`; `EditClientModal` uses `useUpdateClient`+`useDeleteClient`; `can(role,'delete','clients')` hides delete for reception; ApiError 422→inline field errors, 403→toast |
| 4 | Plans screen lists real membership plans and PT-package plans; create/edit owner-only gated; 403 → friendly state | VERIFIED | `PlansPage.tsx` calls `usePlans()` + `usePtPackagePlans()`; `can(role,'edit'|'delete', 'membership-plans'|'pt-package-plans')` hides buttons for reception; `ApiError.code === 'forbidden'` → `EmptyState icon=Lock «Недостаточно прав»`; delete mutation wired; create/edit are toast stubs (owner-gated, per plan explicit deferral) |
| 5 | Staff can sell membership/PT-package (cash, Idempotency-Key); manage lifecycle — freeze/unfreeze/renew/cancel/refund | VERIFIED | `useSellMembership`/`useSellPtPackage` use `crypto.randomUUID()` inside `mutationFn`; `useFreezeMembership`/`useUnfreezeMembership` are ONLY optimistic mutations (onMutate→rollback→onSettled); `useRenewMembership`/`useCancelMembership` (owner-gated)/`useRefundMembership` (NO Idempotency-Key, required reason 1-200) all confirmed in source; `RefundScreen` exists in `SubscriptionModal.tsx` |

**Score:** 5/5 truths verified

### Note on MEM-01 Create/Edit Modal Stubs

`PlansPage.tsx` handlers `handleCreatePlan`/`handleEditPlan` show a toast stub ("Создание тарифа") instead of a real modal. This is an intentional deferral explicitly documented in the 101-02-PLAN.md task instruction ("do NOT add a net-new modal family here") and in 101-02-SUMMARY.md (`D-101-02-MOCKSTUBS`). The requirement says "create/edit are owner-only gated" — the buttons are correctly hidden for reception via `can()`, satisfying the gating requirement. Full modal wiring is explicitly deferred to a future plan. This does not block the phase goal.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/admin-app/src/features/clients/schemas.ts` | ClientSchema, ClientsListResponseSchema, Create/UpdateSchema + types | VERIFIED | E.164 phone regex, email `.or(z.literal(''))`, tags ≤16/≤32, notes ≤4096, ClientUpdateSchema = partial |
| `apps/admin-app/src/features/clients/api.ts` | clientsKeys, useClients, useClient, mutations, ApiError re-export | VERIFIED | staffRequest wired; no mockResponse imports; ApiError re-exported |
| `apps/admin-app/src/features/clients/schemas.test.ts` | Pure Zod assertions (28 tests) | VERIFIED | 324 lines; 28 tests confirmed green in suite run |
| `apps/admin-app/src/features/plans/schemas.ts` | MembershipPlanSchema, Create/UpdateSchema (durationDays omitted on update) | VERIFIED | `MembershipPlanUpdateSchema = MembershipPlanCreateSchema.omit({durationDays:true}).partial()` |
| `apps/admin-app/src/features/plans/api.ts` | plansKeys, usePlans, CRUD mutations, ApiError re-export; /api/v1/membership-plans | VERIFIED | staffRequest wired; no mockResponse |
| `apps/admin-app/src/features/pt-packages/schemas.ts` | PtPackagePlanSchema, full schema set incl. Sell/Cancel/Refund | VERIFIED | 284-line test file; all sell/cancel/refund schemas present |
| `apps/admin-app/src/features/pt-packages/api.ts` | ptPackagesKeys, plan-CRUD + instance lifecycle hooks, /api/v1/pt-package-plans | VERIFIED | includeArchived param; name-only update; sell/cancel/refund/cancel instance hooks all present |
| `apps/admin-app/src/features/memberships/keys.ts` | membershipsKeys with byClient() | VERIFIED | `byClient(clientId)` key confirmed |
| `apps/admin-app/src/features/memberships/schemas.ts` | MembershipSchema (plan snapshot + freeze fields), lifecycle schemas | VERIFIED | FreezePeriodSchema, RefundSchema reason 1-200, CancelSchema reason ≤500 |
| `apps/admin-app/src/features/memberships/api.ts` | Full lifecycle hooks; crypto.randomUUID() inside mutationFn; NO Idempotency-Key on refund | VERIFIED | 7 occurrences of `crypto.randomUUID()` confirmed; refund explicitly has no key; onMutate only in freeze/unfreeze |
| `apps/admin-app/src/components/modals/SubscriptionModal.tsx` | RefundScreen net-new; 'refund' in SubscriptionScreen | VERIFIED | `RefundScreen` at line 515; `'refund'` in modals-context.ts union |
| `apps/admin-app/src/features/visits/schemas.ts` | VisitsListResponseSchema | VERIFIED | 92-line test file; schema present |
| `apps/admin-app/src/features/visits/api.ts` | useClientVisits over GET /api/v1/visits?clientId= | VERIFIED | `query: { clientId }` confirmed |
| `apps/admin-app/src/features/payments/api.ts` | usePaymentsByClient over /api/v1/payments/by-client/{client_id} | VERIFIED | Path interpolation via `params: { client_id: clientId }` confirmed |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `features/clients/api.ts` | `/api/v1/clients` | staffRequest queryFn/mutationFn | WIRED | `staffRequest('get', '/api/v1/clients', { query: filterToQuery(filter) })` |
| `pages/clients/ClientsPage.tsx` | `useClients` | hook call with filter | WIRED | Line 56: `useClients(filter)` with debounce + pagination |
| `components/modals/EditClientModal.tsx` | `useDeleteClient` | can()-gated delete button | WIRED | Line 71: `useDeleteClient()`; `can(role,'delete','clients')` gate at line 229 |
| `features/plans/api.ts` | `/api/v1/membership-plans` | staffRequest | WIRED | `staffRequest('get', '/api/v1/membership-plans', ...)` |
| `features/pt-packages/api.ts` | `/api/v1/pt-package-plans` | staffRequest | WIRED | `staffRequest('get', '/api/v1/pt-package-plans', { query: opts ?? {} })` |
| `pages/plans/PlansPage.tsx` | `can(role,'edit','membership-plans')` | owner-only button gating + 403 EmptyState | WIRED | Lines 205-208: four `can()` calls; Lock EmptyState rendered on 403 |
| `features/memberships/api.ts` | `/api/v1/memberships` | staffRequest + Idempotency-Key | WIRED | `staffRequest('post', '/api/v1/memberships', { body, headers: { 'Idempotency-Key': crypto.randomUUID() } })` |
| `features/memberships/api.ts` | `crypto.randomUUID()` | per-attempt key inside mutationFn | WIRED | 5 occurrences inside mutationFn bodies (not at hook init); refund has none |
| `components/modals/SubscriptionModal.tsx` | `useRefundMembership` | RefundScreen submit | WIRED | Line 518: `const refundMutation = useRefundMembership()` |
| `features/payments/api.ts` | `/api/v1/payments/by-client/{client_id}` | staffRequest params interpolation | WIRED | `params: { client_id: clientId }` — NOT a query string |
| `pages/client/components/ActivityTab.tsx` | `useClientVisits` | visits query hook | WIRED | Line 50: `useClientVisits(clientId)` |
| `pages/client/ClientPage.tsx` | `useMembershipsByClient` | memberships tab query | WIRED | Line 55: `useMembershipsByClient(clientId)` in MembershipsSection |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ClientsPage.tsx` | `data` (ClientsListResponse) | `useClients(filter)` → `staffRequest('get', '/api/v1/clients')` | Yes — staffRequest hits real API; Zod parses `{data:{items,total,page,pageSize}}` | FLOWING |
| `ClientPage.tsx` MembershipsSection | membership list | `useMembershipsByClient(clientId)` → `staffRequest` | Yes | FLOWING |
| `ActivityTab.tsx` | visits list | `useClientVisits(clientId)` → `staffRequest` | Yes | FLOWING |
| `PaymentsTab.tsx` | payments list | `usePaymentsByClient(clientId)` → `staffRequest` (scoped path) | Yes | FLOWING |
| `SubscriptionModal.tsx` RefundScreen | reason, paidAmountKopecks | from parent membership prop + `useRefundMembership` mutation | Yes — no amount field exists; reason required 1-200 | FLOWING |
| `PlansPage.tsx` | plans list + pt-package-plans list | `usePlans()` + `usePtPackagePlans()` → `staffRequest` | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 190 tests pass | `pnpm -F @clubcore/admin-app exec vitest run` | 190 passed (12 test files), 0 failures | PASS |
| TypeScript compiles | `pnpm -F @clubcore/admin-app typecheck` | 0 errors | PASS |
| ESLint passes | `pnpm -F @clubcore/admin-app lint` | 0 warnings/errors | PASS |
| Production build | `pnpm -F @clubcore/admin-app build` | Built in 2.53s, 0 errors | PASS |
| No mock queryFns in clients/api.ts | `grep -c "mockResponse\|clientsPageData" features/clients/api.ts` | 0 matches | PASS |
| No mock queryFns in plans/api.ts | `grep -c "mockResponse\|plansPageData" features/plans/api.ts` | 0 matches | PASS |
| Idempotency-Key in memberships/api.ts | `grep -c "Idempotency-Key" features/memberships/api.ts` | 6 lines (5 with UUID calls + 1 refund explicit absence note) | PASS |
| refund has NO Idempotency-Key | Checked source at line 370 | `// Deliberately NO Idempotency-Key header (UI-SPEC §3.2)` | PASS |
| onMutate only in freeze/unfreeze | `grep -n "onMutate" features/memberships/api.ts` | Lines 129 and 207 only (freeze + unfreeze) | PASS |
| 'refund' in SubscriptionScreen union | `grep "refund" modals-context.ts` | Line 42: `\| 'refund'` | PASS |
| cancel gated for reception | `grep "can(role.*cancel" SubscriptionModal.tsx` | Line 772: `if (!can(role, 'cancel', 'memberships')) return null` | PASS |

### Probe Execution

No probes declared for this phase. Step 7c: SKIPPED (frontend-only phase, no shell probes).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CLI-01 | 101-01-PLAN.md | Clients list with server search + pagination envelope + states | SATISFIED | `useClients` → `staffRequest` → Zod envelope; debounced search; URL pagination; PageLoading/PageError/two EmptyStates |
| CLI-02 | 101-04-PLAN.md | Client detail memberships/visits/payments from real backend | SATISFIED | `useMembershipsByClient`/`useClientVisits`/`usePaymentsByClient` all wired with per-tab states |
| CLI-03 | 101-01-PLAN.md | Create/edit/soft-delete client via Zod-validated forms; owner-gated delete | SATISFIED | `useCreateClient`/`useUpdateClient`/`useDeleteClient`; `ClientCreateSchema.safeParse()`; `can()` gate |
| MEM-01 | 101-02-PLAN.md | Plans screen lists real plans; create/edit owner-only gated; 403 friendly state | SATISFIED | `usePlans`/`usePtPackagePlans` wired; `can()` hides buttons for reception; Lock EmptyState on 403; create/edit modals intentionally toast-stubbed per plan instruction |
| MEM-02 | 101-03-PLAN.md | Sell membership/PT-package (cash, Idempotency-Key) | SATISFIED | `useSellMembership` + `useSellPtPackage` with per-attempt `crypto.randomUUID()` inside mutationFn |
| MEM-03 | 101-03-PLAN.md | Membership lifecycle: freeze/unfreeze/renew/cancel/refund | SATISFIED | All six lifecycle hooks wired; freeze/unfreeze optimistic; refund no Idempotency-Key; cancel owner-gated; RefundScreen net-new |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `pages/plans/PlansPage.tsx` | 232-240 | `handleCreatePlan`/`handleEditPlan` are toast stubs | Info | Intentional deferral per plan instruction ("do NOT add net-new modal family here"). Create/edit buttons are owner-gated and hidden for reception. List + delete are fully wired. No blocker. |
| `components/modals/SubscriptionModal.tsx` | 627-703 | `HistoryScreen` uses hardcoded mock `HISTORY` array | Info | No backend membership-history endpoint exists in Phase 101 scope. Documented in 101-03-SUMMARY.md `D-101-03-HISTORY-STUB`. Does not affect MEM-02/MEM-03 goals. |
| `pages/client/ClientPage.tsx` | (ChatTab, NotesTab) | Mock `clientDetail.chat`/`clientDetail.notes` for chat/notes tabs | Info | No backend chat/notes endpoint in Phase 101 scope. Documented in 101-04-SUMMARY.md. Does not affect CLI-02 (memberships/visits/payments wired). |

No TBD/FIXME/XXX markers found in any of the 14+ phase-modified files.

### Known Stubs (Intentional, Not Blockers)

1. **PlansPage create/edit modals** — toast stubs per `101-02-PLAN.md` explicit instruction; owner-gating is in place; full modal wiring is scheduled for a future plan.
2. **HistoryScreen** — hardcoded mock; no backend membership-history endpoint in Phase 101 scope.
3. **ChatTab / NotesTab** in ClientPage — mock data; no backend chat/notes endpoint in Phase 101 scope.

### Human Verification Required

9 items need testing against a live backend (docker compose). These are all real-data round-trip verifications that cannot be confirmed by static analysis or unit tests.

#### 1. Clients list real search + pagination

**Test:** Search for a client by partial last name (min 2 chars), observe debounce delay, then paginate
**Expected:** Results filter on server side after 300ms; fewer than 2 chars typed leaves list unchanged; page URL syncs to `?page=N`; total count drives pagination controls
**Why human:** Live backend required for real data; debounce timing needs browser observation

#### 2. Client detail per-tab error isolation

**Test:** Open client detail → verify 3 tabs load independently → use browser DevTools to block one endpoint (e.g. /api/v1/visits) → confirm only that tab's inline PageError appears, not a full-page crash
**Expected:** Per-tab `PageError` with "Не удалось загрузить данные" and Retry button; other tabs unaffected
**Why human:** Network error injection requires live backend + browser DevTools

#### 3. Client create 422 field errors

**Test:** Create client with phone format 8999... (should pass Zod but fail backend if different) or duplicate phone; observe response
**Expected:** Zod blocks bad format client-side; backend 422 with `fields` map → inline field error on specific field; form stays open
**Why human:** 422 round-trip requires live backend

#### 4. Owner vs reception delete gating (client)

**Test:** Switch role to reception → open EditClientModal → confirm Delete button absent; switch to owner → confirm Delete present → delete → verify soft-delete toast
**Expected:** Delete hidden for reception; ConfirmModal appears for owner; DELETE 204 → toast "Клиент удалён"; list refreshes
**Why human:** Role switching + live DELETE round-trip

#### 5. Plans screen owner vs reception + delete round-trip

**Test:** As reception: open Plans → no Add/Edit/Delete buttons; as owner: Add/Edit/Delete visible; delete a plan → 204 toast
**Expected:** Reception read-only; owner CRUD; 403 on query → Lock EmptyState; delete removes plan from list
**Why human:** Role gating + live DELETE round-trip

#### 6. Sell membership with Idempotency-Key header inspection

**Test:** Sell a membership → DevTools Network → verify `Idempotency-Key` header present with UUID; click submit again → verify new UUID in new request
**Expected:** Each attempt has a fresh UUID; backend records one sale; toast "Абонемент оформлен" with paid amount
**Why human:** Header value inspection requires browser DevTools + live backend

#### 7. Freeze optimistic + rollback

**Test:** Freeze a membership → observe instant status flip in UI → use DevTools to block the freeze endpoint → confirm UI reverts to original status
**Expected:** Optimistic flip immediate; rollback on error; success path: backend confirms + toast "Абонемент заморожен"
**Why human:** Optimistic mutation rollback requires network throttling with live backend

#### 8. RefundScreen validation + no Idempotency-Key

**Test:** Open RefundScreen → submit empty reason → confirm inline error; submit reason >200 chars → confirm disabled button; submit valid reason → DevTools: confirm no Idempotency-Key header sent
**Expected:** Inline "Причина обязательна для возврата" on empty; >200 blocked; valid submit → no Idempotency-Key header; toast "Возврат оформлен"
**Why human:** Header absence requires browser DevTools + live backend

#### 9. Cancel membership gating

**Test:** As reception: SubscriptionModal → confirm no cancel option rendered; as owner: confirm CancelScreen with optional reason textarea ≤500 chars
**Expected:** `can(role,'cancel','memberships')` returns null for reception → screen not rendered; owner sees full cancel dialog
**Why human:** Live role session + backend cancel endpoint required

---

### Gaps Summary

No automated blockers found. All 5 roadmap success criteria are VERIFIED in the codebase. The 9 human verification items listed above are all live-backend round-trip checks that cannot be verified statically. These are standard UAT items for a frontend-only wiring phase.

---

_Verified: 2026-06-13T15:12:00Z_
_Verifier: Claude (gsd-verifier)_
