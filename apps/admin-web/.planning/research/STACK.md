# Technology Stack — SportZal Adminka

**Project:** SportZal Adminka (gym CRM admin panel, frontend only, mock data)
**Researched:** 2026-04-21
**Overall confidence:** HIGH (stack is mainstream React + shadcn/ui + ReUI; verified against Context7-indexed official docs for every library recommended)

---

## Overview

The project is a greenfield SPA admin panel with a **hard-locked UI stack** (React + shadcn/ui + ReUI) and a **mock-only data layer** that must later be swappable for a real API without touching the UI. That constraint drives most of the decisions below:

- **Build tool:** Vite — the canonical greenfield choice for a React SPA in 2026. shadcn/ui treats Vite as a first-class target alongside Next.js; React docs list Vite as the top recommended non-framework option.
- **Language:** TypeScript in strict mode. Non-negotiable for a "future real API will slot in" architecture: contracts are the seam between mocks and the real backend, and contracts without types are worthless.
- **Component model:** shadcn/ui is the base registry; ReUI is installed through the same `shadcn add` CLI against a second registry (`@reui`). Both libraries target the same Tailwind/CSS-variable token system, so they coexist without style conflicts by design.
- **Data layer:** TanStack Query over a typed "service" module. The service is backed by MSW (Mock Service Worker) in development so the UI actually issues `fetch`/`axios` calls against realistic HTTP handlers — swapping to a real backend is then a one-line change (remove `worker.start()`).
- **State:** TanStack Query for server state (clients, schedule, payments); Zustand for UI/role state (role toggle, sidebar collapse, theme). No Redux.
- **Forms:** react-hook-form + zod via shadcn's Form/Field primitives. This is the documented shadcn pattern.
- **Scheduling:** react-big-calendar with the date-fns localizer (set to `ru`) — mature, free, works inside shadcn theming via CSS overrides. FullCalendar is a runner-up but its Resource/Timeline views are behind a paid Premium license.
- **i18n:** None. Hard-coded Russian strings in a single `ru.ts` dictionary; dates/numbers/currency via `Intl.*` with `ru-RU` locale and `Europe/Moscow` timezone. No i18next, no react-intl.

This stack is deliberately boring. Everything is the path shadcn itself recommends, which keeps upgrades painless.

---

## Core Stack

| Category | Choice | Version (as of 2026-04) | Why |
|----------|--------|-------------------------|-----|
| Runtime/UI | **React** | 19.x | Required by shadcn/ReUI; stable. |
| Build tool | **Vite** | 6.x | Official shadcn "Vite" path; fast HMR; no SSR needed. |
| Language | **TypeScript** | 5.6+ | Strict mode enforces mock→real API contracts. |
| Styling | **Tailwind CSS** | v4 | shadcn@3 / ReUI both target Tailwind v4 with the new `@theme` CSS-first config. |
| Component base | **shadcn/ui** | current | Registry/CLI based; own the code. |
| Component overlay | **ReUI** (reui.io) | current | Second shadcn registry for components shadcn lacks (Data Grid, Date Selector, Timeline, Filters, many patterns). |
| Routing | **TanStack Router** | 1.x | Type-safe routes + search params; no server requirements. |
| Server state | **TanStack Query** | 5.x | De-facto standard; works great against MSW. |
| UI state | **Zustand** | 5.x | Role toggle + sidebar + theme; 1-file stores. |
| Forms | **react-hook-form** + **zod** + `@hookform/resolvers` | rhf 7.x, zod 3.x | shadcn's documented forms recipe. |
| Tables | **@tanstack/react-table** | 8.x | Shadcn Data Table + ReUI Data Grid both sit on top of it. |
| Charts | **Recharts** | 3.x | Powers the shadcn `<Chart>` primitive. |
| Calendar/Scheduler | **react-big-calendar** + `date-fns` localizer | 1.15+ | Week/day/month + agenda; MIT. |
| Dates | **date-fns** | 4.x | Tree-shakable, plays well with `ru` locale, used by rbc localizer and shadcn's Calendar. |
| Icons | **lucide-react** | current | Default icon set for shadcn. |
| Toasts | **sonner** | current | Default toast in shadcn docs. |
| Mocking | **MSW** (Mock Service Worker) | 2.x | Intercepts at network level → swap to real API = stop worker. |
| Fake data | **@faker-js/faker** | 9.x | Realistic ru-RU names, addresses, phones. |
| Linting/format | **ESLint 9** + **Prettier** + **typescript-eslint** | current | Flat config. |
| Testing (optional) | **Vitest** + **@testing-library/react** | current | Vite-native; MSW has first-class Vitest browser-mode recipe. |
| Package manager | **pnpm** | 9.x | Fast, disk-efficient; monorepo-ready if a backend is added later. |

---

## Component Libraries — shadcn/ui + ReUI

### shadcn/ui — the base

shadcn is not a dependency — it's a **code distribution platform via CLI**. Components are copied into `src/components/ui/*` and owned by you. That is exactly what this project wants, because the client brief is "foundation you can sell as MVP" — editable, no vendor lock-in.

**Install (Vite path):**

```bash
pnpm create vite@latest sportzal-adminka -- --template react-ts
cd sportzal-adminka
pnpm add tailwindcss @tailwindcss/vite
pnpm dlx shadcn@latest init
```

`components.json` (created by `init`) should declare **both** registries:

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": false,
  "tsx": true,
  "tailwind": { "config": "", "css": "src/index.css", "baseColor": "neutral", "cssVariables": true },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  },
  "registries": {
    "@reui": "https://reui.io/r/{style}/{name}.json"
  }
}
```

**Install components:**

```bash
# shadcn (default registry)
pnpm dlx shadcn@latest add button input label card dialog dropdown-menu \
  sheet sidebar table tabs tooltip badge avatar separator select \
  form field checkbox radio-group switch textarea calendar popover \
  command sonner skeleton alert-dialog scroll-area chart

# ReUI (second registry) — only components shadcn doesn't have
pnpm dlx shadcn@latest add @reui/data-grid @reui/date-selector \
  @reui/filters @reui/timeline @reui/stepper
```

**Canonical shadcn admin blocks to base screens on:**

| Block | Use for |
|-------|---------|
| `sidebar-07` / `sidebar-08` | Collapsible sidebar with sections + user switcher → basis of the Owner/Reception role toggle. |
| `sidebar-15` | Inset-style sidebar with a command palette trigger — matches "modern SaaS admin". |
| `dashboard-01` | Multi-card dashboard layout (KPIs + table + chart) → basis of the Dashboard module. |
| `login-03` / `login-05` | **Not used** (no auth), but good reference for form spacing. |

Add them with `pnpm dlx shadcn@latest add sidebar-07` etc. — they pull in their own sub-components.

### ReUI (reui.io) — the overlay

ReUI is an open-source library by Keenthemes "designed to pair well with shadcn/ui" (per the library description). It is distributed the **same way** as shadcn — as a CLI registry. It uses the same Tailwind tokens (`--background`, `--foreground`, `--primary`, etc.) and the same component folder (`src/components/ui/*`), so there is zero style conflict as long as you use shadcn's `init` colors as the source of truth.

**What ReUI gives you that shadcn/ui does not:**

| ReUI component | Fills which gap |
|----------------|-----------------|
| `@reui/data-grid` | Heavier production data-grid on top of TanStack Table with built-in sorting/filtering/pagination/column-ordering/DnD, whereas shadcn's "Data Table" is just a bare TanStack Table wrapper you have to compose yourself. For the Clients list and Payments list this cuts hundreds of lines. |
| `@reui/date-selector` | Presets ("Last 7 days", custom range, etc.) for the Finance and Schedule date-range filters — shadcn only ships the underlying `Calendar`. |
| `@reui/filters` | Pre-built "filter chip" pattern (select value → pill → clear) — standard admin UX; shadcn does not ship this. |
| `@reui/timeline` | Vertical timeline — useful for client activity log / payment history. |
| `@reui/stepper` | Multi-step forms (e.g. new-client + first-subscription wizard). |
| ReUI **patterns** (`@reui/p-*`) | Pre-composed examples (`p-data-grid-1`, `p-dialog-1`, etc.) — copy as starting pages then customize. |

**ReUI does *not* ship a full scheduler/calendar component or a chart library.** For scheduling use `react-big-calendar`; for charts use shadcn's `<Chart>` (which wraps Recharts).

**Coexistence rules (to avoid style conflicts):**

1. Run `shadcn init` first; ReUI adopts the same `--background`/`--foreground`/`--primary`/`--radius` tokens.
2. Keep a single `src/index.css` with `@import "tailwindcss";` and one `@theme { ... }` block — do not let ReUI-installed components add a second theme block.
3. If a component name collides (e.g. both have `button.tsx`), let **shadcn's** version win — ReUI components import from `@/components/ui/button` and will happily use the shadcn one.
4. Both libraries depend on `class-variance-authority`, `clsx`, and `tailwind-merge` (already installed by `shadcn init`). Do not re-install these.

**Confidence:** HIGH. Coexistence is by design: ReUI's own docs describe the registry configuration snippet shown above and explicitly position the library as additive to shadcn/ui.

---

## Theming & Dark Mode

shadcn theming is **CSS-variable based**. With Tailwind v4 and the `new-york` style, `shadcn init` generates `src/index.css` roughly like:

```css
@import "tailwindcss";
@custom-variant dark (&:is(.dark *));

@theme {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-primary: var(--primary);
  /* ...etc */
  --radius: 0.5rem;
}

:root {
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  /* sidebar tokens */
  --sidebar: oklch(0.985 0 0);
  --sidebar-foreground: oklch(0.145 0 0);
  --sidebar-primary: oklch(0.205 0 0);
  --sidebar-accent: oklch(0.97 0 0);
  --sidebar-border: oklch(0.922 0 0);
  --sidebar-ring: oklch(0.708 0 0);
}

.dark {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
  --primary: oklch(0.985 0 0);
  --sidebar: oklch(0.205 0 0);
  /* ... */
}
```

**Toggle implementation** (no `next-themes` since we're on Vite — roll a 30-line hook):

```tsx
// src/components/theme-provider.tsx
type Theme = "light" | "dark" | "system";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = React.useState<Theme>(
    () => (localStorage.getItem("theme") as Theme) ?? "system"
  );
  React.useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("light", "dark");
    const resolved =
      theme === "system"
        ? window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
        : theme;
    root.classList.add(resolved);
    localStorage.setItem("theme", theme);
  }, [theme]);
  return <ThemeCtx.Provider value={{ theme, setTheme }}>{children}</ThemeCtx.Provider>;
}
```

Wire a `<ModeToggle />` (shadcn ships the code in the Dark Mode docs — copy verbatim) into the sidebar header.

**ReUI compatibility:** ReUI components read the same `--background`/`--foreground`/`--primary` variables, so the theme toggle flips both libraries in one go. Verified: ReUI's install instructions explicitly say "pair with shadcn" and use `components.json` + Tailwind CSS vars.

---

## Routing

**Choice: TanStack Router (v1).**

Why not react-router? TanStack Router gives **type-safe route params and search params** out of the box, with file-based or code-based route trees. For an admin panel where URLs carry filter state (e.g. `/clients?status=active&subscription=expired&page=3`), typed search params prevent a whole class of bugs when you later swap mocks for a real API that actually validates query strings.

**Setup:**

```bash
pnpm add @tanstack/react-router
pnpm add -D @tanstack/router-plugin
```

```ts
// vite.config.ts
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";
export default defineConfig({ plugins: [react(), TanStackRouterVite()] });
```

**Route tree (file-based, `src/routes/`):**

```
src/routes/
  __root.tsx           # Layout: Sidebar + <Outlet />
  index.tsx            # → redirect to /dashboard
  dashboard.tsx
  clients/
    index.tsx          # list
    $clientId.tsx      # detail
  schedule.tsx
  trainers/
    index.tsx
    $trainerId.tsx
  finance.tsx
  notifications.tsx
```

**Role-gating** is NOT done at the router level (there is no auth). Instead, the sidebar hides items the current role can't see, and each page reads `useRole()` from Zustand to decide whether to render destructive actions. This matches the "role switcher in UI, no login" constraint.

**Alternative considered:** react-router v7. Fine, but you give up type-safe search params. Not worth it for a greenfield project in 2026.

---

## Data & State

### Server state — TanStack Query + service layer

The key architectural rule: **UI never imports mock modules directly.** All data flows through a service layer of pure `async` functions returning typed domain objects. Swapping mocks → real API = replace the implementation; hooks never change.

```
src/
  domain/                # Pure types — the contract.
    client.ts            # export type Client, Subscription, ...
    session.ts           # export type ScheduleSession, ...
    payment.ts
  services/              # Pure async functions — the seam.
    client-service.ts    # listClients(params) → Promise<Client[]>
    schedule-service.ts
  hooks/                 # TanStack Query wrappers.
    use-clients.ts       # useClients = useQuery({ queryKey, queryFn: listClients })
  mocks/                 # MSW handlers + faker factories. Dev-only import.
    handlers.ts
    browser.ts
    seed/                # JSON fixtures generated from faker.
      clients.ts
      sessions.ts
```

The services call `fetch("/api/clients")` unconditionally. MSW intercepts those calls in dev. In production (or when a real backend is wired), MSW is simply not started, and requests hit the real API at the same paths.

**Example service + hook:**

```ts
// services/client-service.ts
import type { Client } from "@/domain/client";
export async function listClients(params: { q?: string; page?: number }) {
  const url = new URL("/api/clients", window.location.origin);
  if (params.q) url.searchParams.set("q", params.q);
  if (params.page) url.searchParams.set("page", String(params.page));
  const res = await fetch(url);
  if (!res.ok) throw new Error(`listClients ${res.status}`);
  return (await res.json()) as { data: Client[]; total: number };
}

// hooks/use-clients.ts
export function useClients(params: { q?: string; page?: number }) {
  return useQuery({
    queryKey: ["clients", params],
    queryFn: () => listClients(params),
    staleTime: 30_000,
  });
}
```

### UI state — Zustand

One tiny store for cross-page UI concerns. **Not** for server data — that's TanStack Query's job.

```ts
// store/ui-store.ts
type Role = "owner" | "reception";
interface UiState {
  role: Role;
  setRole: (r: Role) => void;
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
}
export const useUi = create<UiState>((set) => ({
  role: "owner",
  setRole: (role) => set({ role }),
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
}));
```

Persist to `localStorage` via `zustand/middleware#persist` so the role and theme survive reload during demos.

---

## Forms

**react-hook-form + zod** via shadcn's `Field*` primitives. This is the exact pattern in the shadcn docs (verified via Context7 from `ui.shadcn.com/docs/forms/react-hook-form`).

```tsx
import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import * as z from "zod";

const ClientSchema = z.object({
  fullName: z.string().min(2, "Укажите ФИО"),
  phone: z.string().regex(/^\+7\d{10}$/, "Формат +7XXXXXXXXXX"),
  birthDate: z.coerce.date().optional(),
});
type ClientForm = z.infer<typeof ClientSchema>;

const form = useForm<ClientForm>({
  resolver: zodResolver(ClientSchema),
  defaultValues: { fullName: "", phone: "" },
});
```

Russian error messages live inside the schema (the `"Укажите ФИО"` argument), which keeps localization trivial without pulling i18next. If Zod's built-in default messages leak through, override once with `z.setErrorMap(ruErrorMap)`.

**Shared domain schemas:** keep one `src/domain/schemas.ts` re-used by both the form (validation) and the mock handlers (response shape). Single source of truth.

---

## Tables

Two levels, both on **TanStack Table v8**:

1. **shadcn Data Table** (`components/ui/data-table.tsx`, copied from shadcn docs) — bare-bones, you compose columns, pagination, filters yourself. Use for simple tables (Trainers list, Notifications list).

2. **`@reui/data-grid`** — opinionated production grid with sorting, column-ordering, DnD, row selection, pagination, and column visibility pre-wired. Use for Clients list, Payments list, Schedule list-view. Install once:

   ```bash
   pnpm dlx shadcn@latest add @reui/data-grid
   ```

**Pattern:** the Data Grid consumes the same TanStack Query data as any page. Server-side pagination is simulated in MSW by slicing the fixture by `?page=&pageSize=`.

---

## Scheduling / Calendar

**Choice: react-big-calendar** with the `date-fns` localizer set to the Russian locale.

```bash
pnpm add react-big-calendar date-fns
pnpm add -D @types/react-big-calendar
```

```tsx
import { Calendar, dateFnsLocalizer } from "react-big-calendar";
import { format, parse, startOfWeek, getDay } from "date-fns";
import { ru } from "date-fns/locale";
import "react-big-calendar/lib/css/react-big-calendar.css";

const localizer = dateFnsLocalizer({
  format, parse, startOfWeek: (d) => startOfWeek(d, { locale: ru }),
  getDay, locales: { "ru-RU": ru },
});

<Calendar
  localizer={localizer}
  culture="ru-RU"
  events={events}
  startAccessor="start"
  endAccessor="end"
  views={["week", "day", "month", "agenda"]}
  defaultView="week"
  messages={ruMessages}  // { today: "Сегодня", next: "Далее", ... }
/>;
```

**Styling:** rbc ships its own CSS. Override the relevant classes in `src/styles/rbc.css` to consume the shadcn tokens (`--primary`, `--border`, etc.) so the calendar theme flips with the rest of the app.

**Alternatives evaluated:**

- **FullCalendar** — polished, supports Resource/Timeline views, but the Resource Timeline (needed for "which trainer is in which studio at which hour") is **Premium/paid**. Skip unless the client agrees to buy the license.
- **shadcn `Calendar` + custom grid** — shadcn's `Calendar` is a date-*picker*, not an event scheduler. Building a week-grid with drag-to-create on top would be 2-3 days of work; react-big-calendar gives it for free.
- **Tui Calendar / react-schedule** — smaller communities, fewer types, not worth the risk.

**Confidence:** HIGH for rbc (mature, 7k+ stars, active). MEDIUM on choice between rbc vs FullCalendar-free — if the client later wants resource-timeline, FullCalendar paid may be required.

---

## Charts

**Choice: shadcn `<Chart>` (wraps Recharts v3).**

```bash
pnpm dlx shadcn@latest add chart
pnpm add recharts
```

The `ChartContainer` component takes a `config` object (series names + colors tied to CSS variables), so chart colors auto-flip with dark mode. Use for the Dashboard: monthly revenue bar chart, active-subscriptions line, class-attendance area.

Recharts covers everything an admin needs — no need for Visx/Echarts unless charting becomes a main feature (it isn't here).

---

## Mock Data Layer

**Choice: MSW (Mock Service Worker) + faker-js, seeded deterministically.**

### Why MSW over a plain module

| Concern | Plain module (e.g. `data.ts` with imports) | MSW |
|---------|--------------------------------------------|-----|
| Swap to real API | Every hook changes | Zero hook changes — remove `worker.start()` |
| Realism (latency, errors, pagination) | Manual | Built-in (`HttpResponse`, `delay`) |
| DevTools visibility | Nothing in Network tab | Real requests show up |
| Type drift | Hooks import both mocks and domain — easy to drift | Contracts live in one place (`zod` schemas reused by handlers) |

MSW is explicitly the industry-standard pattern and the one TanStack Query's own docs use for examples.

### Setup

```bash
pnpm add -D msw @faker-js/faker
pnpm dlx msw init public/ --save
```

```ts
// src/mocks/browser.ts
import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";
export const worker = setupWorker(...handlers);

// src/main.tsx
async function enableMocking() {
  if (import.meta.env.PROD) return;
  const { worker } = await import("./mocks/browser");
  return worker.start({ onUnhandledRequest: "bypass" });
}
enableMocking().then(() => {
  ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
});
```

```ts
// src/mocks/handlers.ts
import { http, HttpResponse, delay } from "msw";
import { clientsFixture } from "./seed/clients";

export const handlers = [
  http.get("/api/clients", async ({ request }) => {
    await delay(200); // simulate latency
    const url = new URL(request.url);
    const q = url.searchParams.get("q") ?? "";
    const page = Number(url.searchParams.get("page") ?? "1");
    const pageSize = 20;
    const filtered = clientsFixture.filter((c) =>
      c.fullName.toLowerCase().includes(q.toLowerCase())
    );
    return HttpResponse.json({
      data: filtered.slice((page - 1) * pageSize, page * pageSize),
      total: filtered.length,
    });
  }),
];
```

### Fixtures via faker

```ts
// src/mocks/seed/clients.ts
import { faker } from "@faker-js/faker/locale/ru";
faker.seed(42); // deterministic — the same data every reload

export const clientsFixture: Client[] = Array.from({ length: 80 }, () => ({
  id: faker.string.uuid(),
  fullName: faker.person.fullName(),
  phone: faker.phone.number("+7##########"),
  birthDate: faker.date.birthdate({ min: 16, max: 60, mode: "age" }),
  subscription: { /* ... */ },
}));
```

Deterministic seeding is important: without `faker.seed()`, every reload shuffles data and demos look broken.

### "Swap to real API later" — the recipe

1. Delete `enableMocking()` in `main.tsx` (or gate behind `VITE_USE_MOCKS=1`).
2. Add a `VITE_API_URL` env and a thin `api.ts` that prepends it to every `fetch` in the services layer.
3. That's it — hooks, components, zod schemas all survive.

---

## Dates & Locale

**No i18n library.** Requirements are explicit: RU only, no English. Pulling i18next adds configuration, split bundles, and a `t()` wrapper around every string for zero payoff.

Instead:

1. **UI strings:** `src/i18n/ru.ts` — a flat object with all labels. Components import `import { t } from "@/i18n"` and do `t.clients.list.title`. If English is ever added, you change `@/i18n` to pick the active dictionary — one file.

2. **Dates/times:** `Intl.DateTimeFormat("ru-RU", { timeZone: "Europe/Moscow", ... })` via a tiny helper.

   ```ts
   // src/lib/format.ts
   const RU = "ru-RU";
   const TZ = "Europe/Moscow";
   export const fmtDate = (d: Date) =>
     new Intl.DateTimeFormat(RU, { dateStyle: "medium", timeZone: TZ }).format(d);
   export const fmtDateTime = (d: Date) =>
     new Intl.DateTimeFormat(RU, { dateStyle: "short", timeStyle: "short", timeZone: TZ }).format(d);
   export const fmtMoney = (n: number) =>
     new Intl.NumberFormat(RU, { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(n);
   export const fmtNumber = (n: number) => new Intl.NumberFormat(RU).format(n);
   ```

3. **date-fns locale:** when manipulating dates (for the calendar or forms), pass `{ locale: ru }`:

   ```ts
   import { ru } from "date-fns/locale";
   format(d, "d MMMM yyyy", { locale: ru }); // "21 апреля 2026"
   ```

4. **Zod error messages:** override once:

   ```ts
   import { z } from "zod";
   z.setErrorMap((issue, ctx) => ({
     message: ruZodMessages[issue.code] ?? ctx.defaultError,
   }));
   ```

**Timezone:** hard-code `Europe/Moscow` for v1. If gyms outside MSK are needed later, add a user-preference in Zustand.

---

## Dev Tooling

| Tool | Config |
|------|--------|
| ESLint 9 flat config | `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`, `eslint-plugin-tailwindcss`. Error on unused imports, no-explicit-any. |
| Prettier | `prettier-plugin-tailwindcss` for class-order sorting. |
| TypeScript | `strict: true`, `noUncheckedIndexedAccess: true`, `exactOptionalPropertyTypes: true`, `verbatimModuleSyntax: true`. Path alias `@/*` → `src/*`. |
| Husky + lint-staged | Pre-commit: `eslint --fix` + `prettier --write` on staged files. |
| Commitlint (optional) | Conventional commits — helps when a real team joins. |
| Vitest | `environment: "jsdom"`, MSW browser-mode for integration tests. |
| Storybook (optional, phase 2+) | For component documentation once the design system settles. |

**tsconfig highlights:**

```jsonc
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "jsx": "react-jsx",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  }
}
```

---

## Recommended File Layout

```
sportzal-adminka/
├── public/
│   └── mockServiceWorker.js        # generated by `msw init`
├── src/
│   ├── main.tsx                    # entry; enables MSW in dev
│   ├── App.tsx                     # RouterProvider + QueryClientProvider + ThemeProvider
│   ├── index.css                   # Tailwind + shadcn tokens (light/dark)
│   │
│   ├── routes/                     # TanStack Router file-based routes
│   │   ├── __root.tsx
│   │   ├── index.tsx
│   │   ├── dashboard.tsx
│   │   ├── clients/
│   │   │   ├── index.tsx
│   │   │   └── $clientId.tsx
│   │   ├── schedule.tsx
│   │   ├── trainers/
│   │   ├── finance.tsx
│   │   └── notifications.tsx
│   │
│   ├── components/
│   │   ├── ui/                     # shadcn + ReUI components live here
│   │   ├── layout/
│   │   │   ├── app-sidebar.tsx     # adapted from sidebar-07
│   │   │   ├── role-switcher.tsx   # the "Owner ↔ Reception" toggle
│   │   │   └── mode-toggle.tsx     # theme toggle
│   │   ├── clients/                # feature-specific components
│   │   ├── schedule/
│   │   ├── trainers/
│   │   ├── finance/
│   │   └── dashboard/
│   │
│   ├── domain/                     # pure types + zod schemas
│   │   ├── client.ts
│   │   ├── session.ts
│   │   ├── payment.ts
│   │   └── schemas.ts
│   │
│   ├── services/                   # async fns calling /api/* (pure fetch)
│   │   ├── http.ts                 # fetch wrapper, error handling
│   │   ├── client-service.ts
│   │   ├── schedule-service.ts
│   │   ├── trainer-service.ts
│   │   └── finance-service.ts
│   │
│   ├── hooks/                      # TanStack Query wrappers
│   │   ├── use-clients.ts
│   │   ├── use-schedule.ts
│   │   └── ...
│   │
│   ├── store/                      # Zustand
│   │   └── ui-store.ts             # role, sidebar, theme persistence
│   │
│   ├── mocks/                      # MSW
│   │   ├── browser.ts
│   │   ├── handlers.ts
│   │   └── seed/
│   │       ├── clients.ts
│   │       ├── sessions.ts
│   │       ├── trainers.ts
│   │       └── payments.ts
│   │
│   ├── lib/
│   │   ├── utils.ts                # cn() (from shadcn init)
│   │   ├── format.ts               # fmtDate, fmtMoney (Intl)
│   │   └── permissions.ts          # can(role, action) helper
│   │
│   ├── i18n/
│   │   └── ru.ts                   # single dictionary
│   │
│   └── styles/
│       └── rbc.css                 # react-big-calendar shadcn overrides
│
├── components.json                 # shadcn + @reui registry config
├── tailwind.config.ts              # minimal (Tailwind v4 uses CSS-first)
├── vite.config.ts
├── tsconfig.json
├── eslint.config.js
├── .prettierrc
└── package.json
```

---

## Alternatives Considered

| Category | Chosen | Rejected | Why rejected |
|----------|--------|----------|--------------|
| Build tool | Vite | Next.js | No SSR/SEO requirement; SPA with mocks is simpler. |
| Build tool | Vite | CRA | Deprecated. |
| Router | TanStack Router | react-router v7 | No type-safe search params; admin panels live on URL state. |
| Server state | TanStack Query | SWR | Query has richer devtools, mutations, and matches the shadcn examples. |
| Server state | TanStack Query | Redux Toolkit Query | Overkill; Redux store isn't needed. |
| UI state | Zustand | Redux Toolkit | 20 LOC vs. 200 LOC for the same role-toggle. |
| UI state | Zustand | Jotai | Both are fine; Zustand's store-oriented API fits role+sidebar better. |
| Forms | rhf + zod | Formik | rhf is what shadcn documents; faster, smaller. |
| Forms | zod | yup / valibot | Zod is shadcn-documented; valibot is promising but ecosystem still smaller. |
| Mocks | MSW | json-server | json-server is a real HTTP server; MSW runs in-browser, simpler to ship. |
| Mocks | MSW | plain imports | Hooks bypass the network seam → painful real-API swap. |
| Calendar | react-big-calendar | FullCalendar | Timeline/Resource views are paid. |
| Calendar | react-big-calendar | Custom | Week-grid + drag = 2-3 days of work for nothing. |
| Charts | Recharts (via shadcn Chart) | Visx / ECharts | Overkill; Recharts covers dashboard needs. |
| i18n | None (dict + Intl) | i18next | RU-only requirement, no need for an i18n runtime. |
| Styling | Tailwind v4 | Tailwind v3 | shadcn@3 + ReUI target v4; v3 is legacy. |
| Package manager | pnpm | npm / yarn | Faster, disk-efficient, workspace-ready. |

---

## Installation Cheat-Sheet

```bash
# 1. scaffold
pnpm create vite@latest sportzal-adminka -- --template react-ts
cd sportzal-adminka

# 2. Tailwind v4 + shadcn
pnpm add tailwindcss @tailwindcss/vite
pnpm dlx shadcn@latest init

# 3. add ReUI registry to components.json, then:
pnpm dlx shadcn@latest add button input label card dialog dropdown-menu \
  sheet sidebar table tabs tooltip badge avatar separator select form \
  field checkbox radio-group switch textarea calendar popover command \
  sonner skeleton alert-dialog scroll-area chart sidebar-07 dashboard-01
pnpm dlx shadcn@latest add @reui/data-grid @reui/date-selector \
  @reui/filters @reui/timeline @reui/stepper

# 4. core libs
pnpm add @tanstack/react-router @tanstack/react-query @tanstack/react-table \
  zustand react-hook-form @hookform/resolvers zod \
  date-fns react-big-calendar recharts lucide-react sonner
pnpm add -D @tanstack/router-plugin @types/react-big-calendar

# 5. mocks
pnpm add -D msw @faker-js/faker
pnpm dlx msw init public/ --save

# 6. dev
pnpm add -D eslint @eslint/js typescript-eslint eslint-plugin-react-hooks \
  eslint-plugin-react-refresh eslint-plugin-tailwindcss prettier \
  prettier-plugin-tailwindcss vitest @testing-library/react jsdom \
  husky lint-staged
```

---

## Open Decisions

These are not blockers, but the roadmap should flag them:

1. **Scheduler final choice.** Validate react-big-calendar with a real "drag session to reschedule" prototype in Phase "Schedule". If UX feels limiting (especially for per-trainer Resource/Timeline), revisit FullCalendar (and its license cost). **Owner:** Schedule phase.

2. **URL structure for filters.** Before coding Clients list, agree on a canonical query-string shape (`?status=active&subscription=expiring&page=2&sort=-createdAt`) — it becomes the de-facto API contract for the future backend. **Owner:** Clients phase.

3. **Command palette (`cmd+k`) scope.** shadcn `command` block can act as a global navigator ("go to client 'Иван Петров'", "open schedule for today"). Nice UX, adds ~half a day. Defer to Phase "Polish" unless the demo script requires it.

4. **Notifications center data model.** Real notifications will eventually come from a WebSocket/SSE stream. For v1, keep it a plain `GET /api/notifications` poll (staleTime 60s). Document that the contract is "a list; server decides what's unread" — no client-side read/unread logic.

5. **Role-permission matrix.** The "Reception can see X but not Y" rules need a single source of truth (`src/lib/permissions.ts`). Draft this table in the UX phase before building feature screens, so gating doesn't leak into every component.

6. **Bundle size target.** rbc + recharts + ReUI patterns can push the initial bundle over 500 KB gz. Decide during the dashboard phase whether to route-split (`lazy()` per route) — easy with TanStack Router.

7. **Persistence of the role/theme across sessions.** Use `zustand/middleware#persist` to `localStorage` — trivial, but confirm this is desired for demos (a demo might prefer "always reset to Owner" on reload).

---

## Sources

All references were fetched live via Context7 on 2026-04-21 (confidence HIGH unless marked).

- shadcn/ui docs — `ui.shadcn.com` (Context7 `/websites/ui_shadcn`, 1948 snippets) — install/CLI, Sidebar CSS vars, Dark Mode, Data Table, Form (rhf+zod), Chart component, Blocks.
- ReUI docs — `reui.io` / `keenthemes/reui` (Context7 `/keenthemes/reui` + `/websites/reui_io`, ~600 snippets total) — registry config for `components.json`, `@reui/*` CLI install, Data Grid, Date Selector, Timeline, Filters, Stepper.
- TanStack Router docs — Context7 `/tanstack/router` v1.114+ — file-based routing, typed search params, Vite plugin.
- TanStack Query docs — Context7 `/tanstack/query` v5 — queryKey, queryFn, staleTime patterns.
- TanStack Table docs — underpins both shadcn Data Table and ReUI Data Grid.
- MSW docs — Context7 `/websites/mswjs_io` (897 snippets) — `setupWorker`, conditional mocking in Vite, `http`/`HttpResponse`/`delay`, Vitest recipe.
- Zustand docs — Context7 `/pmndrs/zustand` v5.
- Recharts — Context7 `/recharts/recharts` v3.
- react-big-calendar — Context7 `/jquense/react-big-calendar` — date-fns localizer, RU culture.
- date-fns locale `ru` — official package docs.
- Intl — MDN (general knowledge, well-known API).
- faker-js — official docs, `ru` locale.

---
*Research performed for `/gsd-new-project` Phase 6. File is the single source of truth for stack decisions; PITFALLS / FEATURES / ARCHITECTURE research can be added later as separate siblings.*
