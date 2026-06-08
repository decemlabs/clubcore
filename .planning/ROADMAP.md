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
- 🚧 **v2.5 Chat / Messaging — Client↔Gym** — Phases 90-95 (in progress)

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

### 🚧 v2.5 Chat / Messaging — Client↔Gym (In Progress)

**Milestone Goal:** Клиент ведёт живую 1:1-переписку с залом из PWA в реальном времени; staff отвечает через Telegram-мост; всё под `require_client()`, IDOR-safe, staff-контракт байт-в-байт цел.

**Note on granularity:** Config is `coarse` (3-5 phases recommended), but v2.5 introduces four genuinely new technical surfaces onto the monolith — WebSocket transport, Redis pub/sub fan-out, binary file handling, and bidirectional Telegram bridging — each with independent pitfall density. Research converged on 6 phases as the minimum safe decomposition. Compressing below 6 would require combining the Phase 90 WS-invariant cluster (6 simultaneous must-be-correct-from-day-one constraints) with the Phase 93 Telegram bridge cluster (second-highest pitfall density) into a single phase — an unacceptable risk for a pet project with no rollback mechanism. 6 phases accepted over the granularity hint.

#### Phase 90: Messaging Domain + REST Foundation + WS Scaffold

- [x] **Phase 90: Messaging Domain + REST Foundation + WS Scaffold** - DB schema + REST send/list/mark-read + WS transport + Redis pub/sub fan-out; all six WS invariants locked from day one (3 plans) (completed 2026-06-07)
  - [x] **Plan 01** (DB + models + migrations + audit events) — completed 2026-06-07
  - [x] **Plan 02** (schemas + repository + service + REST router + integration tests) — completed 2026-06-07
  - [x] **Plan 03** (WS endpoint + per-connection pub/sub subscriber + WS tests) — completed 2026-06-07

#### Phase 91: Read Receipts + Typing Indicators

- [x] **Phase 91: Read Receipts + Typing Indicators** - Per-message read status + typing presence delivered over the Phase 90 WS channel (2 plans) (completed 2026-06-07)

#### Phase 92: Photo Attachments

- [x] **Phase 92: Photo Attachments** - Authenticated upload + IDOR-safe serve with magic-byte validation and stored-XSS guards (3 plans) (completed 2026-06-07)
  - [x] 92-01-PLAN.md — Storage seam (S3Storage + magic-byte guard) + migration 0066 + docker S3 service
  - [x] 92-02-PLAN.md — Server-side validated upload endpoint (magic-byte allowlist + 5MB cap) + lifespan wiring
  - [x] 92-03-PLAN.md — Authenticated IDOR-safe serve endpoint (anti-XSS headers) + two-step flow + security suite

#### Phase 93: Telegram Bridge

- [x] **Phase 93: Telegram Bridge** - Bidirectional client↔staff relay through the existing Telegram bot worker (completed 2026-06-08)

#### Phase 94: PWA ChatScreen Wiring

- [ ] **Phase 94: PWA ChatScreen Wiring** - Graduate ChatScreen from D-71-09 placeholder zone; wire REST + WS + attachments

#### Phase 95: OpenAPI Handoff + Milestone Verification

- [ ] **Phase 95: OpenAPI Handoff + Milestone Verification** - Byte-stable openapi.json + schema.d.ts regen + full milestone gate

## Phase Details

### Phase 90: Messaging Domain + REST Foundation + WS Scaffold
**Goal**: Клиент может отправлять и получать текстовые сообщения в режиме реального времени — хранилище в PostgreSQL, доставка через WebSocket, Redis pub/sub fan-out корректен при нескольких worker-процессах
**Depends on**: Phase 89 (v2.4 complete)
**Requirements**: MSG-01, MSG-02, MSG-03, MSG-04, RT-01, RT-02, RT-03, RT-04
**Success Criteria** (what must be TRUE):
  1. Client can fetch their paginated thread history with `unreadCount` via `GET /client/messages`, and messages from a different client return 404 (IDOR-safe)
  2. Client can send a text message via `POST /client/messages`; the message persists in Postgres and arrives on an open WebSocket connection within the same request cycle, including when the sender and subscriber are in different uvicorn workers (Redis pub/sub fan-out)
  3. Client can mark all unread messages read via `PATCH /client/messages/read`; `unreadCount` returns 0 on the next `GET`
  4. WS connection is authenticated via the `cc_client_access` httpOnly cookie (no URL token); a connection with a missing or expired token is rejected before the upgrade completes; a client cannot subscribe to another client's channel (Origin check + principal-derived channel name)
  5. On WS reconnect, client can provide a `last_seen_message_id` cursor and receive all messages written during the disconnection from the REST catch-up endpoint
**Plans**: 3 plans

Plans:
- [x] 90-01-PLAN.md — Foundation: migrations 0064/0065 + ORM models + import-linter + audit-event pre-registration (INFRA-15)
- [x] 90-02-PLAN.md — REST: schemas/repository/service/router for GET/POST/PATCH /client/messages (MSG-01..04 + RT-04 cursor + pub/sub publish seam)
- [x] 90-03-PLAN.md — WS transport: Starlette TestClient convention + verify_ws_origin + @router.websocket endpoint (six WS invariants) + cross-context fan-out tests (RT-01..04)

**Resolved (was open question)**: WS auth — `cc_client_access` is SameSite=Lax (confirmed in app/core/security.py), so httpOnly cookie-based WS auth works; the ws-ticket fallback is NOT required.

### Phase 91: Read Receipts + Typing Indicators
**Goal**: Клиент видит статус своих сообщений («прочитано») и индикатор набора от зала; оба события доставляются через уже существующий WS-канал без сохранения в БД (typing — эфемерный)
**Depends on**: Phase 90
**Requirements**: RCPT-01, RCPT-02, RCPT-03
**Success Criteria** (what must be TRUE):
  1. Client sees a single-check indicator on sent messages (server-persisted) and a double-check indicator when staff has read the message (reply-as-read: when staff sends a reply, prior client messages are marked `read_at = now()` and a `read_receipt` WS event is published)
  2. Client sees a "typing..." indicator that auto-dismisses after 5 seconds when staff begins composing in Telegram; the typing state is never written to Postgres
  3. `PATCH /client/messages/read` REST endpoint persists read state correctly as a polling fallback when the WS is disconnected
**Plans**: 2 plans

Plans:
- [x] 91-01-PLAN.md — Service surface: read_receipt/typing event schemas + reply-as-read repository fn (role='client') + record_staff_message wiring + publish_read_receipt/publish_typing helpers (RCPT-01, RCPT-03)
- [x] 91-02-PLAN.md — Starlette WS tests: read_receipt/typing fan-out + IDOR isolation + e2e reply-as-read + PATCH polling fallback (RCPT-01, RCPT-02, RCPT-03)

### Phase 92: Photo Attachments
**Goal**: Клиент прикрепляет фото к сообщению; вложения хранятся сервером и отдаются через аутентифицированный IDOR-safe endpoint с защитой от stored XSS
**Depends on**: Phase 90
**Requirements**: ATT-01, ATT-02, ATT-03
**Success Criteria** (what must be TRUE):
  1. Client can upload a JPEG, PNG, or WebP image (up to 5 MB) via `POST /client/messages/attachments`; the server validates by magic bytes (not the `Content-Type` header), rejects SVG and HTML with 422, and rejects oversized files with 413
  2. Client can retrieve their own attachment via `GET /client/messages/attachments/{id}`; attempting to fetch another client's attachment by UUID returns 404 (IDOR-safe); the response carries `Content-Disposition: attachment` and `X-Content-Type-Options: nosniff`
  3. Client can include an `attachment_id` in `POST /client/messages`; the photo appears in the thread history
**Plans**: 3 plans (Wave 1: 92-01 storage seam + migration + docker S3; Wave 2: 92-02 upload; Wave 3: 92-03 serve + integration + security suite)
**Resolved (92-CONTEXT.md)**: Storage backend — S3-compatible from day one (USER OVERRIDE over the research-recommended local fs) via `app/integrations/storage/` (aioboto3, env-driven); local dev uses a self-hosted S3-compatible docker service. Upload is server-side validated (not presigned PUT); serve is an authenticated proxy-stream (not presigned GET).
**UI hint**: yes

### Phase 93: Telegram Bridge
**Goal**: Staff получает клиентские сообщения в Telegram и может ответить через стандартный Reply; ответ маршрутизируется в правильный тред и доставляется клиенту по WS; эхо-петля невозможна
**Depends on**: Phase 90, Phase 91
**Requirements**: BRDG-01, BRDG-02, BRDG-03
**Success Criteria** (what must be TRUE):
  1. When a client sends a message, the staff Telegram account receives a DM (forwarded via ARQ task, not synchronously in-transaction); the DM is delivered even if a second client is writing simultaneously
  2. Staff can reply using Telegram's native Reply function; the reply is stored in the correct client thread in Postgres and delivered to the client's WS connection; replying to an older forwarded message routes to the originating client, not the most recently active one (Redis `cc:messaging:tg_msg:{tg_message_id}` → `thread_id` mapping, TTL 7 days)
  3. The bot does not echo-loop: a bot-forwarded message arriving back as an update is skipped (`is_bot` check + `chat_forwarding_log` as natural loop-breaker); each client message appears exactly once in each direction
**Plans**: 2 plans
- [x] 93-01-PLAN.md — Client→staff forward path: forward_to_staff ARQ task + send_photo + config + post-commit router enqueue (BRDG-01)
- [x] 93-02-PLAN.md — Staff→client reply path: staff_reply_handler + HandlerContext.messaging_service + chat_forwarding_log routing + echo/misroute guards (BRDG-02, BRDG-03)

### Phase 94: PWA ChatScreen Wiring
**Goal**: ChatScreen выведен из ComingSoon и de-listed из D-71-09 placeholder-зоны; клиент переписывается с залом в реальном времени из PWA, видит статусы прочтения, typing-индикатор, фото и badge непрочитанных
**Depends on**: Phase 90, Phase 91, Phase 92, Phase 93
**Requirements**: PWA-01, PWA-02, PWA-03
**Success Criteria** (what must be TRUE):
  1. ChatScreen renders the thread history (bubbles: client right / staff left, timestamps in Europe/Moscow HH:MM), and is fully de-listed from the D-71-09 ESLint placeholder zone (3 spots removed, `grep` returns 0, import via `@/data`)
  2. The unread badge on the Chat tab reflects the real `unreadCount` in real time via the WS connection, falling back to a 30-second React Query poll when the WS is disconnected
  3. Client can select a photo from the device (or camera), see a preview thumbnail in the thread, and send it; previously sent photos are viewable full-screen on tap
**Plans**: 2 plans

Plans:
- [ ] 94-01-PLAN.md — Data layer: messaging React Query hooks + useClientMessagingWS + @/data barrel + UIContext unreadChat + App-level WS mount & TabBar badge (PWA-01, PWA-02)
- [ ] 94-02-PLAN.md — Pixel-perfect ChatScreen port: de-list from D-71-09 + scoped CSS list+thread + read ticks/typing/unread + photo picker & full-screen overlay (PWA-01, PWA-03)

**UI hint**: yes

### Phase 95: OpenAPI Handoff + Milestone Verification
**Goal**: Все endpoint'ы v2.5 зафиксированы в byte-stable openapi.json + schema.d.ts; WS-endpoint задокументирован вручную; milestone gate зелёный; staff-контракт байт-в-байт идентичен `contract-freeze-v1.11.0`
**Depends on**: Phase 94
**Requirements**: HND-01
**Success Criteria** (what must be TRUE):
  1. `openapi.json` regenerates byte-stably with all v2.5 REST messaging paths present under the `Messaging` tag; the WS endpoint is manually documented in `_customize_openapi()` post-processor; Redocly lint clean
  2. `schema.d.ts` regenerates byte-stably; `_v25Checks` `AssertNonNever` tuple with `toHaveLength(N)` assertion covers all new v2.5 path×method combos; `git diff --exit-code` on staff paths is empty (drift gate green)
  3. Full milestone gate passes: backend pytest + mypy --strict + lint-imports (including `app.modules.messaging` in `modules-independent` contract) + CISO-01 no-edit guard + frontend vitest + Redocly
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

**Execution Order:** 90 → 91 → 92 → 93 → 94 → 95

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 90. Messaging Domain + REST Foundation + WS Scaffold | 3/3 | Complete    | 2026-06-07 |
| 91. Read Receipts + Typing Indicators | 2/2 | Complete    | 2026-06-07 |
| 92. Photo Attachments | 3/3 | Complete   | 2026-06-07 |
| 93. Telegram Bridge | 2/2 | Complete   | 2026-06-08 |
| 94. PWA ChatScreen Wiring | 0/2 | Not started | - |
| 95. OpenAPI Handoff + Milestone Verification | 0/TBD | Not started | - |
