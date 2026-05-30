# Phase 71: Client Checkout + Full PWA Screen Wiring - Context

**Gathered:** 2026-05-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Two bundled deliverables on top of the Phase 68–70 client foundation:

1. **Client-initiated ЮKassa checkout** from the PWA — membership purchase/renewal (CPAY-01) and PT-package purchase (CPAY-02), reusing the **existing staff-side `online_payments` machinery**: server-authoritative price (raw-SQL read), webhook-only activation, 54-ФЗ email gate (CPAY-04), idempotent checkout (CPAY-05), anti-oracle redirect-back (CPAY-03).
2. **Wire the 6 core PWA screens to the real backend** (PWA-05), replacing `apps/client-pwa/src/data/*.js` mocks: **Home** (`HomeScreen`), **Profile** (`ProfileScreen`), **Book** (`BookScreen`), **Plans** (`PlansSheet`), **Checkout** (`CheckoutSheet`), **QR** (`QRSheet`).

**In scope:** CPAY-01..05, PWA-05. Client checkout write path + the 6 screens running on the real client backend.

**Out of scope:**
- **Net-new screens** (Chat, Referral, trainer reviews, notification inbox, gym-info) → "coming soon" placeholder, **zero** backend calls (success criterion #5). Decided here: strip their mock data (D-71-08/09).
- Service worker must **never** cache `/api/*` (carried from D-69-08; SW denylist already in place).
- Refund flows from the client side (staff-only; unchanged).
- `Client-Portal` OpenAPI tag freeze, `_v20Checks` guards, CI gates, live E2E → **Phase 72**.
- Phase-70 booking/QR endpoints themselves (this phase *consumes* them for the Book/QR screen wiring).

**⚠ Dependency:** Phase 70 (Client Bookings + QR Self Check-In) is **Not started** in ROADMAP.md and Phase 71 depends on it. Book/QR screen wiring needs Phase 70's endpoints to exist. Decisions captured here are stable, but Phase 70 must land before this phase executes its Book/QR wiring.

</domain>

<decisions>
## Implementation Decisions

### Checkout Backend Reuse (CPAY-01..05)
- **D-71-01:** **Extract the actor-agnostic core of `_sell_subject`.** Pull the shared body (email gate, idempotency key handling, replay check, ЮKassa create, row insert, audit emit) into a helper that BOTH the staff `online_payments` service AND a new `client_portal` checkout write-slot call — actor identity parameterized. Keeps the staff path byte-identical (`contract-freeze-v1.11.0` / drift gate stays green), no logic duplication, and respects D-20-MODULE (Protocol-slot write from `client_portal`). Reference body: `apps/backend/app/modules/online_payments/service.py:170-380` (`_sell_subject` / `sell_membership` / `sell_pt_package`).
- **D-71-02:** **Client-initiated attribution.** `online_payments.created_by_user_id = NULL` (the column is already nullable — `models.py:103`) because the initiator is the client, not staff. Audit events (`online_payment_initiated`, `yookassa_payment_created`) record the `ClientPrincipal` (client_id) as the initiating actor. **Open for planner/researcher:** confirm whether `audit.emit(... actor_user_id=)` already supports a non-user / client actor or needs a small client-aware actor field. Do NOT invent a fake staff user for this.
- **D-71-03:** **Single "buy plan" checkout flow — no client-facing renew distinction.** The existing `payment.succeeded` activator (`get_membership_activator()` in `app/api/v1/_internal/yookassa/handlers.py`) already decides extend-active-vs-create-new. The client contract exposes one purchase endpoint per subject; "renewal" (CPAY-01) is the same flow, resolved server-side at activation. No new renew branch.

### Idempotency + Return Flow (CPAY-03, CPAY-05)
- **D-71-04:** **Split idempotency strategy by subject.**
  - **Memberships:** keep the existing server-derived per-day deterministic key `sell-membership:{plan}:{client}:{today}` + replay-returns-same-`confirmation_url` (`service.py:_derive_idempotency_key` + replay check). Renewal is naturally ≤1/day, so this satisfies CPAY-05 with zero new code.
  - **PT-packages:** allow same-day repurchase via a **client-supplied `Idempotency-Key` header** — the PWA generates a UUID per checkout *intent*, reuses it only on retry, and **must persist it across the ЮKassa redirect round-trip**. The extracted core (D-71-01) must therefore accept *either* a derived key (membership) or a supplied key (PT-package).
- **D-71-05:** **New `GET /client/payments/{id}/status` endpoint** — returns only `pending | succeeded | canceled` (anti-oracle: never exposes activation/membership details; satisfies CPAY-03 "awaiting confirmation only"). IDOR-safe per D-20-IDOR: mandatory `client_id` filter + `assert_owns()` → 404-collapse. A dedicated PWA return route (the ЮKassa `return_url` target) **polls** this endpoint; on `succeeded` it routes the client to Home/Profile showing the now-active membership. On the redirect-back screen itself, only "ожидаем подтверждение" is shown — no premature activation.

### PWA Data-Fetching (PWA-05)
- **D-71-06:** **Add `@tanstack/react-query` to `apps/client-pwa`** over `clientFetcher.ts` + `@clubcore/api-client`. Provides caching, loading/error/refetch, dedup, and 401-refresh retry; mirrors the admin-web canonical pattern. **Mirror admin-web conventions:** per-feature query-key factory, `staleTime` baseline, `refetchOnWindowFocus: false`. Stay on React 18.3.1 (D-69-07) and react-router v6 (D-20-PWA-ROUTER) — React Query coexists with both; do NOT migrate to react-router data-router/loaders.
- **D-71-07:** **Swap the mock seam centrally at `apps/client-pwa/src/data/index.js`.** Replace its re-exported mock constants with backend-backed query hooks; the 6 screens change their import call-sites minimally. Keeps the existing single-entry-point design and makes "mock vs real" a one-file boundary, containing blast radius.

### Coming-Soon Placeholders (success criterion #5, PWA-06 carry-forward)
- **D-71-08:** **Strip mock data from net-new screens** (Chat, Referral, trainer reviews / `TrainerDetailSheet`, notification inbox / `NotificationsSheet`, gym-info / `GymInfoSheet`) and render a **shared "в разработке" placeholder component**. Removes their mock-data imports (no stale-mock confusion, smaller bundle), matches the criterion literally.
- **D-71-09:** **Structural enforcement of "no `/api/*` calls."** Net-new screens import only the shared placeholder; add an import-linter/ESLint boundary so these modules **cannot** import the query layer (`data/index.js` hooks, React Query) or `clientFetcher`. Enforced, not review-only. SW `/api/*` denylist (D-69-08) remains.

### Claude's Discretion (planner/researcher decides)
- Whether `audit.emit` needs a client-aware actor field or already supports it (D-71-02) — investigate `app/core/audit.py` and the staff `online_payment_initiated` emit.
- Exact `staleTime` values and per-screen query-key naming for the new React Query hooks — follow admin-web conventions.
- Where the client checkout write-slot + status endpoint live inside `client_portal` (router/service/repository already exist from Phase 69) vs a sub-module; consistent with D-20-MODULE Protocol-slot pattern.
- The precise PWA return-route path and `return_url` construction passed to ЮKassa (must round-trip back to the polling screen, carrying the `online_payment_id` and — for PT — the persisted `Idempotency-Key`).
- Checkout error UX on the PWA for ЮKassa `validation_error` / `transient_error` / `permanent_error` (service already maps these to 422/503/502) and the 422 `client_email_required_for_online_payment` case — surface as inline error consistent with PWA conventions.
- History-page / status polling interval and back-off.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/ROADMAP.md` § Phase 71 — goal + 5 success criteria (verification anchor; especially #1 anti-oracle redirect, #2 idempotent webhook activation, #3 422 email gate, #4 six screens on real backend, #5 net-new placeholders + SW never caches `/api/*`).
- `.planning/REQUIREMENTS.md` — CPAY-01..05, PWA-05 (locked requirement IDs for this phase).
- `.planning/phases/69-client-read-endpoints-pwa-stack-alignment/69-CONTEXT.md` — the read-surface + PWA-stack-alignment foundation this phase builds on (`clientFetcher.ts`, `@clubcore/api-client` wiring, `vite-plugin-pwa` SW `/api/*` denylist, hybrid `/client/home` contract, client-safe catalog projections).
- `.planning/phases/68-client-auth-foundation/68-CONTEXT.md` — `ClientPrincipal`, `require_client()`, `cc_client_*` cookies, `/api/v1/client` mount.

### v2.0 locked decisions (carry-forward — DO NOT re-litigate)
- **D-20-IDOR** — every owned endpoint (incl. new `/client/payments/{id}/status`): mandatory `client_id` param + `assert_owns()` → 404-collapse; parametrized IDOR sweep covers payments.
- **D-20-MODULE** — `app/modules/client_portal/` aggregator; raw-SQL cross-module reads; **Protocol-slot writes** (checkout write-slot delegates into the extracted `online_payments` core); zero new `ignore_imports`.
- **D-20-OPENAPI** — single `openapi.json` extended additively: `Client-Portal` tag + `client_` operationId prefix; staff paths byte-identical to `contract-freeze-v1.11.0` (formal freeze/guards are Phase 72, but stay additive now).
- **D-20-PWA-ROUTER** — react-router v6 kept; no TanStack Router. React Query (D-71-06) coexists; no data-router loader migration.
- **D-69-07** — stay on React 18.3.1.
- **D-69-08** — `vite-plugin-pwa` Workbox; `/api/*` excluded from caching (`navigateFallbackDenylist` + no runtime-cache rule).

### Existing backend code to reuse / extract (full paths)
- `apps/backend/app/modules/online_payments/service.py` (L170-380) — `_sell_subject` / `sell_membership` / `sell_pt_package`; the body to extract per D-71-01. Contains the email gate (`_read_client_email_or_raise`, L100), server-side price read (`_read_membership_plan_or_raise` L108 / `_read_pt_package_plan_or_raise` L139), idempotency key (`_derive_idempotency_key` L88) + replay check.
- `apps/backend/app/modules/online_payments/models.py` (L63, L103) — `OnlinePayment`: `client_id` FK, `created_by_user_id` **nullable** FK (enables D-71-02).
- `apps/backend/app/modules/online_payments/router.py` — staff sell/refund routes; RBAC + Idempotency-Key ordering (the staff contract that must stay byte-identical).
- `apps/backend/app/api/v1/_internal/yookassa/handlers.py` (`handle_payment_succeeded`, L330; `get_membership_activator()` / `get_pt_package_activator()`, L91-93) — the **webhook-only activation seam** (CPAY-03/criterion #2). Reused verbatim; idempotent on duplicate webhook (criterion #2).
- `apps/backend/app/modules/client_portal/` (`router.py` / `service.py` / `repository.py` / `schemas.py`) — Phase-69 module; new checkout write-slot + `/client/payments/{id}/status` read live here. `service.py:list_client_payments` (L145) is the payments-read precedent.
- `apps/backend/app/core/dependencies.py` — `require_client()` + `ClientPrincipal` (auth gate for the new checkout + status endpoints).
- `apps/backend/app/core/audit.py` — investigate actor model for D-71-02 (client-as-actor).
- `apps/backend/app/integrations/yookassa/` — ЮKassa client provider (`get_yookassa_client_provider`), settings, webhook verifier.
- `apps/backend/tests/conftest.py` (SAVEPOINT harness, `async_client` over ASGITransport) + `apps/backend/tests/integration/` — IDOR sweep + idempotency/duplicate-webhook test patterns.

### PWA code to wire (full paths)
- `apps/client-pwa/src/data/index.js` — central mock seam (the single swap point, D-71-07). Currently re-exports `PLANS`, `VISIT_HISTORY`, `UPCOMING_BOOKING`, `TRAINERS`, `CALENDAR`, etc.
- `apps/client-pwa/src/lib/clientFetcher.ts` (+ `clientFetcher.test.tsx`) — typed fetcher over `@clubcore/api-client` (Phase 69); React Query hooks call through it.
- `apps/client-pwa/src/screens/HomeScreen.jsx`, `ProfileScreen.jsx`, `BookScreen.jsx` and sheets `PlansSheet.jsx`, `CheckoutSheet.jsx`, `QRSheet.jsx` — the 6 screens to wire (PWA-05).
- `apps/client-pwa/src/screens/ChatScreen.jsx` + sheets `ReferralSheet.jsx`, `TrainerDetailSheet.jsx`, `NotificationsSheet.jsx`, `GymInfoSheet.jsx` — net-new screens → placeholder (D-71-08/09).
- `apps/client-pwa/package.json` — add `@tanstack/react-query` (D-71-06).
- `packages/api-client/` — `@clubcore/api-client` (typed fetcher + `schema.d.ts`); checkout + status paths must appear in `schema.d.ts` (regen).
- `apps/admin-web/` — reference for React Query key-factory / `staleTime` / `QueryClient` conventions (do NOT modify; frozen mock-reference).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`_sell_subject` core** — already does server-side price, 54-ФЗ email gate, idempotent create, and replay-returns-same-URL. CPAY-03/04/05 are ~80% solved server-side; the work is exposing it under `ClientPrincipal` (D-71-01) not reimplementing it.
- **Webhook activation seam** (`handle_payment_succeeded`) — already idempotent on duplicate delivery (criterion #2) and activation-only (criterion #1 anti-oracle). Client checkout writes the same `OnlinePayment` row shape, so the existing webhook activates it unchanged.
- **`client_portal` module** — router/service/repository scaffolding + `/history/payments` read already exist (Phase 69); checkout write-slot and status endpoint slot in alongside.
- **`clientFetcher.ts` + `@clubcore/api-client`** — typed fetch seam ready (Phase 69); React Query hooks layer on top.
- **`data/index.js`** — pre-existing single-entry-point design makes the mock→real swap a one-file boundary (D-71-07).

### Established Patterns
- **Protocol-slot writes (D-20-MODULE)** — `client_portal` must not import `online_payments` internals directly; the extracted core is invoked via a composition-root Protocol slot (mirrors prior client_portal write patterns). Zero new `ignore_imports`.
- **Anti-oracle (D-20-IDOR + CPAY-03)** — status endpoint returns coarse states only; get-by-id collapses to 404 on non-owned rows.
- **Audit ROOT→CHILD chaining** — `online_payment_initiated` (root) + `yookassa_payment_created` (child) via `audit_correlation_id`; client checkout preserves this, swapping the actor (D-71-02).

### Integration Points
- ЮKassa `return_url` → new PWA return route → polls `GET /client/payments/{id}/status`.
- New client checkout routes mount under `/api/v1/client` (existing mount, `app/api/v1/router.py`).
- `schema.d.ts` regen picks up new client paths (formal `_v20Checks`/freeze is Phase 72; additive only now).

</code_context>

<specifics>
## Specific Ideas

- Redirect-back screen copy: only "ожидаем подтверждение" / "awaiting confirmation" — never show membership as active until the status endpoint reports `succeeded` (criterion #1).
- Net-new placeholder copy: "в разработке" (coming soon) card.
- PT-package same-day repurchase is the explicit reason PT diverges from the membership per-day idempotency key (D-71-04).

</specifics>

<deferred>
## Deferred Ideas

- **Client-side refunds / cancellation of a pending payment** — not in CPAY scope; staff-only refund flow unchanged.
- **Wiring net-new screens (Chat, Referral, reviews, notifications, gym-info) to real backends** — future phases; placeholder only now.
- **`Client-Portal` tag freeze, `_v20Checks` guards, client-pwa CI gates, live E2E runbook** — Phase 72.
- **React 19 bump** — deferred (D-69-07).

None of the discussion strayed outside phase scope beyond the above noted-for-later items.

</deferred>

---

*Phase: 71-client-checkout-full-pwa-screen-wiring*
*Context gathered: 2026-05-30*
