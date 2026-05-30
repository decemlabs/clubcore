# Roadmap: clubcore

## Milestones

- ✅ **v1.0 Phase A: Skeleton** — Phases 1-3 (shipped 2026-05-01) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Auth + Clients** — Phases 4-14 (shipped 2026-05-07) — see [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)
- ✅ **v1.2 Memberships + Visits** — Phases 15-23 (shipped 2026-05-08) — see [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- ✅ **v1.3 Memberships Extras + Tech-Debt** — Phases 24-29 (shipped 2026-05-14) — see [milestones/v1.3-ROADMAP.md](milestones/v1.3-ROADMAP.md)
- ✅ **v1.4 Cash Sales + PT Packages** — Phases 30-36 (shipped 2026-05-16) — see [milestones/v1.4-ROADMAP.md](milestones/v1.4-ROADMAP.md)
- ✅ **v1.5 Schedule + Bookings (PT slots)** — Phases 37-40 (shipped 2026-05-18) — see [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
- ✅ **v1.6 Email channel + Multi-user admin** — Phases 41-46 (shipped 2026-05-21) — see [milestones/v1.6-ROADMAP.md](milestones/v1.6-ROADMAP.md)
- ✅ **v1.7 Online Payments + 54-ФЗ** — Phases 47-53 (shipped 2026-05-24) — see [milestones/v1.7-ROADMAP.md](milestones/v1.7-ROADMAP.md)
- ✅ **v1.8 Reports + Audit Log read API** — Phases 54-57 (shipped 2026-05-24) — see [milestones/v1.8-ROADMAP.md](milestones/v1.8-ROADMAP.md)
- ✅ **v1.9 Trainers Complete** — Phases 58-61 (shipped 2026-05-26) — see [milestones/v1.9-ROADMAP.md](milestones/v1.9-ROADMAP.md)
- ✅ **v1.10 clubcore Rebrand** — Phases 62 + 62.1 (shipped 2026-05-26) — see [milestones/v1.10-ROADMAP.md](milestones/v1.10-ROADMAP.md)
- ✅ **v1.11 API Handoff + Production Hardening** — Phases 63-67 (shipped 2026-05-29) — see [milestones/v1.11-ROADMAP.md](milestones/v1.11-ROADMAP.md)
- 🚧 **v2.0 Frontend Integration — Client PWA** — Phases 68-72 (in progress)

## Phases

<details>
<summary>✅ v1.0 — v1.10 SHIPPED (Phases 1-62.1)</summary>

All shipped milestones detailed in per-milestone ROADMAP archives above.

</details>

<details>
<summary>✅ v1.11 API Handoff + Production Hardening (Phases 63-67) — SHIPPED 2026-05-29</summary>

**Execution order: 63 → 64 → 66 → 65 → 67** (non-monotonic — Phase 65 handoff artifacts derive from the post-Phase-66 frozen spec including `components.parameters.IdempotencyKey`). Full phase details in [milestones/v1.11-ROADMAP.md](milestones/v1.11-ROADMAP.md).

- [x] **Phase 63: Tech-Debt Sweep** — ruff format + ruff safe-fix + mypy strict all exit 0 on the clean clubcore tree; v1.5 `run.sh` hardened; all 6 backend CI gates green (DEBT-01..05) — completed 2026-05-26
- [x] **Phase 64: Contract Freeze — OpenAPI Curation** — curated spec under clubcore name (info/servers/securitySchemes, cleaned operation IDs, 12-domain tags, shared error responses); Redocly lint as 7th CI gate; `contract-freeze-v1.11.0` baseline tag (FRZ-01..08) — completed 2026-05-28
- [x] **Phase 66: Idempotency Hardening** — user-scoped `verify_idempotency` (cross-user replay fix); 86400s TTL; single `idempotent_execute` orchestrator; `components.parameters.IdempotencyKey` $ref on all 22 category-A ops; 48 double-submit integration tests (IDM-01..07) — completed 2026-05-29
- [x] **Phase 65: Handoff Artifacts** — Postman v2.1 collection + Newman smoke harness + `clubcore-auth-runbook.md` + private Redocly doc-site from the post-Phase-66 frozen spec (HND-01..06) — completed 2026-05-29
- [x] **Phase 67: Operator-Pending Runbook Execution** — 4 accumulated walkthroughs executed with real evidence; Mailpit `--profile dev`; `v1.11-OPERATOR-EVIDENCE.md` populated (RUN-00..07) — completed 2026-05-29

</details>

### 🚧 v2.0 Frontend Integration — Client PWA (Phases 68-72)

**Milestone Goal:** Expose gym members as a second principal via a dedicated client-facing API and wire `apps/client-pwa` to it — client auth, client-scoped reads and writes over existing domains, self-service checkout (ЮKassa), QR self-check-in, and a verified full-stack end-to-end flow. Staff contract and frozen `apps/admin-web` are unchanged.

- [x] **Phase 68: Client Auth Foundation** - Separate `ClientPrincipal` / `require_client()` / distinct cookies / anti-oracle OTP; unconditional blocker for all domain work (completed 2026-05-29)
- [x] **Phase 69: Client Read Endpoints + PWA Stack Alignment** - All client-scoped read endpoints (membership, history, catalogs) + PWA bun→pnpm/TS/Vite-6 alignment with verified build; IDOR sweep covers read surface (completed 2026-05-29)
- [x] **Phase 70: Client Bookings + QR Self Check-In** - Self-booking (race-safe via existing partial-UNIQUE), cancellation policy, signed short-lived QR token, and QR-triggered visit creation via existing anti-fraud path (completed 2026-05-30)
- [ ] **Phase 71: Client Checkout + Full PWA Screen Wiring** - Client-initiated ЮKassa membership/PT-package purchase (server-side price, webhook-only activation, 54-ФЗ email gate); all PWA screens wired to real backend
- [ ] **Phase 72: OpenAPI Handoff + CI + E2E Verification** - `Client-Portal` tag in spec, `_v20Checks` guards, client-pwa CI gates, drift gate confirms staff contract byte-identical; live E2E runbook gate

## Phase Details

### Phase 68: Client Auth Foundation

**Goal**: A secure, isolated client principal exists; gym members can authenticate via phone + Telegram OTP, hold a distinct session cookie, view/edit their profile, and the two-principal isolation (staff vs client) is proven by automated test
**Depends on**: Phase 67 (v1.11 shipped — frozen staff contract is the baseline)
**Requirements**: CAUTH-01, CAUTH-02, CAUTH-03, CAUTH-04, CAUTH-05, CAUTH-06, CISO-01, CISO-02, CISO-03, CISO-04, CISO-05
**Success Criteria** (what must be TRUE):

  1. A client can request a Telegram OTP with their phone number, verify the code, and receive a `cc_client_access` session cookie that survives browser restart (refresh rotation works, logout clears the cookie)
  2. Requesting OTP for an unknown, duplicate, or soft-deleted phone number returns a response byte-identical to a known phone (anti-oracle; timing-safe via `_constant_time_floor`)
  3. A staff JWT presented to `GET /api/v1/client/me` receives 401; a client JWT presented to any staff endpoint (e.g. `GET /api/v1/clients`) receives 401 — two-principal isolation test is green
  4. `PATCH /api/v1/client/me` accepts an email update; subsequent `GET /api/v1/client/me` returns the updated email
  5. OTP requests exceeding the rate limit (per-IP 5/15 min, per-phone daily cap) are rejected with 429; brute-force code guessing is blocked

**Plans**: 6 plans (4 waves)

- [x] 68-01-PLAN.md — DB foundation: OtpCode.client_id + XOR CHECK + client_refresh_tokens table (Alembic 0043/0044)
- [x] 68-02-PLAN.md — Client JWT + cookie primitives in security.py (decode_client_token aud=client, cc_client_* cookies)
- [x] 68-03-PLAN.md — Composition root: ClientPrincipal, register_client_loader, require_client, verify_client_csrf
- [x] 68-04-PLAN.md — Client OTP + session service: anti-oracle request, verify, 3-branch rotate, logout, email-only PATCH
- [x] 68-05-PLAN.md — Schemas + /api/v1/client router (6 handlers) + mount + create_app loader wiring
- [x] 68-06-PLAN.md — Verification: two-principal isolation, IDOR sweep, anti-oracle byte-parity, lifecycle, CISO-01 guard

**UI hint**: yes

### Phase 69: Client Read Endpoints + PWA Stack Alignment

**Goal**: Every client-scoped read endpoint exists and is IDOR-safe (mandatory `client_id` filter + `assert_owns()` + parametrized cross-client enumeration test green); `client-pwa` builds and type-checks under pnpm workspace, Vite 6, TypeScript, and reuses `@clubcore/api-client`
**Depends on**: Phase 68
**Requirements**: CHOME-01, CHOME-02, CHOME-03, CHIST-01, CHIST-02, CHIST-03, CPLAN-01, CPLAN-02, CPLAN-03, PWA-01, PWA-02, PWA-03, PWA-04, PWA-06, PWA-07
**Success Criteria** (what must be TRUE):

  1. A client can see their active membership (plan name, days remaining, freeze status) and an "expiring soon" indicator via `GET /api/v1/client/membership`
  2. A client can retrieve their full visits history, PT-session history, and payment history (including refunds) — each endpoint returns only the authenticated client's own records; presenting another client's resource ID returns 404
  3. A client can browse the membership-plans catalog, PT-packages catalog, and trainers catalog (name/specialization) without authentication leaking cross-client data
  4. `pnpm install` at the workspace root installs `client-pwa`; `bun.lock` is removed; the pwa `pnpm build` + `pnpm typecheck` + `pnpm lint` commands all exit 0 with Vite 6 and TypeScript strict mode
  5. The parametrized IDOR enumeration test (covering membership, visits, PT-sessions, payments, bookings as owned resource types) is green — no cross-client leakage is possible

**Plans**: 3 plans (2 waves)

- [x] 69-01-PLAN.md — client_portal read module: raw-SQL repository, client-safe schemas, service (home fan-out), router + mount (CHOME/CHIST/CPLAN)
- [x] 69-02-PLAN.md — PWA stack alignment: pnpm workspace + Vite 6 + TS allowJs ramp + ESLint/Vitest + vite-plugin-pwa (/api never cached) + clientFetcher.ts + smoke test (PWA-01..04,06,07)
- [x] 69-03-PLAN.md — verification: parametrized IDOR sweep (both orderings, all owned reads) + behavioral tests (temporal fields, empty-state 200/null, pagination, catalog projection)

**UI hint**: yes

### Phase 70: Client Bookings + QR Self Check-In

**Goal**: A client can self-book a trainer slot using their active PT-package (race-safe, idempotent), cancel within the policy window, and check into the gym by scanning a short-lived signed QR token — all with IDOR and anti-replay protections
**Depends on**: Phase 69
**Requirements**: CBOOK-01, CBOOK-02, CBOOK-03, CBOOK-04, CBOOK-05, CCHK-01, CCHK-02, CCHK-03
**Success Criteria** (what must be TRUE):

  1. A client with an active PT-package can create a booking for an available trainer slot; a concurrent second booking for the same slot returns 409 (Postgres partial-UNIQUE arbiter)
  2. A client without an active PT-package attempting to book receives a response directing them to Plans/Checkout (not a cryptic error)
  3. A client can cancel their own confirmed booking within the cancellation-policy window; cancelling another client's booking returns 404 (anti-oracle)
  4. A client receives a short-lived signed JWT QR token (≈60s TTL); scanning it creates a visit via the existing `_create_visit_with_anti_fraud()` path, recording `visits.channel = 'client_qr'` (Alembic migration applied)
  5. Replaying an expired QR token is rejected; using a valid QR token to check in a different client's session is rejected (cross-client check-in impossible)

**Plans**: 4 plans
Plans:
**Wave 1**

- [x] 70-01-PLAN.md — QR token helpers (encode/decode + ~60s TTL) + CANCEL_WINDOW_HOURS_CLIENT + visits.channel 'client_qr' Alembic migration
- [x] 70-02-PLAN.md — Extract actor-agnostic booking + cancel core; expose via composition-root Protocol slots (staff byte-identical)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 70-03-PLAN.md — Client booking POST (idempotent, 422 no_active_pt_package) + cancel (IDOR 404) + available-slots read; race + IDOR tests

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 70-04-PLAN.md — QR check-in: qr-token issue (require_client) + token-as-credential /check-in (sub-only); anti-replay/cross-client tests + human-verify checkpoint

**UI hint**: yes

### Phase 71: Client Checkout + Full PWA Screen Wiring

**Goal**: A client can initiate a ЮKassa membership or PT-package purchase entirely from the PWA; payment activation is locked to the existing webhook; server-side price is authoritative; 54-ФЗ email gate is enforced; all core PWA screens (Home, Profile, Book, Plans, Checkout, QR) are wired to the real backend
**Depends on**: Phase 70
**Requirements**: CPAY-01, CPAY-02, CPAY-03, CPAY-04, CPAY-05, PWA-05
**Success Criteria** (what must be TRUE):

  1. A client can initiate a membership purchase or renewal and a PT-package purchase via ЮKassa from the PWA; the redirect-back screen shows only "awaiting confirmation" (anti-oracle — no premature activation)
  2. Membership/PT-package activation occurs only after `payment.succeeded` webhook fires; a duplicate webhook delivery does not double-activate (idempotent checkout)
  3. Attempting checkout without a client email returns 422 `client_email_required_for_online_payment` (54-ФЗ fiscal receipt gate)
  4. The PWA Home, Profile, Book, Plans, Checkout, and QR screens fetch data from the real client backend; the mock data layer is replaced for these six screens
  5. Net-new screens (Chat, Referral, trainer reviews, notification inbox, gym-info) display a "coming soon" placeholder — no backend calls are made from them; the service worker never caches `/api/*` requests

**Plans**: 6 plans (4 waves)

- [x] 71-01-PLAN.md — extract _sell_subject_core actor-agnostic helper + checkout Protocol slot + main.py wiring (CPAY-01..05)
- [x] 71-02-PLAN.md — client_portal checkout endpoints (membership/PT POST + status GET) via Protocol slot; split idempotency; IDOR/anti-oracle status (CPAY-01..05)
- [x] 71-03-PLAN.md — checkout integration tests: success, dual idempotency, 422 email gate, IDOR 404, anti-oracle status, duplicate-webhook activation (CPAY-01..05)
- [x] 71-04-PLAN.md — PWA React Query foundation: queryClient + clientQueries hooks + data/index.js swap seam + ComingSoon + ESLint boundary (PWA-05)
- [x] 71-05-PLAN.md — wire Home/Profile/Plans/Checkout + payment return route (anti-oracle); net-new screens → ComingSoon (PWA-05, CPAY-01..03)
- [ ] 71-06-PLAN.md — wire Book/QR screens to Phase-70 endpoints (DEPENDS ON PHASE 70) (PWA-05)

**UI hint**: yes

### Phase 72: OpenAPI Handoff + CI + E2E Verification

**Goal**: The single `openapi.json` is extended additively with all client paths under the `Client-Portal` tag; `schema.d.ts` is byte-stably regenerated; `client-pwa` CI gates (typecheck/lint/test) run in the workflow; drift gate confirms the staff contract is byte-identical to `contract-freeze-v1.11.0`; and the full client journey passes a live E2E walkthrough
**Depends on**: Phase 71
**Requirements**: HND-01, HND-02, HND-03, VER-01, VER-02, VER-03, VER-04
**Success Criteria** (what must be TRUE):

  1. All client-facing paths appear in `openapi.json` under the `Client-Portal` tag with `client_` operationId prefix; `git diff --exit-code` against the frozen v1.11 staff paths shows zero deletions/modifications (additions only)
  2. `schema.d.ts` is regenerated byte-stably; a new `_v20Checks` `AssertNonNever` block covers every client path×method combination; existing `_v1xChecks` blocks are untouched
  3. CI workflow runs `client-pwa` typecheck, lint, and test gates in parallel with existing backend and admin-web gates; all gates green
  4. IDOR / anti-oracle / two-principal automated tests are green in CI; no cross-client data access is possible
  5. A live `docker compose up` + PWA walkthrough of the full client journey (phone-OTP login → home → book slot → checkout → QR check-in → history) passes end-to-end; the v2.0 runbook is authored and the walkthrough serves as the milestone gate

**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-3. Phase A: Skeleton | v1.0 | 17/17 | Complete | 2026-05-01 |
| 4-14. Auth + Clients | v1.1 | 63/63 | Complete | 2026-05-07 |
| 15-23. Memberships + Visits | v1.2 | — | Complete | 2026-05-08 |
| 24-29. Memberships Extras + Tech-Debt | v1.3 | — | Complete | 2026-05-14 |
| 30-36. Cash Sales + PT Packages | v1.4 | — | Complete | 2026-05-16 |
| 37-40. Schedule + Bookings | v1.5 | 20/20 | Complete | 2026-05-18 |
| 41-46. Email + Multi-user admin | v1.6 | 82/82 | Complete | 2026-05-21 |
| 47-53. Online Payments + 54-ФЗ | v1.7 | 47/47 | Complete | 2026-05-24 |
| 54-57. Reports + Audit Log read API | v1.8 | 10/10 | Complete | 2026-05-24 |
| 58-61. Trainers Complete | v1.9 | 22/22 | Complete | 2026-05-26 |
| 62 + 62.1. clubcore Rebrand | v1.10 | 16/16 | Complete | 2026-05-26 |
| 63-67. API Handoff + Production Hardening | v1.11 | 26/26 | Complete | 2026-05-29 |
| 68. Client Auth Foundation | v2.0 | 6/6 | Complete    | 2026-05-29 |
| 69. Client Read Endpoints + PWA Alignment | v2.0 | 3/3 | Complete    | 2026-05-29 |
| 70. Client Bookings + QR Self Check-In | v2.0 | 4/4 | Complete    | 2026-05-30 |
| 71. Client Checkout + Full PWA Wiring | v2.0 | 5/6 | In Progress|  |
| 72. OpenAPI Handoff + CI + E2E Verification | v2.0 | 0/TBD | Not started | - |

---

*Roadmap last updated: 2026-05-29 — v2.0 Frontend Integration — Client PWA roadmap created (5 phases 68-72, 47 requirements mapped, zero orphans; v1.11 shipped and archived).*

## Backlog

### Phase 999.1: WR-06 restore PT session credit on owner force-cancel (✅ DONE 2026-05-29 — quick task 260529-ny2)

**Closure note (2026-05-29):** Implemented as a **consumption-keyed** restore, not a blind +1. FSM analysis during planning showed `sessions_remaining` is decremented only at check-in (`record_pt_session` → booking `confirmed → completed`), and the owner-cancel cascades only touch `confirmed` (un-consumed) bookings — so a literal "+1 per cancel" would over-credit. The fix restores +1 **only when a live consumed `pt_session` exists for the booking** (flips it cancelled + increments, idempotent/race-safe), emits the new `pt_session_credit_restored` audit event, and removes the NOTE WR-06 block. 5/5 verified; 56 schedule integration tests green. (For a confirmed booking with no consumed session, restore is a correct no-op.)

### Phase 999.2: Wire online-payment EMAIL templates into the dispatcher (✅ DONE 2026-05-29 — quick task 260529-olc)

**Closure note (2026-05-29):** Added 4 owner-signed-off `EmailTemplate` records (mirroring the already-signed Telegram DM copy) to `online_payments/email_templates.py` + the `online_payments` branch in `dispatcher._resolve_template` (the import-linter ignore was already present at `.importlinter:189`). The email channel for online-payment notifications now resolves + renders instead of silently `KeyError`-no-opping. +21 resolve/render tests; 5/5 verified. No new ignore, no schema change, callsites/AST-gate untouched.
