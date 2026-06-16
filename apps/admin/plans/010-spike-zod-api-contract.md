# Plan 010 (spike): Design the runtime API-contract layer (zod) for the mock→backend swap

> **Executor instructions**: This is an INVESTIGATION plan. You will read code
> and write ONE design document — you will NOT modify any source file. Follow
> the steps, answer every question in the deliverable template, and update
> `plans/README.md` (status row AND the zod-decision note) when done. If a
> STOP condition occurs, stop and report.
>
> **Drift check (run first)**: `git diff --stat <baseline SHA from plans/README.md>..HEAD -- src/features src/api src/mocks`
> Drift here doesn't block the spike — but read the changed files fresh rather
> than trusting the excerpts below.

## Status

- **Priority**: P2
- **Effort**: M (investigation + writing; no production code)
- **Risk**: LOW (no code changes)
- **Depends on**: plans/001-init-git-baseline.md (to commit the doc). Plan 007 intentionally left `zod` installed pending this spike's verdict.
- **Category**: direction
- **Planned at**: 2026-06-12 (pre-git; baseline SHA in plans/README.md)

## Why this matters

The entire data layer is built for a backend swap: every page consumes TanStack Query hooks in `src/features/<domain>/api.ts`, and the stated contract is "when the backend lands, only the hook's `queryFn` changes; pages stay untouched." But nothing will *verify* that the real API actually returns what the TypeScript types promise — TS types are erased at runtime. One mis-shaped field from the backend and pages break in ways the error states (plan 003) can't explain. A zod schema layer at the API boundary would: (1) validate mocks against the contract today, (2) validate real responses tomorrow, (3) serve as the machine-readable API spec handed to the backend team. This spike decides whether that's worth the ceremony for THIS project, and produces the design if yes. It also settles whether the currently-unused `zod` dependency stays or goes.

## Current state

- `src/api/client.ts` — fetch wrapper ready for a backend (`BASE_URL` from `VITE_API_BASE_URL ?? '/api'`), `api<T>(path, init)` returns `res.json() as T` (unvalidated cast — the exact hole this spike addresses), plus `mockResponse<T>(value, delay = 0)` used by all hooks today.
- Hook pattern — `src/features/clients/api.ts` (verbatim, representative of all ~18 domains):

  ```ts
  export const clientsKeys = {
    all: ['clients'] as const,
    list: ['clients', 'list'] as const,
    detail: (id: string) => ['clients', 'detail', id] as const,
  };

  export function useClients() {
    return useQuery({
      queryKey: clientsKeys.list,
      queryFn: () => mockResponse<ClientsPageData>(clientsPageData),
    });
  }
  ```

- Types: hand-written per domain in `src/features/<domain>/types.ts` (e.g. `ClientsPageData`, `Client` with nested `visits`, `expiry?`, `plan?`, `trainer?`). Mocks: `src/mocks/<entity>.ts`, registered in `src/mocks/index.ts`, typed against those interfaces (so TS already guarantees mock↔type agreement — the runtime gap is only on the FUTURE real API).
- `zod@^3.24` is installed, imported nowhere.
- Test infra: vitest if plan 002 landed (check `package.json`) — relevant because "validate all mocks against schemas" is naturally a test file.
- One known nuance the design must address: dashboard uses one query key with per-hook `select` (`src/features/dashboard/api.ts` — `useDashboard` and `useDashboardOverview` share `dashboardKeys.all`); validation must happen once per fetch, not per select.

## Commands you will need

| Purpose | Command | Expected |
|---------|---------|----------|
| Inventory | `ls src/features` / `grep -c "useQuery" src/features/*/api.ts` | domain + hook counts |
| Types size | `wc -l src/features/*/types.ts` | complexity signal |
| Typecheck (no-op guard) | `bun run typecheck` | exit 0 before AND after (you changed nothing) |

## Scope

**In scope** (the ONLY writes):
- `plans/research/zod-contract-design.md` (create — the deliverable)
- `plans/README.md` (status row + zod decision)

**Out of scope**:
- ANY file under `src/` — the worked example lives INSIDE the design doc as a fenced code block, not in the codebase.
- Installing or removing anything.

## Git workflow

- Branch: `advisor/010-zod-spike` off `main`. One commit: `docs: zod API-contract design spike`.
- Do NOT push.

## Steps

### Step 1: Inventory the surface

Enumerate every `src/features/*/api.ts`: hook name, query key, mock it resolves, response type, and the type's rough complexity (`wc -l` of its types file; note unions/optionals/dates-as-strings). Produce the table for the doc. Note which domains share one fetch across hooks via `select` (dashboard pattern — grep for `select:`).

### Step 2: Write the worked example (in the doc only)

For the **clients** domain, draft in the doc: a `clientsPageDataSchema` zod schema mirroring `ClientsPageData` (read `src/features/clients/types.ts` carefully — every field), and show both integration directions:
- **Option A — types stay source-of-truth**: schema typed `z.ZodType<ClientsPageData>` (catches schema/type drift at compile time; schema is redundant-but-checked).
- **Option B — schema becomes source-of-truth**: `type ClientsPageData = z.infer<typeof clientsPageDataSchema>` (single definition; but all 18 types files migrate, and z.infer error messages are worse in strict TS).

### Step 3: Analyze the wiring options

In the doc, compare (with code sketches):
1. **Validate in `api<T>()`** — one choke point; activates only when real fetches begin; `safeParse` with a dev-mode `console.error` + a typed `ApiContractError`.
2. **Validate mocks in a test** — a vitest file that parses every mock against its schema (zero runtime cost, catches contract drift in CI… once CI exists).
3. **Both** (likely answer): test validates mocks now; `api()` validates responses later.
Address: bundle cost of zod in the client (~13KB gz — measure or cite), per-response parse cost on large lists, dev-only vs always-on validation, how the dashboard shared-fetch pattern interacts (validate in queryFn, not in select), and error-state UX hookup (plan 003's `PageError` — a contract violation should surface as a query error, distinguishable in dev).

### Step 4: Recommend and decide zod's fate

Write a recommendation section: adopt (which option, which order, effort per domain — S each? — and the first 3 domains to convert) **or** reject (then `zod` gets removed — name the follow-up: a one-line `bun remove zod` task). Be honest: if the backend will be built by the same team mirroring the mocks exactly, say so and weigh it. List open questions for the backend team (envelope format? error shape? dates ISO or epoch? pagination contract?).

### Step 5: Assemble the deliverable

`plans/research/zod-contract-design.md` with EXACTLY these sections: `## Inventory` (Step 1 table) · `## Worked example: clients` · `## Wiring options` · `## Recommendation` · `## Zod verdict (keep/remove)` · `## Open questions for the backend` · `## Effort estimate`. Then update `plans/README.md`: this plan's row, and the "zod gate" note under Dependency notes with the verdict.

**Verify**: file exists with all seven section headings (`grep -c "^## " plans/research/zod-contract-design.md` → ≥ 7); `git status --porcelain` shows ONLY the two in-scope files; `bun run typecheck` still exit 0 (nothing touched).

## Test plan

Not applicable (no code). The deliverable's quality bar: a different agent could implement the recommendation without re-doing this investigation.

## Done criteria

- [ ] `plans/research/zod-contract-design.md` exists with the seven required sections
- [ ] Every `features/*/api.ts` domain appears in the inventory table
- [ ] The zod keep/remove verdict is stated unambiguously in the doc AND in `plans/README.md`
- [ ] `git status --porcelain` → only the deliverable + index
- [ ] `bun run typecheck` → exit 0 (proof of zero code changes)

## STOP conditions

- `src/features/clients/types.ts` is too large/complex to schema by hand (>200 lines of types) — that itself is the finding; write it up with a codegen recommendation (e.g. ts-to-zod) instead of hand-drafting, and say so.
- You catch yourself editing files under `src/` — revert and re-read the scope.

## Maintenance notes

- If adopted, each domain conversion is an S-sized follow-up plan; the doc's "first 3 domains" section seeds them.
- If rejected, remove `zod` promptly (plan 007 left it solely for this verdict) so the dependency list stops lying.
- The "Open questions for the backend" section should be handed to whoever specs the real API — it's the most durable output of this spike either way.
