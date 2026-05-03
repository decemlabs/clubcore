# Phase 10: admin-web Auth + Clients Wiring - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-03
**Phase:** 10-admin-web-auth-clients-wiring
**Areas discussed:** Login route — layout, tabs, Telegram poll UX; Session lifecycle — boot, /auth/me, 401, logout; Clients UX scope — routes, формы, URL-state

---

## Login route — layout, tabs, Telegram poll UX

### Q1 — Layout /login

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone, без AppShell | Pathless layout-route разделяет _public и _protected; AppShell живёт в protected branch; RoleSwitcher не виден до логина | ✓ |
| Внутри AppShell | Проще в реализации, но sidebar и role-switcher видны на /login |  |

**User's choice:** Standalone, без AppShell.
**Notes:** Recommended option выбран без модификаций.

### Q2 — Default tab

| Option | Description | Selected |
|--------|-------------|----------|
| Telegram OTP | Соответствует PROJECT.md "Telegram-first" семантике |  |
| Email/password | Быстрее в dev'е; для бэкендера привычнее | ✓ |
| Remember last-used (localStorage) | Versioned key, но profit сомнителен при 1-2 операторах |  |

**User's choice:** Email/password.
**Notes:** Override проектной "Telegram-first" семантики — explicit. Telegram tab остаётся доступным, но не дефолтным.

### Q3 — Visit /login when authed

| Option | Description | Selected |
|--------|-------------|----------|
| Silent redirect на ?next или / | beforeLoad → ensureQueryData(authKeys.me) → если валидно, redirect | ✓ |
| Switch account screen | Полезно для shared workstation, но избыточно для пет-проекта на 1 зал |  |

**User's choice:** Silent redirect на ?next или /.
**Notes:** Recommended.

### Q4 — Telegram poll cadence/timeout

| Option | Description | Selected |
|--------|-------------|----------|
| 3с poll, stop через 5 мин с кнопкой "Refresh deep link" | Live-feel, не нагружает, мягкий timeout | ✓ |
| 2с poll, stop через 2 мин | Быстрее, но больше traffic; жёсткий timeout |  |
| 5с poll, stop через 10 мин | Дружелюбно к серверу, UX похуже |  |

**User's choice:** 3с poll, 5мин timeout, кнопка "Refresh deep link".
**Notes:** Recommended.

---

## Session lifecycle — boot, /auth/me, 401, logout

### Q1 — Где живёт user

| Option | Description | Selected |
|--------|-------------|----------|
| TanStack Query authKeys.me | Source of truth = сервер; useSessionStore остаётся mock-only | ✓ |
| Расширить useSessionStore до {user, role} | Zustand persist user-объекта; два источника правды |  |
| Гибрид (useQuery как SoT + зеркало в Zustand) | Сложнее настроить, но ровный boot UX |  |

**User's choice:** TanStack Query authKeys.me.
**Notes:** useSessionStore становится mock-only branch; getSession() в router адаптивен по API_MODE.

### Q2 — Boot UX в http-mode

| Option | Description | Selected |
|--------|-------------|----------|
| Splash с логотипом до первого ответа | main.tsx блокирует render router'а до ensureQueryData(authKeys.me); ноль flash; ~150-300мс RTT задержка | ✓ |
| Оптимистичный + skeleton в sidebar | Быстрее ощущаемый старт, но риск flash with wrong role |  |
| Splash только на protected-ветке | /login рендерится сразу; сложнее dual-route-дерево |  |

**User's choice:** Splash с логотипом до первого ответа.
**Notes:** Recommended; цена RTT приемлема.

### Q3 — Где ловим session_expired

| Option | Description | Selected |
|--------|-------------|----------|
| QueryClient global onError + module-flag | queryCache+mutationCache onError; module-scoped redirecting flag для one-shot navigate | ✓ |
| Router error boundary | Только loader/beforeLoad ошибки; не покрывает component hooks |  |
| Оба (defence-in-depth) | Больше страховки, но module-flag нужен в обеих точках |  |

**User's choice:** QueryClient global onError + module-flag.
**Notes:** Recommended.

### Q4 — Logout UX

| Option | Description | Selected |
|--------|-------------|----------|
| ProfileMenu: 'Logout' одним кликом без confirm | services.auth.logout → queryClient.clear → navigate /login; logout-all deferred | ✓ |
| ProfileMenu: 'Logout' + 'Logout all sessions' | Бэк AUTH-LO-04 готов с Phase 5 |  |
| ProfileMenu: 'Logout' с confirm-dialog | Защита от случайных кликов; избыточно для обратимого действия |  |

**User's choice:** ProfileMenu: 'Logout' одним кликом без confirm.
**Notes:** Logout-all UI deferred до v1.2+.

---

## Clients UX scope — routes, формы, URL-state

### Q1 — Структура маршрутов

| Option | Description | Selected |
|--------|-------------|----------|
| /clients (list+формы в dialog) | Один маршрут, dialog'и поверх таблицы; detail-view deferred | ✓ |
| /clients + /clients/$id + /clients/new | Полный split, но detail-tabs пусты в v1.1 |  |
| /clients + /clients/$id (без /clients/new) | Компромисс с shareable detail URL |  |

**User's choice:** /clients (list+формы в dialog).
**Notes:** Detail-route deferred до v1.2+ когда появятся memberships/visits/billing tabs.

### Q2 — Search/pagination state

| Option | Description | Selected |
|--------|-------------|----------|
| URL-driven через TanStack Router validateSearch + Zod | Reload-стабильно, shareable, browser navigation работает | ✓ |
| In-memory через useState | Проще, но reload теряет состояние |  |
| URL только для q, pagination in-memory | Непоследовательный contract |  |

**User's choice:** URL-driven через TanStack Router validateSearch.
**Notes:** Совпадает с admin-web/CLAUDE.md "роутер + Zod validateSearch" pattern.

### Q3 — Owner-only delete UX

| Option | Description | Selected |
|--------|-------------|----------|
| AlertDialog confirm + RoleGate скрывает кнопку для reception | Optimistic update + rollback; reception не видит DOM-узла кнопки | ✓ |
| Inline 'mark for delete' без dialog | Риск случайных списываний |  |
| AlertDialog + Undo toast (5с sonner) | Требует undo-endpoint на бэке, scope-creep |  |

**User's choice:** AlertDialog confirm + RoleGate hides for reception.
**Notes:** Soft-delete на бэке; UI optimistic с rollback.

### Q4 — Mock parity

| Option | Description | Selected |
|--------|-------------|----------|
| Полные mock-имплементации auth + clients по конвенциям CLAUDE.md | Faker.seed=42, latency, RBAC, persisted localStorage; UI идентичен в обоих modes | ✓ |
| Тонкие stub'ы | Удовлетворяют contract, но SC#3 'no regression' хромает |  |
| Отложить моки, изменить SC#3 | Ломает mock-параллельно-бэку философию |  |

**User's choice:** Полные mock-имплементации.
**Notes:** RoleSwitcher продолжает работать в mock-mode; mock services хранят faker-данные с persisted localStorage.

---

## Claude's Discretion

Planner свободен решать (зафиксировано в CONTEXT.md `<decisions>` под "Claude's Discretion"):
- Точная internal-структура `features/auth/` и `features/clients/` (FSD-lite layout).
- `clientsKeys` factory shape (TkDodo pattern recommended).
- Точный набор полей `ClientForm` (зависит от Phase 8 schema).
- Phone input mask library (input-mask vs react-imask vs ручной regex).
- Search debounce interval (typically 300мс).
- DataTable virtualization (вряд ли нужно для ~30 mock-клиентов).
- Empty/loading/error state copy (Russian).
- Splash component design.
- Branded ID local placement (entities/client/types.ts).

## Deferred Ideas

- Detail-route `/clients/$id` + tabs (memberships/visits/billing) — v1.2+.
- Logout-all-sessions UI — бэк готов с Phase 5; UI v1.2+.
- HTTP-mode wiring остальных доменов — каждый когда соответствующий backend появится.
- Switch-account UX — пет-проект на 1 зал.
- Remember last-used auth tab в localStorage — соло-разработчик.
- Multi-tab synchronization (BroadcastChannel) — backlog.
- E2E тесты (Playwright) — v1.2+.
- /clients export CSV / bulk-actions / advanced filters — v1.2+ (CLAUDE.md anti-features).
- `request<P,M>` convenience обёртки — Phase 9 D-10 уже зафиксировал deferral.
- Rate-limit (429) UX countdown timer на /login — Claude discretion в Phase 10 покрывает базовый toast; advanced UX deferred.
- Phone input mask library decision — discretion с возможным deferral.
- DataTable virtualization — backlog для production-scale.
