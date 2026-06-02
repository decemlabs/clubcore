# Phase 69: Client Read Endpoints + PWA Stack Alignment - Context

**Gathered:** 2026-05-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Two bundled deliverables on top of the Phase 68 client-auth foundation:

1. **Client-scoped READ endpoints** over existing domains, all mounted under `/api/v1/client`:
   - **Home** — active membership (plan, days-left, freeze status), nearest upcoming booking, expiring-soon indicator (CHOME-01..03)
   - **History** — visits, PT-sessions (ownership via `pt_packages.client_id`), payments incl. refunds (CHIST-01..03)
   - **Catalogs** — membership plans, PT-packages, trainers (name/specialization only) for browsing (CPLAN-01..03)
   - Every **owned** read is IDOR-safe: mandatory `client_id` filter + `assert_owns()` → 404-collapse (D-20-IDOR). The IDOR sweep covers all owned resource types.

2. **PWA stack alignment** — `apps/client-pwa` joins the monorepo: pnpm workspace (`bun.lock` deleted), JS→TS allowJs ramp, Vite 5→6, shared ESLint/Prettier/import-linter, `@clubcore/api-client` consumed via a thin `clientFetcher.ts` (own cookie names + refresh URL), react-router v6 kept. Build must pass typecheck + lint + test (PWA-01..04, PWA-06..07).

**In scope:** CHOME-01..03, CHIST-01..03, CPLAN-01..03, PWA-01..04, PWA-06, PWA-07. Read surface only. PWA stack alignment + verified build (NOT screen wiring).

**Out of scope:**
- **PWA-05** (screens running on real backend) → **Phase 71**. This phase verifies the *build/stack*, not live screen wiring.
- Client bookings / cancellation / QR check-in → Phase 70 (CBOOK/CCHK).
- Client checkout / ЮKassa → Phase 71 (CPAY).
- Net-new domains (Chat, Referral, trainer reviews, notification inbox, gym-info) stay on mock data / "в разработке" placeholder, no backend calls (PWA-06).
- React 19 bump (staying on React 18.3.1 this phase).

</domain>

<decisions>
## Implementation Decisions

### Home Data Shape (CHOME-01..03)
- **D-69-01:** **Hybrid contract.** Granular endpoints are the real contract (`GET /client/membership`, `GET /client/bookings?upcoming=1` — the upcoming-bookings query is reused by the Book screen later), PLUS a thin server-side fan-out `GET /client/home` returning `{ membership, nextBooking, expiringSoon }` that **reuses the same query functions** (no duplicated logic). Home screen gets one round-trip; individual resources stay independently reusable and independently IDOR-tested.
- **D-69-02:** **Server-derived temporal fields.** Membership response returns `end_date` PLUS computed `daysUntilEnd` (int) and `expiringSoon` (bool), reusing the existing expiring-window logic (`?expiring=true&within=N` precedent) and Europe/Moscow / `gym_date` discipline. PWA renders only — no client-side date math (avoids the DST/TZ risk the project explicitly bans).
- **D-69-03:** **Empty states are 200, not 404.** No active membership → `GET /client/membership` returns 200 with `null` (or `{membership: null}`); no upcoming bookings → 200 with empty list; composite `/client/home` returns `null` in those slots. The client always owns their own scope, so "nothing" is a valid state — never conflated with the IDOR 404-collapse.

### Catalog Endpoints (CPLAN-01..03)
- **D-69-04:** **New `client_`-prefixed catalog routes** (e.g. `GET /client/plans`, `/client/pt-packages`, `/client/trainers`) under the `Client-Portal` OpenAPI tag (D-20-OPENAPI), reusing staff query logic internally. Do NOT point the PWA at staff catalog endpoints — that would leak the frozen staff contract/fields and entangle the staff surface with client auth.
- **D-69-05:** **Client-safe field projection.** Expose only purchase-relevant fields: plan name / price (kopecks) / duration / description; PT-package name / sessions / price; trainer name + specialization. Strip owner-only economics, `freeze_days_limit` internals, audit / `created_by`, soft-delete flags, and any inactive/archived items. Trainer ratings/reviews stay mock (out of scope).

### PWA TypeScript Ramp (PWA-01..04)
- **D-69-06:** **Minimal bootstrap ramp.** Set up `tsconfig` (allowJs + strict), join the pnpm workspace, Vite 5→6, shared ESLint/Prettier/import-linter boundary; write all NEW code (`clientFetcher.ts`, api-client wiring) in TS. Leave existing `.jsx`/`.js` screens as-is (file-by-file ramp continues in later phases). Lowest-risk path that unblocks Phase 71 wiring without rewriting the design-delivered UI.
- **D-69-07:** **Stay on React 18.3.1.** Do not bump to React 19 this phase. The roadmap scopes stack alignment to pnpm/TS/Vite-6, not React. Avoids React 19 migration risk on a frozen design; can bump in a later phase.

### PWA Service Worker & Test Bar (PWA-04, PWA-07)
- **D-69-08:** **`vite-plugin-pwa` (Workbox)** for installability. Declarative manifest + precache of the app shell; `/api/*` excluded from caching via `navigateFallbackDenylist` + no runtime-caching rule for the API origin (PWA-07: SW must NEVER cache `/api/*` — no stale authed data). Battle-tested over a hand-rolled SW.
- **D-69-09:** **Vitest + a real smoke test.** Add Vitest (matching admin-web / api-client) plus a minimal meaningful test (`clientFetcher` unit test + one render-without-crash) so the `pnpm test` CI gate is real, not hollow. Full UI coverage is not attempted this phase.

### Claude's Discretion
- History endpoint pagination shape — follow the project `{items, total, page, pageSize}` convention; page size / default ordering (likely `created_at`/`gym_date DESC`) is planner's choice.
- Module placement of the read endpoints — `app/modules/client_portal/` aggregator is locked (D-20-MODULE); relationship to the Phase-68 `client_auth` module (sibling vs co-location of shared principal/deps) is planner's call, consistent with composition-root patterns.
- `clientFetcher.ts` internals — refresh-on-401 retry behavior, error envelope mapping, CSRF header handling — mirror staff/admin-web conventions unless a reason to diverge.
- Per-IP / proxy handling, exact TS strictness flags, and `import-linter`-equivalent ESLint boundary zones for the PWA — planner to choose, consistent with existing infra.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` § Phase 69 — goal + scope anchor (verification anchor).
- `.planning/REQUIREMENTS.md` — CHOME-01..03, CHIST-01..03, CPLAN-01..03, PWA-01..04, PWA-06, PWA-07 (locked requirement IDs for this phase; PWA-05 is Phase 71).
- `.planning/phases/68-client-auth-foundation/68-CONTEXT.md` — the client-auth foundation this phase builds on (`ClientPrincipal`, `require_client()`, `cc_client_*` cookies, `/api/v1/client` mount, OTP/session stack).

### v2.0 locked decisions (carry-forward — DO NOT re-litigate)
- **D-20-IDOR** — every owned endpoint: mandatory `client_id` repo param + `assert_owns()` → 404-collapse (anti-oracle); parametrized IDOR sweep covers all owned resource types.
- **D-20-MODULE** — `app/modules/client_portal/` aggregator; raw-SQL cross-module reads (D-54-08 precedent); Protocol-slot writes; zero new `ignore_imports`.
- **D-20-OPENAPI** — single `openapi.json` extended additively: `Client-Portal` tag + `client_` operationId prefix; staff paths byte-identical to `contract-freeze-v1.11.0` (drift gate + `AssertNonNever` stay green).
- **D-20-PWA-ROUTER** — react-router v6 kept in `client-pwa`; no TanStack Router migration.

### Existing backend code to reuse / mirror (full paths)
- `apps/backend/app/core/dependencies.py` — `require_client()` + `ClientPrincipal` (Phase 68); the auth gate for every new `/client` read endpoint.
- `apps/backend/app/api/v1/router.py` (L94) — `/api/v1/client` mount point (`client_auth_router`); mount the new client_portal read router here.
- `apps/backend/app/modules/reports/` — read-only module discipline precedent (raw-SQL `text()` cross-module reads, no `models.py`, no business-table writes, D-54-07/08) — the template for `client_portal` reads.
- `apps/backend/app/modules/memberships/` — membership status + freeze + expiring-window (`?expiring=true&within=N`) logic to reuse for D-69-02 server-derived `daysUntilEnd`/`expiringSoon`.
- `apps/backend/app/modules/bookings/` (`client_scoped_bookings_router` pattern, mounted under `/clients`) — upcoming-bookings query source for D-69-01 `nextBooking`.
- `apps/backend/app/modules/pt_sessions/` + `pt_packages/` — PT-session history; ownership resolved via `pt_packages.client_id` (CHIST-02).
- `apps/backend/app/modules/payments/` — payment + refund history (signed-amount ledger) for CHIST-03.
- `apps/backend/app/modules/membership_plans/`, `pt_packages/`, `trainers/` — catalog sources for D-69-04/05 client-safe projections.
- `apps/backend/tests/conftest.py` (SAVEPOINT harness, `async_client` over ASGITransport) + `apps/backend/tests/integration/` — pattern for the parametrized IDOR sweep (D-20-IDOR).

### PWA stack alignment (full paths)
- `apps/client-pwa/package.json` — currently `name: gym-app`, bun, React 18.3.1, react-router-dom 6.26.2, Vite 5.4.8; no real lint/test. Target: pnpm workspace member, Vite 6, TS, Vitest.
- `apps/client-pwa/bun.lock` — **delete** (PWA-01); single `pnpm install` at root.
- `apps/client-pwa/vite.config.js` — migrate to Vite 6 (+ `vite-plugin-pwa`).
- `pnpm-workspace.yaml` — already globs `apps/*`; client-pwa joins automatically once manifest is workspace-shaped.
- `packages/api-client/` — `@clubcore/api-client` (typed fetcher + `schema.d.ts`); consumed via the new thin `apps/client-pwa/src/.../clientFetcher.ts` (PWA-03).
- `apps/admin-web/` — reference for ESLint/Prettier/Vitest config conventions (do NOT modify; frozen mock-reference).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 68 client-auth primitives** — `require_client()`, `ClientPrincipal`, `cc_client_*` cookies, `/api/v1/client` mount: every Phase 69 read endpoint sits behind `require_client()`.
- **Reports read-only discipline** (`app/modules/reports/`) — raw-SQL `text()` cross-module reads, owner-only, no `models.py`: the exact pattern `client_portal` reads should mirror (swap owner-only for client-owned-scope).
- **Expiring-window logic** (`memberships` `?expiring=true&within=N`) — reuse for server-derived `daysUntilEnd`/`expiringSoon` (D-69-02), keeping Europe/Moscow determinism.
- **`client_scoped_bookings_router`** pattern + `pt_sessions_package_scoped_router` — composition pattern for client-scoped reads that keeps leaf modules dependency-clean.
- **SAVEPOINT + `async_client` ASGITransport test harness** — directly supports the parametrized IDOR sweep across all owned resource types.
- **`@clubcore/api-client`** typed fetcher + `schema.d.ts` (+ admin-web's `http` services) — reference for the PWA `clientFetcher.ts` shape.

### Established Patterns
- **IDOR 404-collapse** — get-by-ID on owned resources never reveals existence to a non-owner; mandatory `client_id` repo param (D-20-IDOR). Distinct from D-69-03 empty-state 200s (own scope, nothing there).
- **Anti-oracle convergence** + Europe/Moscow date discipline carry over from Phase 68 / cron-window precedent.
- **Pagination** — `{items, total, page, pageSize}`, never bare arrays (project convention) for history endpoints.
- **OpenAPI additive discipline** — staff paths byte-stable; new client paths under `Client-Portal` tag with `client_` operationId prefix; `schema.d.ts` regen + forward-guards.

### Integration Points
- New `client_portal` read router mounted at `/api/v1/client` in `app/api/v1/router.py` (alongside Phase-68 `client_auth_router`).
- New client read endpoints registered behind `require_client()`.
- `client-pwa` enters pnpm workspace; `bun.lock` removed; CI grows PWA typecheck/lint/test gates (drift gate stays green for staff paths).
- `clientFetcher.ts` bridges PWA → `@clubcore/api-client` with `cc_client_*` cookie names + `/api/v1/client` refresh URL.

</code_context>

<specifics>
## Specific Ideas

- Composite `GET /client/home` returns `{ membership, nextBooking, expiringSoon }` with `null` slots when empty.
- Membership payload carries server-computed `daysUntilEnd` (int) + `expiringSoon` (bool) alongside `end_date`.
- Catalog responses are explicit client-safe projections — purchase-relevant fields only; inactive/archived filtered out.
- `vite-plugin-pwa` config must exclude `/api/*` from caching (`navigateFallbackDenylist` + no runtime API caching).
- PWA smoke test = `clientFetcher` unit test + one render-without-crash.

</specifics>

<deferred>
## Deferred Ideas

- **PWA-05 — screens on real backend** — explicitly Phase 71; this phase verifies the build/stack only.
- **React 19 bump for client-pwa** — deferred to a later phase; staying on React 18.3.1 to keep this diff small.
- **Aggressive JS→TS conversion of existing screens** — file-by-file ramp continues in later phases; this phase converts only new code.
- **Full PWA UI test coverage** — only a smoke test this phase; broader coverage once screens are wired (Phase 71+).
- **Trainer ratings/reviews** — net-new domain, stays mock (PWA-06).

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 69-Client Read Endpoints + PWA Stack Alignment*
*Context gathered: 2026-05-29*
