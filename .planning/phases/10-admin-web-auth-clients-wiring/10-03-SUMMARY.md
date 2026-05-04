---
phase: 10
plan: 03
subsystem: admin-web/mock-services
tags: [admin-web, mock, faker, rbac, localStorage, typescript]
one-liner: "Full mock auth + clients services with faker.seed=42, 120-300ms latency, RBAC enforcement, Zod validation, versioned localStorage, and 12 passing unit tests"
dependency_graph:
  requires:
    - apps/admin-web/src/shared/api/contracts/auth.ts
    - apps/admin-web/src/shared/api/contracts/clients.ts
    - apps/admin-web/src/shared/api/errors.ts
    - apps/admin-web/src/entities/client/types.ts
    - apps/admin-web/src/features/clients/model/schema.ts
    - apps/admin-web/src/features/auth/model/schema.ts
    - apps/admin-web/src/shared/session/can.ts
    - apps/admin-web/src/shared/session/store.ts
  provides:
    - apps/admin-web/src/shared/api/services/mock/_db.ts
    - apps/admin-web/src/shared/api/services/mock/_latency.ts
    - apps/admin-web/src/shared/api/services/mock/auth.ts
    - apps/admin-web/src/shared/api/services/mock/clients.ts
    - apps/admin-web/src/shared/api/services/mock/clients.rbac.test.ts
    - apps/admin-web/src/shared/api/services/mock/clients.crud.test.ts
    - apps/admin-web/src/shared/api/services/mock/index.ts
  affects:
    - All Wave 3+ plans that consume services.auth or services.clients in mock mode
    - apps/admin-web/src/shared/api/services/index.ts (swap seam now compiles with real services)
tech_stack:
  added: []
  patterns:
    - "Central DB shim (_db.ts) with loadDB/saveDB/resetDB + faker.seed(42) deterministic seeding"
    - "Latency helper (_latency.ts) returns Promise<void> resolving in 120-300ms jitter"
    - "RBAC enforcement via ensure() helper calling can(role, action, resource) from shared session/can"
    - "useSessionStore.getState() (not hook) reads role in service functions outside React render"
    - "Telegram state-machine: in-memory Map<token, TelegramSessionState>, bound=true after 3 polls"
    - "Zod schema reuse: clientCreateSchema.safeParse + clientUpdateSchema.safeParse in services"
    - "buildFullName helper joins lastName+firstName+middleName for mock fullName construction"
    - "searchHay function builds lowercase needle from fullName+phone for ILIKE-style search"
key_files:
  created:
    - apps/admin-web/src/shared/api/services/mock/_db.ts
    - apps/admin-web/src/shared/api/services/mock/_latency.ts
    - apps/admin-web/src/shared/api/services/mock/auth.ts
    - apps/admin-web/src/shared/api/services/mock/clients.ts
    - apps/admin-web/src/shared/api/services/mock/clients.rbac.test.ts
    - apps/admin-web/src/shared/api/services/mock/clients.crud.test.ts
  modified:
    - apps/admin-web/src/shared/api/services/mock/index.ts (replaced empty stub with auth+clients exports)
decisions:
  - "ensure() helper centralizes RBAC checks — first line after delay() in every guarded method"
  - "telegramSessions Map is module-scoped (survives component re-renders, reset on hot-reload)"
  - "buildFullName splits current.fullName by space for partial update heuristic (mock-only; Phase 8 backend stores 3 columns)"
  - "email/birthDate fields coerce empty string to undefined to match optional-or-empty-literal Zod schema"
  - "faker is NOT re-seeded on auth/clients — seed(42) is called only once in _db.ts seed() function"
metrics:
  duration: "~4 minutes"
  completed_date: "2026-05-04T13:18:00Z"
  tasks_completed: 2
  files_modified: 7
---

# Phase 10 Plan 03: Mock Services (Auth + Clients) Summary

Full mock service implementations for `auth` and `clients` per D-12: faker.seed=42 deterministic data, 120-300ms latency, RBAC enforcement, Zod validation, versioned localStorage persistence (`sportzal:mock:v1`), RoleSwitcher integration via `useSessionStore.getState()`. FE-03 deliverable that locks SC#3 ("VITE_API_MODE=mock /login + /clients work with no regression").

## Commits

| Hash | Description |
|------|-------------|
| 4cf5b35 | feat(10-03): mock DB shim (faker.seed=42, localStorage sportzal:mock:v1) + latency helper |
| c8833a5 | test(10-03): add failing tests for mock clients RBAC + CRUD (RED phase) |
| 194b29d | feat(10-03): mock auth + clients services + swap-seam container (GREEN phase) |

## Mock Service Surface

### AuthService — 6 methods

| Method | RBAC | Behavior |
|--------|------|----------|
| `me()` | None | Returns `{id:'mock-owner-uuid', role: useSessionStore.getState().role, fullName:'Owner Demo'}` |
| `login(input)` | None | Validates with `emailLoginSchema`; throws `DomainError('validation_failed')` on invalid; no-op + latency on success |
| `logout()` | None | Latency-only; RoleSwitcher controls Zustand role independently |
| `telegramStart()` | None | Creates in-memory TelegramSessionState with UUID token, 5min TTL |
| `telegramStatus(token)` | None | Returns `{bound: false}` for first 2 polls, `{bound: true}` on poll 3+; throws `expired` after 5min |
| `telegramVerify({token, code})` | None | Accepts `code === '123456'`; throws `otp_invalid` otherwise; requires prior `bound === true` |

### ClientsService — 5 methods

| Method | RBAC gate | Behavior |
|--------|-----------|----------|
| `list({q, page, pageSize})` | `ensure('view', 'clients')` | ILIKE search on `fullName+phone`; sorted desc by `createdAt`; `{items, total, page, pageSize}` |
| `get(id)` | `ensure('view', 'clients')` | `DomainError('not_found')` if absent |
| `create(input)` | `ensure('edit', 'clients')` | `clientCreateSchema.parse`; duplicate phone throws `DomainError('validation_failed', ..., {phone: [...]})` |
| `update(id, input)` | `ensure('edit', 'clients')` | `clientUpdateSchema.parse`; splits `current.fullName` by space for partial name heuristic |
| `remove(id)` | `ensure('delete', 'clients')` | Reception throws `DomainError('forbidden')` per T-10-07; owner removes from DB |

### RBAC gates per method (T-10-07 mitigated)

`ensure('delete', 'clients')` is the FIRST expression after `await delay()` in `remove()`. Reception role triggers `DomainError('forbidden')` before any DB read. `clients.rbac.test.ts` asserts this with 3 test cases.

### Zod-validated entry points

- `clients.create()` — calls `clientCreateSchema.safeParse(input)` before any DB mutation
- `clients.update()` — calls `clientUpdateSchema.safeParse(input)` before any DB mutation
- `auth.login()` — calls `emailLoginSchema.safeParse(input)` before any side effects

### Telegram poll state-machine

- `telegramStart()` creates a `TelegramSessionState` with `pollCount: 0, bound: false`
- Each `telegramStatus(token)` call increments `pollCount`
- After `pollCount >= 3` (TELEGRAM_BOUND_AFTER_POLLS), `bound` flips to `true`
- Session expiry after 5 minutes (TELEGRAM_TOKEN_TTL_MS = 5*60*1000ms)
- `telegramVerify` requires `bound === true` and `code === '123456'`

### Seeded client count

`SEED_COUNT = 30` (constant). `faker.seed(42)` is called once in `seed()` before generating all 30 clients. Every seeded client has: valid UUIDv4 id, non-empty fullName (lastName + firstName + optional middleName), E.164 phone (`+7XXXXXXXXXX`), optional email, optional birthDate, ISO createdAt.

## Test Coverage

| File | Tests | What it covers |
|------|-------|---------------|
| `clients.rbac.test.ts` | 3 | Owner delete allowed; reception delete forbidden (DomainError 'forbidden'); reception list allowed |
| `clients.crud.test.ts` | 9 | Pagination shape; search filter; empty result; create valid; invalid phone; duplicate phone; partial update; partial name update heuristic; not_found on missing id update |

**Total: 12 tests, all passing.**

## Deviations from Plan

None — plan executed exactly as written. All 7 files created/modified as specified. CRUD test count is 9 (not 8 as stated in success criteria — the plan's test code has 9 `it()` blocks; the success criteria said "8 CRUD" which was a minor miscalculation in the plan).

## Known Stubs

None — this plan implements full service logic. No data flow stubs.

## Threat Flags

None. Mock services are dev-only (no production surface). T-10-07 is mitigated: `ensure('delete', 'clients')` first in `remove()`, guards verified by tests.

## Self-Check: PASSED

All files verified present:
- FOUND: apps/admin-web/src/shared/api/services/mock/_db.ts
- FOUND: apps/admin-web/src/shared/api/services/mock/_latency.ts
- FOUND: apps/admin-web/src/shared/api/services/mock/auth.ts
- FOUND: apps/admin-web/src/shared/api/services/mock/clients.ts
- FOUND: apps/admin-web/src/shared/api/services/mock/clients.rbac.test.ts
- FOUND: apps/admin-web/src/shared/api/services/mock/clients.crud.test.ts
- FOUND: apps/admin-web/src/shared/api/services/mock/index.ts

All commits verified present:
- FOUND: 4cf5b35 feat(10-03): mock DB shim
- FOUND: c8833a5 test(10-03): add failing tests for mock clients RBAC + CRUD (RED phase)
- FOUND: 194b29d feat(10-03): mock auth + clients services + swap-seam container (GREEN phase)
