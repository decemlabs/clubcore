# Zod API-contract design spike (plan 010)

> Paper-only spike, executed inline by the advisor on 2026-06-12 against baseline `5ceb34b`.
> No `src/` files were changed (proof: `bun run typecheck` exit 0, `git status` shows only `plans/`).

**Verdict (TL;DR): KEEP `zod`.** But do **not** build schemas now — there is no runtime data to validate yet (mocks are compile-time-checked against the same TypeScript types). Adopt the contract layer **lazily, one domain at a time, when backend integration begins**, using **Option A** (TS types stay source-of-truth). This document is the implementation-ready design so that work needs no re-investigation.

---

## Inventory

19 feature domains expose **~23 TanStack Query hooks** (2–3 per domain). The 20th domain, `search`, has **no** fetch hook (it is a client-side command index). Every hook today resolves a mock through `mockResponse<T>(value)` (`src/api/client.ts:34`); the documented backend swap replaces only the `queryFn` body with `api<T>(path)`.

**TypeScript already guarantees mock↔type agreement at compile time** (mocks in `src/mocks/*` are typed against the same interfaces). The **only** runtime hole is the future real API response, in `src/api/client.ts:28`:

```ts
return (await res.json()) as T;   // ← unchecked cast: TS types are erased at runtime
```

| Domain | Query hooks | Response type(s) | `types.ts` LoC | Notes |
|--------|------------|------------------|----------------|-------|
| dashboard | 3 (1 `select`) | `DashboardData` (one shared key) | 254 | **Shared key + `select`** — see wiring nuance |
| trainers | 3 | `TrainersData`, `Trainer` (detail) | 201 | 2nd-largest type |
| clients | 3 | `ClientsPageData`, `ClientDetail` | 131 | worked example below |
| attendance | 2 | `AttendanceData` | 139 | |
| plans | 2 | `PlansPageData` | 128 | |
| messages | 2 | `MessagesData` | 108 | |
| settings | 2 | `SettingsData` | 103 | |
| branches | 3 | `BranchesData`, `Branch | undefined` (detail) | 94 | detail returns `T | undefined` |
| reports | 2 | `ReportsData` | 79 | |
| cashbox | 2 | `CashboxData` | 77 | |
| notifications | 2 | `NotificationsData` | 76 | |
| schedule | 2 | `ScheduleData` | 68 | |
| load | 2 | `LoadData` | 58 | |
| finance | 2 | `FinanceData` | 56 | |
| audit | 2 | `AuditData` | 54 | |
| system-settings | 2 | `SystemSettingsData` | 51 | |
| roles | 2 | `RolesData` | 47 | |
| import-export | 2 | `ImportExportData` | 44 | |
| trash | 2 | `TrashData` | 26 | smallest |
| search | 0 | — | — | client-side index, no hook — out of the contract layer |

Aggregate: **~1,794 lines** of hand-written types across 19 `types.ts` files. Only `dashboard` (254) and `trainers` (201) exceed the 200-line "hand-draft is painful" threshold — they are codegen candidates *if/when* converted (see Recommendation).

**Two structural nuances any design must respect:**
1. **Dashboard shared-key + `select`** (`src/features/dashboard/api.ts`): `useDashboard` and `useDashboardOverview` use the **same** `queryKey: dashboardKeys.all`; the second derives a slice via `select: (data) => data.overview`. Validation must run **once per fetch in `queryFn`**, never in `select` (which runs per-observer and would double-validate / validate already-narrowed slices).
2. **Detail hooks return `T | undefined`** (e.g. `branches` detail does `.find(...)`). Real endpoints will 404 instead — the schema validates the *200 body*, not the absent case; the not-found path stays the hook's concern.

---

## Worked example: clients

`ClientsPageData` (`src/features/clients/types.ts`) — 8 nested interfaces, 4 string-union enums, 3 nullable fields. Hand-drafted schema:

```ts
import { z } from 'zod';
import type { ClientsPageData } from './types';

const clientStatus  = z.enum(['active', 'expiring', 'frozen', 'lead', 'expired']);
const planTone      = z.enum(['normal', 'warn', 'danger', 'muted']);
const expiryUrgency = z.enum(['urgent', 'soon', 'normal']);
const planType      = z.enum(['monthly', 'half', 'year']);
const filterTone    = z.enum(['accent', 'warn', 'danger']);
const clientFilter  = z.enum(['all', 'active', 'expiring', 'frozen', 'lead', 'expired']);

const clientPlan = z.object({
  name: z.string(),
  muted: z.boolean().optional(),
  type: planType,
  fillPct: z.number(),
  tone: planTone,
  daysLabel: z.string(),
});
const clientTrainer = z.object({ initials: z.string(), color: z.string(), name: z.string() });
const clientExpiry  = z.object({ top: z.string(), sub: z.string(), urgency: expiryUrgency, daysLeft: z.number() });
const clientVisits  = z.object({ value: z.string(), strong: z.boolean(), total: z.string().optional(), month: z.number() });
const clientLastVisit = z.object({ top: z.string(), sub: z.string(), rank: z.number() });

const client = z.object({
  id: z.string(),
  initials: z.string(),
  color: z.string(),
  name: z.string(),
  hasNote: z.boolean().optional(),
  phone: z.string(),
  tenure: z.string(),
  status: clientStatus,
  plan: clientPlan.nullable(),          // ← `ClientPlan | null`
  planNote: z.string().optional(),
  expiry: clientExpiry.nullable(),      // ← `ClientExpiry | null`
  visits: clientVisits,
  trainer: clientTrainer.nullable(),    // ← `ClientTrainer | null`
  lastVisit: clientLastVisit,
});

const clientFilterTab = z.object({
  filter: clientFilter, label: z.string(), count: z.number(), tone: filterTone.optional(),
});
const clientsSummary = z.object({
  branch: z.string(), total: z.number(), weeklyNew: z.number(),
  expiringSoon: z.number(), expiringDays: z.number(),
});

// ── Option A: TS type is source-of-truth; schema is checked against it ──
export const clientsPageDataSchema = z.object({
  summary: clientsSummary,
  filters: z.array(clientFilterTab),
  clients: z.array(client),
  shownCount: z.number(),
  totalCount: z.number(),
  totalPages: z.number(),
  currentPage: z.number(),
}) satisfies z.ZodType<ClientsPageData>;
```

**Option A — types stay source-of-truth** (recommended). The `satisfies z.ZodType<ClientsPageData>` makes the compiler reject the schema if it drifts from the interface — you get drift detection for free, and the rich JSDoc on the interfaces (every field is documented) stays the canonical spec. Cost: the shape is written twice.
- Caveat: with `exactOptionalPropertyTypes`/strict optionals, `z.ZodType<T>` matching on `.optional()` fields can be fussy; if `satisfies` complains spuriously, annotate as `const schema: z.ZodType<ClientsPageData> = z.object({...})` (loses the inferred output type for local use, which we don't need — hooks already import the interface).

**Option B — schema is source-of-truth**: `export type ClientsPageData = z.infer<typeof clientsPageDataSchema>` and delete the interface. Single definition, but: (1) all 19 `types.ts` files migrate, (2) the documented JSDoc-rich interfaces become inferred types (worse hover/error messages, lost field docs), (3) `z.infer` widens some unions awkwardly under strict TS. **Rejected** for this codebase — the hand-written, heavily-commented types are an asset worth keeping.

---

## Wiring options

**1. Validate in `api<T>()` — the single choke point** (the eventual home):
```ts
export async function api<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { /* …headers… */ });
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  const json = await res.json();
  const parsed = schema.safeParse(json);
  if (!parsed.success) {
    if (import.meta.env.DEV) console.error(`[contract] ${path}`, parsed.error.format());
    throw new ApiContractError(path, parsed.error);   // new subclass of ApiError
  }
  return parsed.data;
}
```
One enforcement point; activates only when hooks switch from `mockResponse` to `api`. A `ApiContractError extends ApiError` surfaces as a TanStack Query error → plan 003's `PageError` renders it; in DEV the `console.error(error.format())` pinpoints the bad field. **This is the durable target.**

**2. Validate mocks in a vitest file** — parse every mock against its schema in CI:
```ts
it('clientsPageData matches its schema', () => {
  expect(() => clientsPageDataSchema.parse(clientsPageData)).not.toThrow();
});
```
Zero runtime cost. **But** mocks are *already* TS-checked against the same interfaces, and Option A already pins the schema to the interface at compile time — so this test mostly re-proves what `tsc` proves. **Low marginal value today**; worth adding the day a domain is converted (cheap insurance once the schema exists).

**3. Both** — the realistic end-state: mocks validated in tests (once schemas exist), responses validated in `api()` (once real fetches begin).

**Costs & facts:**
- **Bundle**: `zod` v3 is ~13 KB gzip. It ships **only if imported** — under lazy adoption, **zero** bundle impact until the first schema is wired. (Plan 004 already code-splits per route, so even then it lands in the chunks that import it.)
- **Parse cost**: `safeParse` on a list of ~30 clients is sub-millisecond; negligible vs. network. Only worth a thought for endpoints returning thousands of rows (none today).
- **DEV-only vs always-on**: recommend **always-on** validation but **DEV-loud / PROD-quiet** — in production a contract violation still throws `ApiContractError` (better a clean error state than a corrupted render), but only DEV logs the full `error.format()`.

---

## Recommendation

**Keep `zod`. Design now (this doc), implement lazily.** Concretely:

1. **Today: write no schemas, wire nothing.** There is no real API to validate; mocks are compile-time-safe. Building 19 schemas now is speculative work that will drift before a backend exists.
2. **At backend-integration time**, adopt **Option A** and wire **path 1** (validate in `api<T>()`). Convert one domain per integration PR — schema lives in `src/features/<domain>/schema.ts`, imported by that domain's `api.ts` hook when its `queryFn` switches to `api()`.
3. **First 3 domains to convert** (when the time comes): **clients** (representative, worked above), **dashboard** (exercises the shared-key/`select` nuance — validate in `queryFn`), **plans** (rich nested type). These three shake out the pattern + the `ApiContractError`→`PageError` wiring; the remaining 16 are mechanical follow-ons.
4. **For `dashboard`/`trainers`** (200+ LoC types), evaluate **`ts-to-zod`** codegen instead of hand-drafting — but keep Option A semantics (generated schema checked against the interface). Don't add codegen for the whole project; it's only worth it for the two big ones.

Why keep rather than remove-and-re-add: the decision to adopt is now *made and designed*, so the dependency has a committed purpose (not speculative debris). Keeping it + this doc means the future PR just writes a schema; removing it means a future PR must re-litigate the choice. Bundle/maintenance cost of an unimported dep is ~nil.

**Revisit-and-remove trigger:** if two milestones pass with no backend work started and no domain converted, the earmark has gone stale — run `bun remove zod` then and reopen this doc if it later returns.

---

## Zod verdict (keep/remove)

**KEEP** `zod@^3.24` in `package.json`. It is the chosen tool for the API-contract boundary (Option A, validate-in-`api()`), to be implemented per-domain at backend-integration time. It is intentionally unimported until then — this document is the record of *why* it's installed, which resolves the "unused dependency lies to contributors" concern that plan 007 flagged.

---

## Open questions for the backend

These are cheaper to answer before the API is built; hand this list to whoever specs it:

1. **Response envelope**: bare resource (`{...}`) or wrapped (`{ data: {...}, meta: {...} }`)? If wrapped, schemas wrap once in a generic `envelope(schema)` and pagination moves into `meta`.
2. **Error shape**: what does a 4xx/5xx body look like (`{ error: { code, message, fields? } }`)? `ApiError` should parse it so `PageError` can show a real message, not just `statusText`.
3. **Dates**: ISO-8601 strings or epoch ms? Today the UI carries **pre-formatted Russian display strings** (`top: "2 мая"`, `sub: "через 2 дня"`) plus **numeric sort keys** (`daysLeft`, `rank`, `month`). Decide whether the backend returns raw dates (then the client formats via `lib/format.ts`) or the display strings (current shape). This materially changes the schemas and is the single biggest contract question.
4. **Pagination**: the `ClientsPageData` shape carries `shownCount/totalCount/totalPages/currentPage` inline. Cursor or offset? Server-driven page size? Does the list endpoint return the summary+filters every page, or are those a separate call?
5. **Nullability**: confirm the backend's `null` vs **omitted** semantics for the optional/nullable fields (`plan`, `expiry`, `trainer` are `... | null`; `muted`, `total`, `planNote`, `hasNote`, `tone` are `?:`). Zod `.nullable()` vs `.optional()` vs `.nullish()` must match exactly.
6. **Enum stability**: the string unions (`ClientStatus`, `PlanTone`, …) are derived from the design templates. Will the backend emit exactly these literals, or freer strings the client maps? If the latter, schemas use `z.string()` + a mapping layer, not `z.enum`.

---

## Effort estimate

| Work | Effort | When |
|------|--------|------|
| `api<T>()` choke-point + `ApiContractError` + `PageError` wiring | **S** (~1 file, one-time) | first backend fetch |
| Schema per domain — small types (≤130 LoC, 16 domains) | **S** each, incremental | as each domain's `queryFn` switches to `api()` |
| Schema for `dashboard` (254) / `trainers` (201) | **S–M** each (consider `ts-to-zod`) | when those domains integrate |
| Optional: mock-validation vitest per converted domain | **XS** add-on | alongside each schema |

No work is on the critical path today; the entire layer is deferred until the mock→backend swap starts. Total when fully adopted: roughly 19 × S, spread across the backend-integration milestone — never a single big-bang task.
