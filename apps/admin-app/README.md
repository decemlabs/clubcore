# ClubCore Admin Frontend

Админ-панель для сети фитнес-клубов. React + pnpm SPA. Пакет: `@clubcore/admin-app`.

## Стек

- **pnpm** — пакетный менеджер (workspaces, версия 9.15.9)
- **Vite 5** — dev server и production-бандл
- **React 18 + TypeScript (strict)**
- **React Router v6** (data router API)
- **Tailwind CSS v4** — CSS-first через плагин `@tailwindcss/vite`; файла `tailwind.config.ts` нет, токены в `src/styles/tokens.css` + `src/styles/globals.css`
- **TanStack Query v5** — слой данных (моки сейчас → реальный API позже)
- **Radix UI + CVA** — доступные примитивы и варианты компонентов
- **Recharts**, **date-fns** (ru), **lucide-react**, **zod**
- **@clubcore/api-client** — workspace-зависимость (`workspace:*`)

## Скрипты

Запускайте из корня репозитория через pnpm workspace-фильтры:

```bash
pnpm install                                # установка зависимостей (из корня)

pnpm -F @clubcore/admin-app dev             # dev-server на http://localhost:5173
pnpm -F @clubcore/admin-app build           # production-бандл в ./dist
pnpm -F @clubcore/admin-app preview         # предпросмотр продакшен-сборки
pnpm -F @clubcore/admin-app typecheck       # tsc -b --noEmit
pnpm -F @clubcore/admin-app lint            # eslint .
pnpm -F @clubcore/admin-app test            # vitest run (юнит + smoke-тесты роутов)
pnpm -F @clubcore/admin-app test:watch      # vitest в watch-режиме
```

## Структура

```
src/
├── app/          # router, providers, routes
├── layouts/      # AppLayout: Sidebar + Header + Outlet
├── pages/        # один каталог на маршрут
├── components/   # ui / data / charts / icons / layout / modals / feedback / settings
├── features/     # доменная логика (clients, schedule, trainers, …)
├── api/          # fetch-клиент, QueryClient
├── mocks/        # сидовые данные на время отсутствия backend
├── hooks/        # общие хуки
├── lib/          # cn, format, constants
├── types/        # общие типы
├── styles/       # globals.css, tokens.css
└── assets/
```

Архитектура, конвенции и workflow интеграции шаблонов — в [CLAUDE.md](./CLAUDE.md).

## Workflow интеграции HTML-шаблона

1. Шаблон присылается → определяется целевая страница из карты роутов.
2. Извлекаются новые дизайн-токены (если есть) → `src/styles/tokens.css` (raw values) + `src/styles/globals.css` (`@theme inline`).
3. DOM раскладывается на слои:
   - layout-общее остаётся в `layouts/AppLayout`;
   - примитивы — в `components/ui`;
   - доменные виджеты — в `features/<domain>/components`;
   - страничные композиции — в `pages/<page>/components`.
4. Мок-данные — в `mocks/<entity>.ts`, типы — в `features/<entity>/types.ts`.
5. Данные потребляются страницей через хук вида `useDashboardSummary()` поверх
   TanStack Query — внутри пока `Promise.resolve(mock)`, потом меняется на API.
6. Интерактивные состояния (hover/active/focus/disabled) и все брейкпоинты реализуются по референсу — верность визуальному стилю, но чистый адаптивный React, не дословная копия HTML.
