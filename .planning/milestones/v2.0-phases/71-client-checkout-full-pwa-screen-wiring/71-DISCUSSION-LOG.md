# Phase 71: Client Checkout + Full PWA Screen Wiring - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-30
**Phase:** 71-client-checkout-full-pwa-screen-wiring
**Areas discussed:** Checkout backend reuse, Idempotency + return flow, PWA data-fetching, Coming-soon placeholders

---

## Checkout backend reuse

### Q1 — How to reuse the ЮKassa sell logic

| Option | Description | Selected |
|--------|-------------|----------|
| Extract shared core | Pull actor-agnostic body of `_sell_subject` into a helper; staff service + new client_portal write-slot both call it, actor parameterized. | ✓ |
| New client checkout service | client_portal calls ЮKassa provider + repository directly, full isolation, some duplication. | |
| Call staff service directly | Client router calls staff `sell_*` directly; least code but new import-linter edge + client actor in staff signature. | |

**User's choice:** Extract shared core
**Notes:** Keeps staff path byte-identical (drift gate), respects D-20-MODULE Protocol-slot, no duplication. → D-71-01

### Q2 — Client-initiated payment attribution

| Option | Description | Selected |
|--------|-------------|----------|
| Null staff + client actor | `created_by_user_id=NULL` (already nullable); audit records ClientPrincipal as actor. | ✓ |
| Synthetic system user | Dedicated client-portal service user stamped as created_by + audit actor. | |

**User's choice:** Null staff + client actor
**Notes:** Accurate provenance. Planner to confirm `audit.emit` supports a non-user actor. → D-71-02

### Q3 — Renewal vs new purchase

| Option | Description | Selected |
|--------|-------------|----------|
| Single buy flow | One buy endpoint; webhook activator decides extend-vs-create; no client distinction. | ✓ |
| Explicit renew entry point | PWA shows renew on active membership + buy on Plans; same endpoint. | |

**User's choice:** Single buy flow
**Notes:** Reuses activation logic verbatim. → D-71-03

---

## Idempotency + return flow

### Q1 — Idempotency model

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse per-day key as-is | Same deterministic key + replay; blocks same-plan repurchase same day. | |
| Per-day for memberships, looser for PT | Per-day key for memberships; client-supplied Idempotency-Key header for PT same-day repurchase. | ✓ |
| Client-supplied key everywhere | PWA generates key per intent for both subjects. | |

**User's choice:** Per-day for memberships, looser for PT
**Notes:** PT-package same-day repurchase is a real case; membership renewal is naturally ≤1/day. Extracted core must accept either key source. PWA persists the supplied key across the redirect round-trip. → D-71-04

### Q2 — Redirect-back UX

| Option | Description | Selected |
|--------|-------------|----------|
| Poll a status endpoint | Dedicated PWA return route polls new `GET /client/payments/{id}/status` (pending/succeeded/canceled); on succeeded → Home/Profile. | ✓ |
| Static 'awaiting' + manual nav | Static awaiting screen + go-to-Home button; no new endpoint, no live feedback. | |

**User's choice:** Poll a status endpoint
**Notes:** Anti-oracle status (coarse states only), IDOR-safe. → D-71-05

---

## PWA data-fetching

### Q1 — Fetching layer

| Option | Description | Selected |
|--------|-------------|----------|
| Add TanStack Query | @tanstack/react-query over clientFetcher; caching/refetch/401-retry; mirrors admin-web. | ✓ |
| Hand-rolled fetch hook | useEffect+useState hook; no deps but reimplements caching, diverges from admin-web. | |
| react-router v6 data APIs | createBrowserRouter + loaders; higher blast radius on screen/sheet structure. | |

**User's choice:** Add TanStack Query
**Notes:** Canonical repo pattern; coexists with react-router v6 + React 18.3.1. → D-71-06

### Q2 — Mock seam swap

| Option | Description | Selected |
|--------|-------------|----------|
| Swap at data/index.js | Replace central re-exports with backend-backed hooks; minimal call-site changes; one-file boundary. | ✓ |
| Per-screen refactor | Each screen refactored individually; spreads change, no central seam. | |

**User's choice:** Swap at data/index.js
**Notes:** Contains blast radius; keeps existing single-entry-point design. → D-71-07

---

## Coming-soon placeholders

### Q1 — Placeholder treatment

| Option | Description | Selected |
|--------|-------------|----------|
| Strip mock, show в разработке card | Replace net-new screen bodies with shared placeholder; remove mock imports. | ✓ |
| Keep mock UI behind banner | Leave mock UI + overlay coming-soon banner; keeps mock in bundle. | |

**User's choice:** Strip mock, show в разработке card
**Notes:** Guarantees zero backend calls, no stale-mock confusion. → D-71-08

### Q2 — Enforcement of no /api/* calls

| Option | Description | Selected |
|--------|-------------|----------|
| Structural: shared placeholder + lint | import-linter/ESLint boundary forbids net-new screens from importing query layer / clientFetcher. | ✓ |
| Convention + manual review | Rely on placeholder having no fetch code + PR review. | |

**User's choice:** Structural: shared placeholder + lint
**Notes:** Enforced not review-only; SW /api/* denylist (D-69-08) remains. → D-71-09

---

## Claude's Discretion

- Whether `audit.emit` already supports a non-user/client actor or needs a small extension (D-71-02).
- Exact `staleTime` / query-key naming for the new React Query hooks (follow admin-web).
- Sub-module placement of checkout write-slot + status endpoint within client_portal.
- PWA return-route path + `return_url` construction (round-trips online_payment_id + persisted PT Idempotency-Key).
- Checkout error UX for ЮKassa validation/transient/permanent errors + 422 email-gate.
- Status polling interval / back-off.

## Deferred Ideas

- Client-side refunds / cancellation of pending payment — staff-only, out of CPAY scope.
- Wiring net-new screens to real backends — future phases.
- `Client-Portal` tag freeze, `_v20Checks` guards, client-pwa CI gates, live E2E runbook — Phase 72.
- React 19 bump — deferred (D-69-07).

---

## Update — 2026-05-30 (`--auto` re-discuss)

Re-ran `/gsd:discuss-phase 71 --auto` after Phase 70 landed. No new gray areas surfaced; all decisions (D-71-01..09) carried forward unchanged. Sole material change: the Phase 70 dependency warning in CONTEXT.md `<domain>` was stale ("Not started") and is now marked satisfied — Phase 70 completed (`97d57ce6 docs(phase-70): complete phase execution`), so plan `71-06-PLAN.md`'s Book/QR wiring dependency is cleared. `todo.match-phase 71` returned 0 matches. Auto-advancing to plan-phase.
