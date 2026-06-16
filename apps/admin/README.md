# ClubCore Admin Frontend

Админ-панель для сети фитнес-клубов. React + pnpm SPA. Пакет: `@clubcore/admin`.

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

pnpm -F @clubcore/admin dev             # dev-server на http://localhost:5173
pnpm -F @clubcore/admin build           # production-бандл в ./dist
pnpm -F @clubcore/admin preview         # предпросмотр продакшен-сборки
pnpm -F @clubcore/admin typecheck       # tsc -b --noEmit
pnpm -F @clubcore/admin lint            # eslint .
pnpm -F @clubcore/admin test            # vitest run (юнит + smoke-тесты роутов)
pnpm -F @clubcore/admin test:watch      # vitest в watch-режиме
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

## Mock queryFn removal path (FND-03 per-domain zod seam)

Phase 100 establishes the per-domain zod contract layer on the `auth/session` domain.
Each subsequent domain (101–104) repeats this pattern to flip from mock data to the real API.
`features/auth/` is the worked example.

### Steps to graduate a domain from mock to http

**1. Add `features/<domain>/schemas.ts`**

Create zod schemas that match the verified backend wire shapes. The backend serialises to
camelCase (`alias_generator=to_camel` on `ContractModel`) — confirm field names against the
backend `schemas.py` file, not the Python identifiers. Export inferred types alongside each
schema.

```ts
// features/<domain>/schemas.ts
import { z } from 'zod'

export const DomainItemSchema = z.object({ id: z.string(), name: z.string() })
export type DomainItem = z.infer<typeof DomainItemSchema>

export const DomainListResponseSchema = z.object({
  data: z.object({
    items: z.array(DomainItemSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
})
```

**2. Replace `mockResponse()` with `staffRequest` + `Schema.parse` in `features/<domain>/api.ts`**

```ts
// Before (mock):
export function useDomainItems() {
  return useQuery({
    queryKey: domainKeys.list,
    queryFn: () => mockResponse<DomainItem[]>(mockItems),
  })
}

// After (http):
import { staffRequest } from '@/api/client'
import { DomainListResponseSchema } from './schemas'

export function useDomainItems() {
  return useQuery({
    queryKey: domainKeys.list,
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/<domain>')
      return DomainListResponseSchema.parse(raw).data
    },
  })
}
```

**3. VITE_API_MODE chokepoint (optional gradual flip)**

If a domain needs a gradual mock→http transition, read `import.meta.env.VITE_API_MODE`
inside `features/<domain>/api.ts` (the ESLint chokepoint exempts `features/**/api.ts`).
The end state removes the mock branch entirely — do not leave dead mock branches in
production-ready domains.

**4. Delete the domain's mock seed file once live**

Once the domain is wired, delete `mocks/<domain>.ts` and its import from `mocks/index.ts`.
The page components do not change — they only depend on the hook's return type.

### Reference

`features/auth/api.ts` and `features/auth/schemas.ts` are the canonical example.
See `100-03-SUMMARY.md` for design decisions made during the auth domain wiring.

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
