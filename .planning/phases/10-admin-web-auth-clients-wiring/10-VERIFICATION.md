---
phase: 10-admin-web-auth-clients-wiring
verified: 2026-05-04T23:45:00Z
status: passed
score: 5/5 must-haves verified; 7/7 requirement IDs satisfied; gap resolved on 2026-05-04
overrides_applied: 0
re_verification: true
gaps: []
deferred: []
re_verified_notes:
  - "Original gap (components-json.test.ts asserting 'new-york') resolved on disk: line 27 now asserts 'base-nova', matching components.json line 3. pnpm exec vitest run src/shared/ui/components-json.test.ts exits 0."
  - "Phase 11 (clients HTTP-mode shape adapter, status: passed 2026-05-04T23:30:00Z) closes the integration gap surfaced post-Phase-10 — INTEGRATION-CHECK F-01 (response shape) and F-02 (request shape) — making SC #2 durable against the real backend."
  - "Phase 12.1 quick-task (commit ba14aba, 2026-05-04) added await session.commit() to clients/service.py write paths, unblocking the Phase 11 SC #4 live-runbook walkthrough that depends on Phase 10 SC #2 in http-mode. Persistence regression test added at apps/backend/tests/integration/clients/test_persistence.py."
---

# Phase 10: admin-web Auth + Clients Wiring — Verification Report

**Phase Goal:** An operator running the admin-web with `VITE_API_MODE=http` can log in (email/password OR Telegram OTP), see the real Clients list/detail/create/edit/delete backed by Postgres, and never falls into a 401-redirect loop — while every other domain (memberships, billing, etc.) keeps using the existing mock services unchanged.
**Verified:** 2026-05-04T17:10:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC#1: /login has two tabs (email/password + Telegram OTP); Telegram polls status endpoint; prompts for code after bound; redirects back on success | ✓ VERIFIED | `LoginPage.tsx` contains `defaultValue="email"`, `TabsTrigger value="telegram"`. `hooks.ts:46` has `refetchInterval: 3000`. `TelegramLoginTab.tsx` has `TIMEOUT_MS = 5 * 60 * 1000` and `InputOTP`. `LoginPage.tsx:14` has `sanitizeNext` that redirects to `search.next`. `_public/login.tsx:8` has `validateSearch` with `next`. |
| 2 | SC#2: /clients/* lists/searches/creates/edits/(owner-)deletes via @sportzal/api-client; optimistic mutations; loader uses same clientsKeys | ✓ VERIFIED | `_protected/clients.tsx:25` uses `clientsKeys.list(search)` in `ensureQueryData`. `clients/api/hooks.ts` has `onMutate`, `onError`, `onSettled`. `ClientsTable.tsx:67` wraps delete in `<RoleGate action="delete" resource="clients">`. `http/auth.ts` and `http/clients.ts` import from `@sportzal/api-client`. |
| 3 | SC#3: VITE_API_MODE=mock keeps /login and /clients/* working against mock services with no regression for other domains | ✓ VERIFIED | `services/index.ts` exports `API_MODE === 'http' ? httpServices : mockServices`. `mock/index.ts` exports `{ auth, clients } as const`. `http/index.ts` exports `{ auth, clients } as const`. Swap seam is in `shared/api/config/env.ts`. |
| 4 | SC#4: 401 triggers single-flight refresh; on refresh failure redirects to /login?next= exactly once; logout clears TanStack Query cache and redirects | ✓ VERIFIED | `redirect-on-session-expired.ts` has `let redirecting = false` module flag. `queryClient.ts` has `new QueryCache({ onError: redirectOnSessionExpired })` and `new MutationCache`. `ProfileMenu.tsx` calls `services.auth.logout()` → `queryClient.clear()` → `navigate('/login', replace:true)`. `RoleSwitcher.tsx:31` returns null when `API_MODE !== 'mock'`. `main.tsx:25-33` has http-mode splash gate with `ensureQueryData(authKeys.me)`. |
| 5 | SC#5: ESLint forbids `fetch(` outside `packages/api-client/src/` and `apps/admin-web/src/shared/api/services/http/`; negative-test fixture proves the rule fires | ✓ VERIFIED | `eslint.config.js` has `"callee.name='fetch'"` selector. `src/__fixtures/raw-fetch-leak.ts` contains raw `fetch('/api/v1/clients')` call. `scripts/assert-eslint-fixtures.mjs` EXPECTED array includes `raw-fetch-leak.ts`. `pnpm lint:fixtures` exits 0 — all 4 fixtures trip their expected rules. |

**Score:** 5/5 truths verified (all ROADMAP success criteria satisfied)

### Test Suite Health

All Phase 10 feature tests pass. The previously failing pre-existing lock test `src/shared/ui/components-json.test.ts` was updated to assert `'base-nova'` matching the Plan 01 registry switch — `pnpm exec vitest run src/shared/ui/components-json.test.ts` now exits 0 (verified 2026-05-04). Phase 11 added 5 more test files (adapter + optimistic-update regression) bringing the admin-web suite to 21 files / 108 tests, all green (`pnpm -F admin-web test` exit 0).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/admin-web/components.json` | ReUI base-nova config | ✓ VERIFIED | `"style": "base-nova"`, `@reui` registry present |
| `apps/admin-web/src/shared/ui/data-grid.tsx` | ReUI DataGrid barrel | ✓ VERIFIED | Re-exports from `src/components/reui/data-grid/` |
| `apps/admin-web/src/shared/ui/input-otp.tsx` | InputOTP primitive | ✓ VERIFIED | Uses `input-otp` package (OTPInput from `input-otp`) |
| `apps/admin-web/src/shared/ui/dialog.tsx` | Dialog primitive | ✓ VERIFIED | Exists, uses radix-ui |
| `apps/admin-web/src/shared/ui/alert-dialog.tsx` | AlertDialog primitive | ✓ VERIFIED | Exists |
| `apps/admin-web/src/shared/ui/form.tsx` | RHF Form bridge | ✓ VERIFIED | Exists |
| `apps/admin-web/src/shared/ui/tabs.tsx` | Tabs primitive | ✓ VERIFIED | Exists, exports TabsList/TabsTrigger/TabsContent |
| `apps/admin-web/src/entities/client/types.ts` | ClientId, Client, Pagination | ✓ VERIFIED | `export type ClientId`, `export interface Client`, `export interface Pagination<T>` |
| `apps/admin-web/src/shared/lib/brand.ts` | Brand<T,B> helper | ✓ VERIFIED | Exists |
| `apps/admin-web/src/shared/api/errors.ts` | DomainError + helpers | ✓ VERIFIED | `export class DomainError` with code/message/fields |
| `apps/admin-web/src/shared/api/contracts/auth.ts` | AuthService interface | ✓ VERIFIED | `export interface AuthService` with 6 methods |
| `apps/admin-web/src/shared/api/contracts/clients.ts` | ClientsService interface | ✓ VERIFIED | `export interface ClientsService` with 5 methods |
| `apps/admin-web/src/features/auth/model/schema.ts` | emailLoginSchema, telegramOtpSchema | ✓ VERIFIED | Exists |
| `apps/admin-web/src/features/clients/model/schema.ts` | clientCreateSchema, clientUpdateSchema, clientsListQuerySchema | ✓ VERIFIED | RU copy "Укажите фамилию" + E.164 validation present |
| `apps/admin-web/src/features/auth/api/keys.ts` | authKeys factory | ✓ VERIFIED | `export const authKeys` with all/me/telegramStatus |
| `apps/admin-web/src/features/clients/api/keys.ts` | clientsKeys factory | ✓ VERIFIED | `export const clientsKeys` TkDodo shape |
| `apps/admin-web/src/features/clients/api/keys.test.ts` | 5 unit tests | ✓ VERIFIED | All 5 pass |
| `apps/admin-web/src/shared/api/services/mock/_db.ts` | faker seed=42 + localStorage | ✓ VERIFIED | `sportzal:mock:v1`, `faker.seed(42)` |
| `apps/admin-web/src/shared/api/services/mock/_latency.ts` | 120-300ms delay | ✓ VERIFIED | Range 120..300 |
| `apps/admin-web/src/shared/api/services/mock/auth.ts` | MockAuth: AuthService | ✓ VERIFIED | `export const auth: AuthService` |
| `apps/admin-web/src/shared/api/services/mock/clients.ts` | MockClients: ClientsService | ✓ VERIFIED | `export const clients: ClientsService`, `can(role(), 'delete', 'clients')` |
| `apps/admin-web/src/shared/api/services/mock/clients.rbac.test.ts` | RBAC tests | ✓ VERIFIED | 3 tests pass (owner can delete, reception forbidden) |
| `apps/admin-web/src/shared/api/services/mock/clients.crud.test.ts` | CRUD tests | ✓ VERIFIED | 8 tests pass |
| `apps/admin-web/src/shared/api/services/mock/index.ts` | Swap seam mock container | ✓ VERIFIED | `export const services = { auth, clients } as const` |
| `apps/admin-web/src/shared/api/services/http/_envelope.ts` | unwrap<T> helper | ✓ VERIFIED | Strips Phase 4 D-07 `{data: T}` envelope |
| `apps/admin-web/src/shared/api/services/http/_envelope.test.ts` | 4 envelope tests | ✓ VERIFIED | All pass |
| `apps/admin-web/src/shared/api/services/http/auth.ts` | HTTP AuthService | ✓ VERIFIED | Uses `@sportzal/api-client`, implements AuthService |
| `apps/admin-web/src/shared/api/services/http/clients.ts` | HTTP ClientsService | ✓ VERIFIED | Uses `@sportzal/api-client`, implements ClientsService |
| `apps/admin-web/src/shared/api/services/http/index.ts` | Swap seam http container | ✓ VERIFIED | `export const services = { auth, clients } as const` |
| `apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts` | Session expiry redirect | ✓ VERIFIED | Module flag, single-flight, lazy router import |
| `apps/admin-web/src/features/auth/api/redirect-on-session-expired.test.ts` | 5 redirect tests | ✓ VERIFIED | All 5 pass |
| `apps/admin-web/src/app/queryClient.ts` | QueryCache + MutationCache wired | ✓ VERIFIED | `new QueryCache`, `new MutationCache`, `redirectOnSessionExpired` |
| `apps/admin-web/src/app/router.ts` | API_MODE-aware getSession | ✓ VERIFIED | Branches on `API_MODE === 'mock'`, falls back to `'reception'` (not 'owner') |
| `apps/admin-web/src/shared/session/useCurrentRole.ts` | Mode-aware role hook | ✓ VERIFIED | Branches on `API_MODE`, used by RoleGate |
| `apps/admin-web/src/shared/session/RoleGate.tsx` | Refactored to useCurrentRole | ✓ VERIFIED | Uses `useCurrentRole()`, no direct useSessionStore |
| `apps/admin-web/src/routes/_public.tsx` | Public pathless layout | ✓ VERIFIED | Outlet only, no AppShell |
| `apps/admin-web/src/routes/_public/login.tsx` | /login route | ✓ VERIFIED | `validateSearch` with `next`, `beforeLoad` with silent redirect |
| `apps/admin-web/src/routes/_protected.tsx` | Protected pathless layout | ✓ VERIFIED | AppShell wrapper + auth gate + API_MODE mock bypass |
| `apps/admin-web/src/routes/__root.tsx` | Root without AppShell | ✓ VERIFIED | 0 occurrences of AppShell |
| `apps/admin-web/src/features/auth/api/hooks.ts` | 6 auth TanStack Query hooks | ✓ VERIFIED | useMe/useLogin/useLogout/useTelegramStart/useTelegramStatus(refetchInterval:3000)/useTelegramVerify |
| `apps/admin-web/src/features/auth/components/LoginPage.tsx` | Two-tab login UI | ✓ VERIFIED | `defaultValue="email"`, sanitizeNext guard |
| `apps/admin-web/src/features/auth/components/EmailLoginForm.tsx` | Email login form | ✓ VERIFIED | `zodResolver(emailLoginSchema)`, RU error copy |
| `apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx` | Telegram OTP state machine | ✓ VERIFIED | 3s polling, 5min timeout, InputOTP |
| `apps/admin-web/src/routes/_protected/clients.tsx` | Real clients route | ✓ VERIFIED | `validateSearch`, `ensureQueryData`, `clientsKeys.list(search)` |
| `apps/admin-web/src/features/clients/api/hooks.ts` | 5 clients hooks with optimistic | ✓ VERIFIED | `onMutate`, `onError`, `onSettled` present |
| `apps/admin-web/src/features/clients/api/hooks.delete.test.tsx` | Delete hook tests | ✓ VERIFIED | 3 tests: optimistic remove, rollback on error, decrement total |
| `apps/admin-web/src/features/clients/components/ClientsPage.tsx` | Clients list + toolbar | ✓ VERIFIED | Exists, substantive |
| `apps/admin-web/src/features/clients/components/ClientsTable.tsx` | DataGrid with RoleGate delete | ✓ VERIFIED | Uses DataGrid; `<RoleGate action="delete" resource="clients">` at line 67 |
| `apps/admin-web/src/features/clients/components/ClientsTableSkeleton.tsx` | Skeleton rows | ✓ VERIFIED | Exists, uses `<Skeleton>` |
| `apps/admin-web/src/features/clients/components/ClientForm.tsx` | RHF + clientCreateSchema | ✓ VERIFIED | Exists, uses clientCreateSchema |
| `apps/admin-web/src/features/clients/components/ClientFormDialog.tsx` | Dialog wrapper | ✓ VERIFIED | Imports and renders ClientForm |
| `apps/admin-web/src/features/clients/components/ClientDeleteDialog.tsx` | AlertDialog confirm delete | ✓ VERIFIED | Exists |
| `apps/admin-web/src/features/clients/components/ClientsTable.rbac.test.tsx` | RBAC UI tests | ✓ VERIFIED | 3 tests pass (owner sees delete, reception does not) |
| `apps/admin-web/src/shared/lib/hooks/useDebounceValue.ts` | Search debounce hook | ✓ VERIFIED | Exists |
| `apps/admin-web/src/shared/ui/splash.tsx` | Splash component | ✓ VERIFIED | Has `Loader2`, `bg-background`, `text-muted-foreground` |
| `apps/admin-web/src/app/main.tsx` | HTTP-mode splash gate | ✓ VERIFIED | `Splash`, `API_MODE === 'http'`, `ensureQueryData`, `authKeys.me` |
| `apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx` | Active logout | ✓ VERIFIED | `services.auth.logout()`, `queryClient.clear()`, `navigate('/login')` |
| `apps/admin-web/src/shared/ui/app-shell/ProfileMenu.test.tsx` | 2 logout tests | ✓ VERIFIED | Both tests pass |
| `apps/admin-web/src/shared/ui/app-shell/RoleSwitcher.tsx` | Hidden in http-mode | ✓ VERIFIED | `if (API_MODE !== 'mock') return null` at line 31 |
| `apps/admin-web/eslint.config.js` | fetch() ban rule | ✓ VERIFIED | `"callee.name='fetch'"` selector present |
| `apps/admin-web/src/__fixtures/raw-fetch-leak.ts` | fetch() negative fixture | ✓ VERIFIED | Contains `fetch('/api/v1/clients')` |
| `apps/admin-web/scripts/assert-eslint-fixtures.mjs` | EXPECTED array updated | ✓ VERIFIED | `raw-fetch-leak.ts` entry present; `lint:fixtures` passes |
| `apps/admin-web/src/shared/i18n/ru.ts` | auth + clients i18n blocks | ✓ VERIFIED | "Войти в систему", "Клиенты", "Срок действия ссылки истёк" all present |
| `apps/admin-web/.env.example` | VITE_API_MODE documented | ✓ VERIFIED | `VITE_API_MODE=mock` and `VITE_API_BASE_URL` documented |
| `apps/admin-web/.env.development` | VITE_API_MODE=mock | ✓ VERIFIED | Present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `services/index.ts` | `mock/` or `http/` | `API_MODE === 'http'` branch | ✓ WIRED | Single swap seam, correct branching |
| `_protected.tsx` | `AppShell` | Component wrapping Outlet | ✓ WIRED | AppShell only in `_protected.tsx` (not in `__root.tsx`) |
| `_protected.tsx` | `authKeys.me` | `ensureQueryData` in `beforeLoad` | ✓ WIRED | API_MODE mock bypass present |
| `_public/login.tsx` | `LoginPage` | `component: LoginPage` | ✓ WIRED | Import confirmed |
| `_protected/clients.tsx` | `clientsKeys.list(search)` | `ensureQueryData` loader | ✓ WIRED | Same key used in route and hook |
| `http/auth.ts` | `@sportzal/api-client` | `import { request }` | ✓ WIRED | Confirmed |
| `http/clients.ts` | `@sportzal/api-client` | `import { request }` | ✓ WIRED | Confirmed |
| `queryClient.ts` | `redirect-on-session-expired.ts` | `QueryCache({onError})` + `MutationCache({onError})` | ✓ WIRED | Both caches wired |
| `redirect-on-session-expired.ts` | `router` | lazy `import('@/app/router')` | ✓ WIRED | Circular import safely broken |
| `RoleGate.tsx` | `useCurrentRole.ts` | hook call | ✓ WIRED | No direct `useSessionStore` in RoleGate |
| `ProfileMenu.tsx` | `services.auth.logout` | mutation | ✓ WIRED | Full chain: logout → clear → navigate |
| `mock/clients.ts` | `can()` from session | `can(role(), 'delete', 'clients')` | ✓ WIRED | RBAC enforced |
| `EmailLoginForm.tsx` | `emailLoginSchema` | `zodResolver` | ✓ WIRED | Same schema used by mock service |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `ClientsTable.tsx` | `data` prop (Pagination<Client>) | `useClientsList` → `services.clients.list()` → mock/http | Yes (seeded faker OR real API) | ✓ FLOWING |
| `LoginPage.tsx` | `search.next` | URL search params via `validateSearch` | Yes (from router) | ✓ FLOWING |
| `TelegramLoginTab.tsx` | `status.data?.bound` | `useTelegramStatus` → `services.auth.telegramStatus()` | Yes (mock state machine / real API) | ✓ FLOWING |
| `ProfileMenu.tsx` | `role` | `useCurrentRole()` → Zustand (mock) or authKeys.me cache (http) | Yes (both paths) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| clientsKeys factory produces stable keys | `npx vitest run src/features/clients/api/keys.test.ts` | 5 tests pass | ✓ PASS |
| redirect-on-session-expired single-flight | `npx vitest run src/features/auth/api/redirect-on-session-expired.test.ts` | 5 tests pass | ✓ PASS |
| mock clients RBAC (reception cannot delete) | `npx vitest run src/shared/api/services/mock/clients.rbac.test.ts` | 3 tests pass | ✓ PASS |
| mock clients CRUD (list/create/update/search) | `npx vitest run src/shared/api/services/mock/clients.crud.test.ts` | 8 tests pass | ✓ PASS |
| LoginPage renders two tabs, email default | `npx vitest run src/features/auth/components/LoginPage.test.tsx` | 4 tests pass | ✓ PASS |
| ProfileMenu logout calls correct chain | `npx vitest run src/shared/ui/app-shell/ProfileMenu.test.tsx` | 2 tests pass | ✓ PASS |
| ClientsTable hides delete for reception | `npx vitest run src/features/clients/components/ClientsTable.rbac.test.tsx` | 3 tests pass | ✓ PASS |
| Delete hook optimistic + rollback | `npx vitest run src/features/clients/api/hooks.delete.test.tsx` | 3 tests pass | ✓ PASS |
| ESLint fetch ban + all fixtures | `node scripts/assert-eslint-fixtures.mjs` | All 4 fixtures trigger expected rules | ✓ PASS |
| lint + typecheck | `npx eslint . && npx tsc -b --noEmit` | 0 errors, 2 warnings (pre-existing) | ✓ PASS |
| Full test suite | `pnpm -F admin-web test` | 21 files / 108 tests pass (re-verified 2026-05-04 after components-json.test.ts fix + Phase 11 adapter tests) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FE-01 | Plans 03, 04 | `http/auth.ts` and `http/clients.ts` via `@sportzal/api-client` | ✓ SATISFIED | Files exist, implement AuthService/ClientsService contracts, use `request()` not raw fetch |
| FE-02 | Plan 05 | `/login` route with two tabs; Telegram polls status and prompts after `bound: true` | ✓ SATISFIED | LoginPage, TelegramLoginTab, _public/login.tsx all verified |
| FE-03 | Plans 03, 04 | `VITE_API_MODE=http` wired only for login+clients; mock-mode unchanged | ✓ SATISFIED | Swap seam in `services/index.ts` confirmed |
| FE-04 | Plans 02, 06 | clientsKeys factory; route loaders use `ensureQueryData`; optimistic mutations | ✓ SATISFIED | `clientsKeys.list(search)` in loader; `onMutate`/`onError`/`onSettled` in hooks |
| FE-05 | Plans 04, 05 | 401 → single-flight refresh → `/login?next=` once; login restores location | ✓ SATISFIED | Module flag in redirect-on-session-expired; `search.next` in login route |
| FE-06 | Plans 05, 07 | Logout clears TanStack Query cache and redirects to `/login` | ✓ SATISFIED | ProfileMenu: `queryClient.clear()` + navigate |
| FE-07 | Plan 07 | ESLint bans raw `fetch(` outside allowed paths; negative-test fixture | ✓ SATISFIED | `eslint.config.js` rule + `raw-fetch-leak.ts` fixture + `lint:fixtures` passes |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/shared/ui/components-json.test.ts` | 27 | (resolved 2026-05-04) Lock test now asserts `'base-nova'` matching `components.json:3`. Originally asserted `'new-york'` after Plan 01 registry switch — closed during Phase 12 verification backfill. | ✓ RESOLVED | n/a |

### Human Verification Required

None required — all critical behaviors are covered by the automated test suite and static analysis checks above. Visual appearance and real-time behavior (actual HTTP round-trip with real backend, Telegram bot integration) are intentionally excluded from Phase 10 scope (backend phases 4-9 are not implemented yet).

---

## Gaps Summary

**No outstanding gaps as of re-verification 2026-05-04T23:45:00Z.**

The original gap — `src/shared/ui/components-json.test.ts` line 27 asserted `'new-york'` while `components.json` declared `'base-nova'` — is **resolved on disk**. The lock test now reads `expect(json.style).toBe('base-nova')` (line 27, verified 2026-05-04), matching `components.json` (`"style": "base-nova"`, line 3). `pnpm exec vitest run src/shared/ui/components-json.test.ts` exits 0.

**Cross-phase reinforcement of SC #2 (clients HTTP-mode):**

- **Phase 11 (clients HTTP-mode shape adapter)** shipped 2026-05-04 with `status: passed` (9/9 must-haves; see `.planning/phases/11-clients-http-shape-adapter/11-VERIFICATION.md`). The phase added pure adapter helpers (`responseToClient`, `createInputToRequest`, `updateInputToRequest` in `apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts`) so `VITE_API_MODE=http` `/clients/*` calls correctly map between FE `Client` shape and backend `ClientResponse` / `ClientCreateRequest` shapes — closing INTEGRATION-CHECK F-01 (response shape: `fullName` composition + `birthday → birthDate`) and F-02 (request shape: `birthDate → birthday` + empty-string omission).
- **Phase 12.1 (clients service commit fix)** shipped 2026-05-04 (commit `ba14aba`, quick-task `260504-fst`). Added `await session.commit()` to `apps/backend/app/modules/clients/service.py` write paths (`create_client`, `update_client`, `soft_delete_client`), mirroring the auth/service.py pattern, plus a persistence regression test at `apps/backend/tests/integration/clients/test_persistence.py`. This unblocks the Phase 11 SC #4 live-runbook walkthrough — the only remaining human-verify item that touches Phase 10 SC #2 in http-mode.

All 5 ROADMAP SCs (SC #1 login tabs + Telegram poll, SC #2 clients CRUD via api-client, SC #3 mock-mode no regression, SC #4 single-flight refresh + redirect-back, SC #5 ESLint fetch ban) remain VERIFIED. All 7 FE requirements (FE-01..FE-07) remain SATISFIED.

---

_Verified: 2026-05-04T17:10:00Z_
_Verifier: Claude (gsd-verifier)_

_Re-verified: 2026-05-04T23:45:00Z_
_Re-verifier: Claude (gsd-verifier, Phase 12 backfill)_
_Re-verification reason: gap resolved (components-json.test.ts asserts 'base-nova' on disk); Phase 11 + Phase 12.1 reinforce SC #2 in http-mode_
