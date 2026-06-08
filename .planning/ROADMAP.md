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
- ◆ **v2.6 Referral System** — Phases 96-99 (in progress 2026-06-08)

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

<details>
<summary>✅ v2.1 Client PWA — Fill the Gaps (Phases 75-78) — SHIPPED 2026-06-02</summary>

**Milestone Goal:** Turn on already-built-but-hidden client PWA functionality via small backend field additions + pure-frontend wiring, fold in the two deferred v2.0 warnings, and surface the backend-complete fields in the UI. Audit `tech_debt` (0 blockers, 10/10 requirements delivered; live human-verify checks + pre-existing debt deferred). Full phase details in [milestones/v2.1-ROADMAP.md](milestones/v2.1-ROADMAP.md).

- [x] **Phase 75: Backend Field Additions** — priceKopecks/autoRenew on membership; notif_prefs JSONB on /client/me (migration 0050); FIT15 seed (migration 0051) (PMEM-01, NOTIF-01, PROMO-01) — completed 2026-06-02
- [x] **Phase 76: PWA Wiring + Cleanup** — newbie-Home live trainers + plan chip; PersonalDataSheet read/save; mock chat badge removed (NHOME-01/02, PDATA-01/02, CLEAN-01) — completed 2026-06-02
- [x] **Phase 77: v2.0 Debt Closures** — cancel-booking E2E wired (FIX-01, real booking threaded); receipt-destination reconciled via UI-SPEC amendment (FIX-02) — completed 2026-06-02
- [x] **Phase 78: PMEM/NOTIF/PROMO Frontend Surfacing** — Profile price/auto-renew; Settings notif toggles server-backed; FIT15 checkout chip surfaced — closes the audit frontend-surfacing debt — completed 2026-06-02

**Deferred at close (acknowledged):** Phase 76 PDATA-02 live persistence check; Phase 78 live checks (FIT15 chip in sub+PT checkout, notif toggle survives reload); pre-existing `router.py` ruff I001; WR-75-02 receipt-lookup heuristic. See `.planning/STATE.md` `## Deferred Items`.

</details>

<details>
<summary>✅ v2.2 Membership self-service depth (Phases 79-81 + 81.1) — SHIPPED 2026-06-03</summary>

**Milestone Goal:** Углубить client-PWA self-service — клиент сам управляет привязанной картой и автоплатежом (UI-only: токен + preference + ФЗ-376 consent, без реальных списаний), переносит брони и видит недельную активность. Audit `passed` (11/11 requirements; PAYM-01 PWA-capture gap closed by Phase 81.1; live-infra checks OPERATOR-PENDING). Full phase details in [milestones/v2.2-ROADMAP.md](milestones/v2.2-ROADMAP.md).

- [x] **Phase 79: Payment Methods Foundation + Card-on-File** — migration 0052 `client_payment_methods`, `payment_methods/` module, webhook step-8.5 token save, GET/DELETE/PATCH endpoints, ФЗ-376 consent (PAYM-01..04) — completed 2026-06-03
- [x] **Phase 80: Booking Reschedule** — atomic cancel+create `reschedule_booking_for_client`, migration 0053, `booking_rescheduled` audit, reschedule DM, BookingManageSheet wiring, PT-credit preserved (RESCH-01..03) — completed 2026-06-03
- [x] **Phase 81: Weekly Activity + PWA Flag Flips + OpenAPI Handoff** — `GET /client/activity/weekly` (gym_date STORED, golden TZ test), flip `linkedCard`/`weeklyActivity` ON, CardSheet wiring, byte-stable openapi.json + schema.d.ts regen (WACT-01/02, PAYM-05, HND-01) — completed 2026-06-03
- [x] **Phase 81.1: Checkout Save-Card Capture (audit gap closure)** — PWA save-card opt-in threads `savePaymentMethod` through both checkout hooks; closes the PAYM-01 PWA-capture gap (PAYM-01) — completed 2026-06-03

</details>

<details>
<summary>✅ v2.3 Loyalty / Club Bonuses + Real Autopay (Phases 82-85) — SHIPPED 2026-06-06</summary>

**Milestone Goal:** Дать клиенту бонусный баланс (event-based начисление + server-authoritative списание скидкой в чекауте) и закрыть реальный off-session autopay-leg, отложенный из v2.2. Всё под `require_client()`; frozen `apps/admin-web` staff-контракт байт-в-байт цел (drift gate зелёный). Audit `passed` (14/14 requirements, integration 5/5 green; live-ЮKassa legs OPERATOR-PENDING by design). Full phase details in [milestones/v2.3-ROADMAP.md](milestones/v2.3-ROADMAP.md).

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

## v2.6 Referral System (Phases 96-99)

**Milestone Goal:** Клиент приглашает друзей персональным реф-кодом; обе стороны получают бонус на `loyalty_ledger` после первой покупки приглашённого; экран «Приведи друга» переносится пиксель-в-пиксель с готового макета. Всё под `require_client()`, IDOR-safe; бонусы server-authoritative (webhook-only); `apps/admin-web` заморожен.

- [x] **Phase 96: Referral Domain Backend** — персональные реф-коды (идемпотентная генерация), захват реферала при онбординге (referrer↔referee, self-referral блок, 1-bonus-per-referee), deep-link endpoint, owner-only конфигурация сумм бонусов + seed; LOCKED audit events зарегистрированы до первого callsite (REFER-01, REFER-02 backend, REFER-03, REFER-07) (completed 2026-06-08)
- [x] **Phase 97: Reward Crediting** — двусторонний бонус на `payment.succeeded` ПЕРВОЙ покупки: co-transactional, idempotent по `(referral_id, online_payment_id)`, через `accrue_welcome_bonus`/`owner_grant_loyalty` примитивы; LOCKED audit events (REFER-04) (completed 2026-06-08)
- [x] **Phase 98: PWA ReferralScreen** — graduate из D-71-09 ESLint-зоны; пиксель-в-пиксель порт макета (промокод + ссылка + copy, share Telegram/WhatsApp/native, блок «Как это работает»); список приглашённых со статусами; «Уже накоплено» из ledger; deep-link авто-подстановка кода; тир-трекер hide-for-future (REFER-02 PWA, REFER-05, REFER-06) (completed 2026-06-08)
- [ ] **Phase 99: OpenAPI Handoff + Milestone Verification** — byte-stable `openapi.json` + `schema.d.ts` + `_v26Checks` AssertNonNever; staff-контракт байт-в-байт цел (drift gate зелёный); полный milestone gate зелёный (HND-01)

## Phase Details

### Phase 96: Referral Domain Backend
**Goal**: Клиент может получить персональный реферальный код и ссылку; друг может привязать реферера при регистрации; owner может настроить суммы бонусов через API
**Depends on**: Phase 95 (v2.5 complete baseline)
**Requirements**: REFER-01, REFER-02 (backend: deep-link resolve endpoint), REFER-03, REFER-07
**Success Criteria** (what must be TRUE):
  1. `GET /client/referral/code` returns a stable, idempotent code and shareable link for the authenticated client; calling it twice returns the same code
  2. `POST /client/referral/capture` at onboarding binds referrer↔referee atomically; a second call for the same referee is a no-op (idempotent); self-referral returns 422
  3. `GET /i/<code>` resolves a referral code to the matching client's referral info (deep-link entry point for the PWA)
  4. Owner can GET/PUT referral bonus amounts via owner-only API (`/referral/config`); reception gets 403; amounts seed-initialized with sensible defaults
  5. All new LOCKED audit events (`referral_code_generated`, `referral_captured`) are pre-registered in `LOCKED_AUDIT_EVENTS` before any callsite (INFRA-15 discipline)
**Plans**: 3 plans
  - [x] 96-01-PLAN.md — INFRA-15 audit foundation: lock referral_code_generated + referral_captured pairs + payload schemas + unit test
  - [x] 96-02-PLAN.md — Data layer: referrals module models + schemas, migrations 0067 (tables) + 0068 (seed config), pwa_base_url setting
  - [x] 96-03-PLAN.md — Service + triple-router (public /i/<code>, client code/capture, owner config) + mounting + integration tests

### Phase 97: Reward Crediting
**Goal**: Обе стороны автоматически получают бонус на `loyalty_ledger` после первой покупки абонемента приглашённым другом
**Depends on**: Phase 96
**Requirements**: REFER-04
**Success Criteria** (what must be TRUE):
  1. On `payment.succeeded` for a referee's first membership purchase, a `loyalty_ledger` row is inserted for the referrer (referrer bonus amount) and for the referee (welcome-style bonus amount) within the same atomic UoW
  2. Webhook replay (same `online_payment_id`) inserts nothing and emits no second audit event — idempotent by `(referral_id, online_payment_id)` partial UNIQUE guard
  3. A second membership purchase by the same referee does NOT trigger another referral bonus (one-bonus-per-referee invariant)
  4. Bonus amounts come exclusively from the owner-configurable config (Phase 96); no hardcoded amounts at the crediting callsite
**Plans**: 3 plans
  - [x] 97-01-PLAN.md — INFRA-15 audit foundation: lock referral_bonus_accrued + typed payload + registry + unit test (before any callsite)
  - [x] 97-02-PLAN.md — Data layer: loyalty_ledger referral_capture_id FK + entry_type CHECK widen + migration 0069 partial UNIQUE + accrue_referral_bonus primitive
  - [x] 97-03-PLAN.md — Webhook orchestration in handle_payment_succeeded (first-purchase gate, referrer-alive void, config-sourced amounts) + 7-case integration suite

### Phase 98: PWA ReferralScreen
**Goal**: Экран «Приведи друга» выведен из ComingSoon и отображает реальные данные: персональный код, список приглашённых, сумму накопленных бонусов
**Depends on**: Phase 97
**Requirements**: REFER-02 (PWA deep-link handling), REFER-05, REFER-06
**Success Criteria** (what must be TRUE):
  1. `ReferralSheet.jsx` is de-listed from the D-71-09 ESLint zone (all 3 spots removed; `grep ReferralSheet eslint.config.js` returns 0) and imports referral data via `@/data`
  2. The screen matches the pixel-perfect reference design: hero illustration, reward rows (your bonus / friend's bonus), referral code box with copy button, share chips (Telegram / WhatsApp / native), "Как это работает" steps — with stripped device chrome and scoped CSS (same pattern as ChatScreen v2.5)
  3. The invited-friends list shows real data: each referee with name, join date, and status badge ("Присоединился + bonus amount" or "Ждём"); an empty state renders when there are no referrals yet
  4. The "Уже накоплено" figure reflects the real sum of referral-category `loyalty_ledger` entries for the authenticated client (not a mock constant)
  5. Opening the PWA via `…/i/<code>` auto-populates the referral code in the onboarding flow (deep-link handled client-side); the gamification tier tracker is present in the DOM but hidden (hide-for-future, not deleted)
**Plans**: 3 plans
Plans:
- [x] 98-01-PLAN.md — Backend aggregate read endpoint GET /client/referral/summary (invitees + referral-only accruedKopecks) + integration tests (REFER-06)
- [x] 98-02-PLAN.md — PWA ReferralScreen pixel-perfect port + useClientReferralSummary @/data hook + D-71-09 ESLint graduation (REFER-05, REFER-06)
- [x] 98-03-PLAN.md — Deep-link /i/:code landing + post-auth referral capture wiring (REFER-02)
**UI hint**: yes

### Phase 99: OpenAPI Handoff + Milestone Verification
**Goal**: Все endpoint'ы v2.6 зафиксированы в byte-stable контракте; полный milestone gate зелёный
**Depends on**: Phase 98
**Requirements**: HND-01
**Success Criteria** (what must be TRUE):
  1. `openapi.json` and `schema.d.ts` regenerate byte-stably; CI `git diff --exit-code` is clean on both artifacts
  2. `_v26Checks` `AssertNonNever` tuple covers all new v2.6 path×method combos with a runtime `toHaveLength(N)` assertion
  3. Staff contract paths are byte-identical to the Phase 95 baseline (drift gate green); `CISO-01` no-edit guard passes
  4. Full milestone gate green: `pytest` (backend) + `mypy --strict` + `lint-imports` + `vitest` (client-pwa) + Redocly lint
**Plans**: TBD

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

## Progress

**Execution Order:** 96 → 97 → 98 → 99

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 96. Referral Domain Backend | 3/3 | Complete    | 2026-06-08 |
| 97. Reward Crediting | 3/3 | Complete    | 2026-06-08 |
| 98. PWA ReferralScreen | 3/3 | Complete   | 2026-06-08 |
| 99. OpenAPI Handoff + Milestone Verification | 0/TBD | Not started | - |
