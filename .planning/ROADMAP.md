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
- ✅ **v2.1 Client PWA — Fill the Gaps** — Phases 75-78 (shipped 2026-06-02) — see [milestones/v2.1-ROADMAP.md](milestones/v2.1-ROADMAP.md)
- ✅ **v2.2 Membership self-service depth** — Phases 79-81 + 81.1 (shipped 2026-06-03) — see [milestones/v2.2-ROADMAP.md](milestones/v2.2-ROADMAP.md)
- ✅ **v2.3 Loyalty / Club Bonuses + Real Autopay** — Phases 82-85 (shipped 2026-06-06) — see [milestones/v2.3-ROADMAP.md](milestones/v2.3-ROADMAP.md)
- ✅ **v2.4 Content & Communication — Client-First** — Phases 86-89 (shipped 2026-06-06) — see [milestones/v2.4-ROADMAP.md](milestones/v2.4-ROADMAP.md)
- ✅ **v2.5 Chat / Messaging — Client↔Gym** — Phases 90-95 (shipped 2026-06-08) — see [milestones/v2.5-ROADMAP.md](milestones/v2.5-ROADMAP.md)
- ✅ **v2.6 Referral System** — Phases 96-99 (shipped 2026-06-08) — see [milestones/v2.6-ROADMAP.md](milestones/v2.6-ROADMAP.md)
- ✅ **v3.0 Production Admin — Backend Wiring** — Phases 100-106 (shipped 2026-06-14) — see [milestones/v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md)
- ✅ **v3.1 Admin — Fill the Gaps** — Phases 107-111 (shipped 2026-06-15) — see [milestones/v3.1-ROADMAP.md](milestones/v3.1-ROADMAP.md)
- 🚧 **v3.2 Admin — Wire the Rest** — Phases 112-117 (in progress)

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
- [x] **Phase 999.3: client-pwa Home — newbie (no-subscription) state** — server-derived `membershipState: active|newbie|lapsed` + data-driven newbie Home + onboarding strip — completed 2026-05-31
- [x] **Phase 999.4: client-pwa Checkout — visual restyle + real promo codes** — payment.html restyle + `app/modules/promo_codes/` (percentage/fixed, usage limits, migrations 0046/0047, server-authoritative discount, race-safe redemption; admin CRUD deferred) — completed 2026-05-31
- [x] **Phase 999.5: client-pwa Onboarding + receipt-email** — 4-step onboarding questionnaire (name/goal/height/weight/email) + post-payment receipt-email screen + missing checkout `session.commit()` hotfix — completed 2026-06-02

</details>

<details>
<summary>✅ v2.1 Client PWA — Fill the Gaps (Phases 75-78) — SHIPPED 2026-06-02</summary>

Full phase details in [milestones/v2.1-ROADMAP.md](milestones/v2.1-ROADMAP.md).

- [x] **Phase 75: Newbie home + active home gap-close** — completed 2026-06-02
- [x] **Phase 76: Profile membership hero + money format** — completed 2026-06-02
- [x] **Phase 77: Settings notif toggles server-backed** — completed 2026-06-02
- [x] **Phase 78: FIT15 promo chip + checkout flag** — completed 2026-06-02

</details>

<details>
<summary>✅ v2.2 Membership self-service depth (Phases 79-81 + 81.1) — SHIPPED 2026-06-03</summary>

Full phase details in [milestones/v2.2-ROADMAP.md](milestones/v2.2-ROADMAP.md).

- [x] **Phase 79: Card-on-file (save-payment-method)** — completed 2026-06-02
- [x] **Phase 80: Client booking reschedule** — completed 2026-06-02
- [x] **Phase 81: Weekly activity + flag flips + card sheet** — completed 2026-06-03
- [x] **Phase 81.1: Checkout save-card gap closure** — completed 2026-06-03

</details>

<details>
<summary>✅ v2.3 Loyalty / Club Bonuses + Real Autopay (Phases 82-85) — SHIPPED 2026-06-06</summary>

**Milestone Goal:** Loyalty balance + append-only ledger, server-authoritative checkout redemption, real off-session `charge_expiring_autopay` leg, byte-stable OpenAPI freeze — all staff-free under `require_client()`, staff contract byte-identical. Full phase details in [milestones/v2.3-ROADMAP.md](milestones/v2.3-ROADMAP.md).

- [x] **Phase 82: Loyalty Foundation — Ledger + Balance + Accrual** — append-only `loyalty_ledger` (migration 0054), balance/history IDOR-safe reads, welcome auto-credit (idempotent), owner-only grant API, `loyalty_accrued` LOCKED audit event, PWA LoyaltyBalanceCard/BonusHistorySheet behind clubBonuses flag (LOYL-01..03, ACCR-01..03) — completed 2026-06-05
- [x] **Phase 83: Bonus Redemption at Checkout** — server-authoritative `discount_kopecks` recompute, idempotent overdraft-clamped webhook debit keyed on `online_payment_id`, promo-attribution fix, `loyalty_redeemed` LOCKED event (migration 0055), CheckoutSheet wired to real balance + `loyaltyRedeemKopecks` (REDM-01..03) — completed 2026-06-05
- [x] **Phase 84: Real Autopay Charge** — off-session `charge_expiring_autopay` cron with DB-claim idempotency + sha256 provider key, YooKassa off-session charge by saved `payment_method_id`, webhook-locked renewal activation, `autopay_charges` table (migration 0056) + 2 LOCKED audit events, channel-idempotent success/failure notifications (Telegram + email) (APAY-01..04) — completed 2026-06-05
- [x] **Phase 85: OpenAPI Handoff + Milestone Verification** — byte-stable `openapi.json` + `schema.d.ts` regen + `_v23Checks` AssertNonNever forward-guards; staff paths byte-identical to `contract-freeze-v1.11.0` (drift gate green); full milestone gate green (HND-01) — completed 2026-06-06

**Deferred at close (acknowledged):** Phase 83 live-ЮKassa bonus-redemption E2E + PWA bonus-UX visual; Phase 84 live off-session autopay charge — both OPERATOR-PENDING by design (no live creds; logic paths covered by ASGITransport/respx suites). ФЗ-376 consent disclosure wording (Phase 81 carry-forward) needs legal review. See `.planning/milestones/v2.3-MILESTONE-AUDIT.md` + STATE.md `## Deferred Items`.

</details>

<details>
<summary>✅ v2.4 Content & Communication — Client-First (Phases 86-89) — SHIPPED 2026-06-06</summary>

**Milestone Goal:** Client-first контент/коммуникационный слайс — gym-info/CMS, in-app notification inbox, trainer bio/detail; всё под `require_client()` (IDOR-safe), owner-only write-API + seeds (без admin-web UI), staff-контракт байт-в-байт цел. Audit `tech_debt` (13/13 requirements satisfied, 0 blockers, 7/7 E2E flows wired; live docker+browser verification deferred to per-phase HUMAN-UAT). Full phase details in [milestones/v2.4-ROADMAP.md](milestones/v2.4-ROADMAP.md).

- [x] **Phase 86: Gym-Info / CMS** — `gym` module + `GET /client/gym` + owner-only `PUT /gym` (reception 403) + seed migration 0059 + GymInfoSheet wired (GYM-01..03) — completed 2026-06-06
- [x] **Phase 87: Notification Inbox** — `in_app_notifications` + `client_push_tokens` tables (migrations 0060/0061) + client feed/mark/push endpoints + 7 system-event create_notification hooks (anti-oracle) + NotificationsSheet + bell badge (INBOX-01..05) — completed 2026-06-06
- [x] **Phase 88: Trainer Detail / Bio** — trainer bio/specialization/photo_url columns (migrations 0062/0063) + client-safe `GET /client/trainers/{id}` (404-collapse) + owner PATCH (XSS-guarded photo_url) + TrainerDetailSheet (TRNR-01..04) — completed 2026-06-06
- [x] **Phase 89: OpenAPI Handoff + Milestone Verification** — byte-stable openapi.json + schema.d.ts regen + `_v24Checks` AssertNonNever[8] forward-guards + staff drift gate green + full milestone gate (HND-01) — completed 2026-06-06

**Deferred at close (acknowledged tech_debt):** live docker+browser verification for the 3 graduated PWA sheets (86/87/88 HUMAN-UAT — gym render+badge, notification round-trip+badge, trainer render); INBOX-04 real web-push delivery (storage/rails only); advisory UI-review nits; pre-existing flaky test_freeze_race + promo F821 + test_alembic_clean (NOT v2.4 regressions). See `.planning/v2.4-MILESTONE-AUDIT.md` + STATE.md `## Deferred Items`.

</details>

<details>
<summary>✅ v2.5 Chat / Messaging — Client↔Gym (Phases 90-95) — SHIPPED 2026-06-08</summary>

- [x] **Phase 90: Messaging Domain + REST Foundation + WS Scaffold** (3 plans) — completed 2026-06-07
- [x] **Phase 91: Read Receipts + Typing Indicators** (2 plans) — completed 2026-06-07
- [x] **Phase 92: Photo Attachments** (3 plans) — completed 2026-06-07
- [x] **Phase 93: Telegram Bridge** (2 plans) — completed 2026-06-08
- [x] **Phase 94: PWA ChatScreen Wiring** (2 plans) — completed 2026-06-08
- [x] **Phase 95: OpenAPI Handoff + Milestone Verification** (2 plans) — completed 2026-06-08

Full phase detail: [milestones/v2.5-ROADMAP.md](milestones/v2.5-ROADMAP.md).

**Deferred at close (acknowledged):** RCPT-02 typing producer → v2.6 (Telegram has no typing API; admin-web frozen until v2.6); Phase 94 HUMAN-UAT (pixel-perfect parity, live WS round-trip, photo flow on a real device — see 94-HUMAN-UAT.md); carried-forward flakes (test_freeze_race, promo F821, test_alembic_clean). See `.planning/milestones/v2.5-MILESTONE-AUDIT.md` + STATE.md `## Deferred Items`.

</details>

<details>
<summary>✅ v2.6 Referral System (Phases 96-99) — SHIPPED 2026-06-08</summary>

**Milestone Goal:** Клиент приглашает друзей персональным реф-кодом; обе стороны получают бонус на `loyalty_ledger` после первой покупки приглашённого; экран «Приведи друга» перенесён пиксель-в-пиксель с готового макета. Всё под `require_client()`, IDOR-safe; бонусы server-authoritative (webhook-only); `apps/admin-web` заморожен. Audit `tech_debt` (8/8 requirements satisfied, 0 blockers, full E2E referral flow wired, milestone gate green). Full phase detail: [milestones/v2.6-ROADMAP.md](milestones/v2.6-ROADMAP.md).

- [x] **Phase 96: Referral Domain Backend** (3 plans) — idempotent referral codes, capture (self-referral block, 1-bonus-per-referee), public deep-link resolver, owner-only bonus config + seed; LOCKED audit events pre-registered (REFER-01/02-backend/03/07) — completed 2026-06-08
- [x] **Phase 97: Reward Crediting** (3 plans) — dual bonus on payment.succeeded first purchase, co-transactional, idempotent partial UNIQUE, config-sourced amounts, referrer-alive void; referral_bonus_accrued LOCKED event (REFER-04) — completed 2026-06-08
- [x] **Phase 98: PWA ReferralScreen** (3 plans) — graduated from D-71-09, pixel-perfect port (code/link/copy, share chips, steps), real invitees + «Уже накоплено» via @/data, /i/<code> deep-link capture, tier tracker hide-for-future (REFER-02-PWA/05/06) — completed 2026-06-08
- [x] **Phase 99: OpenAPI Handoff + Milestone Verification** (2 plans) — byte-stable openapi.json + schema.d.ts + _v26Checks AssertNonNever[8] + staff drift gate green + full milestone gate (HND-01) — completed 2026-06-08

**Deferred at close (acknowledged tech_debt):** WARN-1 zeroed-referrer-bonus → permanent "pending" invitee (latent cross-phase coupling; never at seeded default); 98-HUMAN-UAT browser-only items (pixel parity, live deep-link round-trip, share chips); dev-DB clean re-migrate before live manual checks; cosmetic landing bonus-preview stub + PWA cast escape hatch. See `.planning/milestones/v2.6-MILESTONE-AUDIT.md` + STATE.md `## Deferred Items`.

</details>

<details>
<summary>✅ v3.0 Production Admin — Backend Wiring (Phases 100-106) — SHIPPED 2026-06-14</summary>

Full phase details archived in [milestones/v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md). 7/7 phases, 24 plans, 30/30 requirements; milestone gate green (mypy --strict + lint-imports + pytest 2867 + admin-app 337 + client-pwa 222 + Redocly); `apps/admin-web` deleted, `apps/admin-app` live on the real backend; OpenAPI byte-stable (zero new routes). Deferred-at-close: 4 P101–104 live-UAT gaps (per D-V30-VERSION — most ad-hoc live-verified 2026-06-14) + 1 future-milestone-sequencing note (see STATE.md `## Deferred Items`).

### v3.0 Production Admin — Backend Wiring (Phases 100-106)

**Milestone Goal:** Превратить `apps/admin-app` из mock-прототипа в боевую staff-админку на реальном backend (одно-клубный срез по уже существующим доменам) и удалить `apps/admin-web`, перенеся его роль RBAC-reference.

**Wire-only — no new backend domains.** Every screen maps to an already-shipped endpoint. Multi-branch screens stay hidden-for-future (D-V30-BRANCH). admin-web deleted after admin-app auth+RBAC is proven (D-V30-ADMINWEB-DELETE).

## Phase Details

### Phase 100: Foundation + Authentication

**Goal**: admin-app is in the clubcore repo, talks to the real backend over staff cookies + CSRF, the deferred screens are gated, and a staff member can log in / log out / see their role reflected in the UI.
**Depends on**: Nothing (first phase of v3.0)
**Requirements**: FND-01, FND-02, FND-03, FND-04, AUTH-01, AUTH-02, AUTH-03
**Success Criteria** (what must be TRUE):

  1. `apps/admin-app` builds, tests, and runs inside the clubcore pnpm workspace (or chosen alternative); a dedicated CI job passes `check`/`test`/`build`.
  2. The staff login form submits to `/api/v1/auth/login`, persists the httpOnly `cc_access`/`cc_refresh` session cookies, captures the JS-readable `clubcore_csrf` token, and a browser refresh keeps the session alive (via `GET /api/v1/auth/me`).
  3. All mutating requests carry `X-CSRF-Token`; a `401` response navigates to `/login` without a crash.
  4. Deferred screens (Branches, Branch-Settings, System-Settings, ImportExport, Duplicates, Archive, Trash, Messages, Roles, Notifications-mgmt) render a "coming soon" placeholder — not broken, not wired.
  5. Owner vs reception role is visible in the UI; each domain's per-domain zod contract seam is in place (mock `queryFn` removal path ready for Phase 101+).

**RBAC re-home (D-V30, decided at plan time):** port `can.ts`/`registry.ts`/`types.ts` byte-identically into `apps/admin-app/src/shared/session/` and repoint the CISO-01 `test_rbac_parity.py` at admin-app — admin-web is left untouched and deleted in Phase 105.
**Plans**: 4 plans, 4 waves

- [x] 100-01-PLAN.md — Workspace absorption (Bun→pnpm `@clubcore/admin-app`, api-client dep, dev proxy, ESLint boundary + VITE_API_MODE chokepoint, dedicated CI job) [FND-01] · wave 1
- [x] 100-02-PLAN.md — Transport seam (staffRequest: credentials+CSRF `clubcore_csrf`, 401→refresh→retry→session_expired, authBus, QueryClient cache onError; mockResponse preserved) [FND-02] · wave 2
- [x] 100-03-PLAN.md — Auth domain (zod seam + useSession over `/auth/me`, login/logout, RequireAuth guard + 401-expiry redirect, password-reset, hide twofa, anti-oracle login errors, mock-removal doc) [FND-03, AUTH-01, AUTH-02] · wave 3
- [x] 100-04-PLAN.md — RBAC re-home + hide-for-future (port can/registry + repoint parity test, ComingSoon placeholder + deferred-route swap + nav removal, session-driven role badge + can()-gated sidebar) [FND-04, AUTH-03] · wave 4

**UI hint**: yes

### Phase 101: Clients + Memberships

**Goal**: Staff can manage the full client-membership lifecycle on real data — list, view, create, edit, delete clients; manage plans; sell, freeze, renew, and cancel memberships.
**Depends on**: Phase 100
**Requirements**: CLI-01, CLI-02, CLI-03, MEM-01, MEM-02, MEM-03
**Success Criteria** (what must be TRUE):

  1. Clients list renders real `GET /api/v1/clients` with server-side search and `{items,total,page,pageSize}` pagination; loading, error, and empty states are visible.
  2. Client detail shows the client's profile, active memberships, visits, and payments from the real backend; mock `queryFn`s are removed.
  3. Create and edit client forms validate via Zod, submit to `POST`/`PATCH /api/v1/clients`, and soft-delete via `DELETE`; owner-only actions are gated for reception.
  4. Plans screen lists real membership plans and PT-package plans; create/edit are owner-only gated with a `403` surfaced as a friendly state.
  5. Staff can sell a membership or PT-package (cash, with `Idempotency-Key`); and manage a membership lifecycle — freeze, unfreeze, renew, cancel + refund — with rules surfaced.

**Plans**: 4 plans, 3 waves

- [x] 101-01-PLAN.md — Clients domain: list (server search+pagination, filter/sort reduction), detail profile head, create/edit/soft-delete (Zod, owner-gated delete) [CLI-01, CLI-03] · wave 1
- [x] 101-02-PLAN.md — Plans domain: membership-plans + pt-package-plans list + owner-only CRUD (immutable-field rules, 403 friendly state) [MEM-01] · wave 1
- [x] 101-03-PLAN.md — Memberships + PT-package lifecycle: sell (cash, Idempotency-Key), freeze/unfreeze (optimistic), renew, cancel (owner), refund (required reason, full-only) + net-new RefundScreen [MEM-02, MEM-03] · wave 2
- [x] 101-04-PLAN.md — Client-detail child reads: memberships/visits/payments tabs on real data (payments /by-client/{id}, read-only) with per-tab states [CLI-02] · wave 3

**UI hint**: yes

### Phase 102: Schedule + Trainers

**Goal**: Staff can manage trainer availability and PT bookings, and owner can configure trainer payroll — all on real backend data.
**Depends on**: Phase 101
**Requirements**: SCH-01, SCH-02, TRN-01, TRN-02
**Success Criteria** (what must be TRUE):

  1. Schedule screen renders real trainer slots, recurring templates, and time-off blocks; create/edit are owner-only; mock `queryFn`s removed.
  2. Staff can book / cancel / complete a PT booking against a slot; race-safe conflict (slot taken) surfaces as a clear state, not a crash.
  3. Trainers list and detail render real catalog data (name, bio, specialization) from `/trainers`.
  4. Owner can view trainer payroll — comp-config, accrual preview, run, and pending→paid — on the trainer detail or finance surface; reception is gated with a `403`.

**Plans**: 4 plans, 2 waves

- [x] 102-01-PLAN.md — Schedule write layer: features/schedule http (slots/templates/time-off zod + keys + Idempotency-Key hooks) + owner-only ScheduleManagementModal (slot/template/time-off tabs, time_off_booked_conflict force-override) [SCH-01] · wave 1
- [x] 102-02-PLAN.md — Trainers catalog + CRUD: features/trainers http (queries + PATCH/POST/DELETE), TrainersPage reduction (hide Load/Requests/Earnings/KPIs), owner edit/create/delete affordances, TrainerHero/Overview real data, TrainerFormModal wired [TRN-01] · wave 1
- [x] 102-03-PLAN.md — Bookings lifecycle + calendar merge: features/bookings http (create/cancel/complete-via-pt-sessions), BookingModal (race-safe 409), BookingDetailModal (24h cancel + complete), SchedulePage slot+booking merge + owner FAB, OverviewTab today-schedule [SCH-02] · wave 2
- [x] 102-04-PLAN.md — Payroll: features/payroll http (comp-config INSERT-only + preview→run + accruals + mark-paid, owner-only enabled-gated), PayoutsTab wired (reception Lock state, kopecks↔rubles/bps↔pct, 409 already_run/already_paid) [TRN-02] · wave 2

**UI hint**: yes

### Phase 103: Attendance + Finance

**Goal**: Reception can check in visits on real data; owner can see the cashbox, revenue, and online payments — all without mocks.
**Depends on**: Phase 102
**Requirements**: ATT-01, ATT-02, FIN-01, FIN-02
**Success Criteria** (what must be TRUE):

  1. Attendance screen renders real visits list (`/visits`) with loading/error/empty states; reception can check in a client via `POST /visits {clientId}`.
  2. Load screen renders the real hourly/daily visits aggregate from `/reports/visits`; no NaN on empty buckets.
  3. Cashbox screen renders the real cash ledger (`/payments`) with sell + refund records and daily totals; the refund flow is wired (rows read-only); mock removed.
  4. Finance screen renders real revenue report (`/reports/revenue`, net-of-refund, by method/subject) and online payments read; mock removed.

**Plans**: 4 plans, 3 waves

- [x] 103-01-PLAN.md — Domain foundation: extend visits (list/check-in/gym-meta) + payments (global ledger) hooks; NEW reports domain (revenue+visits schemas/keys/api) + zero-fill utils [ATT-01, ATT-02, FIN-01, FIN-02] · wave 1
- [x] 103-02-PLAN.md — Attendance: real visits list + CheckInModal (client picker, optimistic, 3 distinct 409 states), hide 9 mock analytics widgets [ATT-01] · wave 2
- [x] 103-03-PLAN.md — Cashbox + Load + nav gating: /payments ledger (read-only refund rows + client-side daily totals), zero-filled /reports/visits, Касса+Загруженность ownerOnly, shared DateRangePicker, Lock-EmptyState [FIN-01, ATT-02] · wave 2
- [x] 103-04-PLAN.md — Finance: 2 real tabs (Выручка /reports/revenue day|month + Онлайн-платежи method=online slice), zero-filled signed-net chart, Lock guard, mock tabs + CSV export removed [FIN-02] · wave 3

**UI hint**: yes

### Phase 104: Dashboard, Reports + Settings

**Goal**: The landing dashboard shows live KPI data; all four reports render with CSV export; owner can manage users and profile/sessions — all on real data.
**Depends on**: Phase 103
**Requirements**: RPT-01, RPT-02, RPT-03, SET-01, SET-02
**Success Criteria** (what must be TRUE):

  1. Dashboard `/` renders real KPI aggregates from `/reports/*` (revenue/clients/visits) and charts; empty-data guards prevent NaN/null crashes.
  2. Reports screen renders all four aggregate reports (revenue / clients / visits / trainers) with working CSV export (UTF-8 BOM, Cyrillic-safe).
  3. Audit screen renders the real owner-only audit log with filters, stable pagination, and CSV export; reception sees a gated/disabled state.
  4. Settings (profile) reads/edits the current staff profile + theme and lists active sessions from `/auth/sessions`; sessions can be revoked.
  5. Users screen (owner-only) wires invite / list / deactivate / soft-delete against `/api/v1/users`; reception sees a gated state.

**Plans**: 5 plans

- [x] 104-01-PLAN.md — Foundation: downloadCsv helper + reports clients/trainers hooks + audit domain layer
- [x] 104-02-PLAN.md — Dashboard role-gated composition on real /reports/* + bookings/memberships
- [x] 104-03-PLAN.md — Reports 4-tab page (+CSV) + Audit page (filters/pagination/CSV) + «Журнал действий» nav
- [x] 104-04-PLAN.md — Settings: read-only profile (no PATCH /auth/me) + active sessions (revoke + self-revoke→/login)
- [x] 104-05-PLAN.md — Users admin (owner-only) in Settings→Team: invite/list/deactivate/reactivate/soft-delete

**UI hint**: yes

### Phase 105: admin-web Retirement + RBAC Re-home

**Goal**: `apps/admin-web` is deleted and the three-way RBAC-parity reference is re-homed so the chosen guard stays green — CI, workspace, and drift-gate stay valid after removal.
**Depends on**: Phase 100 (admin-app auth+RBAC proven)
**Requirements**: ADMW-01, ADMW-02, ADMW-03
**Success Criteria** (what must be TRUE):

  1. `apps/admin-web` directory is removed from the repo; workspace entry, CI job, ESLint/import-linter zones, and dangling references are cleaned with no build errors.
  2. The three-way RBAC-parity guard (`permissions.py` ↔ chosen admin-app anchor ↔ `registry.ts` or equivalent) is re-homed and green — the mechanic decided at Phase 100 plan is implemented.
  3. The OpenAPI staff drift-gate and `@clubcore/api-client` codegen pipeline pass after removal; no consumer is left dangling.

**Plans**: 1 plan

- [x] 105-01-PLAN.md — delete apps/admin-web + regenerate lockfile + repoint CISO-01 byte-parity guard (admin-web→admin-app) + update functional doc pointers + verify gates green

### Phase 106: OpenAPI Handoff + Milestone Gate

**Goal**: The staff OpenAPI contract is byte-stable, the full milestone gate passes, and v3.0 is verified complete.
**Depends on**: Phase 105
**Requirements**: HND-01
**Success Criteria** (what must be TRUE):

  1. `openapi.json` + `schema.d.ts` regenerate byte-stably; no new backend domains means the staff contract is unchanged vs `contract-freeze-v1.11.0`.
  2. Staff drift-gate is green; full milestone gate passes: mypy --strict + lint-imports + pytest + admin-app `check`/`test` + Redocly.
  3. All 30 v3.0 requirements are verified satisfied (no open blockers).

**Plans**: 2 plans, 2 waves

- [x] 106-01-PLAN.md — NO-OP contract freeze: regenerate openapi.json + schema.d.ts + assert BOTH byte-UNCHANGED (zero git diff — v3.0 added zero routes); _v26Checks[8] intact, no _v30Checks; Redocly clean [HND-01] · wave 1
- [x] 106-02-PLAN.md — Full 7-gate green vs live docker stack (backend ruff/mypy/lint-imports/alembic/pytest + frontend recursive + admin-app + client-pwa + Redocly) + flake classification (only the 4 accepted) + CISO-01 parity green + 30/30 reqs + 106-GATE-EVIDENCE.md [HND-01] · wave 2

</details>

<details>
<summary>✅ v3.1 Admin — Fill the Gaps (Phases 107-111) — SHIPPED 2026-06-15 — full detail in milestones/v3.1-ROADMAP.md</summary>

### v3.1 Admin — Fill the Gaps (Phases 107-111)

**Milestone Goal:** Довести staff-админку до полнофункционального состояния — закрыть FE-заглушки на текущем backend, проверить вживую отложенный P102, и добавить минимальный backend для редактируемых Настроек (зал/график/запись/уведомления) + профиля.

**Scope principle (D-V31-SCOPE):** v3.1 сознательно ослабляет v3.0 `D-V30-SCOPE-WIRE` (wire-only) — **новые backend-эндпоинты разрешены**, но минимальны и в рамках single-club; переиспользовать существующее где можно (v2.4 `gym` модуль, notification-диспетчер, уже-готовые PT-package хуки). Because new endpoints land, the milestone OpenAPI contract WILL change (additive, NOT byte-stable) — the handoff phase regenerates artifacts and runs the full gate.

**Backend discipline (carried, all phases that touch backend):** FastAPI modular monolith — raw-SQL cross-module reads / Protocol-slot writes (D-20-MODULE), `client_id`/actor only from principal where relevant (D-20-IDOR), RBAC byte-parity with admin-app `can.ts`/`registry.ts` (CISO-01; extend `Resource`/`OWNER_ONLY` if a new gated resource appears), LOCKED audit events pre-registered before any callsite (INFRA-15), Alembic migrations round-trip clean, money in integer kopecks, all dates/windows Europe/Moscow. Frontend: per-domain Zod seam + TanStack Query + `staffRequest` (cc_* cookies + `X-CSRF-Token`) + `can()`-gating; per-attempt `Idempotency-Key` on sales.

### Phase 107: Admin FE Completion on Existing Backend

**Goal**: Every remaining staff toast-stub becomes a real, reachable action against an already-shipped endpoint — plan create/edit, PT-package sell/cancel/refund, and client delete from the hero — with no backend or contract change.
**Depends on**: Nothing (v3.0 admin-app shipped; first phase of v3.1)
**Requirements**: PLAN-01, PLAN-02, PTPKG-01, PTPKG-02, CLI-04
**Success Criteria** (what must be TRUE):

  1. Owner can create AND edit a membership plan from a real form modal (`POST`/`PATCH /api/v1/membership-plans`) with Zod validation, immutable-field rules (durationDays/freezeDaysLimit), and 422 field-error mapping — the toast stub is gone.
  2. Owner can create AND edit a PT-package plan from a real form modal (`POST`/`PATCH /api/v1/pt-package-plans`) with name editable + other fields immutable per the backend contract — the toast stub is gone.
  3. Staff can sell a PT-package to a client from a reachable UI (PtPackageScreen in SubscriptionModal or equivalent) — cash, per-attempt `Idempotency-Key` — and an `amount_mismatch` 422 surfaces as a clear state, not a crash.
  4. Staff can cancel and refund a client's PT-package from reachable TrainingsTab actions (refund owner-only, required reason) using the existing cancel/refund hooks.
  5. Staff can delete a client directly from the client-page hero — a real owner-gated soft-delete (`DELETE /api/v1/clients/{id}`) behind a confirm — replacing the `toast.info(...)` stub.

**Plans**: 3 plans, 1 wave

- [x] 107-01-PLAN.md — Plan create/edit: shared PlanFormModal (kind×mode, Zod safeParse, immutable-on-edit, 422 mapping) wired into PlansPage [PLAN-01, PLAN-02] · wave 1
- [x] 107-02-PLAN.md — PT-package instance UI: PtPackageSellModal (locked amount + amount_mismatch) + cancel/refund required-reason dialogs + TrainingsTab sell button & kebab [PTPKG-01, PTPKG-02] · wave 1
- [x] 107-03-PLAN.md — Client delete from hero: real owner-gated useDeleteClient soft-delete + navigate to clients list, toast.info stub removed [CLI-04] · wave 1

**UI hint**: yes

### Phase 108: Editable Settings — Backend + Wiring

**Goal**: Owner can edit the single-club operational settings — gym card, working hours / breaks / closures, online-booking rules, and the client-notification matrix — and the changes persist and are honored by the schedule, the booking window, the client PWA, and the notification dispatcher.
**Depends on**: Phase 107
**Requirements**: CFG-01, CFG-02, CFG-03, CFG-04
**Success Criteria** (what must be TRUE):

  1. Owner can edit the gym card (name, address, coordinates, contacts, description, amenities, capacity) and changes persist across reload; reception is `403`. Reuse/extend the v2.4 `gym` module (`PUT /gym`) where possible.
  2. Owner can edit working hours + technical breaks + holiday/closure dates; they persist and the schedule / booking window respects them.
  3. Owner can edit online-booking rules (schedule step, booking-ahead window, booking cutoff, cancel/reschedule policy + no-show penalty, group limit + waitlist, PT self-booking flags); they persist and apply to the client PWA.
  4. Owner can edit the client-notification matrix (per-trigger × per-channel toggles) + sender signature + quiet hours; they persist and are honored by the notification dispatcher.
  5. Each Settings surface is owner-gated in the UI (reception sees a friendly Lock/403 state, not a crash); every new endpoint is RBAC byte-parity safe and added additively to the staff contract.

**Plans**: 5 plans (4 waves)
Plans:
**Wave 1**

- [x] 108-01-PLAN.md — Backend foundation: RBAC (EDIT,SETTINGS) byte-parity + 4 LOCKED audit events + 3 settings singleton models + gym lat/lng + migrations 0070/0071

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 108-02-PLAN.md — Settings endpoints (hours/booking/notifications GET+PUT, RBAC+CSRF+audit) + staff GET /api/v1/gym + lat/lng (CFG-01 backend complete)
- [x] 108-03-PLAN.md — Enforcement: bookings.service reads booking_config + working_hours/closures; notifications dispatcher matrix gate + quiet hours + always-on (raw-SQL cross-module reads)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 108-04-PLAN.md — FE data layer: Zod wire+form schemas + 8 TanStack Query hooks (gym/hours/booking/notifications) gated by can()

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 108-05-PLAN.md — FE section wiring: BranchSection/HoursSection/BookingSection/NotificationsSection + Lock cards + SaveBar + navigate-away guard + human-verify

**UI hint**: yes

### Phase 109: Profile & Security — Backend + Wiring

**Goal**: A staff member can edit their own profile and change their own password from Settings, on real new endpoints, with the existing session-revocation discipline.
**Depends on**: Phase 108
**Requirements**: PROF-01, PROF-02
**Success Criteria** (what must be TRUE):

  1. Staff can edit their own profile — full name, email, theme — via a new `PATCH /api/v1/auth/me`, replacing the read-only profile (the v3.0 `D-104-04-PROFILE-READONLY` gap closes).
  2. Profile edits persist and are reflected after reload and in the session-driven sidebar identity.
  3. Staff can change their own password from Settings (current + new, validated to the existing 12-char NIST policy); a wrong current password surfaces as a clear field error.
  4. A successful password change revokes the staff member's other sessions per the existing refresh-family-revoke discipline.

**Plans**: 4 plans in 2 waves
Plans:
**Wave 1**

- [x] 109-01-PLAN.md — Backend foundation: profile_updated audit event + ProfileUpdate/ChangePassword schemas + update_profile/change_password/revoke-others-except-current service fns
- [x] 109-03-PLAN.md — FE foundation: ProfileUpdate/ChangePassword zod schemas + useUpdateProfile/useChangePassword hooks

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 109-02-PLAN.md — Backend routes + tests: PATCH /auth/me + POST /auth/change-password (verify_csrf, auth-only) + ASGITransport integration tests
- [x] 109-04-PLAN.md — FE wiring: editable ProfileSection (SaveBar) + ChangePasswordModal + SettingsPage registration (human-verify checkpoint)

**UI hint**: yes

### Phase 110: Live Verification — Deferred P102 (Bookings + Payroll)

**Goal**: The P102 booking lifecycle and trainer payroll that were `data-setup-blocked` at v3.0 close are verified working live against the running stack on seeded data.
**Depends on**: Phase 109
**Requirements**: VER-01, VER-02
**Success Criteria** (what must be TRUE):

  1. On seeded data against the running stack, the booking lifecycle works end-to-end — create a booking against a slot, cancel it, and complete one via pt-sessions — closing the P102 `data-setup-blocked` deferral.
  2. A race conflict (slot already taken) surfaces as a clear state, not a crash, when exercised live.
  3. On seeded data, trainer payroll works end-to-end — comp-config → accrual preview → run → pending→paid — and reception is gated (zero owner-only payroll API calls).
  4. The seed path/fixtures used for live verification are captured so the walkthrough is repeatable (the v3.0 data-setup blocker does not recur).

**Plans**: 3 plans (2 waves)
Plans:
**Wave 1**

- [x] 110-01-PLAN.md — Committed repeatable seed (`scripts/seed_p102_walkthrough.py`, idempotent, local-only-guarded) + captured live-HTTP walkthrough script/README (criterion #4)

**Wave 2** *(blocked on Wave 1; 110-02 and 110-03 run in parallel)*

- [x] 110-02-PLAN.md — VER-01 booking lifecycle E2E (create→cancel→complete-via-pt-session) + slot-already-taken race conflict (real-commit) on seeded Postgres
- [x] 110-03-PLAN.md — VER-02 payroll lifecycle E2E (comp-config→preview→run→pending→paid) + accrual snapshot assertions + reception-403 RBAC negative

### Phase 111: OpenAPI Handoff + Milestone Gate

**Goal**: The changed staff OpenAPI contract is regenerated and forward-guarded, and the full milestone gate passes — closing v3.1.
**Depends on**: Phase 110
**Requirements**: HND-01 (milestone-handoff requirement — not one of the 13 feature reqs; see note)
**Success Criteria** (what must be TRUE):

  1. `openapi.json` + `packages/api-client/src/schema.d.ts` are regenerated to reflect the new v3.1 routes (`PATCH /auth/me`, password-change, the Settings persistence endpoints) — additively, NOT byte-stable — and a `_v31Checks` `AssertNonNever` forward-guard tuple covers each new path×method.
  2. The full milestone gate is green: mypy `--strict` + lint-imports + pytest + admin-app `check`/`test`/`build` + Redocly lint; the CISO-01 RBAC byte-parity guard is green.
  3. All 13 v3.1 feature requirements (PLAN/PTPKG/CLI/CFG/PROF/VER) are verified satisfied with no open blockers.

**Plans**: 2 plans
**Wave 1**

- [x] 111-01-PLAN.md — Regen openapi.json + schema.d.ts + add _v31Checks forward-guard + commit

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 111-02-PLAN.md — Run full milestone gate + confirm 13/13 reqs + write 111-GATE-EVIDENCE.md handoff doc

</details>

### v3.2 Admin — Wire the Rest (Phases 112-117)

**Milestone Goal:** Закрыть операционную полноту staff-админки — критичные дыры (возврат произвольного платежа, смена роли сотрудника) и «дожимку» уже готового backend (промокоды, аналитика посещаемости, экспорт, чат-инбокс). Приоритет по backend-готовности: большинство фич — дешёвое FE-wiring к уже существующим эндпоинтам.

**Scope principle (D-V32-SCOPE):** Additive-контракт (не byte-stable). Урок v3.0/v3.1: **≥1 contract-тест на домен**, парсящий РЕАЛЬНЫЙ ответ backend (mock↔real schema-дрейф дважды прошёл формальный гейт, пойман только browser-UAT). `_v32Checks` forward-guard закрывает milestone.

**Backend discipline (carried):** FastAPI modular monолит — raw-SQL cross-module reads / Protocol-slot writes (D-20-MODULE), RBAC byte-parity (CISO-01; extend `Resource`/`OWNER_ONLY` + `can.ts`/`registry.ts` для новых gated ресурсов: `REFUND`/`PAYMENTS`, `USERS_ROLE`), LOCKED audit events pre-registered (INFRA-15), Alembic round-trip clean, деньги в integer kopecks, даты Europe/Moscow. Frontend: per-domain Zod seam + TanStack Query + `staffRequest` (`cc_*` cookies + `X-CSRF-Token`) + `can()`-gating; `Idempotency-Key` на денежных мутациях.

**Execution order: 112 → 113 → 114 → 115 → 116 → 117**

- [ ] **Phase 112: Critical Money & Access (P0)** — arbitrary payment refund (`POST /payments/{id}/refund` + `Action.REFUND` RBAC + un-stub Cashbox/Finance) + staff role-change (`PATCH /users/{id}/role` + modal + audit)
- [ ] **Phase 113: Promo Codes CRUD (P1)** — staff CRUD over existing `promo_codes` backend; wire PlansPage «Скидки и акции» mock→real
- [ ] **Phase 114: Attendance Analytics on Existing Reports (P1)** — heatmap/hour-curve/day-of-week/peak/frequency/duration FE widgets wired to existing `reports/visits` aggregate
- [ ] **Phase 115: Live & Advanced Analytics (P1)** — cohort/anomaly/risk (new window-function queries) + LiveNow (`/reports/load/now`) + dashboard activity-feed/trainer-KPI/plans sales-chart on existing read endpoints
- [ ] **Phase 116: Chat Inbox & Exports (P2)** — staff REST over existing messaging module (list threads, send/reply) + CSV exports over existing `csv_export.py`
- [ ] **Phase 117: OpenAPI Handoff + Milestone Gate** — additive `openapi.json` + `schema.d.ts` regen for new v3.2 routes + `_v32Checks` forward-guard + ≥1 real-backend contract test per new domain + full gate green

## Phase Details

### Phase 112: Critical Money & Access

**Goal**: Owner can refund any recorded payment (not just membership/PT) and can change a staff user's role — the two P0 operational gaps that block daily gym management.
**Depends on**: Nothing (first phase of v3.2)
**Requirements**: REF-01, TEAM-01
**Success Criteria** (what must be TRUE):

  1. Owner can select any payment row in Cashbox or Finance and issue a refund with a required reason; the refund is recorded in the ledger and the cashbox balance reflects it — the `T-103-03-FAKEREFUND` read-only stub is gone.
  2. The refund endpoint enforces RBAC — reception gets a 403; owner sees the refund action; a duplicate refund attempt is rejected gracefully.
  3. Owner can open a staff user's profile in Team settings and change their role (owner ↔ reception) via a modal; the change persists and the new role is reflected on next login.
  4. Role-change is audited; reception cannot access the role-change UI or endpoint (403).

**Plans**: 3 plans, 2 waves
Plans:
**Wave 1** *(parallel — disjoint backend modules)*
- [x] 112-01-PLAN.md — Backend refund: POST /payments/{id}/refund (by-id, partial allowed, approach-b keeps frozen unique constraint) + new exceptions + ASGITransport tests [REF-01] · wave 1
- [x] 112-02-PLAN.md — Backend role-change: PATCH /users/{id}/role + user_role_changed LOCKED audit event + self/last-owner guards + ASGITransport tests [TEAM-01] · wave 1

**Wave 2** *(blocked on 112-01 + 112-02)*
- [x] 112-03-PLAN.md — FE wiring: useRefundPayment + useChangeUserRole hooks + RefundModal (Cashbox + Finance, owner-gated) + ChangeRoleModal (Settings Team) + human-verify [REF-01, TEAM-01] · wave 2
**UI hint**: yes

### Phase 113: Promo Codes CRUD

**Goal**: Owner can manage promo codes directly in the admin app — create, edit, deactivate — and the Plans page displays real promo data instead of mock cards.
**Depends on**: Phase 112
**Requirements**: PROMO-01, PROMO-02
**Success Criteria** (what must be TRUE):

  1. Owner can create a new promo code (percentage or fixed discount, with usage limits and validity window) from the Plans page; the code is persisted to the `promo_codes` backend and immediately visible.
  2. Owner can edit an existing promo code (adjust limits, dates, description) and deactivate/archive it; reception is gated from write actions.
  3. The Plans page «Скидки и акции» section lists real promo codes from `GET /api/v1/promo-codes` — mock cards are replaced; empty state renders correctly.

**Plans**: 3 plans
- [x] 113-01-PLAN.md — Backend admin CRUD + migration 0072 + RBAC parity (permissions.py/can.ts/registry/parity test)
- [x] 113-02-PLAN.md — Backend integration tests (RBAC 403, CRUD happy path, normalization/conflict, used_count, CSRF)
- [ ] 113-03-PLAN.md — Frontend wiring (features/promoCodes seam, PromoCodeModal, PromoCard + PlansPage section mock→real)
**UI hint**: yes

### Phase 114: Attendance Analytics on Existing Reports

**Goal**: Owner sees real attendance analytics derived from the already-shipped `reports/visits` aggregate — the built-but-unwired analytics widgets render live data.
**Depends on**: Nothing (independent of 112/113 — no new backend)
**Requirements**: ANL-01
**Success Criteria** (what must be TRUE):

  1. Owner sees an hourly heatmap and hour-curve chart on the Load or Analytics screen, driven by real `GET /api/v1/reports/visits` data; buckets with zero visits render as zero, not NaN.
  2. Owner sees day-of-week breakdown, peak-hour, and visit-frequency distribution widgets — all derived from the same aggregate endpoint without new backend queries.
  3. Owner sees a visit-duration widget (if the backend aggregate carries duration data) or a clearly labeled "coming soon" state if not — no silent mock data.

**Plans**: TBD
**UI hint**: yes

### Phase 115: Live & Advanced Analytics

**Goal**: Owner sees cohort, anomaly, and at-risk member widgets backed by new aggregate queries, a live gym-load counter, and real-data dashboard feed/KPI/sales widgets.
**Depends on**: Phase 114
**Requirements**: ANL-02, ANL-03, ANL-04
**Success Criteria** (what must be TRUE):

  1. Owner sees cohort retention and visit-anomaly widgets, backed by new window-function report queries on the existing `visits` + `memberships` tables; reception is not exposed to owner-only aggregate endpoints.
  2. Owner sees a "сейчас в зале" live-load count on the Load page, backed by a new `GET /api/v1/reports/load/now` endpoint returning the current in-gym headcount.
  3. Dashboard activity feed shows real recent events (from audit log or visits/payments read endpoints); top-trainer KPIs and plans sales chart render real data — mock widgets are removed.

**Plans**: TBD
**UI hint**: yes

### Phase 116: Chat Inbox & Exports

**Goal**: Staff can read and reply to client messages from the admin app, and owner can download payments and attendance data as CSV files.
**Depends on**: Phase 112
**Requirements**: MSG-01, MSG-02, EXP-01, EXP-02
**Success Criteria** (what must be TRUE):

  1. Staff sees a chat inbox listing all client↔gym threads with unread counts, backed by new staff-side REST endpoints over the existing `messaging` module; reception sees the inbox (read-permitted), owner can send.
  2. Staff can open a thread and send or reply to a client message; the message is persisted and the client PWA receives it via the existing WS/Telegram channel.
  3. Owner can export payments to a UTF-8 BOM CSV file over a date range from Cashbox or Finance; the download starts immediately and Cyrillic content round-trips cleanly in Excel.
  4. Owner can export visits/attendance to a UTF-8 BOM CSV file over a date range from the Attendance screen; the file matches the same format discipline.

**Plans**: TBD
**UI hint**: yes

### Phase 117: OpenAPI Handoff + Milestone Gate

**Goal**: The v3.2 OpenAPI contract is regenerated additively, forward-guarded, and each new domain has at least one contract test that parses a real backend response — closing the mock↔real schema-drift lesson from v3.0/v3.1.
**Depends on**: Phases 112, 113, 114, 115, 116
**Requirements**: HND-01
**Success Criteria** (what must be TRUE):

  1. `openapi.json` + `schema.d.ts` are regenerated to include all new v3.2 paths (refund, role-change, promo CRUD, analytics endpoints, staff-messages, exports) — additively, NOT byte-stable — and a `_v32Checks` `AssertNonNever` forward-guard tuple covers each new path×method.
  2. For each new domain introduced in v3.2 (refund, role-change, promo, analytics/LiveNow, staff-messages), at least one contract test parses a REAL backend response (not a mock fixture) and asserts the Zod schema passes — the v3.0/v3.1 drift lesson is structurally closed.
  3. The full milestone gate is green: mypy `--strict` + lint-imports + pytest + admin-app `check`/`test`/`build` + Redocly lint; CISO-01 RBAC byte-parity guard is green; all 13 v3.2 requirements are verified satisfied.

**Plans**: TBD

## Backlog

### Backlog 999.1 — WR-06 restore PT session credit on owner force-cancel (✅ DONE 2026-05-29 — quick task 260529-ny2)

**Closure note (2026-05-29):** Implemented as a **consumption-keyed** restore, not a blind +1. FSM analysis during planning showed `sessions_remaining` is decremented only at check-in (`record_pt_session` → booking `confirmed → completed`), and the owner-cancel cascades only touch `confirmed` (un-consumed) bookings — so a literal "+1 per cancel" would over-credit. The fix restores +1 **only when a live consumed `pt_session` exists for the booking** (flips it cancelled + increments, idempotent/race-safe), emits the new `pt_session_credit_restored` audit event, and removes the NOTE WR-06 block. 5/5 verified; 56 schedule integration tests green. (For a confirmed booking with no consumed session, restore is a correct no-op.)

### Backlog 999.2 — Wire online-payment EMAIL templates into the dispatcher (✅ DONE 2026-05-29 — quick task 260529-olc)

**Closure note (2026-05-29):** Added 4 owner-signed-off `EmailTemplate` records (mirroring the already-signed Telegram DM copy) to `online_payments/email_templates.py` + the `online_payments` branch in `dispatcher._resolve_template` (the import-linter ignore was already present at `.importlinter:189`). The email channel for online-payment notifications now resolves + renders instead of silently `KeyError`-no-opping. +21 resolve/render tests; 5/5 verified. No new ignore, no schema change, callsites/AST-gate untouched.

### Backlog 999.3 — client-pwa Home — newbie (no-subscription) state (✅ SHIPPED in v2.0 — 2026-05-31)

### Backlog 999.4 — client-pwa Checkout — visual restyle + real promo codes (✅ SHIPPED in v2.0 — 2026-05-31)

## Progress

**Current milestone:** v3.2 Admin — Wire the Rest — in progress (Phases 112-117).

**Execution Order:** 112 → 113 → 114 → 115 → 116 → 117

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 112. Critical Money & Access | 3/3 | Complete   | 2026-06-15 |
| 113. Promo Codes CRUD | 2/3 | In Progress|  |
| 114. Attendance Analytics on Existing Reports | 0/TBD | Not started | - |
| 115. Live & Advanced Analytics | 0/TBD | Not started | - |
| 116. Chat Inbox & Exports | 0/TBD | Not started | - |
| 117. OpenAPI Handoff + Milestone Gate | 0/TBD | Not started | - |

<details>
<summary>✅ v3.1 Admin — Fill the Gaps (Phases 107-111) — Progress (SHIPPED 2026-06-15)</summary>

**Execution Order:** 107 → 108 → 109 → 110 → 111

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 107. Admin FE Completion on Existing Backend | 3/3 | Complete    | 2026-06-14 |
| 108. Editable Settings — Backend + Wiring | 5/5 | Complete    | 2026-06-14 |
| 109. Profile & Security — Backend + Wiring | 4/4 | Complete    | 2026-06-14 |
| 110. Live Verification — Deferred P102 | 3/3 | Complete    | 2026-06-14 |
| 111. OpenAPI Handoff + Milestone Gate | 2/2 | Complete    | 2026-06-14 |

</details>

<details>
<summary>✅ v3.0 Production Admin — Backend Wiring (Phases 100-106) — Progress (SHIPPED 2026-06-14)</summary>

**Execution Order:** 100 → 101 → 102 → 103 → 104 → 105 → 106

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 100. Foundation + Authentication | 4/4 | Complete   | 2026-06-13 |
| 101. Clients + Memberships | 4/4 | Complete   | 2026-06-13 |
| 102. Schedule + Trainers | 4/4 | Complete   | 2026-06-13 |
| 103. Attendance + Finance | 4/4 | Complete   | 2026-06-13 |
| 104. Dashboard, Reports + Settings | 5/5 | Complete   | 2026-06-13 |
| 105. admin-web Retirement + RBAC Re-home | 1/1 | Complete   | 2026-06-13 |
| 106. OpenAPI Handoff + Milestone Gate | 2/2 | Complete   | 2026-06-13 |

</details>
