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
- 🚧 **v3.0 Production Admin — Backend Wiring** — Phases 100-106 (in progress)

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

### 🚧 v3.0 Production Admin — Backend Wiring (Phases 100-106)

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
- [ ] 102-02-PLAN.md — Trainers catalog + CRUD: features/trainers http (queries + PATCH/POST/DELETE), TrainersPage reduction (hide Load/Requests/Earnings/KPIs), owner edit/create/delete affordances, TrainerHero/Overview real data, TrainerFormModal wired [TRN-01] · wave 1
- [ ] 102-03-PLAN.md — Bookings lifecycle + calendar merge: features/bookings http (create/cancel/complete-via-pt-sessions), BookingModal (race-safe 409), BookingDetailModal (24h cancel + complete), SchedulePage slot+booking merge + owner FAB, OverviewTab today-schedule [SCH-02] · wave 2
- [ ] 102-04-PLAN.md — Payroll: features/payroll http (comp-config INSERT-only + preview→run + accruals + mark-paid, owner-only enabled-gated), PayoutsTab wired (reception Lock state, kopecks↔rubles/bps↔pct, 409 already_run/already_paid) [TRN-02] · wave 2
**UI hint**: yes

### Phase 103: Attendance + Finance
**Goal**: Reception can check in visits on real data; owner can see the cashbox, revenue, and online payments — all without mocks.
**Depends on**: Phase 102
**Requirements**: ATT-01, ATT-02, FIN-01, FIN-02
**Success Criteria** (what must be TRUE):
  1. Attendance screen renders real visits list (`/visits`) with loading/error/empty states; reception can check in a client via `/visits/check-in`.
  2. Load screen renders the real hourly/daily visits aggregate from `/reports/visits`; no NaN on empty buckets.
  3. Cashbox screen renders the real cash ledger (`/payments`) with sell + refund records and daily totals; the refund flow is wired; mock removed.
  4. Finance screen renders real revenue report (`/reports/revenue`, net-of-refund, by method/subject) and online payments read; mock removed.
**Plans**: TBD
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
**Plans**: TBD
**UI hint**: yes

### Phase 105: admin-web Retirement + RBAC Re-home
**Goal**: `apps/admin-web` is deleted and the three-way RBAC-parity reference is re-homed so the chosen guard stays green — CI, workspace, and drift-gate stay valid after removal.
**Depends on**: Phase 100 (admin-app auth+RBAC proven)
**Requirements**: ADMW-01, ADMW-02, ADMW-03
**Success Criteria** (what must be TRUE):
  1. `apps/admin-web` directory is removed from the repo; workspace entry, CI job, ESLint/import-linter zones, and dangling references are cleaned with no build errors.
  2. The three-way RBAC-parity guard (`permissions.py` ↔ chosen admin-app anchor ↔ `registry.ts` or equivalent) is re-homed and green — the mechanic decided at Phase 100 plan is implemented.
  3. The OpenAPI staff drift-gate and `@clubcore/api-client` codegen pipeline pass after removal; no consumer is left dangling.
**Plans**: TBD

### Phase 106: OpenAPI Handoff + Milestone Gate
**Goal**: The staff OpenAPI contract is byte-stable, the full milestone gate passes, and v3.0 is verified complete.
**Depends on**: Phase 105
**Requirements**: HND-01
**Success Criteria** (what must be TRUE):
  1. `openapi.json` + `schema.d.ts` regenerate byte-stably; no new backend domains means the staff contract is unchanged vs `contract-freeze-v1.11.0`.
  2. Staff drift-gate is green; full milestone gate passes: mypy --strict + lint-imports + pytest + admin-app `check`/`test` + Redocly.
  3. All 30 v3.0 requirements are verified satisfied (no open blockers).
**Plans**: TBD

## Backlog

### Phase 999.1: WR-06 restore PT session credit on owner force-cancel (✅ DONE 2026-05-29 — quick task 260529-ny2)

**Closure note (2026-05-29):** Implemented as a **consumption-keyed** restore, not a blind +1. FSM analysis during planning showed `sessions_remaining` is decremented only at check-in (`record_pt_session` → booking `confirmed → completed`), and the owner-cancel cascades only touch `confirmed` (un-consumed) bookings — so a literal "+1 per cancel" would over-credit. The fix restores +1 **only when a live consumed `pt_session` exists for the booking** (flips it cancelled + increments, idempotent/race-safe), emits the new `pt_session_credit_restored` audit event, and removes the NOTE WR-06 block. 5/5 verified; 56 schedule integration tests green. (For a confirmed booking with no consumed session, restore is a correct no-op.)

### Phase 999.2: Wire online-payment EMAIL templates into the dispatcher (✅ DONE 2026-05-29 — quick task 260529-olc)

**Closure note (2026-05-29):** Added 4 owner-signed-off `EmailTemplate` records (mirroring the already-signed Telegram DM copy) to `online_payments/email_templates.py` + the `online_payments` branch in `dispatcher._resolve_template` (the import-linter ignore was already present at `.importlinter:189`). The email channel for online-payment notifications now resolves + renders instead of silently `KeyError`-no-opping. +21 resolve/render tests; 5/5 verified. No new ignore, no schema change, callsites/AST-gate untouched.

### Phase 999.3: client-pwa Home — newbie (no-subscription) state (✅ SHIPPED in v2.0 — 2026-05-31)

### Phase 999.4: client-pwa Checkout — visual restyle + real promo codes (✅ SHIPPED in v2.0 — 2026-05-31)

## Progress

**Execution Order:** 100 → 101 → 102 → 103 → 104 → 105 → 106

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 100. Foundation + Authentication | 4/4 | Complete   | 2026-06-13 |
| 101. Clients + Memberships | 4/4 | Complete   | 2026-06-13 |
| 102. Schedule + Trainers | 1/4 | In Progress|  |
| 103. Attendance + Finance | 0/TBD | Not started | - |
| 104. Dashboard, Reports + Settings | 0/TBD | Not started | - |
| 105. admin-web Retirement + RBAC Re-home | 0/TBD | Not started | - |
| 106. OpenAPI Handoff + Milestone Gate | 0/TBD | Not started | - |
