# Phase 9: OpenAPI Pipeline + packages/api-client - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 9 закрывает FE↔BE drift: любое изменение Pydantic-схемы или роута на бэке либо **в том же PR** регенерирует `apps/backend/openapi.json` + сгенерированные TS-типы, либо CI падает. Phase 9 ships:

1. **`apps/backend/scripts/export_openapi.py`** (API-01) — lifespan-safe экспорт. Скрипт зовёт `create_app().openapi()` без входа в `combined_lifespan` (DB/Redis startup НЕ выполняется по построению). Запускается с `ENVIRONMENT=dev` (см. D-04) → prod-assertion на `cookie_secure` (Phase 4 D-25) не срабатывает. Output — `apps/backend/openapi.json` через `json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False)` + trailing newline для байт-стабильности macOS↔Linux.

2. **CI workflow `.github/workflows/ci.yml`** (API-02 + API-07) — единственный workflow, заводимый Phase 9. Триггеры: `pull_request` (любая ветка) + `push` to `main`. Два job:
   - `backend` — uv + Python 3.12, `uv sync`, ruff + mypy + import-linter, затем `uv run python -m scripts.export_openapi` + `git diff --exit-code apps/backend/openapi.json`. Pytest и реальная Postgres — **out of scope для Phase 9 CI** (см. Deferred); сейчас только drift-gate, чтобы не растить scope.
   - `frontend` — pnpm + Node 20, `pnpm install`, eslint + `tsc -b` + vitest, затем `pnpm --filter @sportzal/api-client codegen` + `git diff --exit-code packages/api-client/src/schema.d.ts`. Зависит от backend job (нужен свежий openapi.json — actions/checkout достаточно, поскольку в репо уже лежит регенерированный backend job'ом артефакт через download/upload — простейший вариант: оба job'а делают свой checkout и frontend полагается на закоммиченный `openapi.json`).

3. **`packages/api-client/`** — placeholder `package.json` обрастает реальной структурой:
   - devDep: `openapi-typescript@^7.13.0` (API-05).
   - `src/fetcher.ts` (~80 LOC) — `request<P, M>(method, path, init)` с `credentials: 'include'`, X-CSRF-Token injection (D-A4), single-flight `/auth/refresh` (D-A1..D-A3), типизированный `ApiError`.
   - `src/errors.ts` — `ApiError` class (`{code, message, fields?}` matching backend `AppError` shape).
   - `src/index.ts` — публичный re-export: `request`, `ApiError`, `type paths`, `type components`.
   - `src/schema.d.ts` — генерируется `openapi-typescript` из `apps/backend/openapi.json`. **Закоммичен в git** (см. D-05 — отступление от REQUIREMENTS-формулировки 'gitignored').
   - `package.json` scripts: `codegen` (`openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts`), `typecheck` (`tsc --noEmit`).

4. **admin-web hookup** — Phase 9 НЕ wires `apps/admin-web/src/shared/api/services/http/*` (это Phase 10 FE-01). Phase 9 только публикует пакет в pnpm workspace и убеждается, что `import { request, ApiError } from '@sportzal/api-client'` работает (тип-чеком). Чтобы `predev` всегда регенерировал типы — добавить `predev: pnpm --filter @sportzal/api-client codegen` в `apps/admin-web/package.json` (D-05).

**In scope (Phase 9 REQ-IDs):** API-01, API-02, API-05, API-06, API-07.

**Out of scope (deferred):**
- Wiring `http/auth.ts` + `http/clients.ts` в admin-web — Phase 10 (FE-01).
- /login UI с двумя tab'ами — Phase 10 (FE-02).
- ESLint rule "ban raw fetch( outside packages/api-client" — Phase 10 (FE-07).
- Backend pytest в CI с Postgres-сервисом — отдельный backlog item (premature: SAVEPOINT-фикстура и так покрывается локально через docker-compose).
- Backend security scan / SAST в CI — backlog.
- packages/api-client publish to npm — никогда (private monorepo package).

</domain>

<decisions>
## Implementation Decisions

### Refresh-failure UX contract (User-discussed)

- **D-A1 [LOCKED]:** **Synthetic `ApiError {code: 'session_expired'}` при провале single-flight `/auth/refresh`.** Это синтетический client-side код — сервер его никогда не возвращает. Любой исход refresh'а кроме 2xx (4xx, 5xx, network fail, JSON parse fail, timeout) → fetcher бросает `new ApiError('session_expired', 'Session expired, please log in again.', undefined)`. Phase 10 ловит этот код в QueryClient `onError` или router error boundary и редиректит в `/login?next=<encoded>`. Server-issued коды (`invalid_credentials`, `forbidden`, `csrf_mismatch`, `family_reuse_detected` и т.д.) пробрасываются pass-through (D-A3).

- **D-A2 [LOCKED]:** **Fetcher — pure transport; admin-web владеет редиректом.** packages/api-client НЕ импортирует `@tanstack/react-router`, НЕ читает/пишет `window.location`, НЕ знает про `/login` URL. На `session_expired` fetcher только бросает; FE-05 redirect-логика (`one-shot module flag`, `next=<encoded>` query, `redirect-back-after-login`) живёт исключительно в `apps/admin-web/src/features/auth/*` и подвешивается через QueryClient global `onError` или router error boundary в Phase 10. Это сохраняет packages/api-client framework-agnostic и unit-тестируемым в jsdom без mock'ов location/router.

- **D-A3 [LOCKED]:** **401 от `/auth/*` (refresh skipped path) — pass-through server-кода.** Endpoints: `/auth/login`, `/auth/refresh`, `/auth/me`, `/auth/logout`, `/auth/logout-all`, `/auth/telegram/start`, `/auth/telegram/status`, `/auth/telegram/verify`. Для всех — fetcher НЕ запускает refresh, читает JSON body и строит `new ApiError(server.code, server.message, server.fields)` вербатим. Phase 10 на `/login` form ловит `code === 'invalid_credentials'` и показывает inline-ошибку; на `/auth/me` 401 при boot — Phase 10 решает (вероятно, рендерит публичный `/login`, не редиректит). Никакой синтетической перемаппинговой логики в fetcher для `/auth/*`. Edge-case `/auth/refresh` 401 ВНУТРИ single-flight уже покрыт D-A1 (там session_expired); прямой call `/auth/refresh` извне single-flight (Phase 10 этого не делает) тоже идёт pass-through — server вернёт `family_reuse_detected` или `refresh_expired`, fetcher просто пробрасывает.

- **D-A4 [LOCKED]:** **Single-flight semantics — стандартная pattern с module-scoped Promise.**
  - При первом 401 (на не-`/auth/*` path) fetcher проверяет `inFlightRefresh: Promise<void> | null`. Если null — стартует `inFlightRefresh = fetch('/api/v1/auth/refresh', {method:'POST', credentials:'include'})`. Все последующие 401-ретраи во время `inFlightRefresh != null` await'ят тот же promise.
  - Если refresh 2xx — все ожидающие callers retry-ят свой original запрос **ровно один раз**. Если retry опять даёт 401 → throw `session_expired` БЕЗ повторного refresh-цикла (защита от бесконечных лупов; D-A4-rule "max 1 refresh per failed call").
  - Если refresh non-2xx (включая network fail) — все ожидающие callers throw `session_expired` (D-A1).
  - `inFlightRefresh` сбрасывается в null в `.finally()` после завершения refresh (success или fail).
  - Реализация: module-scoped `let inFlightRefresh: Promise<Response> | null = null` в `fetcher.ts`. Никаких ContextVar-magic, никаких Subject/EventEmitter — обычный shared promise.

### CI workflow scope & layout (Discretion — recommended)

- **D-01 (Discretion):** **Один файл `.github/workflows/ci.yml` с двумя job'ами `backend` и `frontend`.** Триггеры — `pull_request` (любая base ветка) + `push` к `main`. Параллельные job'ы (нет dependency между ними — каждый делает свой `actions/checkout`). Branch protection (required checks для main) — настройка вне scope Phase 9, но workflow готов это поддержать. Альтернатива (отдельные `backend-ci.yml` + `frontend-ci.yml`) отвергнута: один файл проще ревьюить, общая `concurrency`-группа предотвращает дубль-runs на пуш-в-PR.

- **D-02 (Discretion):** **Phase 9 CI = только drift-gates + статика (lint/typecheck/unit).** Backend job runs: `uv sync` → `ruff check` → `ruff format --check` → `mypy` → `lint-imports` → `uv run python -m scripts.export_openapi` → `git diff --exit-code apps/backend/openapi.json`. Frontend job: `pnpm install --frozen-lockfile` → `pnpm -r lint` → `pnpm -r typecheck` → `pnpm -r test` → `pnpm --filter @sportzal/api-client codegen` → `git diff --exit-code packages/api-client/src/schema.d.ts`. **Pytest интеграционный против реальной Postgres — НЕ в Phase 9 CI** (требует services-контейнера, scope-blow для phase под "OpenAPI pipeline"). Backlog item.

- **D-03 (Discretion):** **`concurrency: group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: true`** — на push в открытый PR старый run отменяется. Спасает от фейков очередей на активных PR.

### OpenAPI export script (Discretion — recommended)

- **D-04 (Discretion):** **`os.environ.setdefault('ENVIRONMENT', 'dev')` ПЕРЕД `from app.main import create_app`.** Скрипт `scripts/export_openapi.py` начинается с этой строки до любого импорта `app.*`, чтобы prod-assertion `assert settings.cookie_secure` (Phase 4 D-25) в `create_app()` не сработал. `ENVIRONMENT=dev` в settings даёт `cookie_secure=False` по умолчанию — assertion пропускается. Альтернатива (добавить `bypass_prod_assertion: bool` параметр в `create_app`) отвергнута: расширение API factory ради CI-скрипта — over-engineering. Альтернатива (запускать с `ENVIRONMENT=prod` + `COOKIE_SECURE=true` через env) тоже сработает, но менее очевидна для разработчика, бегущего скрипт локально.

- **D-05 (Discretion):** **Lifespan не входим вообще — `create_app().openapi()` напрямую.** FastAPI `combined_lifespan` (`db_lifespan` + `redis_lifespan`) выполняется только когда приложение реально стартует через ASGI — `app.openapi()` это lazy property, она не триггерит lifespan по построению. Не нужно ни `with TestClient(app)` (он бы запустил lifespan), ни ASGITransport. Просто `spec = create_app().openapi(); pathlib.Path('apps/backend/openapi.json').write_text(json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + '\n', encoding='utf-8')`. Постнагрузочный sanity-check: `assert 'paths' in spec` чтобы скрипт упал быстро если FastAPI вернул что-то неожиданное.

- **D-06 (Discretion):** **Servers/title/version sanitation НЕ нужна в v1.1.** FastAPI `app.openapi()` детерминирован по `app.title`, `app.version`, `app.servers` — все они задаются в `create_app()` и не зависят от platform. `json.dumps(..., sort_keys=True, ensure_ascii=False)` гарантирует стабильность ключей (alphabetical) и unicode-output. Если в будущем drift-gate начнёт false-positive'ить из-за platform-specifics (например, путь к Python в `description`) — добавить normalization-step. Сейчас premature.

### Codegen ergonomics & DX (Discretion — recommended)

- **D-07 (Discretion):** **`packages/api-client/src/schema.d.ts` КОММИТИТСЯ в git** (отступление от REQUIREMENTS API-05 формулировки 'gitignored locally'). Причина: API-07 требует `git diff --exit-code` после `pnpm codegen` — это работает только если файл tracked. Если оставить gitignored — drift-gate вакуумен (untracked files не показываются в `git diff` без `git add -N`). Закоммитить — единственный способ дать API-07 реальный смысл. Plan-фаза должна явно отметить расхождение с REQUIREMENTS.md и получить апрув; либо обновить REQUIREMENTS API-05 строкой 'committed' вместо 'gitignored'. **Recommended: коммитим**.

- **D-08 (Discretion):** **`pnpm codegen` в `packages/api-client` — manual + `predev` hook в admin-web.** В `apps/admin-web/package.json`: `"predev": "pnpm --filter @sportzal/api-client codegen"`. Локальный `pnpm dev` всегда регенерирует types перед стартом Vite — разработчик не забывает. **NO `postinstall`** хук — медленные installs, surprise side effects на CI/Docker. NO `prebuild` тоже — build-pipeline в админке ничего не знает про OpenAPI.

- **D-09 (Discretion):** **Fetcher импортирует types relative path: `import type { paths } from './schema'`.** TypeScript разрешит `./schema` → `./schema.d.ts`. tsconfig в packages/api-client настраивает `composite: true` + `declaration: true` чтобы admin-web (через workspace import) получил публичные типы. Если schema.d.ts отсутствует у нового разработчика (первый clone) → `pnpm install` в корне → `pnpm --filter @sportzal/api-client codegen` (можно добавить в README ROOT'а). Альтернатива (postinstall) отвергнута за побочки на CI.

### fetcher.ts surface + CSRF policy (Discretion — recommended)

- **D-10 (Discretion):** **Public surface: только generic `request<P extends keyof paths, M extends keyof paths[P]>(method: M, path: P, init?: RequestInit & {body?, params?}): Promise<...>` + `ApiError` class + types re-export.** NO convenience-обёртки `get`/`post`/`patch`/`del` — добавляют ~20 LOC к ~80 LOC бюджету (API-06), не дают реальной economy для админки (5 service-files, каждый зовёт `request('POST', '/clients', {body})` напрямую). Если в Phase 10 окажется громоздко — добавим в backlog. **`packages/api-client/src/index.ts`** экспортирует: `request`, `ApiError`, `type paths`, `type components`.

- **D-11 (Discretion):** **X-CSRF-Token инжектится только на mutating methods (POST/PATCH/PUT/DELETE).** Логика `if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS')` — match с server-side `verify_csrf` short-circuit (Phase 6 D-07). Cookie парсится через простой `document.cookie.split(';').find(c => c.trim().startsWith('sportzal_csrf='))?.split('=')[1]`. **Если cookie отсутствует на mutating call** — fetcher всё равно отправляет request без header'а; server вернёт 403 `csrf_mismatch` через AppError handler — fetcher замапит это в `ApiError {code:'csrf_mismatch'}` через стандартный error path. Phase 10 в редком случае логаута-без-логина может увидеть это; стандартный flow (login → CSRF cookie выставлен) исключает edge case. Альтернатива (client-side throw 'no_csrf_cookie' до request) отвергнута: дублирует серверную проверку, добавляет код, может рассинхронизироваться.

- **D-12 (Discretion):** **`ApiError` shape mirror'ит backend `AppError`:** `class ApiError extends Error { constructor(public code: string, public message: string, public fields?: Record<string, unknown>) { super(message); this.name = 'ApiError'; } }`. На non-2xx response fetcher: try { body = await res.json() } catch { body = {code: 'unknown_error', message: res.statusText} }; throw new ApiError(body.code ?? 'unknown_error', body.message ?? '', body.fields). Network fail (fetch reject) → `throw new ApiError('network_error', err.message)`. Это не покрывает D-A1's session_expired path — там explicit throw из refresh-failure ветки.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specs
- `CLAUDE.md` — backend stack lock; pnpm + Node 20 frontend tooling; `httpx ASGITransport` testing rule (НЕ применяется в Phase 9 — нет network тестов).
- `apps/admin-web/CLAUDE.md` — frontend conventions; layered import boundary; `VITE_API_MODE` chokepoint (Phase 9 НЕ трогает — Phase 10 будет менять).
- `.planning/PROJECT.md` — milestone scope; `core ⊥ modules` invariant; Out of Scope (no FE-09 поломок, никакой реальной API логики в `packages/api-client` сверх transport).
- `.planning/REQUIREMENTS.md` — Phase 9 owns: `API-01`, `API-02`, `API-05`, `API-06`, `API-07`. **Внимание planner'а: API-05 формулировка 'gitignored' конфликтует с API-07 drift-gate. См. D-07 Discretion-decision и обнови REQUIREMENTS либо отбей решение.**
- `.planning/ROADMAP.md` Phase 9 section — goal + 4 success criteria (lifespan-safe export, drift-gate openapi.json, drift-gate schema.d.ts, fetcher single-flight + typed ApiError).

### Cross-phase context (load-bearing)
- `.planning/phases/04-auth-foundations-cookie-rbac-primitives/04-CONTEXT.md` — D-09..D-13 (ContractModel + ResponseEnvelope[T] camelCase wire format — fetcher должен распарсить `{data: T}` для success); D-26 (`sportzal_csrf` cookie attributes: non-httpOnly, SameSite=Lax, Secure env-driven); D-25 (prod-assertion на cookie_secure — фактор для D-04 export-script env override).
- `.planning/phases/05-user-schema-email-password-auth/05-CONTEXT.md` — `/auth/login` 401 returns `code:'invalid_credentials'` (AUTH-EP-02) — pass-through через D-A3.
- `.planning/phases/06-rbac-wiring-parity-tests/06-CONTEXT.md` — D-04 (`verify_csrf` на mutating routes; safe-method short-circuit подтверждает D-11 client policy); D-09 (CSRF exempt list `/auth/login`, `/auth/refresh`, `/auth/telegram/*` — клиентский D-A3 списком path'ов); error code `csrf_mismatch` (для D-12 mapping).
- `.planning/phases/07-telegram-otp-channel/07-CONTEXT.md` — `/auth/telegram/*` endpoints — pass-through через D-A3.
- `.planning/phases/08-clients-module-audit-log/08-CONTEXT.md` — D-04 audit event таблица содержит `login_success`/`session_revoked` etc; не влияет на Phase 9 кроме того, что fetcher НЕ инициирует audit-events напрямую (это server-side).

### Source files Phase 9 directly creates or mutates
- `apps/backend/scripts/export_openapi.py` — NEW (API-01, D-04, D-05, D-06).
- `apps/backend/app/main.py` — *возможно* нужен `app.title` / `app.version` явный (если ещё не задан) для byte-stability (D-06). Planner проверит.
- `.github/workflows/ci.yml` — NEW (API-02, API-07, D-01, D-02, D-03).
- `packages/api-client/package.json` — расширение из placeholder: dependencies (нет — только devDeps), devDeps `openapi-typescript@^7.13.0` + `typescript`; scripts `codegen` + `typecheck`.
- `packages/api-client/tsconfig.json` — NEW. composite + declaration + strict.
- `packages/api-client/src/index.ts` — NEW. re-export `request`, `ApiError`, `type paths`, `type components`.
- `packages/api-client/src/fetcher.ts` — NEW (~80 LOC; API-06; D-A1..D-A4, D-10..D-12).
- `packages/api-client/src/errors.ts` — NEW. `ApiError` class (D-12).
- `packages/api-client/src/schema.d.ts` — NEW (generated from openapi.json; **committed to git** per D-07).
- `packages/api-client/.gitignore` — НЕ добавляем `schema.d.ts` сюда (D-07).
- `packages/api-client/README.md` — обновить с реальным usage примером.
- `apps/admin-web/package.json` — добавить `"predev": "pnpm --filter @sportzal/api-client codegen"` (D-08).
- `apps/admin-web/package.json` — добавить `@sportzal/api-client: 'workspace:*'` в dependencies (для будущего Phase 10 импорта).
- `apps/backend/openapi.json` — NEW (committed; result of first export-script run).
- `apps/backend/pyproject.toml` — *возможно* добавить `[tool.uv.dev-dependencies]` если export-script нужен dev-only deps (вероятно, ничего нового — script использует stdlib + FastAPI).

### External docs (consulted)
- `openapi-typescript` v7 docs — CLI usage `openapi-typescript ./input.json --output ./output.d.ts`; output schema (`paths` + `components`); встроенный type-helper `paths['/clients']['get']['responses']['200']['content']['application/json']`.
- FastAPI OpenAPI customization docs — `app.openapi()` returns dict; `app.openapi_schema` cache; `app.title` / `app.version` — fields в output.
- GitHub Actions docs — `setup-uv@v3` (astral-sh action), `pnpm/action-setup@v3`, `actions/setup-node@v4` с `cache: 'pnpm'`.
- pnpm workspace protocol — `workspace:*` dependency для package consumed in monorepo.
- Pydantic v2 ContractModel + camelCase wire — Phase 4 D-09 (внутренний контекст).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/backend/app/main.py:create_app()` — фабрика; `.openapi()` lazy property не входит в lifespan.
- `apps/backend/app/core/config.py:Settings.environment` — Literal['dev', 'staging', 'prod'] = 'dev'; D-04 setdefault'ит env var.
- `apps/backend/app/core/schemas.py:ContractModel` (Phase 4 D-09) — все request/response модели наследуют → camelCase wire — openapi.json содержит camelCase ключи автоматически.
- `apps/backend/app/core/exceptions.py:AppError` + `_app_error_handler` (Phase 2 D-12) — server-side error envelope `{code, message, fields?}` — fetcher D-12 ApiError mirror'ит этот контракт.
- `apps/backend/app/core/pagination.py:PaginatedData[T]` (Phase 4 D-10) — generic в openapi.json превращается в discrete schema per concrete `T`; openapi-typescript генерирует corresponding TS type.
- `apps/admin-web/src/shared/api/services/index.ts` — swap seam (Phase 1); Phase 9 НЕ трогает; Phase 10 заполнит `./http/*` через `@sportzal/api-client`.
- `apps/admin-web/src/shared/api/config/env.ts:API_MODE` — chokepoint для VITE_API_MODE; Phase 9 не использует.
- `pnpm-workspace.yaml` — `apps/*` + `packages/*`; `@sportzal/api-client` уже в workspace, не нужно регистрировать.

### Established patterns to honor
- **Phase 1 placeholder rule** (CLAUDE.md): `packages/ui` + `packages/api-client` — только package.json + README в Phase 1. **Phase 9 НАРУШАЕТ это разрешённо** — это первый раз, когда api-client получает реальный код. Tooling (ruff/mypy/eslint) уже установлен с Phase A; никаких дополнительных пермишенов не нужно.
- **camelCase wire / snake_case Python** (Phase 4 D-09) — openapi.json содержит camelCase property names; openapi-typescript генерит camelCase TS-типы (D-12 ApiError fields сохраняет sever-key shape).
- **`AppError → JSONResponse` handler** (Phase 2 D-12) — server-side error envelope; fetcher D-12 раскручивает обратно.
- **Module-level functions, не классы** — но `ApiError` это class (extends Error) — стандарт TS error-hierarchy, не нарушение.
- **Russian-narrative + English-code** (Phase 3 D-05) — PLAN.md narrative по-русски, код англ.
- **`tsconfig.json` strict + composite** (Phase 1 + admin-web tsconfig) — packages/api-client копирует pattern.
- **No `console.log` in prod code** (frontend conventions) — fetcher не логирует.

### Integration points
- **Phase 4 (shipped) — `sportzal_csrf` cookie выставляется при /auth/login + refresh + OTP-verify** (D-26). Fetcher читает её через `document.cookie` (D-11). non-httpOnly — это намеренная архитектура, фронт ОБЯЗАН читать.
- **Phase 5/6/7/8 — все routes уже в FastAPI app**; export-script автоматически захватит. ContractModel→camelCase →openapi.json пайплайн уже работает.
- **Phase 6 (shipped) — `verify_csrf` server-side**; D-11 client mirror. CSRF exempt list `/auth/login`, `/auth/refresh`, `/auth/telegram/*` — D-A3 path-list клиента.
- **Phase 10 (forthcoming) — admin-web `http/*` services будут импортить `request` + `ApiError` через `import { request, ApiError } from '@sportzal/api-client'`.** Phase 9 публикует API; Phase 10 потребляет. QueryClient global `onError` hook + router error boundary в Phase 10 ловят `ApiError {code: 'session_expired'}` и редиректят (D-A2).

</code_context>

<specifics>
## Specific Ideas

- **`session_expired` — синтетический client-side код** (D-A1). Сервер его не возвращает; это маркер от fetcher'а Phase 10'у "session lost после refresh failure, нужен redirect". Любая другая 401-ошибка идёт pass-through как server-issued (D-A3).

- **Fetcher НЕ редиректит — admin-web редиректит** (D-A2). packages/api-client остаётся framework-agnostic. Redirect-логика (`next=` query, one-shot module flag, redirect-back-after-login per FE-05) живёт в Phase 10's QueryClient `onError` или router error boundary.

- **Single-flight через module-scoped `Promise<void> | null`** (D-A4). Никаких subjects/event-emitter'ов. Простая shared promise. Reset в `.finally()`. Max-1-refresh-per-call защита от лупов.

- **`schema.d.ts` коммитится в git** (D-07) — несмотря на REQUIREMENTS API-05 'gitignored'. Без commit'а API-07 drift-gate бессмыслен. Planner должен явно поднять это решение (либо обновить REQUIREMENTS, либо переоформить API-07 как нечто другое).

- **`predev` hook в admin-web регенерирует types** (D-08) — `pnpm dev` в admin-web всегда сначала зовёт `pnpm --filter @sportzal/api-client codegen`. Защита от 'забыл регенерировать локально'.

- **`ENVIRONMENT=dev` setdefault до import'а app** (D-04) — обходит prod-assertion в `create_app()` без модификации фабрики. Один импорт-порядок-чувствительный момент в скрипте.

- **CI = только статика + drift-gates** (D-02) — pytest + Postgres-services НЕ Phase 9. Защита от scope-creep'а.

- **Один workflow `ci.yml` с двумя параллельными job'ами** (D-01) — простой ревью, общая `concurrency`-группа (D-03).

</specifics>

<deferred>
## Deferred Ideas

- **Backend pytest integration в CI** — нужен Postgres+Redis services-контейнер, fixtures setup, longer runtime. Backlog. Текущая локальная docker-compose разработка покрывает unit + integration через SAVEPOINT-фикстуру (Phase 5 D-22).

- **Frontend Playwright/E2E** — не сейчас. Phase 10 ставит первый http-mode прототип; E2E приходит после.

- **Backend SAST / security scan (bandit / ruff-security)** — backlog.

- **CodeQL / dependency vulnerability scan** — backlog.

- **API contract tests (Schemathesis / Dredd)** — backlog. Phase 9 dropping schema drift gate уже большой шаг; contract-driven property-based testing — v1.2+.

- **`packages/api-client` — добавить convenience-функции `get<P>(path)` / `post<P>(path, body)` etc** (D-10) — backlog. Если Phase 10 покажет, что raw `request('POST', ...)` громоздко — добавим в v1.2.

- **CSRF rotation на каждый refresh** — Phase 4 D-26 уже фиксирует регенерацию на login/refresh/OTP-verify. Fetcher НЕ кэширует csrf токен — читает cookie на каждый request (D-11). Если профайлинг покажет cost — backlog.

- **Network-error retry/backoff** — fetcher НЕ ретраит `network_error`. Идемпотентные GET'ы — TanStack Query будет ретраить (Phase 10 настроит). Mutations — пользователь ретраит руками. Auto-retry для mutations опасно (idempotency keys нужны).

- **OpenAPI `servers` field customization для prod docs** — Phase 9 оставляет default из FastAPI. v1.2+.

- **Workflow caching strategy refinements** — `setup-uv@v3` и `actions/setup-node@v4` дают basic кэширование; tuning (pnpm store mount, uv cache mount) — backlog.

- **Branch protection rule на `main`** — настройка GitHub UI/Settings вне scope Phase 9. Workflow готов поддержать.

- **`packages/ui` Phase A placeholder остаётся placeholder'ом** — Phase 9 не трогает. v2 milestone.

- **`packages/api-client` publish to npm** — нет, private monorepo package навсегда.

</deferred>

---

*Phase: 09-openapi-pipeline-api-client*
*Context gathered: 2026-05-03*
