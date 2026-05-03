# Phase 9: OpenAPI Pipeline + packages/api-client - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 09-openapi-pipeline-api-client
**Areas discussed:** Refresh-failure UX contract

---

## Refresh-failure UX contract

### Q1: Что fetcher должен бросить, когда single-flight `/auth/refresh` вернул 401 и retry невозможен?

| Option | Description | Selected |
|--------|-------------|----------|
| ApiError {code: 'session_expired'} | Синтетический клиент-код. Phase 10 различает от server-issued unauthorized/invalid_credentials/forbidden. | ✓ |
| ApiError {code: 'unauthorized'} | Тот же код, что и server-issued 401. Проще, но Phase 10 не различает source. | |
| Pass-through server code | Бросаем буквально, что вернул /auth/refresh (family_reuse_detected, refresh_expired). | |

**User's choice:** ApiError {code: 'session_expired'} (Recommended)
**Notes:** Покрыто D-A1 в CONTEXT.md.

---

### Q2: Кто редиректит в /login при `session_expired`?

| Option | Description | Selected |
|--------|-------------|----------|
| Fetcher throws only; admin-web ловит и редиректит | packages/api-client остаётся framework-agnostic; redirect-логика (next=, one-shot flag) в Phase 10. | ✓ |
| Fetcher принимает `onAuthFailure` callback при инициализации | Factory-pattern + config; callback вызывается на session_expired. | |
| Fetcher делает window.location.href = '/login?next=...' | Минимум кода в admin-web; но тесная связь с browser global, full-reload вместо SPA-нав. | |

**User's choice:** Fetcher throws only; admin-web ловит и редиректит (Recommended)
**Notes:** Покрыто D-A2 в CONTEXT.md.

---

### Q3: 401 от /auth/* (refresh не пытаемся) — как fetcher обрабатывает?

| Option | Description | Selected |
|--------|-------------|----------|
| Pass-through server's `{code,message,fields}` на ApiError | Fetcher читает body, строит ApiError(server.code, ...) вербатим. Phase 10 видит invalid_credentials, family_reuse_detected etc. без перемаппинга. | ✓ |
| 401 на /auth/me → session_expired (исключение) | Спец-кейс для boot-time 'who am I'. | |
| 401 от /auth/refresh внутри single-flight → session_expired; остальные /auth/* pass-through | Edge-case покрытие явно. | |

**User's choice:** Pass-through (Recommended)
**Notes:** Покрыто D-A3 в CONTEXT.md.

---

### Q4: Edge cases single-flight'a (network-fail refresh + retry-after-refresh-401)?

| Option | Description | Selected |
|--------|-------------|----------|
| Network-fail = session_expired; retry-after-refresh-401 = НЕ рефрешим опять | Стандартная single-flight семантика; защита от бесконечных лупов. | ✓ |
| Network-fail = ApiError {code:'network_error'} | Различает 'connection lost' от 'session lost'. | |
| Retry-after-refresh-401 = опять refresh (до maxAttempts=2) | Двойная попытка перед сдачей. | |

**User's choice:** Network-fail = session_expired; max 1 refresh per failed call (Recommended)
**Notes:** Покрыто D-A4 в CONTEXT.md.

---

## Claude's Discretion

Пользователь не выбрал к обсуждению, но решения зафиксированы в CONTEXT.md как рекомендованные defaults:

- **CI workflow scope & layout** — D-01..D-03: один `.github/workflows/ci.yml` с параллельными job'ами `backend`/`frontend`; только статика + drift-gates; concurrency-cancellation на push.
- **OpenAPI export script** — D-04..D-06: `os.environ.setdefault('ENVIRONMENT', 'dev')` до import app; `create_app().openapi()` напрямую без lifespan; никакой sanitation servers/title в v1.1.
- **Codegen ergonomics & DX** — D-07..D-09: `schema.d.ts` КОММИТИТСЯ (расхождение с REQUIREMENTS API-05 — planner поднимает); `predev` hook в admin-web регенерирует; relative `import type { paths } from './schema'`.
- **fetcher.ts surface + CSRF policy** — D-10..D-12: только generic `request<P, M>` (no convenience helpers) + `ApiError` + types re-export; X-CSRF-Token только на mutating methods; absent cookie → не throw client-side, server вернёт 403 csrf_mismatch.

## Deferred Ideas

См. `<deferred>` в `09-CONTEXT.md`. Краткий список:

- Backend pytest integration в CI (нужен services-контейнер).
- Frontend E2E (Playwright).
- Backend SAST / CodeQL / dependency-vuln scan.
- API contract testing (Schemathesis).
- `packages/api-client` convenience helpers (`get`/`post`/`patch`/`del`).
- Network-error retry/backoff (TanStack Query покроет GET).
- OpenAPI `servers` customization.
- Workflow caching tuning.
- GitHub branch protection (vне scope Phase 9; settings UI).
- `packages/ui` остаётся placeholder.
- `packages/api-client` publish to npm — никогда (private monorepo).
