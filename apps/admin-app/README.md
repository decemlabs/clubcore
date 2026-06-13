# ClubCore Admin Frontend

Админ-панель для сети фитнес-клубов. React + Bun SPA.

## Стек

- **Bun** — пакетный менеджер и рантайм
- **Vite 5** — dev server и production-бандл
- **React 18 + TypeScript (strict)**
- **React Router v6** (data router API)
- **Tailwind CSS v4** — CSS-first через плагин `@tailwindcss/vite`; файла `tailwind.config.ts` нет, токены в `src/styles/tokens.css` + `src/styles/globals.css`
- **TanStack Query v5** — слой данных (моки сейчас → реальный API позже)
- **Radix UI + CVA** — доступные примитивы и варианты компонентов
- **Recharts**, **date-fns** (ru), **lucide-react**, **zod**

## Скрипты

```bash
bun install           # установка зависимостей
bun run dev           # dev-server на http://localhost:5173
bun run build         # production-бандл в ./dist
bun run preview       # предпросмотр продакшен-сборки
bun run typecheck     # tsc -b --noEmit
bun run lint          # eslint, ошибка при любом предупреждении
bun run format        # prettier --write .
bun run check         # typecheck + lint + prettier --check (gate перед коммитом)
bun run test          # vitest run (юнит + smoke-тесты роутов)
bun run test:watch    # vitest в watch-режиме
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
