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
- ✅ **v2.0 Frontend Integration — Client PWA** — Phases 68-74 + 999.3/999.4/999.5 (shipped 2026-06-02) — see [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)
- 🚧 **v2.1 Client PWA — Fill the Gaps** — Phases 75-78 (opened 2026-06-02; Phase 78 added 2026-06-02 to close audit frontend-surfacing debt) — in progress

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

<details>
<summary>✅ v2.0 Frontend Integration — Client PWA (Phases 68-74 + 999.3/999.4/999.5) — SHIPPED 2026-06-02</summary>

**Milestone Goal:** Expose gym members as a second principal via a dedicated client-facing API and wire `apps/client-pwa` to it — client auth, client-scoped reads and writes over existing domains, self-service ЮKassa checkout, QR self-check-in, and a verified full-stack end-to-end flow. Staff contract and frozen `apps/admin-web` unchanged. Audit `tech_debt` (0 blockers, 47/47 requirements, 45/47 integration wired). Full phase details in [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md).

- [x] **Phase 68: Client Auth Foundation** — `ClientPrincipal` / `require_client()` / `cc_client_*` cookies / anti-oracle OTP; CISO-01 staff byte-parity guard (CAUTH-01..06 + CISO-01..05) — completed 2026-05-29
- [x] **Phase 69: Client Read Endpoints + PWA Stack Alignment** — 9 IDOR-safe `/api/v1/client` GETs (membership/history/catalogs) + PWA pnpm/Vite-6/TS alignment + 12-case IDOR sweep (CHOME/CHIST/CPLAN + PWA-01..04/06/07) — completed 2026-05-29
- [x] **Phase 70: Client Bookings + QR Self Check-In** — self-booking (race-safe, idempotent) + cancel policy + signed ~60s QR token + anti-replay check-in `visits.channel='client_qr'` (CBOOK-01..05 + CCHK-01..03) — completed 2026-05-30
- [x] **Phase 71: Client Checkout + Full PWA Screen Wiring** — ЮKassa checkout (server-authoritative price, webhook-only activation, 54-ФЗ email gate) + Home/Profile/Plans/Checkout/Book/QR on the real backend (CPAY-01..05 + PWA-05) — completed 2026-05-30
- [x] **Phase 72: OpenAPI Handoff + CI + E2E Verification** — `Client-Portal` tag additive regen + `_v20Checks` guards + parallel client-pwa CI + staff drift gate green + live read-path E2E + v2.0 runbook (HND-01..03 + VER-01..04) — completed 2026-05-31
- [x] **Phase 73: Home restyle (Home.html)** — active-subscription Home restyled to the approved mockup (decision-driven, no formal REQ-IDs) — completed 2026-06-01
- [x] **Phase 74: Profile + Settings restyle (Profile.html / Settings.html)** — pass-style profile hero (API-backed fields only) + standalone protected `/settings` + local notif toggles + feature-flagged decor — completed 2026-06-02
- [x] **Phase 999.3: Newbie (no-subscription) Home** — server-derived `membershipState: active|newbie|lapsed` enum + data-driven onboarding strip — completed 2026-05-31
- [x] **Phase 999.4: Checkout restyle + real promo codes** — payment.html restyle + `app/modules/promo_codes/` (percentage/fixed, usage limits, migrations 0046/0047, server-authoritative discount, race-safe redemption; admin CRUD deferred) — completed 2026-05-31
- [x] **Phase 999.5: Onboarding questionnaire + post-payment receipt-email** — 4-step questionnaire persisting profile + email up-front; email-OR-phone 54-ФЗ receipt path — completed 2026-06-01

**Quick tasks (shipped separately):** 999.1 (WR-06 PT-session credit restore on owner force-cancel) + 999.2 (online-payment email-template dispatcher wiring) — both ✅ DONE 2026-05-29.

**Deferred at close (acknowledged):** WARNING-1 (cancel-booking not E2E-wired in PWA — CBOOK-05 frontend gap); WARNING-2 (receipt-destination chip removed vs 999.5-UI-SPEC D-09); 3 Phase-70 security items → `/gsd:secure-phase 70`; promo-code admin CRUD UI; live ЮKassa leg RUN-01 (OPERATOR-PENDING by design). See `.planning/milestones/v2.0-MILESTONE-AUDIT.md` + STATE.md `## Deferred Items`.

</details>

### v2.1 Client PWA — Fill the Gaps (Phases 75-78) — IN PROGRESS

**Milestone Goal:** Turn on already-built-but-hidden client PWA functionality via feature-flag flips, small backend field additions to existing schemas, and pure-frontend wiring. Fold in the two deferred v2.0 warnings. No new backend domains; payment/activation path untouched.

- [x] **Phase 75: Backend Field Additions** - Add `price_kopecks`/`auto_renew` to membership response, `notif_prefs` to `/client/me`, seed FIT15 promo (completed 2026-06-02)
- [x] **Phase 76: PWA Wiring + Cleanup** - Wire trainers/plans catalog to newbie-Home, bind PersonalDataSheet to `/client/me`, remove mock chat badge (completed 2026-06-02)
- [x] **Phase 77: v2.0 Debt Closures** - Wire `useCancelBooking()` in BookingManageSheet (WARNING-1), reconcile receipt-destination display (WARNING-2) (completed 2026-06-02)

## Phase Details

### Phase 75: Backend Field Additions
**Goal**: The client membership response exposes price and auto-renewal status; `/client/me` accepts and persists notification preferences; the FIT15 promo code is seeded and validates via the existing endpoint.
**Depends on**: Phase 74 (v2.0 shipped — client portal baseline)
**Requirements**: PMEM-01, NOTIF-01, PROMO-01
**Success Criteria** (what must be TRUE):
  1. `GET /client/membership` response includes `price_kopecks` (integer) and `auto_renew` (boolean or null if the domain has no such flag — open question resolution applies here)
  2. `PATCH /client/me` accepts a `notif_prefs` JSONB field and the value is retrievable on subsequent `GET /client/me` calls (persists across PWA reinstall / device change)
  3. `POST /client/promo/validate` with code `"FIT15"` returns a valid discount response on a clean demo DB (seed migration executed idempotently)
**Plans**: 2 plans

Plans:
- [x] 75-01-PLAN.md — Membership price/auto_renew fields + notif_prefs JSONB persistence on /client/me (PMEM-01, NOTIF-01)
- [x] 75-02-PLAN.md — FIT15 idempotent seed migration + validate-endpoint test (PROMO-01)

### Phase 76: PWA Wiring + Cleanup
**Goal**: The newbie-Home screen displays real trainer avatars and live plan-catalog chips; the Personal Data sheet reads from and saves to the backend; the mock chat-badge is gone.
**Depends on**: Phase 75
**Requirements**: NHOME-01, NHOME-02, PDATA-01, PDATA-02, CLEAN-01
**Success Criteria** (what must be TRUE):
  1. A logged-in newbie client opening the Home screen sees trainer avatars/initials sourced from `GET /client/trainers` (not the static `TRAINERS` array); overflow counter reflects live trainer count
  2. The plan info chip on newbie-Home shows the count and minimum monthly price computed from `GET /client/plans` (not the hardcoded string)
  3. Opening the Personal Data sheet shows the client's real name, phone, and email from `GET /client/me` — no placeholder/hardcoded values
  4. Editing and saving a profile field (name, email, goal, height, or weight) in the Personal Data sheet calls `PATCH /client/me` and the change persists after a full page reload
  5. The chat unread-messages badge shows 0 or is hidden; the `CONVERSATIONS` mock import is absent from `App.jsx`
**Plans**: 3 plans
**UI hint**: yes

Plans:
- [x] 76-01-PLAN.md — Wire newbie-Home trainer avatar strip + plan info chip to live catalogs (NHOME-01, NHOME-02)
- [x] 76-02-PLAN.md — Bind PersonalDataSheet read/save to /client/me with editable goal/height/weight (PDATA-01, PDATA-02)
- [x] 76-03-PLAN.md — Remove mock chat-badge CONVERSATIONS dependency + delete orphaned mock (CLEAN-01)

### Phase 77: v2.0 Debt Closures
**Goal**: The two v2.0 integration warnings are resolved: booking cancellation reaches the backend, and the post-payment receipt-destination display is consistent with the agreed UI spec.
**Depends on**: Phase 74 (v2.0 baseline; independent of Phase 75/76)
**Requirements**: FIX-01, FIX-02
**Success Criteria** (what must be TRUE):
  1. Tapping "Отменить бронь" in `BookingManageSheet` calls `POST /client/booking/{id}/cancel` via `useCancelBooking().mutateAsync`; the booking is cancelled server-side and the booking list updates without a page reload
  2. After a successful payment, the success screen either shows the receipt-destination chip ("чек отправлен на …" with `receiptEmail` or `receiptPhone`) in line with 999.5-UI-SPEC §Screen 2 D-09, or the UI-SPEC is explicitly amended with a rationale and the current state is declared the accepted behavior
**Plans**: 2 plans

Plans:
- [x] 77-01-PLAN.md — Wire cancel-confirm button in BookingManageSheet to useCancelBooking (loading + inline error + 409 mapping) + Vitest (FIX-01)
- [x] 77-02-PLAN.md — Amend 999.5-UI-SPEC D-09 to accept the no-chip PaymentSucceededView + non-behavioral cross-ref comment (FIX-02)

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 75. Backend Field Additions | 2/2 | Complete   | 2026-06-02 |
| 76. PWA Wiring + Cleanup | 3/3 | Complete   | 2026-06-02 |
| 77. v2.0 Debt Closures | 2/2 | Complete   | 2026-06-02 |
| 78. PMEM/NOTIF/PROMO Frontend Surfacing | 0/TBD | Not started | - |

### Phase 78: PMEM/NOTIF/PROMO Frontend Surfacing
**Goal**: The backend-complete v2.1 fields are surfaced in the PWA UI: the client sees their membership price and auto-renewal indicator on the Profile screen; the Settings notification toggles persist to the backend (not just localStorage); and the recommended FIT15 promo code is applied one-tap from a chip in checkout. Closes the v2.1 audit's frontend-surfacing tech debt for PMEM-01 / NOTIF-01 / PROMO-01.
**Depends on**: Phase 75 (backend fields), Phase 76 (PWA wiring patterns)
**Requirements**: PMEM-01 (frontend), NOTIF-01 (frontend), PROMO-01 (frontend)
**Success Criteria** (what must be TRUE):
  1. The Profile screen displays the client's membership `priceKopecks` (formatted ₽) and an auto-renewal indicator driven by `autoRenew` (hidden / "—" when `autoRenew` is null, per D-75-01), sourced from the real membership read (not hardcoded).
  2. Toggling a notification category in Settings (промо / расписание / тренер / звук) calls `PATCH /client/me` with `notifPrefs` and the choice persists after a full reload / fresh session (server-backed, not localStorage-only); Settings hydrates from `GET /client/me` `notifPrefs`.
  3. A recommended-promo chip in the checkout surface applies `FIT15` in one tap (calls the existing `POST /client/promo/validate`), showing the discounted amount; manual entry still works.
**Plans**: TBD
**UI hint**: yes

---

*Roadmap last updated: 2026-06-02 — v2.1 Client PWA — Fill the Gaps opened (Phases 75-77, 3 phases, 10/10 requirements mapped). ROADMAP updated in-place; milestone list entry added as 🚧 in progress.*

## Backlog

### Phase 999.1: WR-06 restore PT session credit on owner force-cancel (✅ DONE 2026-05-29 — quick task 260529-ny2)

**Closure note (2026-05-29):** Implemented as a **consumption-keyed** restore, not a blind +1. FSM analysis during planning showed `sessions_remaining` is decremented only at check-in (`record_pt_session` → booking `confirmed → completed`), and the owner-cancel cascades only touch `confirmed` (un-consumed) bookings — so a literal "+1 per cancel" would over-credit. The fix restores +1 **only when a live consumed `pt_session` exists for the booking** (flips it cancelled + increments, idempotent/race-safe), emits the new `pt_session_credit_restored` audit event, and removes the NOTE WR-06 block. 5/5 verified; 56 schedule integration tests green. (For a confirmed booking with no consumed session, restore is a correct no-op.)

### Phase 999.2: Wire online-payment EMAIL templates into the dispatcher (✅ DONE 2026-05-29 — quick task 260529-olc)

**Closure note (2026-05-29):** Added 4 owner-signed-off `EmailTemplate` records (mirroring the already-signed Telegram DM copy) to `online_payments/email_templates.py` + the `online_payments` branch in `dispatcher._resolve_template` (the import-linter ignore was already present at `.importlinter:189`). The email channel for online-payment notifications now resolves + renders instead of silently `KeyError`-no-opping. +21 resolve/render tests; 5/5 verified. No new ignore, no schema change, callsites/AST-gate untouched.

### Phase 999.3: client-pwa Home — newbie (no-subscription) state (✅ SHIPPED in v2.0 — 2026-05-31)

**Goal:** `apps/client-pwa` `HomeScreen.jsx` renders a dedicated onboarding state for an authenticated client with **no active subscription**, matching the approved mockup: hero card with "Выбрать абонемент" CTA, onboarding strip (4 steps with progress), "Первый визит — бесплатно" nudge, **locked QR placeholder** ("активируется после оплаты"), and quick tiles (Тренеры / Чат). The existing active-subscription Home state is preserved and selected by subscription status.

**Depends on:** Phase 72 (v2.0 shipped — client read endpoints + wired PWA are the baseline)
**Scope:** Frontend + a small backend addition. `/api/v1/client/home` gains a `membershipState: 'active' | 'newbie' | 'lapsed'` enum (per 999.3-CONTEXT.md D-01) so the PWA can distinguish a true newbie from a lapsed/expired member — `membership === null` alone cannot. The newbie Home renders only when `membershipState === 'newbie'`; `lapsed` keeps the existing expired/danger screen; `active` keeps the existing variant dispatch. Onboarding-strip step states are live (profile from `/client/me`, first-visit from existing bookings reads), not hardcoded. No dev-panel preview toggle — purely data-driven.
**Design input:** `.planning/design-inputs/client-pwa-newbie-and-payment/home-newbie.html`
**UI design contract:** `.planning/phases/999.3-client-pwa-home-newbie-state/999.3-UI-SPEC.md` (visuals locked; CONTEXT D-05/D-06 override its static onboarding step/progress values with live data)
**UI hint:** yes

**Plans:** 2/2 plans complete

Plans:

- [x] 999.3-01-PLAN.md — Backend: add server-derived `membershipState` enum to `/client/home` (newbie/lapsed/active) + integration tests
- [x] 999.3-02-PLAN.md — Frontend: newbie Home render gate + 5 components + live onboarding-step derivation + tests

### Phase 999.4: client-pwa Checkout — visual restyle + real promo codes (✅ SHIPPED in v2.0 — 2026-05-31)

**Goal:** Restyle the existing client checkout surface (`CheckoutSheet.jsx` + paying / success / error / return state screens) to match the approved payment mockup's visual language (amount header, order summary card, method affordances, state screens).

**Depends on:** Phase 71, Phase 72
**Scope:** Restyle the existing redirect/return/state screens under the mockup's visual language. The ЮKassa hosted-redirect flow is unchanged (D-71-04): the PWA **must not** build an in-app card-entry form and **must not** collect PAN/CVC/expiry — payment data stays on the ЮKassa hosted page. Webhook-only activation and server-authoritative pricing are untouched. The mockup's card-form, СБП bank-selection, and 3-D Secure panels are non-binding visual reference, not a contract to collect card data client-side.
**Scope expansion (discuss-phase 2026-05-31):** This phase is **no longer a pure visual restyle / frontend-only.** It also adds **real promo codes** (frontend + backend) — mirrors the 999.3 precedent of folding a backend addition into a "visual" phase. New: `promo_codes` model + `promo_redemptions` (per-client / global usage limits, `valid_from`/`valid_until`/`is_active`, percentage + fixed-amount discount types), seeded via migration (no admin UI this phase), a client validate endpoint, and server-authoritative discount recompute passed to ЮKassa. **Admin CRUD UI for promo codes is deferred to the backlog** (admin frontend not ready). See `999.4-CONTEXT.md` (D-01..D-13) for the full decision set.
**Design input:** `.planning/design-inputs/client-pwa-newbie-and-payment/payment.html`
**UI hint:** yes

**Plans:** 6/6 plans complete

Plans:

- [x] 999.4-01-PLAN.md — Backend: promo_codes + promo_redemptions models, migration 0046, idempotent seeds, import-linter registration
- [x] 999.4-02-PLAN.md — Backend: server-authoritative /client/promo/validate endpoint with per-reason errors (D-06/D-09)
- [x] 999.4-03-PLAN.md — Backend: discounted amount through checkout core + redemption recording on succeeded webhook (D-05/D-06/D-07)
- [x] 999.4-04-PLAN.md — Frontend: PaymentReturnScreen success/pending/canceled restyle + state CSS (D-10/D-11/D-12)
- [x] 999.4-05-PLAN.md — Frontend: CheckoutSheet restyle + info plate + server promo wiring (D-01/D-02/D-09/D-12/D-13)
- [x] 999.4-06-PLAN.md — GAP: fix checkout amount units — pass kopecks into checkoutCtx so CheckoutSheet shows real price (sub + pt), promo original >= discounted (CPAY-01/CPAY-02)

### Phase 999.5: client-pwa onboarding questionnaire + post-payment receipt-email (✅ SHIPPED in v2.0 — 2026-06-01)

**Goal:** Add two new `apps/client-pwa` screens matching the approved mockups, both persisted to the backend: (1) a newbie onboarding questionnaire (4 steps — имя → цель → рост/вес → проверка → «Готово!», progress segments + slide transitions) shown for new clients and finishing into newbie Home; (2) a post-payment receipt-email screen («Куда отправить чек?» — email field with validation + domain-suggestion chips, 54-ФЗ reassurance note, «Отправить чек»/«Чек не нужен», success flash) shown after a successful payment from the PaymentReturnScreen success flow.

**Depends on:** Phase 72, Phase 999.3 (newbie Home — onboarding finishes into it), Phase 999.4 (PaymentReturnScreen success flow + the `client_email_required_for_online_payment` gate)
**Scope:** Frontend + backend. Backend: new client-profile fields (`name`/`goal`/`height_cm`/`weight_kg`) with a client-portal write endpoint, and a write path for `client.email` (feeds the 54-ФЗ fiscal receipt). Frontend: reuse the existing `styles.css` token system + `.state`/`.btn` primitives — no hardcoded hex; map mockup colors to `var(--token)` (mockups share the 999.4 jade/stone palette). Onboarding profile + receipt email both persist server-side (decision: "оба на бэкенд").
**Open question (resolve in discuss/spec):** the backend currently raises `client_email_required_for_online_payment` BEFORE online payment (verified live in 999.4 UAT — dev client has no email and checkout blocks), which conflicts with collecting the receipt email *after* payment under 54-ФЗ (fiscal receipt generated at payment time). Resolve the email-timing contract — likely onboarding collects email up-front so checkout never blocks, and the post-payment screen confirms/edits the receipt destination.
**Design input:** `.planning/design-inputs/client-pwa-newbie-and-payment/onboarding.html`, `.planning/design-inputs/client-pwa-newbie-and-payment/receipt-email.html`
**UI hint:** yes

**Plans:** 8/8 plans complete

Plans:

- [x] 999.5-01-PLAN.md — Backend data layer: clients goal/height/weight/onboarding columns + 0048 migration + client_portal schemas
- [x] 999.5-02-PLAN.md — Backend client_portal endpoints: GET/PATCH /client/me (server-validated, IDOR-safe) + receiptEmail/Phone on payment-status
- [x] 999.5-03-PLAN.md — Backend gate rewrite: email-OR-phone online-payment gate + ЮKassa customer.phone receipt fallback (inspect-first)
- [x] 999.5-04-PLAN.md — Frontend onboarding: 4-step questionnaire + «Готово!» overlay + /onboarding route + newbie auto-redirect + re-entry
- [x] 999.5-05-PLAN.md — Frontend receipt-email gate (CheckoutSheet stage) + post-payment receipt-destination confirmation (anti-oracle) + human-verify checkpoint
- [x] 999.5-06-PLAN.md — Gap (UAT 10, MAJOR): retry membership checkout once with a fresh key on ЮKassa Idempotence-Key collision (fixes 502 yookassa_permanent_error)
- [x] 999.5-07-PLAN.md — Gap (UAT 12, BLOCKER) foundation: migration 0049 phone-aware fiscal_receipts + create_receipt email-OR-phone
- [x] 999.5-08-PLAN.md — Gap (UAT 12, BLOCKER): phone-only payment.succeeded webhook + ARQ dispatch fiscalize-to-phone (fixes webhook 500)
