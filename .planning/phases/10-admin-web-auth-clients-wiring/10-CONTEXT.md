# Phase 10: admin-web Auth + Clients Wiring - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 10 закрывает цикл "frontend ↔ backend" для **двух доменов** — `auth` и `clients` — и **только для них**. Все остальные домены (`memberships`, `billing`, `schedule`, `staff`, `finance`, `settings`) продолжают идти через mock-сервисы без регрессий.

**Что должно появиться к концу Phase 10:**

1. **`apps/admin-web/src/features/auth/`** — `/login` route (standalone, **без AppShell**) с двумя tab'ами (email/password и Telegram OTP); поддерживает single-flight refresh + redirect-back через `?next=` (FE-02, FE-05).
2. **`apps/admin-web/src/features/clients/`** — `/clients` route (single page, list + dialog-формы) c URL-driven search/pagination (`?q=&page=&pageSize=`) через TanStack Router `validateSearch` + Zod; CRUD c оптимистичными мутациями + rollback через `clientsKeys` factory (FE-04).
3. **`apps/admin-web/src/shared/api/services/http/{auth,clients}.ts`** — реализуют existing service contracts через `@sportzal/api-client.request<paths,methods>` (FE-01).
4. **`apps/admin-web/src/shared/api/services/mock/{auth,clients}.ts`** — **полные** mock-имплементации тех же contract'ов по конвенциям CLAUDE.md (faker.seed=42, 120-300мс латентность, RBAC enforcement, versioned localStorage) — чтобы SC#3 'no regression в mock-mode' был честным (FE-03).
5. **`apps/admin-web/src/shared/api/contracts/{auth,clients}.ts`** — transport-agnostic contracts: `AuthService`, `ClientsService` с `Pagination<T>`, branded `ClientId` (UUIDv4), Zod-схемы переиспользуются формами и mock-валидацией.
6. **Глобальный `session_expired` handler** — `QueryClient` с `queryCache + mutationCache` `onError`; module-flag в redirect-helper гарантирует single-flight `router.navigate({to:'/login', search:{next:...}})` (FE-05). Logout — пункт в существующем `ProfileMenu`, один клик без confirm, очищает `queryClient.clear()` + редирект на `/login` (FE-06).
7. **ESLint rule** запрещающий `fetch(` вне `packages/api-client/src/` и `apps/admin-web/src/shared/api/services/http/`; negative-test fixture (FE-07).
8. **`VITE_API_MODE=http`** становится валидным runtime-режимом (раньше только type-checked) — chokepoint в `apps/admin-web/src/shared/api/config/env.ts` уже готов из Phase 1.
9. **ReUI registry установлен и используется** — `apps/admin-web/components.json` сконфигурирован с `@reui` namespace + `style: 'base-nova'` (D-13/D-14); selected primitives + `DataGrid` + `InputOTP` установлены через `pnpm dlx shadcn add @reui/<name>` (D-16); Sidebar и AppShell не мигрируются (D-15); прочие неиспользуемые в Phase 10 примитивы — не мигрируются (D-17).

**В scope (Phase 10 REQ-IDs):** FE-01, FE-02, FE-03, FE-04, FE-05, FE-06, FE-07.

**Out of scope (deferred):**
- Detail-route `/clients/$id` + tabs (memberships/visits/billing) — v1.2+ когда соответствующие домены появятся.
- Logout-all-sessions UI — бэк (`POST /auth/logout-all`, AUTH-LO-04) готов с Phase 5; surface в UI откладываем до v1.2+.
- HTTP-mode wiring для остальных доменов (`memberships`, `billing`, `schedule`, ...) — каждый домен подключаем когда соответствующий бэк-модуль появится (v1.2+).
- Switch-account UX на /login для shared workstation — пет-проект на 1 зал, не нужен.
- Remember last-used auth tab в localStorage — текущий пользователь — соло-разработчик; деферрим.
- Multi-tab synchronization (BroadcastChannel) для logout/session-expired — backlog.
- E2E тесты (Playwright) — v1.2+. Phase 10 покрывает unit (vitest) + integration через mock-services.
- /clients export CSV / bulk-actions / advanced filters (status/tag/segment) — v1.2+ (CLAUDE.md "Anti-features" prohibits в v1).

</domain>

<decisions>
## Implementation Decisions

### Login Route — layout, tabs, Telegram poll UX

- **D-01 [LOCKED]:** **`/login` рендерится standalone — без AppShell.** TanStack Router pathless layout-route разделяет дерево на `_public` (где `/login`) и `_protected` (где AppShell + все остальные routes). На /login не виден sidebar, не виден `RoleSwitcher` (mock-only dev affordance). Альтернатива (рендерить /login внутри AppShell) отвергнута: оператор увидит навигацию к недоступным разделам и dev-only RoleSwitcher до аутентификации.

- **D-02 [LOCKED]:** **Default tab — Email/password** (не Telegram). Это override проектной "Telegram-first" семантики (PROJECT.md). User explicitly выбрал email/password как открытый по умолчанию tab. Telegram tab остаётся доступным и функциональным — просто не дефолтный. Пользовательский tab-state не персистится.

- **D-03 [LOCKED]:** **Уже-залогиненный визит /login → silent redirect через `beforeLoad`.** Маршрут /login имеет `beforeLoad: ({context, search}) => { try { const me = await context.queryClient.ensureQueryData({queryKey: authKeys.me, queryFn: services.auth.me}); throw redirect({to: search.next ?? '/', replace: true}) } catch (e) { /* if 401 → render /login */ } }`. Никаких "switch account" экранов.

- **D-04 [LOCKED]:** **Telegram-tab poll: 3с cadence, 5мин idle timeout, кнопка "Refresh deep link" после timeout.** `useQuery({queryKey: authKeys.telegramStatus(token), queryFn: services.auth.telegramStatus, refetchInterval: 3000, enabled: !timedOut})`. После 5мин (отсчитывается от первого start, не сбрасывается) — `enabled=false`, UI меняет состояние на "Срок действия ссылки истёк" + кнопка `/auth/telegram/start` заново. Когда `bound: true` — polling останавливается, появляется поле для 6-значного кода → `POST /auth/telegram/verify`.

### Session Lifecycle — boot, /auth/me, 401, logout

- **D-05 [LOCKED]:** **Source of truth для пользователя в http-mode = TanStack Query `authKeys.me`.** `useQuery({queryKey: authKeys.me, queryFn: services.auth.me, staleTime: 30_000, retry: false})`. Cache `getQueryData(authKeys.me)` — то, что router/`can()`/RoleGate читают через адаптер. `useSessionStore` Zustand остаётся mock-only (используется RoleSwitcher в dev'е); в http-mode session-store не активен. Адаптер `getSession()` в `router.ts` определяется по `API_MODE`: в `mock` берёт из `useSessionStore.getState()`, в `http` — из `queryClient.getQueryData(authKeys.me)`. Альтернатива (расширить useSessionStore до {user, role}) отвергнута: два источника правды, риск stale role при server-side смене.

- **D-06 [LOCKED]:** **Boot UX в http-mode — splash до первого ответа `/auth/me`.** `apps/admin-web/src/app/main.tsx` блокирует render `<RouterProvider>` через `await queryClient.ensureQueryData({queryKey: authKeys.me, queryFn: services.auth.me, retry: false})` (catch — продолжаем; router beforeLoad сам разрулит). Splash = простой centered logo + "Загрузка..." — без AppShell. Цена: ~150-300мс RTT перед первым рендером. Выгода: ноль "flash of wrong role" / ноль перекраски shell. В mock-mode — boot мгновенный (нет http-вызова), session-store rehydrates как сейчас.

- **D-07 [LOCKED]:** **`session_expired` ловится в QueryClient global onError + module-flag.** `apps/admin-web/src/app/queryClient.ts` создаёт `new QueryClient` с `queryCache: new QueryCache({onError: handleApiError})` и `mutationCache: new MutationCache({onError: handleApiError})`. `handleApiError` в `apps/admin-web/src/features/auth/redirect-on-session-expired.ts` имеет module-scoped `let redirecting = false`; на `error instanceof ApiError && error.code === 'session_expired'` если `!redirecting` → `redirecting = true; queryClient.clear(); router.navigate({to:'/login', search:{next: encodeURIComponent(router.state.location.href)}, replace: true}).finally(() => { redirecting = false })`. Любые server-issued ошибки (`invalid_credentials`, `forbidden`, `csrf_mismatch` и т.д.) — pass-through, обрабатываются на месте (форма логина, RoleGate, etc.) per Phase 9 D-A3.

- **D-08 [LOCKED]:** **Logout — пункт в существующем `ProfileMenu` (`apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx`), один клик без confirm.** Handler: `await services.auth.logout(); queryClient.clear(); router.navigate({to:'/login', replace: true})`. Logout-all-sessions UI **отложен до v1.2+** (бэк готов с Phase 5 AUTH-LO-04). Без confirm-dialog — logout обратимое действие.

### Clients UX Scope — routes, формы, URL-state

- **D-09 [LOCKED]:** **Один маршрут `/clients`** — table + toolbar (search input + "Новый клиент" button) + pagination footer. Create/Edit формы — shadcn `Dialog` поверх таблицы. Detail-route `/clients/$id` **отложен до v1.2+** (когда появятся memberships/visits/billing tabs). Существующий placeholder `apps/admin-web/src/routes/clients.tsx` полностью заменяется.

- **D-10 [LOCKED]:** **Search/pagination state — URL-driven через TanStack Router `validateSearch` + Zod.** `Route = createFileRoute('/clients')({validateSearch: z.object({q: z.string().optional(), page: z.number().int().min(1).default(1), pageSize: z.number().int().min(10).max(100).default(20)}).parse, loader: ({context, deps: {search}}) => context.queryClient.ensureQueryData({queryKey: clientsKeys.list(search), queryFn: () => services.clients.list(search)}), loaderDeps: ({search}) => ({search})})`. Search-input `onChange` → `navigate({search: prev => ({...prev, q: value, page: 1})})`. Reload сохраняет состояние, URL shareable, browser back/forward работают.

- **D-11 [LOCKED]:** **Owner-only delete UX — shadcn `AlertDialog` confirm + `RoleGate` скрывает кнопку для reception.** В row-actions (`@tanstack/react-table` actions cell): `<RoleGate action="delete" resource="clients"><Button variant="ghost" onClick={() => setDeletingId(client.id)}><Trash2/></Button></RoleGate>`. Confirm-dialog: "Удалить клиента {fullName}? Это soft-delete (бэк сохраняет запись), но клиент перестанет отображаться в списках". Optimistic update via `useMutation` `onMutate` (убираем из cached list) + `onError` rollback + `onSettled` invalidate. Reception для этой кнопки даже не видит DOM-узла (RoleGate возвращает null).

- **D-12 [LOCKED]:** **Mock parity — полные mock-имплементации auth + clients по конвенциям CLAUDE.md.**
  - `services.mock.clients`: faker.seed(42) → ~30 клиентов на boot; localStorage key `sportzal:mock:v1` (versioned, существующий ключ); 120-300мс латентность; ILIKE-поиск по `fullName + phone` через `String.includes` + lowercase; pagination с `{items, total, page, pageSize}`; CRUD с `DomainError {code: 'not_found' | 'validation_failed'}`; RBAC enforcement (`if (!can(role, 'delete', 'clients')) throw new DomainError({code: 'forbidden'})`).
  - `services.mock.auth`: hardcoded "fake user" с persisted role из `useSessionStore`; `me()` возвращает `{id: 'mock-owner-uuid', role: useSessionStore.getState().role, fullName: 'Owner Demo'}`; `login()` — no-op + 200мс задержка; `logout()` — no-op; `telegramStart/Status/Verify` — стейт-машина с timeoutами для realism.
  - `RoleSwitcher` (dev affordance) **продолжает работать в mock-mode** — переключает `useSessionStore.role`, `services.mock.auth.me()` следующий раз вернёт обновлённый role. В http-mode `RoleSwitcher` не виден (через `API_MODE === 'mock'` гард в компоненте).

### UI Component Source — ReUI Registry

- **D-13 [LOCKED]:** **ReUI (`https://reui.io/r/{style}/{name}.json`) становится primary UI component registry для `apps/admin-web`.** Конфигурируется через `apps/admin-web/components.json`:
  ```json
  {
    "style": "base-nova",
    "registries": {
      "@reui": "https://reui.io/r/{style}/{name}.json"
    }
  }
  ```
  Установка компонентов: `pnpm dlx shadcn add @reui/<name>` (с правами на запись в `apps/admin-web/src/shared/ui/`). Используем **Radix-варианты** ReUI (consistency с существующим shadcn-стеком на Radix). Это **не замена shadcn-CLI**, а namespaced registry поверх него.

- **D-14 [LOCKED]:** **Style switch `new-york` → `base-nova`.** Пользователь явно выбрал base-nova как новый default style. Последствие: визуальный сдвиг существующих shadcn-компонентов, переустановленных через ReUI. **AppShell layout-структура (header / Sidebar / main wrapper) остаётся**, но primitive-уровень обновится. Theme tokens в `src/app/index.css` `@theme` блоке могут потребовать корректировки под base-nova палитру; semantic-token convention (CLAUDE.md "raw palette banned") сохраняется.

- **D-15 [LOCKED]:** **Sidebar carve-out — у ReUI нет sidebar-компонента, существующий `apps/admin-web/src/shared/ui/app-shell/Sidebar.tsx` (и весь AppShell) НЕ мигрируется.** Sidebar остаётся на текущей реализации; Phase 10 не трогает его, кроме того что планировалось ранее (никаких изменений к Sidebar). Аналогично `RoleSwitcher`, `ProfileMenu` — остаются shadcn-based, Phase 10 модифицирует их по D-08 / D-12 без миграции на ReUI.

- **D-16 [LOCKED]:** **Phase 10 components, мигрируемые на ReUI:**
  - **`Button`, `Input`, `Form`, `Label`, `DropdownMenu`, `Dialog`, `AlertDialog`** — `pnpm dlx shadcn add @reui/<name>`; перезаписывают существующие файлы в `src/shared/ui/`.
  - **`DataGrid`** (ReUI in-house) → используется в `ClientsTable` для `/clients` вместо ручной разметки на `@tanstack/react-table`. ReUI DataGrid сам обёртка над `@tanstack/react-table` — keys factory, optimistic mutations и URL-driven search/pagination остаются (D-09, D-10) — DataGrid принимает `data`, `columns`, `pagination`, `state` props.
  - **`InputOTP`** (ReUI / shadcn primitive) → 6-значный код в `TelegramLoginTab` после `bound: true` (D-04). Заменяет ручную верификацию.
  - **Phone input** — если у ReUI есть `PhoneInput` / mask-input, используем; иначе остаётся в Claude's Discretion (см. ниже).
  - **`Toaster`** (Sonner-обёртка) — оставляем существующий (Sonner уже в стеке per CLAUDE.md); если ReUI предлагает свою — Claude discretion в planner'е.
  - **Splash** — нет в ReUI, остаётся ручной (D-06).

- **D-17 [LOCKED]:** **Migration scope в Phase 10 — только primitives, перечисленные в D-16, плюс DataGrid + InputOTP.** Остальные shadcn-компоненты в `src/shared/ui/` (`Card`, `Badge`, `Avatar`, `Tabs`, `Tooltip`, etc., если присутствуют) **в Phase 10 не мигрируются** — будут мигрированы по мере необходимости в последующих phase'ах (lazy migration). Это снижает blast-radius визуального change и держит Phase 10 в рамках "auth + clients wiring".

### Claude's Discretion

Пункты, которые planner свободен решать в рамках выше зафиксированного:
- Точная структура `features/auth/` и `features/clients/` (внутренний layout — components/, hooks/, model/, schema.ts, keys.ts) — следовать FSD-lite из CLAUDE.md.
- Имена branded ID типов (`type ClientId = Brand<string, 'ClientId'>`) и где живут — `entities/client/types.ts` или inline.
- Точный shape `clientsKeys` factory (рекомендация: `{all: ['clients'], lists: () => [...all, 'list'], list: (filter) => [...lists(), filter], details: () => [...all, 'detail'], detail: (id) => [...details(), id]}` per TkDodo).
- Фактический набор полей в `ClientForm` (минимум: `fullName`, `phone`; possibly `email`, `birthDate`, `notes` — что Phase 8 положил в `clients` таблицу).
- Phone input mask (`+7 (XXX) XXX-XX-XX`) — если ReUI предоставляет `PhoneInput`, использовать; иначе выбрать lib (react-imask, input-mask) или ручной regex.
- Search debounce (typically 300мс).
- DataGrid props (pageSize default, sortable columns, sticky header, density) — следовать ReUI defaults где возможно.
- Empty/loading/error state copy (Russian; per CLAUDE.md i18n).
- Splash component design (centered logo + spinner — детали).
- Theme token diff `new-york` → `base-nova` в `src/app/index.css` — корректировки под ReUI base-nova палитру при сохранении semantic-naming (background, foreground, primary, muted, etc.).
- Toaster — оставить текущий Sonner-based или взять ReUI-вариант, если предложит лучший UX.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning или implementing.**

### Project specs
- `CLAUDE.md` — backend stack lock; pnpm + Node 20 frontend; Frontend integrity rule (`apps/admin-web` — перенос ./frontend, правки структуры/моков требуют явного решения — Phase 10 явно их разрешает для auth+clients).
- `apps/admin-web/CLAUDE.md` — **load-bearing для Phase 10**: layered import boundary; swap seam через `services/index.ts` + `VITE_API_MODE` chokepoint; FSD-lite layout; branded UUIDv4 IDs; Money in minor units; one Zod schema per resource (form + mock validation); per-feature `xKeys` factory; `staleTime: 30_000`; route loader uses `queryClient.ensureQueryData`; semantic shadcn tokens; Russian-only UI; canonical templates (List = toolbar+filters+DataTable+pagination+three-state empty/loading/error).
- `.planning/PROJECT.md` — milestone scope; Out of Scope (без `apps/client-web`, без многоканальности); Russian user-facing language; Telegram primary channel.
- `.planning/REQUIREMENTS.md` — Phase 10 owns: `FE-01` (http services), `FE-02` (login route + tabs + telegram poll), `FE-03` (VITE_API_MODE=http only for /login + /clients), `FE-04` (clientsKeys + ensureQueryData + optimistic mutations), `FE-05` (single-flight refresh redirect + one-shot loop guard), `FE-06` (logout clears cache + redirect), `FE-07` (ESLint ban raw fetch).
- `.planning/ROADMAP.md` Phase 10 section — Goal + 5 Success Criteria.

### Cross-phase context (load-bearing)

- `.planning/phases/04-auth-foundations-cookie-rbac-primitives/04-CONTEXT.md` — D-09..D-13 ContractModel + ResponseEnvelope[T] camelCase wire (fetcher парсит `{data: T}`); D-26 `sportzal_csrf` cookie attributes; D-25 prod-assertion (не влияет на frontend); RBAC `Role`/`Action`/`Resource`/`OWNER_ONLY`/`can()` — параметры parity с `apps/admin-web/src/shared/session/can.ts`.
- `.planning/phases/05-user-schema-email-password-auth/05-CONTEXT.md` — `POST /auth/login` 200 → `{user:{id,role,fullName}}` + httpOnly cookies; 401 `invalid_credentials` (timing-equivalent); 6-я попытка → 429; `POST /auth/logout` (current); `POST /auth/logout-all` (AUTH-LO-04 — UI deferred); `GET /auth/me`.
- `.planning/phases/06-rbac-wiring-parity-tests/06-CONTEXT.md` — server-side `verify_csrf` — фронт (Phase 9 fetcher D-11) уже инжектит на mutating; CSRF exempt list совпадает с D-A3.
- `.planning/phases/07-telegram-otp-channel/07-CONTEXT.md` — `/auth/telegram/start` returns `{token, deepLink}`; `/auth/telegram/status?token=...` returns `{bound: bool, expiresAt}`; `/auth/telegram/verify` принимает `{token, code}` → set-cookies + `{user}` (тот же shape, что email-login). Token TTL — определит Phase 7 (важно для D-04 5мин timeout).
- `.planning/phases/08-clients-module-audit-log/08-CONTEXT.md` — `/api/v1/clients` endpoints + camelCase + paginated `{items,total,page,pageSize}`; ILIKE по `fullName + phone`; soft-delete (`deletedAt` column); audit-log пишется бэком (Phase 10 не вызывает audit-events напрямую).
- `.planning/phases/09-openapi-pipeline-api-client/09-CONTEXT.md` — **критично для Phase 10**: D-A1 (`session_expired` синтетический code); D-A2 (fetcher framework-agnostic, admin-web владеет редиректом); D-A3 (401 от `/auth/*` pass-through); D-A4 (single-flight refresh module-scoped Promise); D-10 (public surface = `request<P,M>` + `ApiError` + types); D-11 (CSRF auto-injection); D-12 (`ApiError {code, message, fields?}` shape mirrors backend `AppError`); D-08 (`predev` hook регенерирует types — admin-web уже имеет это).

### Source files Phase 10 directly creates or mutates

- `apps/admin-web/src/app/main.tsx` — UPDATE: добавить `await queryClient.ensureQueryData(authKeys.me)` (с retry: false) перед `<RouterProvider>` mount в http-mode (D-06).
- `apps/admin-web/src/app/queryClient.ts` — UPDATE: `queryCache: new QueryCache({onError: handleApiError})` + `mutationCache: new MutationCache({onError: handleApiError})` (D-07).
- `apps/admin-web/src/app/router.ts` — UPDATE: `getSession()` адаптер ветвится по `API_MODE` (D-05).
- `apps/admin-web/src/routes/__root.tsx` — UPDATE: возможно реорганизация под `_public` / `_protected` layout-routes (D-01).
- `apps/admin-web/src/routes/_public/login.tsx` (или аналогичный путь) — NEW (D-01, D-02, D-03, D-04, FE-02).
- `apps/admin-web/src/routes/clients.tsx` — REPLACE placeholder реальным route с `validateSearch` + `loader` (D-09, D-10).
- `apps/admin-web/src/features/auth/` — NEW directory: `api/keys.ts`, `api/hooks.ts`, `api/redirect-on-session-expired.ts` (D-07), `components/EmailLoginForm.tsx`, `components/TelegramLoginTab.tsx`, `model/schema.ts`, `index.ts`.
- `apps/admin-web/src/features/clients/` — NEW directory: `api/keys.ts` (clientsKeys factory), `api/hooks.ts` (useClientsList, useCreateClient, useUpdateClient, useDeleteClient — оптимистичные mutations), `components/ClientsTable.tsx`, `components/ClientForm.tsx`, `components/ClientDeleteDialog.tsx`, `model/schema.ts` (Zod), `index.ts`.
- `apps/admin-web/src/entities/client/` — NEW directory: `types.ts` (branded `ClientId`, `Client` domain type), `index.ts`.
- `apps/admin-web/src/shared/api/contracts/auth.ts` — NEW: `AuthService` interface + types.
- `apps/admin-web/src/shared/api/contracts/clients.ts` — NEW: `ClientsService` interface + types (включая `Pagination<T>`).
- `apps/admin-web/src/shared/api/contracts/index.ts` — UPDATE: re-export auth + clients contracts.
- `apps/admin-web/src/shared/api/services/http/auth.ts` — NEW (FE-01): wraps `request('POST', '/auth/login', ...)` etc.
- `apps/admin-web/src/shared/api/services/http/clients.ts` — NEW (FE-01): wraps `request('GET', '/api/v1/clients', ...)` etc.
- `apps/admin-web/src/shared/api/services/http/index.ts` — UPDATE: `export const services = {auth, clients} as const`.
- `apps/admin-web/src/shared/api/services/mock/auth.ts` — NEW (D-12, FE-03).
- `apps/admin-web/src/shared/api/services/mock/clients.ts` — NEW (D-12, FE-03): faker.seed=42 + localStorage `sportzal:mock:v1`.
- `apps/admin-web/src/shared/api/services/mock/index.ts` — UPDATE: `export const services = {auth, clients} as const`.
- `apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx` — UPDATE: добавить пункт "Logout" (D-08).
- `apps/admin-web/src/shared/ui/app-shell/RoleSwitcher.tsx` — UPDATE: гард `if (API_MODE !== 'mock') return null` (D-12).
- `apps/admin-web/src/shared/ui/splash.tsx` — NEW: centered logo + spinner (D-06).
- `apps/admin-web/eslint.config.js` — UPDATE: добавить `no-restricted-syntax` правило, банящее `CallExpression[callee.name='fetch']` outside allowed paths (FE-07).
- `apps/admin-web/src/test/__fixtures__/raw-fetch-leak.ts` — NEW: negative-test fixture доказывает что rule срабатывает (FE-07, по аналогии с существующими `api-mode-leak.ts`).
- `apps/admin-web/.env.example` / `apps/admin-web/.env.development` — UPDATE: документировать `VITE_API_MODE=http` как валидный режим.
- `apps/admin-web/package.json` — UPDATE: добавить `@sportzal/api-client: 'workspace:*'` в dependencies (если ещё не добавлено в Phase 9).
- **`apps/admin-web/components.json`** — UPDATE: переключить `style` на `base-nova`, добавить `registries: { "@reui": "https://reui.io/r/{style}/{name}.json" }` (D-13).
- **`apps/admin-web/src/app/index.css`** — UPDATE: ревизия `@theme` блока под палитру base-nova; semantic-token naming сохраняется (D-14).
- **`apps/admin-web/src/shared/ui/{button,input,form,label,dropdown-menu,dialog,alert-dialog}.tsx`** — REPLACE через `pnpm dlx shadcn add @reui/<name>` (D-16). Существующие файлы перезаписываются ReUI-вариантами.
- **`apps/admin-web/src/shared/ui/data-grid.tsx`** — NEW (`pnpm dlx shadcn add @reui/data-grid`) — для `ClientsTable`.
- **`apps/admin-web/src/shared/ui/input-otp.tsx`** — NEW (`pnpm dlx shadcn add @reui/input-otp`) — для Telegram OTP в `TelegramLoginTab`.

### External docs (consulted)
- TanStack Router docs — `createFileRoute` + `validateSearch` + `loader` + `loaderDeps` + pathless layout-routes (`_public.tsx`, `_protected.tsx`); typed search params; `redirect()` from `beforeLoad`.
- TanStack Query v5 docs — `QueryCache`/`MutationCache` `onError` hooks; `ensureQueryData`; optimistic mutations pattern (`onMutate`/`onError`/`onSettled`); query key factory pattern (TkDodo).
- **ReUI registry (`https://reui.io/r/{style}/{name}.json`)** — primary UI source per D-13. shadcn-CLI compatible; namespaced via `@reui` в `components.json`. Style: `base-nova` (D-14). Используем Radix-варианты компонентов.
- ReUI components в Phase 10: `Button`, `Input`, `Form`, `Label`, `DropdownMenu`, `Dialog`, `AlertDialog`, `DataGrid`, `InputOTP` (D-16).
- shadcn/ui (legacy primitives оставшиеся после миграции D-17) — `Sidebar` и AppShell-внутренние компоненты остаются на текущем shadcn-стеке.
- react-hook-form + Zod resolver — controlled forms with shared schema.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/admin-web/src/shared/api/services/index.ts` — swap seam (Phase 1, не трогать); просто заполнятся `./mock` и `./http` пустые containers.
- `apps/admin-web/src/shared/api/config/env.ts:API_MODE` — chokepoint для `VITE_API_MODE` (Phase 1, готов; runtime будет `'http'` валидным).
- `apps/admin-web/src/shared/session/can.ts:can()` + `OWNER_ONLY` frozenset — байт-эквивалентен бэкенду (Phase 4 D-04). Используется в RoleGate, mock-сервисах, route guards. Phase 10 продолжает использовать без изменений.
- `apps/admin-web/src/shared/session/RoleGate.tsx` — обёртка для action-guard'ов (D-11 использует для delete-кнопки).
- `apps/admin-web/src/shared/session/registry.ts:routeRegistry` — sidebar/router/tests source of truth (Phase 10 не трогает; добавит запись `/login` в **отдельный** registry или сделает /login special-cased).
- `apps/admin-web/src/shared/ui/app-shell/{Sidebar,ProfileMenu,RoleSwitcher,...}.tsx` — Phase 10 модифицирует ProfileMenu (добавить Logout, D-08) и RoleSwitcher (гард по API_MODE, D-12).
- `apps/admin-web/src/app/queryClient.ts` — существующий QueryClient (`staleTime: 30_000`, `refetchOnWindowFocus: false`); Phase 10 расширяет cache `onError` (D-07).
- `apps/admin-web/src/app/router.ts` — RouterContext с `queryClient` + `getSession()`; Phase 10 модифицирует `getSession()` ветвлением по API_MODE (D-05).
- `apps/admin-web/src/app/main.tsx` — bootstrap; Phase 10 добавляет `ensureQueryData(authKeys.me)` перед mount в http-mode (D-06).
- `packages/api-client/` (Phase 9) — `request<P,M>(method, path, init)` + `ApiError` + types — Phase 10 потребляет это API.
- `apps/admin-web/src/shared/i18n/ru.ts` — добавить ключи для login/clients UI copy (existing dict pattern).
- `apps/admin-web/src/shared/lib/cn.ts` + shadcn tokens — для всех style decisions (semantic only, raw palette banned).

### Established Patterns
- **Layered import boundary** (apps/admin-web/eslint.config.js + CLAUDE.md): UI → Query hook → services.X → {mock|http}. Components не импортируют `./mock` или `./http` напрямую — только через `services` swap seam.
- **`xKeys` factory pattern** (TkDodo): `clientsKeys` будет иметь `{all, lists, list(filter), details, detail(id)}` shape; используется ВСЮДУ (loader + hook + invalidate).
- **Optimistic mutations**: `onMutate` (snapshot + apply), `onError` (rollback из snapshot), `onSettled` (invalidate). Pattern из CLAUDE.md.
- **Zod schema reuse**: одна schema на resource, валидирует RHF форму И mock service input. Pattern из CLAUDE.md.
- **Pagination contract**: всегда `{items, total, page, pageSize}` (CLAUDE.md + Phase 8 backend). Никаких bare arrays.
- **DomainError vs ApiError**: mock-services throw `DomainError {code, message, fields?}`; `packages/api-client` throws `ApiError {code, message, fields?}`. Mirror shape, но **разные классы**. UI должен принимать оба (либо unified в Phase 10 helper, либо отдельно).
- **Russian-only**, semantic shadcn tokens, branded UUIDv4 IDs, ISO date strings, money в minor units.
- **Pathless layout-routes** в TanStack Router (admin-web/CLAUDE.md упоминает file-based routing) — для D-01 разделения public/protected.

### Integration Points
- **Phase 9 fetcher** уже бросает `ApiError {code: 'session_expired'}` при провале single-flight refresh — Phase 10 ловит в QueryClient onError (D-07).
- **Phase 4 `OWNER_ONLY`** frozenset — параметры parity между backend Python и frontend TS уже зафиксированы (Phase 4 SC#1). Phase 10 RoleGate использует тот же `can()`.
- **`sportzal_csrf` cookie** ставится бэком (Phase 4 D-26) на login/refresh/telegram-verify; fetcher (Phase 9 D-11) читает и инжектит в mutating-методы автоматически. Phase 10 ничего не делает с CSRF на уровне UI.
- **Existing `useSessionStore`** — Phase 10 НЕ удаляет (mock-mode продолжает использовать). Просто http-mode не читает оттуда (D-05).
- **Existing routes** (`/`, `/clients`, `/schedule`, `/staff`, `/finance`, `/settings`) — Phase 10 модифицирует только `/clients` (replace placeholder); остальные остаются нетронутыми и продолжают работать через `services.mock` (которые остаются пустыми объектами для остальных доменов — но routes их и не вызывают, рендерят placeholder UI).
- **`apps/admin-web/eslint.config.js`** — добавить FE-07 правило рядом с существующими `import/no-restricted-paths` и `VITE_API_MODE` правилами.

</code_context>

<specifics>
## Specific Ideas

- **`/login` standalone, без AppShell** (D-01) — ключевая структурная развилка. Planner должен решить: pathless layout-routes (`_public.tsx` без UI + `_protected.tsx` с AppShell) или conditional render в __root. Pathless layout-routes — идиоматичный TanStack Router.
- **Default tab Email/password** (D-02) — explicit override проектной "Telegram-first" семантики. Planner НЕ должен переинтерпретировать.
- **Telegram poll: 3с / 5мин timeout / Refresh deep link button** (D-04) — конкретные числа.
- **`useQuery(authKeys.me)` как SoT в http-mode** (D-05) — useSessionStore становится mock-only branch. `getSession()` адаптер ветвится по API_MODE.
- **Splash до первого ответа `/auth/me`** (D-06) — explicit choice не "оптимистичный render". Цена ~150-300мс RTT — приемлемо.
- **QueryClient global onError + module-flag** (D-07) — single точка для session_expired. Не дублировать в router error boundary.
- **Logout одним кликом без confirm** (D-08) — обратимое действие. Logout-all UI deferred.
- **`/clients` single route + dialog-формы** (D-09) — НЕ создавать `/clients/$id` маршрут в Phase 10.
- **URL-driven search/page через validateSearch + Zod** (D-10) — schema в самом маршруте, loader-deps для invalidation.
- **AlertDialog confirm + RoleGate скрывает delete для reception** (D-11) — Reception для кнопки даже не получает DOM-узла.
- **Полные mock-имплементации auth+clients** (D-12) — НЕ thin stubs. Faker.seed=42, latency, RBAC, persisted localStorage. RoleSwitcher продолжает работать в mock-mode.
- **ReUI как primary registry** (D-13) — добавляется namespace `@reui` в `components.json`, style меняется на `base-nova`. Используются Radix-варианты ReUI.
- **Style switch new-york → base-nova** (D-14) — primitives, мигрируемые через ReUI (Button, Input, Form, Label, DropdownMenu, Dialog, AlertDialog), визуально сдвинутся; AppShell-внутренние компоненты (Sidebar, ProfileMenu, RoleSwitcher) — нет (D-15).
- **DataGrid вместо ручной @tanstack/react-table разметки** (D-16) — для `/clients`. Keys factory + optimistic mutations + URL-driven search/pagination остаются (D-09, D-10).
- **InputOTP** (D-16) — для 6-значного Telegram-кода после `bound: true` (D-04).
- **Lazy migration** (D-17) — Phase 10 НЕ мигрирует все shadcn-компоненты, только перечисленные в D-16.

</specifics>

<deferred>
## Deferred Ideas

- **Detail-route `/clients/$id` + tabs (memberships/visits/billing)** — v1.2+ когда соответствующие домены появятся в бэке.
- **Logout-all-sessions UI** — бэк готов с Phase 5 (AUTH-LO-04); UI откладываем до v1.2+.
- **HTTP-mode wiring остальных доменов** (memberships, billing, schedule, staff, finance) — каждый домен подключается когда соответствующий бэк-модуль появится.
- **Switch-account UX на /login** — для shared workstation reception. Пет-проект на 1 зал, не нужен сейчас.
- **Remember last-used auth tab в localStorage** — текущий пользователь — соло-разработчик. v1.2+ если появятся reception со своими предпочтениями.
- **Multi-tab synchronization** (BroadcastChannel для logout/session_expired sync между табами) — backlog. Phase 10 покрывает single-tab сценарий полностью.
- **E2E тесты (Playwright)** — v1.2+. Phase 10 покрывает unit (vitest) + integration через mock-services.
- **/clients export CSV / bulk-actions / advanced filters (status/tag/segment)** — v1.2+ (CLAUDE.md "Anti-features" prohibits в v1).
- **`features/auth` convenience-обёртки `get`/`post`/...** на `request<P,M>` — Phase 9 D-10 уже зафиксировал, что добавим только если станет громоздко.
- **Rate-limit (429) UX на /login** — Phase 5 определяет 6-я попытка → 429. Базовый UX (toast "Слишком много попыток, попробуйте через {N} секунд") — Claude discretion в Phase 10. Фичу "блокировка формы с countdown timer" — deferred.
- **Phone input mask library decision** — Claude discretion в planner; если решит ввести зависимость — deferred к согласованию.
- **DataTable virtualization** — ~30 mock-клиентов не требуют. Если в продакшне зал вырастет (>1000 клиентов) — backlog.
- **Migration остальных shadcn-компонентов на ReUI** (Card, Badge, Avatar, Tabs, Tooltip, etc., Sidebar — отсутствует у ReUI) — lazy, по мере необходимости в последующих phase'ах (D-17).
- **ReUI Pro компоненты** — open-source часть достаточна для Phase 10. Pro-tier не рассматриваем.

</deferred>

---

*Phase: 10-admin-web-auth-clients-wiring*
*Context gathered: 2026-05-03*
