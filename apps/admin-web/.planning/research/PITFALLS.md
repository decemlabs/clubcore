# Domain Pitfalls — SportZal Adminka

**Domain:** React admin panel (gym CRM), mock-data-first, shadcn/ui + reui.io, RU-only, two roles toggled in UI.
**Researched:** 2026-04-21
**Overall confidence:** MEDIUM-HIGH (training-knowledge-based; WebFetch and Context7 were unavailable at research time — flagged per-item where applicable).

> How to read this file: each pitfall follows the pattern **What it looks like → Why it happens → How to avoid → Code-review checklist**. Topics are grouped in the order requested. An "Anti-features" list at the end catalogs things we should explicitly NOT build in v1.

---

## 1. Mock-First Apps That Never Successfully Migrate

The goal of SportZal v1 is to build on mock data such that "replace mocks with a real API" is a *local* change. The dominant failure mode is that the UI absorbs mock shapes and mock timing, and the migration turns into a rewrite.

### 1.1 UI coupled directly to in-memory shapes (no DTO boundary)

- **What it looks like:** A `ClientCard` component reads `client.memberships[0].visitsLeft` where `memberships` is the internal JS array the mock store happens to expose. The real API returns `{ memberships: { data: [...] } }` or requires a separate `/clients/:id/memberships` call, and half the components break.
- **Why it happens:** Mocks are convenient JS objects; there's no type-level or runtime barrier forcing developers to go through a boundary.
- **How to avoid:**
  - Define **two type layers**: `ApiClient` (wire shape, the future backend contract, as DTO) and `Client` (domain/UI model). Even when they are identical today, keep the alias.
  - Centralize all mock access behind a **service layer** (`clientsService.list()`, `clientsService.getById()`). UI never imports the mock store directly.
  - Use **Zod/Valibot schemas** for mock responses. Validate on the way out of the mock. When the real API ships, the schema stays; the transport changes.
- **Review checklist:**
  - [ ] Does this component import anything from `mocks/**`? (Should be no.)
  - [ ] Is the data fetched through a service/hook, not a direct store read?
  - [ ] Is there a DTO type and a domain type, even if they're currently a re-export?

### 1.2 Synchronous mock calls break async assumptions

- **What it looks like:** `const clients = mockStore.listClients()` returns immediately. UI renders. Later the real API requires `await` — every call site needs loading/error handling retrofitted.
- **Why it happens:** Mocks "just work" synchronously; no one enforces async discipline until too late.
- **How to avoid:**
  - All service methods return `Promise`, always. Even if the mock resolves synchronously, wrap with `Promise.resolve()` or `await new Promise(r => setTimeout(r, 150))`.
  - Add an **artificial latency** (150-400ms) and **random failure injection** (1-5% error rate in dev) so loading and error paths get exercised daily.
  - Use TanStack Query from day one so components already think in terms of `data | isPending | isError`.
- **Review checklist:**
  - [ ] Does this service method return a Promise?
  - [ ] Does the UI handle `isPending`, `isError`, and empty states?
  - [ ] Is there at least one scenario in the app that reliably reproduces a loading state > 200ms?

### 1.3 Missing error / loading states ("silent crashes" after migration)

- **What it looks like:** In dev everything renders instantly. In prod, a 3-second network hiccup shows a blank screen; a 500 from the backend shows a cryptic white page.
- **Why it happens:** Mocks never fail. Developers never see the empty or error branches, so they never write them.
- **How to avoid:**
  - Enforce a **three-state contract** for every data view: `loading` (skeleton, never a spinner-dot alone), `empty` (illustrated empty state with a call-to-action), `error` (message + retry).
  - Add a **global error boundary** per route plus **React Query's `useQuery` error surfaces**.
  - Add a dev-only "Chaos mode" toggle that forces 20% error rate and 2s latency on all mock calls.
- **Review checklist:**
  - [ ] Does the list/table render a skeleton, empty state, and error state?
  - [ ] Is there a retry affordance on error?
  - [ ] Was this screen tested with Chaos mode enabled?

### 1.4 Wire-unsafe data types

- **What it looks like:** IDs that are array indices (`id: 0, 1, 2`) collide after deletes; `Date` objects that silently become strings after `JSON.stringify` / HTTP; numbers for currency that lose cents on reload; enums that are free-form strings.
- **Why it happens:** Mocks use ergonomic JS types; nothing enforces JSON-serializability.
- **How to avoid:**
  - **IDs:** always strings, generate UUIDs (crypto.randomUUID()) in the mock. Never array indices. Never reuse after delete.
  - **Dates:** store as ISO strings (`"2026-04-21T10:00:00Z"`) or, for dates without time (birthday, membership end date), as ISO date-only (`"2026-04-21"`). Parse at the boundary, not in the store.
  - **Money:** store as integer minor units (kopecks: `5000` = 50₽) or a decimal string. Never IEEE-754 floats for currency.
  - **Enums:** use TS string-literal unions plus a Zod enum validator; do not tolerate free strings.
- **Review checklist:**
  - [ ] Does this record round-trip through `JSON.parse(JSON.stringify(x))` unchanged?
  - [ ] Are all IDs UUIDs?
  - [ ] Are currency fields integers (minor units) or typed as `Money`?
  - [ ] Are dates ISO strings at the data boundary?

### 1.5 Mock store mutates and the UI depends on reference identity

- **What it looks like:** A mock `update` mutates the object in place. React doesn't re-render because the reference didn't change. Or, worse, it *does* re-render when identity happens to change and breaks when the real API returns fresh objects.
- **Why it happens:** In-memory stores feel like databases but share object identity with the view.
- **How to avoid:** The mock store should return **structurally cloned, frozen** copies on reads. Mutations produce new objects. This matches real-API behavior.
- **Review checklist:**
  - [ ] Does the mock `get` / `list` return a deep clone?
  - [ ] Are mock entities `Object.freeze`d in dev?

### 1.6 No pagination / filtering envelope

- **What it looks like:** Lists are returned as a raw array. Real API returns `{ items, total, nextCursor }`. Every list screen has to change.
- **How to avoid:** Decide the envelope now (`{ items: T[], total: number, page: number, pageSize: number }` or cursor-based) and return it from the mock. Tables consume the envelope from day one.
- **Review checklist:**
  - [ ] Does every list endpoint return an envelope, not a bare array?
  - [ ] Does the table component read `total` from the envelope for pagination?

---

## 2. shadcn/ui Mistakes

shadcn is "copy the code into your repo." That's a superpower and a footgun — the code is *yours*, including every mistake you graft into it.

### 2.1 Copy-pasting components and never updating — upstream drift

- **What it looks like:** Someone `npx shadcn add button` in month 1, hand-edits it in month 2, and in month 6 upstream has fixed three a11y bugs and added a new variant. You have neither.
- **Why it happens:** shadcn doesn't give you an "update" command; it assumes you own the code.
- **How to avoid:**
  - Keep a **`components/ui/` boundary** containing only upstream-ish primitives; put all customizations in wrappers (`components/app/Button.tsx` that composes `ui/button.tsx`).
  - Periodically diff against `npx shadcn diff` (if supported) or re-run the generator to a sibling dir and eyeball the diff.
  - Comment any intentional local divergence with `// SHADCN-DIVERGENCE: <reason>` so reviewers don't "fix" it.
- **Review checklist:**
  - [ ] Are custom behaviors in a wrapper, not in `ui/*`?
  - [ ] Are divergences from upstream commented?
  - [ ] Has `ui/*` been diffed against upstream in the last release cycle?

### 2.2 Over-customizing CSS variables until tokens are unmaintainable

- **What it looks like:** `--primary`, `--primary-hover`, `--primary-2`, `--primary-muted`, `--primary-brand`, `--brand-primary-on-surface`… nobody remembers which applies where.
- **Why it happens:** Every new design need invents a new variable.
- **How to avoid:**
  - Stick to the **shadcn token set** (`background`, `foreground`, `primary`, `primary-foreground`, `secondary`, `accent`, `destructive`, `border`, `input`, `ring`, `muted`, `card`, `popover`). Extend *only* if a real semantic need exists.
  - Name tokens by **role, not color** (`--success`, not `--green-500`). Map roles to Tailwind color palette in one place.
  - Define all tokens in one `globals.css` block per theme; no scattered variable definitions.
- **Review checklist:**
  - [ ] Are all new tokens semantic (role-based)?
  - [ ] Is there exactly one source of truth for theme variables?
  - [ ] Are colors never hard-coded in components?

### 2.3 Dark mode broken on third-party or custom components

- **What it looks like:** The default shadcn components flip cleanly between `.light` and `.dark`, but a custom chart or a third-party date picker is stuck on a white background in dark mode.
- **Why it happens:** Components that use raw Tailwind colors (`bg-white`, `text-slate-900`) don't participate in the theme; they're pinned to a fixed palette.
- **How to avoid:**
  - Ban raw palette colors in components: lint rule against `bg-(white|black|slate-\d+|gray-\d+)` etc. in `src/**/*.tsx`.
  - All colors come from **semantic tokens** (`bg-background`, `text-foreground`, `bg-card`, `text-muted-foreground`).
  - For chart libs, pass CSS variables explicitly (`stroke="hsl(var(--primary))"`).
- **Review checklist:**
  - [ ] Does this component render correctly in both themes (visual check)?
  - [ ] Are any raw color utilities used?
  - [ ] Do charts/data-viz read colors from tokens?

### 2.4 Accessibility regressions after restyling

- **What it looks like:** After "making the input prettier," focus rings are gone; buttons have no accessible name; modals don't trap focus.
- **Why it happens:** shadcn ships with good a11y from Radix. Custom restyling strips `focus-visible:ring-*`, removes `aria-*`, or forgets `sr-only` labels on icon buttons.
- **How to avoid:**
  - Preserve `focus-visible:ring-2 focus-visible:ring-ring` on every interactive element.
  - Every icon-only button has `aria-label` or an `<span className="sr-only">`.
  - Use Radix primitives (Dialog, DropdownMenu, Popover) — they handle focus trap, ESC, and `aria-*` correctly out of the box.
  - Add `@axe-core/react` in dev or an eslint-plugin-jsx-a11y config.
- **Review checklist:**
  - [ ] Does every interactive element have a visible focus ring?
  - [ ] Does every icon-only button have an accessible name?
  - [ ] Did axe report zero serious issues for this page?

### 2.5 Form components used without react-hook-form + zodResolver

- **What it looks like:** Controlled inputs with bespoke `useState` per field, ad-hoc validation, no error surfaces.
- **Why it happens:** shadcn form primitives (`Form`, `FormField`, `FormItem`, etc.) are opinionated about RHF + Zod and it's tempting to skip the setup.
- **How to avoid:** Standardize on `react-hook-form` + `zod` + `@hookform/resolvers/zod`. One pattern everywhere. `FormField` always wraps inputs so `FormMessage` surfaces errors.
- **Review checklist:**
  - [ ] Is this form using `useForm` + `zodResolver`?
  - [ ] Is each field wrapped in `FormField` → `FormItem` → `FormControl` → `FormMessage`?

---

## 3. reui.io + shadcn Mixing

**Confidence: MEDIUM.** reui.io positions itself as shadcn-compatible (same Radix + Tailwind + CSS-vars foundation), but the specifics shift over time. Verify against current reui.io docs before locking patterns in.

### 3.1 Conflicting Tailwind configs

- **What it looks like:** reui.io's install instructions say "extend your `tailwind.config.ts` with these plugins/animations"; shadcn's say similar. Half-merged configs produce missing animations or duplicate keyframes.
- **How to avoid:**
  - Create a single `tailwind.config.ts` with **clearly commented sections**: `// shadcn base`, `// reui additions`, `// project additions`.
  - Both libraries rely on `tailwindcss-animate` (historically) — install it once.
  - When reui requires a plugin shadcn doesn't use, verify no conflicting class names (e.g., both defining a `.animate-shimmer`).
- **Review checklist:**
  - [ ] Is there exactly one Tailwind config?
  - [ ] Are the shadcn and reui config contributions labeled and diffable?

### 3.2 Duplicate component names / paths

- **What it looks like:** Both libraries install `components/ui/button.tsx`. Second install silently overwrites the first, or a merge conflict appears.
- **How to avoid:**
  - Namespace them: put reui components under `components/reui/` and shadcn under `components/ui/`. Never install reui with default paths without checking.
  - Pick **one** as the "primitive" library per component family. Rule of thumb: shadcn wins for forms, dialogs, menus (Radix-backed primitives); reui wins for higher-level opinionated blocks (data tables with filters, charts, calendar views) — but confirm per component.
  - Don't alias imports to the same name from both.
- **Review checklist:**
  - [ ] Is every UI component's provenance (shadcn vs reui vs custom) obvious from its path?
  - [ ] Are there any duplicate exports with the same name?

### 3.3 Incompatible theme tokens

- **What it looks like:** reui may ship its own variable names (`--reui-primary`, etc.) or different HSL conventions (some libs use `hsl()` with commas vs space-separated). Components look off-brand.
- **How to avoid:**
  - Single source of truth: **shadcn's variable names** (`--primary`, `--background`, etc.) defined once in `globals.css`. If reui uses different names, add aliasing rules or override at the component level.
  - Audit reui components on install: grep for any hardcoded colors or non-token CSS vars.
  - Keep radii/spacing in one place: `--radius` from shadcn; do not introduce a second radius token system.
- **Review checklist:**
  - [ ] Do reui components render with the project's brand colors?
  - [ ] Is there a single `--radius` token driving all rounded corners?

### 3.4 Different dark-mode triggers

- **What it looks like:** shadcn uses `class="dark"` on `<html>`; some libraries default to `data-theme="dark"` or media query. One theme toggle doesn't flip both sets.
- **How to avoid:** Standardize on `next-themes` (or a minimal equivalent) with `class` strategy. Verify reui components respect `.dark` parent; if not, fork or wrap.
- **Review checklist:**
  - [ ] Does toggling the theme flip every component, including reui ones?

---

## 4. Admin UI UX Traps

### 4.1 Overloaded data tables

- **What it looks like:** 18 columns, 200 rows, no filters, horizontal scroll into oblivion.
- **How to avoid:**
  - Default column set: 5-7 columns. Additional columns in a "Columns" menu, with user preferences persisted (for v1 — localStorage).
  - Always provide **column-level filtering** and **global search**.
  - Density toggle (compact / comfortable). Sticky header on scroll.
- **Review checklist:**
  - [ ] Does the table fit on a 1366×768 screen without horizontal scroll at default columns?
  - [ ] Are filters accessible from the table header?

### 4.2 Missing empty states

- **What it looks like:** New install, no clients yet — the Clients screen is blank and looks broken.
- **How to avoid:** Every list/table must have a **branded empty state**: illustration or icon, one-sentence explanation, primary CTA ("Add first client").
- **Review checklist:**
  - [ ] Does this screen have an empty state component?
  - [ ] Does the empty state have a CTA or next-step hint?

### 4.3 Destructive actions without confirm

- **What it looks like:** "Delete client" with one click, no undo, no confirmation.
- **How to avoid:**
  - All destructive actions go through `AlertDialog` with an explicit "type the name to confirm" pattern for high-stakes operations (delete client with history).
  - Prefer **soft delete + undo toast** (5-second window) over hard confirm for medium-stakes operations.
  - Never use the same color as primary for destructive; use `--destructive` token.
- **Review checklist:**
  - [ ] Does this destructive action have a confirm step OR undo?
  - [ ] Is the destructive button styled with the destructive token?

### 4.4 Modals inside modals

- **What it looks like:** Edit client modal contains an "Add membership" button that opens *another* modal on top. ESC closes both. Focus is lost.
- **How to avoid:** One modal at a time. Nested flows become **side panels/sheets** or **wizards** (multi-step inside one dialog). Reserve modals for quick confirmations and simple forms (< 6 fields).
- **Review checklist:**
  - [ ] Is any modal opening another modal?
  - [ ] Could this be a `Sheet` (side panel) instead?

### 4.5 Forms without autosave / draft — lost work

- **What it looks like:** Reception fills a long form, clicks an outside link by accident, loses everything.
- **How to avoid:**
  - Short forms (< 8 fields): no autosave needed, but warn on navigation away while `isDirty`.
  - Long forms (client profile, schedule): **debounced draft to localStorage** under a stable key; restore on reopen with "Restore draft?" banner.
  - Never silently discard. `beforeunload` on dirty forms.
- **Review checklist:**
  - [ ] Does leaving a dirty form prompt a confirmation?
  - [ ] For long forms, is there a draft in localStorage?

### 4.6 Inconsistent pagination / filtering across modules

- **What it looks like:** Clients uses page numbers; Schedule uses "Load more"; Finance uses infinite scroll. Users are confused.
- **How to avoid:** Pick **one** pagination pattern (page numbers for v1; simple, predictable, sortable, permalinkable) and one **filter UI pattern** (faceted filters in a toolbar, chip-style active filters, clear-all). Document it. Reuse components.
- **Review checklist:**
  - [ ] Is this list using the standard `<DataTable>` component?
  - [ ] Do filters look identical to other modules?

### 4.7 Toasts used for critical errors

- **What it looks like:** "Payment failed" shown as a 3-second toast in the corner. User misses it.
- **How to avoid:** Toasts for non-blocking success/info. Inline alerts or dialogs for critical errors. Toasts that require action (undo) stay until dismissed.
- **Review checklist:**
  - [ ] Is critical information shown in a persistent, in-context location?

---

## 5. Role Toggling Traps

The project uses an in-UI role toggle without real auth. That's fine for v1, but habits set here carry forward.

### 5.1 Believing client-side gating is security

- **What it looks like:** Owner-only endpoints are "protected" by hiding menu items. Later when a real API arrives, the backend has no role checks because "the UI handles it."
- **How to avoid:** Even in mock v1, **structure the mock API as if it were remote**: the mock service refuses reception-role calls with a 403 analog. This trains the team and the backend team to enforce on the server.
- **Review checklist:**
  - [ ] Does the mock service check the active role before returning data?
  - [ ] Is role enforcement duplicated on both UI and (mock) API layers?

### 5.2 Menu shown but route forbidden (or vice versa)

- **What it looks like:** Reception sees "Finance" in the nav, clicks, gets a 403 / "access denied" page. Or: the nav hides Finance but typing `/finance` in the URL still renders it.
- **How to avoid:**
  - Single source of truth: a `routeRegistry` with `{ path, roles, menuGroup }`. Sidebar, breadcrumbs, and route guards all read from it.
  - Route guard component checks roles on mount; sidebar filters by the same predicate.
- **Review checklist:**
  - [ ] Is there exactly one place that declares which roles can see each route?
  - [ ] Does hitting a forbidden URL directly return a proper 403 screen?

### 5.3 Leaking "admin-only" data in responses

- **What it looks like:** The mock returns the full client record including `internalNotes` and `revenueShare`, and the reception-facing component just doesn't render those fields. DevTools shows everything.
- **How to avoid:** The mock service filters fields by role before returning. The UI-level filtering is a redundant second layer, not the primary one.
- **Review checklist:**
  - [ ] Can you open the network tab as a reception user and see fields they shouldn't see? (Should be no.)

### 5.4 Action-level permissions missed

- **What it looks like:** Reception can see a client card (fine) and edit it (not fine). The page-level guard lets them in; no action-level guard stops them.
- **How to avoid:** Centralize with a `can(role, action, resource)` helper. Buttons render conditionally; services re-check.
- **Review checklist:**
  - [ ] Does every mutating button go through `can()`?

---

## 6. Gym Domain Modeling Pitfalls

### 6.1 Membership end-date arithmetic and timezones

- **What it looks like:** "30-day membership starting Oct 27" ends on Nov 26 in Moscow but Nov 25 in some users' render due to a DST or UTC conversion bug.
- **Why it happens:** Date math done on `Date` objects in local TZ; some clients run in UTC; date arithmetic crosses DST boundaries.
- **How to avoid:**
  - Membership periods are **date-only** (`"YYYY-MM-DD"`), not date-times. Use a date-only library (`date-fns` with `startOfDay`, or store as plain strings and compute with `addDays` on `yyyy-mm-dd`).
  - Never `new Date(string)` for a date-only field.
  - All comparisons in UTC *or* in a fixed TZ (Europe/Moscow for a Russian gym) — pick one and document.
- **Review checklist:**
  - [ ] Are membership start/end stored as date-only strings?
  - [ ] Is any code using local `Date` constructor for date-only fields?

### 6.2 Frozen memberships (заморозка) — forgetting to extend

- **What it looks like:** A client freezes their 3-month membership for 10 days. End date is not recalculated. Client loses 10 paid days.
- **Why it happens:** Freeze modeled as a boolean flag rather than as a period.
- **How to avoid:**
  - Model freezes as **periods**: `freezes: { from: Date, to: Date, reason?: string }[]`.
  - `effectiveEndDate = originalEndDate + sum(freezeDurations)` computed, not stored (or stored and recomputed on every freeze change).
  - Business rules: typically a max freeze duration per year, a min advance notice, and no overlapping freezes. Encode as Zod refinements.
- **Review checklist:**
  - [ ] Is freeze a period, not a flag?
  - [ ] Is effective end date derived, not stored by hand?
  - [ ] Are overlapping freezes rejected?

### 6.3 Visit-count vs unlimited vs hybrid memberships

- **What it looks like:** A "10 visits" membership and a "monthly unlimited" share the same shape (`visitsLeft: number`). `null` vs `0` vs `Infinity` confusion renders "-1 visits left."
- **How to avoid:** Discriminated union:
  ```ts
  type Membership =
    | { kind: 'visits'; visitsTotal: number; visitsUsed: number }
    | { kind: 'period'; start: string; end: string }
    | { kind: 'hybrid'; visitsTotal: number; visitsUsed: number; start: string; end: string };
  ```
- **Review checklist:**
  - [ ] Is membership a discriminated union?
  - [ ] Is "remaining visits" computed, not stored?

### 6.4 Group class capacity vs enrollment vs waitlist confusion

- **What it looks like:** Capacity 15, enrolled 16, because a waitlist promotion raced with a cancellation.
- **How to avoid:**
  - Three distinct concepts: `capacity` (fixed), `enrolled` (active enrollments, <= capacity), `waitlist` (ordered).
  - Enroll action: if `enrolled < capacity`, enroll; else, enqueue to waitlist.
  - Cancel action: if enrolled was promoted, pop waitlist head.
  - Invariant: `enrolled.length <= capacity` — enforce and assert.
  - For mock v1: single-user so no races, but the model must still be right.
- **Review checklist:**
  - [ ] Is `enrolled.length` guaranteed `<= capacity`?
  - [ ] Is waitlist ordered and FIFO?
  - [ ] Does canceling auto-promote?

### 6.5 Trainer compensation edge cases

- **What it looks like:** Trainer paid per class; a class was canceled; a client no-showed; two trainers co-taught. Hourly vs percent-of-revenue vs fixed-per-client models mix.
- **How to avoid:**
  - Compensation is a **rule object** attached to a trainer: `{ kind: 'perClass' | 'perClient' | 'percentRevenue' | 'fixed', rate: Money, rules: { countNoShows: boolean, splitWithCoTrainers: boolean } }`.
  - Compute payouts from **actual class occurrences** (with status: `held | canceled | rescheduled`), not from schedule intent.
  - Always persist the compensation rule snapshot on each occurrence so historical rate changes don't retroactively alter old payouts.
- **Review checklist:**
  - [ ] Is compensation a typed rule, not free text?
  - [ ] Does each past class carry its own rate snapshot?
  - [ ] Are no-shows, cancels, and co-teaching handled?

### 6.6 Schedule data model: recurring classes

- **What it looks like:** "Yoga, Mondays 19:00" modeled as 52 separate records. When the trainer changes, you have to edit 52 rows. Or: modeled as a single rule and every single-instance override leaks.
- **How to avoid:**
  - Pattern: **series + exceptions** (like calendar apps). `ClassSeries { rrule, defaultTrainerId, ... }` and `ClassOccurrence { seriesId, date, overrides?: Partial<ClassSeries> }`.
  - Canceling a single instance creates an exception, not a series edit.
- **Review checklist:**
  - [ ] Are recurring classes modeled as series + exceptions?

### 6.7 Payment → membership linkage

- **What it looks like:** Payments and memberships are separate lists; reconciling "did this client actually pay for this membership?" is manual.
- **How to avoid:** Payment has `appliedTo: { kind: 'membership', membershipId } | { kind: 'dropIn' } | { kind: 'other' }`. A membership has `paymentIds[]`. Invariant: a non-free membership has at least one payment or a written-off flag.
- **Review checklist:**
  - [ ] Can you answer "what did this client pay for?" in one query?

---

## 7. React + TanStack Query Pitfalls

**Confidence: HIGH** for listed items (widely documented TanStack guidance).

### 7.1 Non-stable query keys → infinite refetch

- **What it looks like:** `useQuery({ queryKey: ['clients', { filters }], ... })` where `filters` is a new object literal each render → different reference → React Query treats it as a new query → refetch loop.
- **How to avoid:**
  - Query keys must be **serializable and stable**. Pass primitives or memoized objects.
  - Use a **query key factory**: `clientKeys.list(filters) => ['clients', 'list', filters]`. Filters object is a plain JSON value, not a mutable state object.
  - Do not put functions, class instances, or Dates in query keys. Use ISO strings.
- **Review checklist:**
  - [ ] Is the query key from a central `*Keys` factory?
  - [ ] Are all key parts JSON-serializable primitives?

### 7.2 Missing invalidation after mutation

- **What it looks like:** User adds a client via mutation; list doesn't update until refresh.
- **How to avoid:** Every `useMutation` has an `onSuccess` that calls `queryClient.invalidateQueries({ queryKey: clientKeys.all })` or uses `setQueryData` for optimistic updates.
- **Review checklist:**
  - [ ] Does this mutation invalidate affected queries?
  - [ ] For optimistic UX, is there a rollback on error?

### 7.3 Using Query for client-only state

- **What it looks like:** `useQuery` wrapping a `useState`-type value (e.g., the currently-selected tab). Overkill and confusing.
- **How to avoid:** Query is for *server* state (anything that's a snapshot of a remote source of truth). Use `useState`, `useReducer`, or Zustand for client state (filters-in-progress, UI toggles, theme).
- **Review checklist:**
  - [ ] Is this query actually fetching data from a service? If not, it doesn't belong in Query.

### 7.4 `enabled` misused / over-fetching

- **What it looks like:** A detail query fires before the ID is known, hits the mock with `undefined`, and either 404s or returns garbage.
- **How to avoid:** `enabled: !!id`. Type the service to reject undefined IDs. Use `skipToken` (TanStack v5) for strict typing.
- **Review checklist:**
  - [ ] Does every dependent query have a correct `enabled` guard?

### 7.5 `staleTime: 0` everywhere = refetch on every mount

- **What it looks like:** Every tab switch triggers a refetch, loading flickers.
- **How to avoid:** Set sensible defaults on `QueryClient` (e.g., `staleTime: 30_000`, `gcTime: 5 * 60_000`). Override per query only when needed.
- **Review checklist:**
  - [ ] Are global defaults set?
  - [ ] Is per-query `staleTime` justified when present?

### 7.6 Suspense + ErrorBoundary not wired

- **What it looks like:** A thrown error in a query bubbles to the root and crashes the app.
- **How to avoid:** Either don't use `suspense: true` and handle `isError` inline, or wrap each route in an ErrorBoundary with a reset handler (`useQueryErrorResetBoundary`).

---

## 8. Performance Traps in Admin Dashboards

### 8.1 Rendering thousands of rows without virtualization

- **What it looks like:** Clients table with 5,000 rows freezes the browser on first paint.
- **How to avoid:** Use `@tanstack/react-virtual` for any table that can exceed ~200 rows. Even at v1 mock scale (50-100 clients), wire virtualization into the shared `<DataTable>` so it's there for free.
- **Review checklist:**
  - [ ] Is this table using the virtualized `<DataTable>` primitive?
  - [ ] Has the table been tested with 5,000 rows to verify perf?

### 8.2 Charts recomputing every render

- **What it looks like:** Each re-render of the dashboard recomputes aggregates and re-instantiates chart data → jank.
- **How to avoid:**
  - Memoize aggregations (`useMemo`) keyed on raw data identity.
  - Charts take **stable references**. If using Recharts, pass arrays that don't change identity between unrelated renders.
  - Heavy aggregates belong in the query's `select` function, which is itself memoized.
- **Review checklist:**
  - [ ] Is any non-trivial data transformation inside a `useMemo` or a `select`?

### 8.3 Unoptimized re-renders from Zustand selectors

- **What it looks like:** Components subscribe to `useStore(state => state)` and re-render on any state change.
- **How to avoid:**
  - Always use **narrow selectors**: `useStore(s => s.selectedClientId)`.
  - For multi-field reads, use `shallow`: `useStore(s => ({ a: s.a, b: s.b }), shallow)`.
  - Split stores by domain (UI store, auth/role store, filters store) to reduce the surface.
- **Review checklist:**
  - [ ] Does every Zustand consumer use a narrow selector?
  - [ ] Is `shallow` used when selecting multiple fields?

### 8.4 Inline components and functions in render

- **What it looks like:** Table cells define `<Cell />` inside the `render` prop → new component on every render → React unmounts/mounts.
- **How to avoid:** Define cell components at module scope. Pass props, not closures, where possible.

### 8.5 Big bundle from pulling all icons / all chart components

- **What it looks like:** `import * as Icons from 'lucide-react'` or importing an entire charting library when using two chart types.
- **How to avoid:** Named imports only. Tree-shakeable entry points. Verify with a bundle analyzer.

---

## 9. Russian-Locale Specifics

**Confidence: HIGH** (standard locale conventions, well-documented).

### 9.1 Date format and ordering

- **Standard:** `DD.MM.YYYY` (e.g., `21.04.2026`). For short contexts, `DD.MM` or `DD MMM` (`21 апр.`). Full: `21 апреля 2026 г.`
- **How to implement:** Use `date-fns` with `import { ru } from 'date-fns/locale'` and `format(date, 'dd.MM.yyyy', { locale: ru })`. Or `Intl.DateTimeFormat('ru-RU', { ... })`.
- **Never** rely on `toLocaleDateString()` without specifying `'ru-RU'` — defaults to host locale.

### 9.2 First day of week = Monday

- **Trap:** shadcn's `Calendar` (react-day-picker) defaults to Sunday. Calendar widgets look broken to Russian users.
- **How to implement:** `weekStartsOn: 1` in date-fns, `locale={ru}` on react-day-picker, plus `ISOWeek` where relevant.
- **Review checklist:** Is every calendar component configured with `locale=ru, weekStartsOn=1`?

### 9.3 Phone number formatting

- **Standard:** `+7 (XXX) XXX-XX-XX` (mobile) or `+7 XXX XXX-XX-XX`. Leading `8` is legacy and should be auto-converted to `+7`.
- **How to implement:** `libphonenumber-js` with default country `RU`. Mask library (`react-imask` or `imask`) with `+7 (000) 000-00-00`.
- **Trap:** Storing formatted phones. Store **E.164** (`+79991234567`), format only at render.

### 9.4 Currency

- **Standard:** `1 234,56 ₽`. Thousands separator: **non-breaking space** (U+00A0) or narrow NBSP (U+202F). Decimal: comma. `₽` symbol after the amount with a non-breaking space.
- **How to implement:** `new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', minimumFractionDigits: 0 })`. Often gyms show whole rubles; use `minimumFractionDigits: 0` unless kopecks matter.
- **Trap:** Hardcoding `${amount} ₽` — breaks grouping and NBSP.

### 9.5 Pluralization

- **Standard (Russian):** 3 plural forms: one, few, many. "1 клиент / 2 клиента / 5 клиентов".
- **How to implement:** `Intl.PluralRules('ru-RU')` + a lookup map, or a lib like `numeral-ru`. Even without i18n infra, build a small helper.
- **Trap:** `"${n} клиентов"` everywhere — reads wrong for 1, 2, 3, 4.

### 9.6 Name ordering and patronymics

- **Standard:** Surname + Name + Patronymic (ФИО) in formal contexts; Name + Surname in casual. Store as three fields (`lastName`, `firstName`, `middleName`), render as needed.
- **Trap:** Single `fullName` field; search and sorting break.

### 9.7 Time format

- **Standard:** 24-hour (`19:00`, not `7:00 PM`).
- **Trap:** `Intl.DateTimeFormat(undefined, { hour: 'numeric' })` may produce 12h depending on host. Force `'ru-RU'` and `hour12: false`.

---

## 10. General Greenfield-Admin Traps

### 10.1 No design tokens → later theme rework

Covered in §2.2. Start with a semantic token set in `globals.css` from commit one.

### 10.2 No layout shell abstraction

- **What it looks like:** Each page renders its own `<Sidebar />` and `<Header />`. Changing the nav means editing every page.
- **How to avoid:** Single `<AppShell>` component (sidebar + topbar + content slot) used as a router layout. Pages are just the content slot.
- **Review checklist:**
  - [ ] Do pages render header/sidebar directly? (Should be no.)
  - [ ] Is there exactly one `<AppShell>`?

### 10.3 No standard list / detail / form pattern → inconsistent modules

- **What it looks like:** Clients uses a table-with-drawer pattern; Trainers uses a master-detail; Schedule uses cards. Users have to relearn each screen.
- **How to avoid:** Define **three canonical screen types** and implement them as composable templates:
  1. **List screen:** toolbar (search, filters, primary action) + data table + pagination + empty/error states.
  2. **Detail screen:** breadcrumb + header (title, status, primary actions) + tabs for sections + side panel (related info).
  3. **Form screen / modal:** stepper if > 8 fields, grouped sections, sticky submit bar, cancel-with-confirm when dirty.
- Reuse these. Every module implements only its specifics.

### 10.4 No feature-folder structure → everything in `src/components/`

- **What it looks like:** `src/components/` grows to 400 files; client-related, schedule-related, and shared files intermixed.
- **How to avoid:** Feature-first layout:
  ```
  src/
    features/
      clients/
        components/
        hooks/
        services/
        types.ts
      schedule/
      trainers/
      finance/
      dashboard/
      notifications/
    shared/
      ui/            # shadcn primitives
      components/    # cross-feature (DataTable, PageHeader, EmptyState)
      lib/           # date, money, phone, plural helpers
    app/             # routes, providers, layout
    mocks/           # mock data store (will be replaced)
    api/             # service interfaces + implementations (mock now, real later)
  ```

### 10.5 No routing-level code splitting

- **What it looks like:** First paint blocked on loading the entire app bundle.
- **How to avoid:** Lazy-load route components (`React.lazy` or TanStack Router's lazy routes). Prefetch on nav hover.

### 10.6 Mixing state management libs

- **What it looks like:** Redux + Zustand + Context + useState, no rule for which is used when.
- **How to avoid:** One rule:
  - **Server state → TanStack Query.**
  - **Shared UI state → Zustand.**
  - **Local UI state → `useState`/`useReducer`.**
  - **Avoid Context** except for dependency injection (providers: QueryClient, theme, role).

### 10.7 No error and loading boundaries

- Covered in §1.3. Every route has an ErrorBoundary and a Suspense fallback (skeleton).

### 10.8 No testing seams

- **What it looks like:** At month 6, the team decides to add tests; every service call is hardcoded; there's no way to swap a mock.
- **How to avoid:** Services are injected through a provider (`ServicesContext` or a factory passed to the Query client). Mock services today; real services tomorrow; test services in between.

### 10.9 No toolbar of developer utilities

- **What it looks like:** Changing the role or reseeding mocks requires editing code.
- **How to avoid:** A dev-only `<DevToolbar>` with: role switcher, theme switcher, chaos mode toggle, "reseed mocks," "clear localStorage," current build hash. Invisible in prod.

### 10.10 Over-ambitious scope in v1

- **What it looks like:** Attempting real-time updates, audit logs, reports builder, CSV import all in v1.
- **How to avoid:** Ship the three canonical screens per module. Defer everything optional. See Anti-Features below.

---

## Phase-Specific Warnings

| Phase topic | Likely pitfall | Mitigation |
|---|---|---|
| Foundations (tokens, shell, routing) | Tokens bolted on late; shell not truly generic | Define tokens and AppShell in phase 1; refuse to merge module code that renders its own header |
| Clients & memberships | Membership model too simple (flag-based freezes, float money) | Discriminated union for membership kind; freeze as period; money as integer minor units |
| Schedule | Recurring classes done as flat list; TZ bugs | Series + exceptions; date-only or explicit Europe/Moscow |
| Trainers & payroll | Payouts recomputed from current rates, retroactively changing history | Snapshot rate onto each occurrence |
| Finance | Floats for money; reports directly queried on every render | Integer minor units; memoized aggregates via `select` |
| Dashboard | Charts rerender on every role toggle; no loading skeleton | Memoize series; skeleton per widget |
| Notifications | Toasts used for everything; critical notifications disappear | Notification center with persistence; toasts only for transient acks |
| Role toggle | Client-side gating only; menu/route drift | routeRegistry + mock-service role enforcement |
| Theming | Raw color classes leak in | Lint rule banning raw palette colors |
| Real-API migration (future) | Service signatures didn't survive | Define DTO/domain split and schemas from day one |

---

## Anti-Features (Things We Explicitly Will NOT Build in v1)

Each of these is a well-known trap for greenfield admin panels. Defer all of them until user feedback demands them.

1. **Real authentication / password recovery / 2FA.** Role toggle is by design. Do not build a fake login screen — it trains wrong habits.
2. **Real-time / websocket live updates.** Mock data has no backend; fake real-time is noise. Refetch-on-focus via TanStack Query is plenty.
3. **Audit log / activity history.** Large feature; irrelevant without multi-user prod. Defer.
4. **Reports builder / ad-hoc query UI.** Users ask for it; it becomes a second app. Ship a fixed report set per module instead.
5. **CSV / Excel import/export of clients and finance.** High complexity, low v1 value, invites bad data. Defer; add per-module export (CSV) post-v1 only when real backend exists.
6. **Bulk actions on tables (bulk delete, bulk edit).** Always underspecified; easy to destroy data. Defer; single-row actions only in v1.
7. **Granular per-permission RBAC (beyond the two roles).** YAGNI; two roles are scoped.
8. **Client-facing mobile/web portal (booking, self-service).** Explicitly out of scope per PROJECT.md.
9. **i18n infrastructure / English locale.** RU-only; don't pay the i18n tax. But: keep strings in one `strings.ts` per feature so a later i18n pass is mechanical.
10. **SMS / email / push sending.** Notification *center* only — no transports.
11. **Payment integrations (Stripe, CloudPayments, YooKassa, etc.).** Mock payments only.
12. **Offline support / PWA.** Admin is a desk tool; skip.
13. **Nested modals and wizards longer than 3 steps.** Use sheets or dedicated pages instead.
14. **Drag-and-drop schedule editing in v1.** Nice demo, high complexity, hides edge cases (overlap, DST, recurring series). Defer to v2.
15. **Advanced charting (custom cohort analysis, funnels).** Dashboard stays on 4-6 key metrics.
16. **Dense keyboard shortcut system.** One or two (search, new) is fine; full shortcut layer is v2.
17. **Theming beyond light + dark.** No brand themes, no accessibility "high contrast" variant in v1.
18. **User preferences sync (beyond localStorage).** No backend → nowhere to sync to.
19. **Email templates / SMS templates editor.** Out of scope.
20. **Multi-gym / multi-branch support.** Single-gym model; adding multi-tenancy later is a real refactor, but v1 is explicitly one gym.

---

## Sources and Confidence

- **TanStack Query pitfalls (§7):** HIGH — standard guidance from TanStack Query v5 docs and well-known community patterns (TkDodo's blog "React Query" series). WebFetch and Context7 unavailable during this research pass; verify against current docs before locking exact API calls (e.g., `skipToken` availability).
- **shadcn/ui guidance (§2):** HIGH — reflects public shadcn documentation patterns (CSS variable tokens, Radix-backed a11y, RHF+Zod form pattern).
- **reui.io interop (§3):** MEDIUM — reui.io's exact token names, install paths, and dark-mode strategy should be verified against current reui.io docs before implementation.
- **Gym domain modeling (§6):** MEDIUM-HIGH — reflects common patterns in fitness/CRM software (memberships, freezes, recurring classes, trainer payroll). Specific Russian gym regulatory or tax edge cases (e.g., kassovy chek integration, PDn consent UX) are out of scope for v1 and not covered here.
- **Russian locale (§9):** HIGH — well-documented Intl conventions and ICU rules.
- **Admin UX traps (§4) and greenfield traps (§10):** HIGH — decade-old industry wisdom; cross-referenced with common design-system guidance (Nielsen Norman on data tables, Refactoring UI on forms, Shopify Polaris and Atlassian Design System patterns for destructive actions).

**Research gap:** No live WebFetch / Context7 access during this pass. Before Phase 1 implementation, re-verify (a) current shadcn CLI behavior and diff tooling, (b) reui.io's current install flow and token naming, (c) TanStack Query v5 specifics (`skipToken`, `gcTime` vs old `cacheTime`).
