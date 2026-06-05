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
- 🚧 **v2.3 Loyalty / Club Bonuses + Real Autopay** — Phases 82-85 (in progress)

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

### 🚧 v2.3 Loyalty / Club Bonuses + Real Autopay (In Progress)

**Milestone Goal:** Дать клиенту бонусный баланс (event-based начисление + server-authoritative списание скидкой в чекауте) и закрыть реальный off-session autopay-leg, отложенный из v2.2 (off-session charge по сохранённой карте на cron для истекающих абонементов). Всё под `require_client()`; frozen `apps/admin-web` staff-контракт байт-в-байт цел (drift gate зелёный). Earning-модель: welcome/promo + ручной owner-грант через owner-only backend API (NO admin-web UI). APAY (recurring real-money charges) — highest-risk, наиболее независимый блок, изолирован в отдельную фазу для верификации в одиночку.

**Coverage:** 14/14 v2.3 requirements mapped (zero orphans, zero duplicates). Phase numbering continues from v2.2 (last phase 81) → v2.3 starts at Phase 82.

#### Phase 82: Loyalty Foundation — Ledger + Balance + Accrual

**Goal**: Клиент имеет бонусный баланс, выведенный из append-only ledger, видит его и историю; бонусы начисляются автоматически новому клиенту и вручную owner'ом через backend API; каждое начисление аудируется.
**Depends on**: Nothing (first phase of v2.3; builds on existing `client_portal` + audit infra)
**Requirements**: LOYL-01, LOYL-02, LOYL-03, ACCR-01, ACCR-02, ACCR-03
**Success Criteria** (what must be TRUE):

  1. Клиент получает текущий бонусный баланс через `GET /client/loyalty/balance` (баланс = свёртка append-only ledger-строк в integer kopecks; никаких деструктивных UPDATE)
  2. Клиент видит историю бонусов (начисления + списания) с датой, типом и суммой по каждой строке, IDOR-safe (`client_id` только из `require_client()` principal per D-20-IDOR)
  3. Новый клиент автоматически получает приветственный бонус ровно один раз (идемпотентно по событию онбординга/регистрации — повторное событие не начисляет повторно)
  4. Owner начисляет бонус произвольному клиенту через owner-only backend API (reception 403; admin-web UI отсутствует — прецедент засеянных промокодов); покрывает акционные + реферальные гранты
  5. Каждое начисление пишет аудируемое ledger-событие через новый LOCKED audit event, зарегистрированный ДО любого callsite (INFRA-15); count-lock guard-тесты обновлены

**Plans**: 3 plans

Plans:
**Wave 1**

- [x] 82-01-PLAN.md — Append-only loyalty_ledger schema (migration 0054) + loyalty_accrued LOCKED audit event registered before callsites (count-lock → 102)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 82-02-PLAN.md — Loyalty service + owner-only grant API + IDOR-safe client balance/history reads + welcome accrual callsite + integration tests

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 82-03-PLAN.md — PWA LoyaltyBalanceCard + BonusHistorySheet behind clubBonuses flag + query hooks + Vitest

**UI hint**: yes

#### Phase 83: Bonus Redemption at Checkout

**Goal**: Клиент списывает бонусы скидкой в чекауте; сервер авторитетно пересчитывает `discount_kopecks`, redemption записывается атомарно и идемпотентно на `payment.succeeded` webhook; PWA `CheckoutSheet` показывает реальный баланс за флагом `clubBonuses`.
**Depends on**: Phase 82 (нужен ledger + balance read для расчёта доступной скидки)
**Requirements**: REDM-01, REDM-02, REDM-03
**Success Criteria** (what must be TRUE):

  1. Клиент в чекауте уменьшает сумму к оплате списанием бонусов; `discount_kopecks` пересчитывается сервером — клиент не задаёт размер скидки сам (D-06 цел, скидка только server-side)
  2. Списание бонусов записывается в ledger атомарно на `payment.succeeded` webhook, идемпотентно по `(online_payment_id)` (образец `promo_codes`); при неоплате/отмене списания не происходит
  3. Anti-oracle return-screen invariant сохранён — return-экран не подтверждает результат списания/оплаты раньше webhook (D-06)
  4. PWA `CheckoutSheet` за флагом `clubBonuses` ON показывает реальный баланс + контрол списания; mock `BONUS_PLACEHOLDER = { balance: 1080, toGold: 220 }` удалён

**Plans**: TBD
**UI hint**: yes

#### Phase 84: Real Autopay Charge

**Goal**: Cron `charge_expiring_autopay` реально списывает с сохранённой карты off-session для истекающих абонементов с `autopay_enabled=true` + `consent_recorded_at`; списание идёт в charge-ledger, активация продления locked на webhook, исход аудируется и клиент уведомляется.
**Depends on**: Phase 82 (audit-event discipline established). Independent of Phase 83 — изолированный highest-risk блок, верифицируется в одиночку. Строится на v2.2 card-on-file инфраструктуре (`client_payment_methods`).
**Requirements**: APAY-01, APAY-02, APAY-03, APAY-04
**Success Criteria** (what must be TRUE):

  1. Cron `charge_expiring_autopay` (ARQ, `expire_memberships` shape — caller-owns-txn, `cron(..., unique=True)`, fn в `WorkerSettings.functions`) находит истекающие в окне абонементы с `autopay_enabled=true` + записанным `consent_recorded_at` и инициирует off-session charge
  2. YooKassa-адаптер выполняет off-session charge по сохранённому `payment_method_id`; списание пишется в charge-ledger по дисциплине v1.4 `payments`; активация продления locked на `payment.succeeded` webhook
  3. Автосписание идемпотентно — повторные тики cron / рестарты контейнера не приводят к двойному charge; пропускаются неподходящие (нет consent / autopay off / нет активной карты / уже продлён)
  4. Исход автосписания (успех/ошибка) аудируется новым LOCKED audit event (зарегистрирован ДО callsite, INFRA-15) и клиент уведомляется через Telegram/email mirror с идемпотентностью через `channel` discriminator

**Plans**: TBD

#### Phase 85: OpenAPI Handoff + Milestone Verification

**Goal**: Контракт v2.3 заморожен — byte-stable regen `openapi.json` + `schema.d.ts` со всеми новыми loyalty/autopay client-путями + `_v23Checks` forward-guards; staff-пути байт-идентичны `contract-freeze-v1.11.0` (drift gate зелёный); milestone-gate проверен.
**Depends on**: Phase 84 (все новые пути должны существовать перед regen)
**Requirements**: HND-01
**Success Criteria** (what must be TRUE):

  1. `openapi.json` + `schema.d.ts` регенерированы byte-stably со всеми новыми loyalty/autopay client-путями (loyalty balance/history, redemption surface, autopay-relevant client routes)
  2. `_v23Checks` `AssertNonNever` forward-guards добавлены для каждого нового path×method combo + runtime `toHaveLength` assertion; `_v1x`/`_v20`/`_v22` guards не тронуты
  3. Staff-пути байт-идентичны `contract-freeze-v1.11.0` — `git diff --exit-code` drift gate зелёный на обоих артефактах; Redocly lint clean
  4. Milestone-gate green: backend pytest (incl. новые ledger/redemption/autopay race + idempotency тесты), mypy --strict, lint-imports (zero new `ignore_imports` где возможно, per D-20-MODULE), PWA vitest, no-edit guard на `permissions.py`/`can.ts`/`registry.ts`

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

**Execution Order:** 79 → 80 → 81 → 81.1 → 82 → 83 → 84 → 85

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 79. Payment Methods Foundation + Card-on-File | 4/4 | Complete   | 2026-06-03 |
| 80. Booking Reschedule | 3/3 | Complete   | 2026-06-03 |
| 81. Weekly Activity + PWA Flag Flips + OpenAPI Handoff | 3/3 | Complete   | 2026-06-03 |
| 81.1. Checkout Save-Card Capture | 1/1 | Complete   | 2026-06-03 |
| 82. Loyalty Foundation — Ledger + Balance + Accrual | 2/3 | In Progress|  |
| 83. Bonus Redemption at Checkout | 0/TBD | Not started | - |
| 84. Real Autopay Charge | 0/TBD | Not started | - |
| 85. OpenAPI Handoff + Milestone Verification | 0/TBD | Not started | - |
