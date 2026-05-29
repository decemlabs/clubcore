# Project Research Summary

**Project:** clubcore — v2.0 Frontend Integration — Client PWA
**Domain:** Client-facing API + member PWA over an existing FastAPI modular-monolith gym CRM (RF/CIS)
**Researched:** 2026-05-29
**Confidence:** HIGH — all findings from direct codebase inspection (no speculation)

> Synthesized from STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md (committed `d4cfac83`).

---

## Executive Summary

v2.0 is the **first full-stack milestone** after a series of backend-only releases. The v1.11 *staff* OpenAPI contract is frozen; the task is to expose gym members as a **second principal** through a dedicated client-facing API and wire `apps/client-pwa` (React 18 + react-router v6, currently 100% mock data) to that backend. The core challenge: add a completely **orthogonal authentication principal** alongside a frozen, fully-tested staff RBAC system **without touching either the staff contract or the frozen `apps/admin-web`**.

Four structural decisions must be settled before any domain work begins:
1. **Separate `ClientPrincipal` + `require_client()`** dependency tree with a distinct JWT audience claim (`aud: "client"`) and distinct cookie names — **NOT** extending the staff `Role` enum.
2. **`app/modules/client_portal/`** aggregator module with raw-SQL reads (the `reports/` D-54-08 read-only precedent) and Protocol-slot writes — preserves `modules-independent`.
3. **Telegram-OTP-only** for v2.0 — reuse existing OTP infra; **no SMS provider**.
4. **Single OpenAPI spec extended additively** with a `"Client-Portal"` tag and `client_` operationId prefix — frozen staff paths byte-identical.

The **#1 risk is cross-client data leakage (IDOR)**. Every client repository function must carry `client_id` as a mandatory parameter; every domain phase must ship a parametrized cross-client enumeration test. The **#2 risk is privilege-boundary collapse** — adding `Role.CLIENT` to `permissions.py` breaks the three-way RBAC byte-parity test against frozen `admin-web/can.ts` and must never happen.

---

## Reconciled Decision: Client Principal (IMPORTANT)

STACK.md initially suggested `Role.CLIENT = "client"`. ARCHITECTURE.md and PITFALLS.md both independently argue against it: the three-way RBAC byte-parity test pins `permissions.py` against the **frozen** `admin-web/can.ts`/`registry.ts` (admin-web is out of scope and cannot be touched). **Resolution: the separate-principal design wins.**

- New `ClientPrincipal` Protocol in `app/core/dependencies.py` (parallel to the staff `CurrentUser`; no `Role` field).
- New `require_client()` dependency factory reading a `cc_client_access` cookie with an `aud: "client"` claim validated by an additive `decode_client_access_token()`.
- New `register_client_loader` composition-root slot.
- Staff `require_authenticated()` structurally rejects client tokens via the distinct cookie name + audience claim.
- **Mandatory Phase 68 test:** client JWT → `GET /api/v1/clients` → 401; staff JWT → `GET /api/v1/client/me` → 401.

---

## Stack Recommendation (elevated, convergent)

- **Auth channel:** Telegram-OTP-only for v2.0 (Telegram Gateway API, ~$0.01/code, REST; reuses the existing `OtpChannel`-discriminated OTP infra). **SMS provider is an explicit DEFERRED backlog item** (SMS Aero / SMSC.ru / МТС Exolve — Twilio is blocked in RF). Cost/abuse surface is the reason to defer.
- **`clients.phone`** is currently free-form `Text` — needs **E.164 normalization/validation** at OTP-request time for Telegram Gateway.
- **PWA alignment:** delete `bun.lock` → `pnpm install`; Vite 5→6 (`@vitejs/plugin-react@^5`); TypeScript via `allowJs: true` + `strict` ramp, file-by-file rename (~20 files); reuse the **framework-agnostic** `@clubcore/api-client` `fetcher.ts` (add client auth paths to `AUTH_EXEMPT_PATHS`); **KEEP react-router v6** (no TanStack Router migration); add TanStack Query v5 + a thin `clientFetcher.ts` wrapper overriding only the client CSRF cookie name + refresh-endpoint URL. React 18/19 coexist in one pnpm workspace.
- **Codegen:** single `openapi.json` → single `schema.d.ts`; client paths land additively. No multi-schema split.

---

## Feature Landscape (6 IN-SCOPE areas over EXISTING domains)

| Area | Backing domain | Client read/write surface | Notes / dependency |
|---|---|---|---|
| Client auth + `/me` | (new) client_portal + clients | phone+OTP login, `GET/PATCH /client/me` | unknown/duplicate/soft-deleted phone → identical anti-oracle response; phone↔`clients` match |
| Home — my membership | memberships | active membership, days left, freeze status, expiring-soon | read-only |
| My bookings + self-book | bookings + schedule + pt_packages | upcoming/past bookings, book a slot w/ trainer, cancel within policy | **`Booking.pt_package_id` is NOT NULL** → no active PT package = no self-book; route to Plans/Checkout |
| QR self check-in | visits | signed short-lived QR token → 1/day check-in | `visits.channel` CHECK needs Alembic add of `'client_qr'`; must keep `gym_date` 1/day + active-membership |
| Self checkout | online_payments (ЮKassa) | client-initiated membership/PT purchase + renewal | **email mandatory** for 54-ФЗ receipt → `PATCH /client/me` email; activation LOCKED to existing webhook |
| History | visits, pt_sessions, payments | my visits / trainings / purchases (incl. refunds) | **`pt_sessions` has no direct `client_id`** → join via `pt_packages.client_id` (ownership guard) |

**OUT OF SCOPE (net-new domains NOT built — screens stay mock/placeholder):** Chat, Referral, trainer reviews/ratings, in-app notification inbox, gym-info-from-backend.

---

## Architecture Integration

- **Placement:** `app/modules/client_portal/` with `/api/v1/client/*` prefix. Reads via raw-SQL `text()` (reports precedent, zero new `ignore_imports`); writes via Protocol slots wired at `app/main.py:create_app()`.
- **Data-isolation chokepoint:** list endpoints take a **mandatory `client_id` parameter** in repository signatures (injected into every WHERE); get-by-ID does fetch-then-`assert_owns(principal, row.client_id)` raising `NotFoundError` (404 collapse, anti-oracle). A parametrized sweep test covers every client-owned resource type.
- **Contract preservation:** new `"Client-Portal"` tag in `OPENAPI_TAGS`; `client_` operationId prefix (no staff collision); additive `_v20Checks` `AssertNonNever` block; staff `_v1xChecks` blocks untouched; drift gate confirms staff paths byte-identical to the `contract-freeze-v1.11.0` baseline.
- **PWA data flow:** react-router v6 loaders + `queryClient.ensureQueryData` (TanStack Query v5) + reused `fetcher.ts` via thin wrapper; client auth/refresh/CSRF over the distinct cookie family.

---

## Watch Out For (convergent across all 4 files)

| # | Risk | Prevention | Phase |
|---|------|-----------|-------|
| P-01 | **IDOR / cross-client leakage (TOP)** | mandatory `client_id` repo param; `assert_owns()` on get-by-ID; IDOR enumeration test per domain phase (mandatory success criterion) | every domain phase |
| P-02 | Phone OTP enumeration oracle | `_constant_time_floor()` + uniform 200 across all branches; timing integration test | 68 |
| P-03 | Client token on staff endpoints / `Role.CLIENT` parity break | separate `ClientPrincipal` + `aud:"client"` + distinct cookies; `Role.CLIENT` banned; route-introspection guard recognizes `require_client` | 68 |
| P-04 | OTP bombing / SMS cost | per-IP 5/15min + per-phone 60s cooldown + per-phone daily cap; commit-before-raise on attempts | 68 |
| P-05 | Checkout activated on redirect-back | activation LOCKED to existing `/_internal/yookassa/webhook`; no 2nd path; server-read price; "Ожидаем подтверждение" screen | 71 |
| P-06 | QR replay / cross-client check-in | short-lived signed JWT QR (≈60s TTL); full `_create_visit_with_anti_fraud()` chain | 70 |
| P-07 | Staff OpenAPI contract broken | `client_` operationId prefix; staff check-blocks unchanged; `git diff` additions-only | 68 + 72 |
| P-08 | Cookie name collision (staff+client same origin) | distinct `cc_client_*` names + `Path=/api/v1/client`; never call `issue_session_cookies()` from client routes | 68 |
| P-09 | Service-worker caching authed API data | scope SW caching away from `/api/*`; decide if PWA offline is in scope (else defer) | 69/70 |
| P-10 | bun→pnpm / TS adoption breakage | isolated alignment phase with a verified build BEFORE any API wiring | 69 |

---

## Open Decisions for Plan Phase (do NOT resolve in research)

1. `client_otp_codes` separate table **vs** `client_id` nullable FK on `otp_codes` (existing partial UNIQUE has no `client_id` slot — separate is cleaner).
2. `client_refresh_tokens` separate table **vs** `purpose` column on `refresh_tokens` (separate isolates from staff `revoke_all_sessions`).
3. `ClientBookingCreator` Protocol slot **vs** raw-SQL re-validation in `client_portal/service.py` (inspect `bookings/service.py` first).
4. Single-spec `_v20Checks` extension **vs** split `client-openapi.json` (consensus: single-spec).
5. `verify_client_idempotency` Redis key design scoped to `clients.id` (Phase 70 — needs one planning investigation).

---

## Suggested Phase Structure (roadmapper input; numbering continues at 68)

- **Phase 68 — Client Auth Foundation** *(unconditional blocker)* — `ClientPrincipal`, `require_client()`, `decode_client_access_token()`, distinct cookies, `register_client_loader`, Telegram Gateway adapter, OTP request/verify/refresh/logout/me with full anti-oracle + rate limiting, route-introspection guard extension, `"Client-Portal"` OpenAPI tag, two-principal isolation test. No domain work until green.
- **Phase 69 — Client Read Endpoints + PWA Stack Alignment** — ownership pattern across all read resources + parametrized IDOR sweep (ships before any write path); PWA pnpm/Vite6/TS/api-client/TanStack-Query alignment + `clientFetcher.ts`; Home + Profile history wired.
- **Phase 70 — Client Bookings + QR Self Check-In** — booking create/cancel (idempotency-keyed, cross-client guarded) + signed QR token + self-checkin via `_create_visit_with_anti_fraud()` + `visits.channel` Alembic migration; Book + QR screens wired.
- **Phase 71 — Client Checkout (ЮKassa)** — email update, membership/PT purchase via existing webhook (server-side price), status polling, 54-ФЗ email gate; Plans + Checkout screens wired.
- **Phase 72 — OpenAPI Handoff + CI Integration** — byte-stable `schema.d.ts` regen, `_v20Checks` complete, client-pwa CI gates added, drift gate confirms staff paths byte-identical to v1.11 baseline.

---

## Research Flags

- **Phase 70 client idempotency** — confirm `verify_client_idempotency` Redis key design (scope to `clients.id`) before writing the plan (~1 planning session).
- All other phases follow standard patterns with direct codebase precedents — no per-phase research needed.

## Confidence & Gaps

**Overall: HIGH.** Every pitfall traces to a specific function (`_constant_time_floor`, `_create_visit_with_anti_fraud`, `issue_session_cookies`, `OWNER_ONLY`, `modules-independent` contract). Remaining gaps are all **plan-phase schema decisions** (OTP/refresh table shape, booking slot mechanism, idempotency key) — flagged above, not blockers for roadmapping.
