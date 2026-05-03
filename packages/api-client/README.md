# @sportzal/api-client

Типизированный transport для backend'а Sportzal. Публичная поверхность (D-10):

- `request<P, M>(method, path, init?)` — единственная функция для запросов.
- `ApiError` — класс ошибки, зеркалит backend `AppError` envelope (`code` / `message` / `fields?`).
- `paths`, `components` — типы, сгенерированные `openapi-typescript` из `apps/backend/openapi.json`.

## Usage

```typescript
import { request, ApiError, type paths } from '@sportzal/api-client'

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
pnpm --filter @sportzal/api-client codegen
```

Локально перед `pnpm dev` в `apps/admin-web` это выполняется автоматически через `predev` hook (см. `apps/admin-web/package.json`). Не редактируй `src/schema.d.ts` руками — CI откатит изменения через `git diff --exit-code` (Phase 9 API-07).

`src/schema.d.ts` **закоммичен в git** (Phase 9 D-07) — отступление от REQUIREMENTS API-05 wording 'gitignored locally'. Без коммита drift-gate бессмыслен.

## Single-flight refresh

Fetcher держит module-scoped `inFlightRefresh: Promise<Response> | null`. На 401 от non-`/auth/*` путей запускается ОДИН `/api/v1/auth/refresh`; параллельные запросы ждут тот же promise. Любой провал (4xx, 5xx, network, timeout) → синтетический `ApiError('session_expired', ...)`. Если retry после успешного refresh снова даёт 401 — тоже `session_expired` (max 1 refresh per failed call, защита от лупов). Подробности в Phase 9 CONTEXT D-A1..D-A4.

Fetcher НЕ редиректит и НЕ знает про `/login` — он pure transport (D-A2). Redirect-логика живёт в admin-web (Phase 10 FE-05).

## CSRF

На mutating методы (POST / PATCH / PUT / DELETE) fetcher читает cookie `sportzal_csrf` (выставляется backend'ом на `/auth/login` и `/auth/refresh`) и отправляет header `X-CSRF-Token`. На GET / HEAD / OPTIONS header не добавляется — соответствует server-side `_SAFE_METHODS` short-circuit (Phase 6 D-04).

## Phase 9 deviation note

Этот пакет в Phase 1 был placeholder'ом (только `package.json` + `README.md`). Phase 9 разрешённо нарушает это правило — здесь приземляется первый реальный код (см. CONTEXT.md `09-CONTEXT.md` § "Established patterns to honor").
