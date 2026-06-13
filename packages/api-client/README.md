# @clubcore/api-client

Типизированный transport для backend'а clubcore. Публичная поверхность (D-10):

- `request<P, M>(method, path, init?)` — единственная функция для запросов.
- `ApiError` — класс ошибки, зеркалит backend `AppError` envelope (`code` / `message` / `fields?`).
- `paths`, `components` — типы, сгенерированные `openapi-typescript` из `apps/backend/openapi.json`.

## Usage

```typescript
import { request, ApiError, type paths } from '@clubcore/api-client'

try {
  const me = await request('GET', '/api/v1/auth/me')
  // ...
} catch (err) {
  if (err instanceof ApiError) {
    if (err.code === 'session_expired') {
      // synthetic client-side code — single-flight /auth/refresh failed.
      // Phase 10 ловит это в QueryClient onError / router error boundary
      // и редиректит в /login?next=<encoded>.
    }
    if (err.code === 'invalid_credentials') {
      // server-issued — pass-through на /auth/login.
    }
  }
}
```

Convenience-обёртки (`get` / `post` / ...) **не** добавлены умышленно (D-10 — backlog).

## Codegen

`src/schema.d.ts` генерируется из `apps/backend/openapi.json`:

```bash
pnpm --filter @clubcore/api-client codegen
```

Локально перед `pnpm dev` в `apps/admin-app` это можно выполнить вручную или через `predev` hook. Не редактируй `src/schema.d.ts` руками — CI откатит изменения через `git diff --exit-code` (Phase 9 API-07).

`src/schema.d.ts` **закоммичен в git** (Phase 9 D-07) — отступление от REQUIREMENTS API-05 wording 'gitignored locally'. Без коммита drift-gate бессмыслен.

## v1.4 changelog

Новые типизированные paths в v1.4 (Phases 31-34, backend-only handoff per 2026-05-15 pivot — production frontends разрабатываются дизайн-командой вне репо):

- **Trainers** (Phase 31): owner-only CRUD каталога тренеров; reception видит только active в PT-session picker.
- **Payments ledger** (Phase 32): append-only журнал; GET-listing (owner) + per-client / per-membership history (reception+owner).
- **Membership refund** (Phase 32): `POST /memberships/{id}/refund` — full-only, B-08/B-09 guards (frozen / renewed-source отвергаются 409).
- **PT-package plans** (Phase 33): owner-only CRUD каталога; `session_count` / `price_kopecks` / `validity_days` immutable post-creation.
- **PT-packages** (Phase 33): продажа / отмена / refund инстансов; status machine `active → exhausted | expired | cancelled`.
- **PT-package refund** (Phase 33): `POST /pt-packages/{id}/refund` — симметрично membership refund.
- **PT-sessions** (Phase 34): запись / отмена тренировок; race-safe декремент `sessions_remaining` на DB-уровне.

Полный surface — в `apps/backend/openapi.json` (source-of-truth, не дублируется здесь чтобы избежать rot). v1.3 paths (`/membership-plans`, `/memberships`, `/memberships/{id}/freeze|unfreeze|renew`, `/visits`) остались без изменений.

## Auth quick-start

Внешние потребители контракта (дизайн-команда v2.0):

- **Login**: `POST /api/v1/auth/login` принимает `{email, password}`, проверяет Argon2id; ставит cookies `cc_access` + `clubcore_csrf` и возвращает access JWT в body.
- **Token rotation**: `POST /api/v1/auth/refresh` — refresh-rotation family; см. § "Single-flight refresh" ниже для runtime contract.
- **Mutating requests**: добавляй header `X-CSRF-Token` из cookie `clubcore_csrf`; см. § "CSRF" ниже.
- **Telegram OTP path** (client-app): `POST /api/v1/auth/telegram/start` → `GET /api/v1/auth/telegram/status` → `POST /api/v1/auth/telegram/verify`.

Sample curl examples и полный Postman collection будут опубликованы в v1.5 API Handoff milestone.

## Single-flight refresh

Fetcher держит module-scoped `inFlightRefresh: Promise<Response> | null`. На 401 от non-`/auth/*` путей запускается ОДИН `/api/v1/auth/refresh`; параллельные запросы ждут тот же promise. Любой провал (4xx, 5xx, network, timeout) → синтетический `ApiError('session_expired', ...)`. Если retry после успешного refresh снова даёт 401 — тоже `session_expired` (max 1 refresh per failed call, защита от лупов). Подробности в Phase 9 CONTEXT D-A1..D-A4.

Fetcher НЕ редиректит и НЕ знает про `/login` — он pure transport (D-A2). Redirect-логика живёт в admin-app (Phase 10 FE-05).

## CSRF

На mutating методы (POST / PATCH / PUT / DELETE) fetcher читает cookie `clubcore_csrf` (выставляется backend'ом на `/auth/login` и `/auth/refresh`) и отправляет header `X-CSRF-Token`. На GET / HEAD / OPTIONS header не добавляется — соответствует server-side `_SAFE_METHODS` short-circuit (Phase 6 D-04).

## Phase 9 deviation note

Этот пакет в Phase 1 был placeholder'ом (только `package.json` + `README.md`). Phase 9 разрешённо нарушает это правило — здесь приземляется первый реальный код (см. CONTEXT.md `09-CONTEXT.md` § "Established patterns to honor").
