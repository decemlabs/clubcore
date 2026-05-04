---
phase: 10
plan: 02
subsystem: admin-web/contracts-types-keys
tags: [admin-web, contracts, types, zod, tanstack-query]
one-liner: "Transport-agnostic AuthService + ClientsService contracts, branded ClientId + DomainError, Zod schemas with RU copy, and TkDodo authKeys + clientsKeys factories with unit test"
dependency_graph:
  requires:
    - apps/admin-web/src/shared/session/types.ts
    - packages/api-client/src/errors.ts
  provides:
    - apps/admin-web/src/shared/lib/brand.ts
    - apps/admin-web/src/shared/api/errors.ts
    - apps/admin-web/src/entities/client/types.ts
    - apps/admin-web/src/entities/client/index.ts
    - apps/admin-web/src/shared/api/contracts/auth.ts
    - apps/admin-web/src/shared/api/contracts/clients.ts
    - apps/admin-web/src/shared/api/contracts/index.ts
    - apps/admin-web/src/features/auth/model/schema.ts
    - apps/admin-web/src/features/clients/model/schema.ts
    - apps/admin-web/src/features/auth/api/keys.ts
    - apps/admin-web/src/features/clients/api/keys.ts
    - apps/admin-web/src/features/clients/api/keys.test.ts
  affects:
    - All Wave 3+ plans that consume contracts, schemas, or query key factories
tech_stack:
  added: []
  patterns:
    - "Brand<T,B> type helper for compile-time branded UUIDv4 IDs (unique symbol pattern)"
    - "DomainError mirrors ApiError shape: code+message+fields; isDomainError/isAppError/appErrorCode helpers"
    - "TkDodo query key factory pattern (.all, .lists(), .list(filter), .details(), .detail(id))"
    - "z.coerce for URL search param coercion (strings → numbers for page/pageSize)"
    - "Zod .optional().or(z.literal('')) for optional string fields that may be empty string"
key_files:
  created:
    - apps/admin-web/src/shared/lib/brand.ts
    - apps/admin-web/src/shared/api/errors.ts
    - apps/admin-web/src/entities/client/types.ts
    - apps/admin-web/src/entities/client/index.ts
    - apps/admin-web/src/shared/api/contracts/auth.ts
    - apps/admin-web/src/shared/api/contracts/clients.ts
    - apps/admin-web/src/features/auth/model/schema.ts
    - apps/admin-web/src/features/clients/model/schema.ts
    - apps/admin-web/src/features/auth/api/keys.ts
    - apps/admin-web/src/features/clients/api/keys.ts
    - apps/admin-web/src/features/clients/api/keys.test.ts
  modified:
    - apps/admin-web/src/shared/api/contracts/index.ts (replaced Record<string,never> stub with barrel re-exports)
decisions:
  - "authKeys.me is a tuple constant (not a function) — only one /auth/me entry ever exists in cache"
  - "clientsKeys.me and clientsKeys.detail use spread to create new arrays, ensuring referential freshness per call"
  - "Pagination<T> defined in entities/client/types.ts and re-exported through contracts/clients.ts (single source)"
  - "email + birthDate fields in clientCreateSchema accept empty string OR undefined (optional().or(literal(''))) to support controlled inputs in RHF that initialize as ''"
  - "E.164 regex accepts 10-15 digits after '+' prefix covering +7 Russian numbers and international formats"
metrics:
  duration: "~3 minutes"
  completed_date: "2026-05-04T13:12:14Z"
  tasks_completed: 3
  files_modified: 12
---

# Phase 10 Plan 02: Contracts, Types, Schemas, and Key Factories Summary

Transport-agnostic AuthService + ClientsService contracts, branded ClientId + DomainError, Zod schemas with Russian UI-SPEC copy, and TkDodo authKeys + clientsKeys factories with unit test — establishing the frozen contract surface all Wave 3+ plans consume.

## Commits

| Hash | Description |
|------|-------------|
| f28f76b | feat(10-02): brand helper, DomainError, ClientId, Client, Pagination |
| 2a580c8 | feat(10-02): AuthService + ClientsService contracts + Zod schemas |
| e23d9fa | feat(10-02): authKeys + clientsKeys factories + unit test |

## Contract Surface

### AuthService (6 methods)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `me()` | `() => Promise<MeResponse>` | Bootstrap /auth/me call |
| `login(input)` | `(EmailLoginInput) => Promise<MeResponse>` | Email/password auth |
| `logout()` | `() => Promise<void>` | Clear session |
| `telegramStart()` | `() => Promise<TelegramStartResponse>` | Get deep-link + token |
| `telegramStatus(token)` | `(string) => Promise<TelegramStatusResponse>` | Poll bound status |
| `telegramVerify(input)` | `(TelegramVerifyInput) => Promise<MeResponse>` | Submit OTP code |

### ClientsService (5 methods)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `list(query)` | `(ClientsListQuery) => Promise<Pagination<Client>>` | Paginated list |
| `get(id)` | `(ClientId) => Promise<Client>` | Single client by ID |
| `create(input)` | `(ClientCreateInput) => Promise<Client>` | Create new client |
| `update(id, input)` | `(ClientId, ClientUpdateInput) => Promise<Client>` | Partial update |
| `remove(id)` | `(ClientId) => Promise<void>` | Soft-delete |

## Zod Schema Names + UI-SPEC Copy Parity

| Schema | File | RU Validation Messages |
|--------|------|----------------------|
| `emailLoginSchema` | `features/auth/model/schema.ts` | "Введите корректный email", "Введите пароль" |
| `telegramOtpSchema` | `features/auth/model/schema.ts` | "Введите 6-значный код" |
| `clientCreateSchema` | `features/clients/model/schema.ts` | "Укажите фамилию", "Укажите имя", "Укажите номер телефона", "Введите телефон в формате +7 (XXX) XXX-XX-XX", "Введите корректный email", "Дата в формате ГГГГ-ММ-ДД" |
| `clientUpdateSchema` | `features/clients/model/schema.ts` | Partial of clientCreateSchema |
| `clientsListQuerySchema` | `features/clients/model/schema.ts` | z.coerce for URL search params; defaults page=1, pageSize=20 |

## Key Factory Shapes

### authKeys (TkDodo, no deviations)

```typescript
authKeys.all             // ['auth']
authKeys.me              // ['auth', 'me']  — tuple constant, not function
authKeys.telegramStatus('tok') // ['auth', 'telegram-status', 'tok']
```

Note: `me` is a tuple constant (not a function) per plan specification — there is only ever one `/auth/me` cache entry.

### clientsKeys (TkDodo canonical shape, FE-04)

```typescript
clientsKeys.all          // ['clients']
clientsKeys.lists()      // ['clients', 'list']
clientsKeys.list({q,page,pageSize})  // ['clients', 'list', {q,page,pageSize}]
clientsKeys.details()    // ['clients', 'detail']
clientsKeys.detail(id)   // ['clients', 'detail', id]
```

All 5 unit tests pass verifying structural shape and filter distinctness.

## Deviations from Plan

None — plan executed exactly as written. All 12 files created/modified as specified. authKeys.me implemented as a tuple constant (not function) per plan's explicit note: "me is a tuple constant, not a function — the cache only ever holds one /auth/me entry."

## Known Stubs

None — this plan defines pure types, contracts, schemas, and key factories. No data flows, no UI, no runtime side effects.

## Threat Flags

None. All files are pure type definitions and schemas — no network endpoints, no auth paths, no file access patterns introduced.

T-10-04 (Zod schema accepts E.164 but mock/http may skip revalidation): mitigation is Wave 3's responsibility per threat register — Wave 3 mock + http services MUST call `clientCreateSchema.parse(input)` before side-effects.

## Self-Check: PASSED

All 12 files verified present:
- FOUND: apps/admin-web/src/shared/lib/brand.ts
- FOUND: apps/admin-web/src/shared/api/errors.ts
- FOUND: apps/admin-web/src/entities/client/types.ts
- FOUND: apps/admin-web/src/entities/client/index.ts
- FOUND: apps/admin-web/src/shared/api/contracts/auth.ts
- FOUND: apps/admin-web/src/shared/api/contracts/clients.ts
- FOUND: apps/admin-web/src/shared/api/contracts/index.ts
- FOUND: apps/admin-web/src/features/auth/model/schema.ts
- FOUND: apps/admin-web/src/features/clients/model/schema.ts
- FOUND: apps/admin-web/src/features/auth/api/keys.ts
- FOUND: apps/admin-web/src/features/clients/api/keys.ts
- FOUND: apps/admin-web/src/features/clients/api/keys.test.ts

All commits verified present:
- FOUND: f28f76b feat(10-02): brand helper, DomainError, ClientId, Client, Pagination
- FOUND: 2a580c8 feat(10-02): AuthService + ClientsService contracts + Zod schemas
- FOUND: e23d9fa feat(10-02): authKeys + clientsKeys factories + unit test
