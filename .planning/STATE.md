---
gsd_state_version: 1.0
milestone: v3.2
milestone_name: Admin — Wire the Rest
status: verifying
stopped_at: Phase 112 executed — automated verify 8/8, 4 browser-UAT deferred
last_updated: "2026-06-15T08:06:57.610Z"
last_activity: 2026-06-15
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 17
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 112 — Critical Money & Access

## Current Position

Phase: 112 (Critical Money & Access) — EXECUTING
Plan: 3 of 3
Status: Phase complete — ready for verification
Last activity: 2026-06-15

## v3.2 Roadmap Summary

| Phase | Goal | Requirements |
|-------|------|--------------|
| 112. Critical Money & Access | Arbitrary payment refund (`POST /payments/{id}/refund` + RBAC) + staff role-change (`PATCH /users/{id}/role` + modal + audit) — P0 operational gaps | REF-01, TEAM-01 |
| 113. Promo Codes CRUD | Staff CRUD over existing `promo_codes` backend; wire PlansPage «Скидки и акции» mock→real | PROMO-01, PROMO-02 |
| 114. Attendance Analytics on Existing Reports | FE heatmap/hour-curve/day-of-week/peak/frequency/duration widgets wired to existing `reports/visits` aggregate — zero new backend | ANL-01 |
| 115. Live & Advanced Analytics | Cohort/anomaly/risk (new window-function queries) + LiveNow (`/reports/load/now`) + dashboard activity-feed/trainer-KPI/plans sales-chart | ANL-02, ANL-03, ANL-04 |
| 116. Chat Inbox & Exports | Staff REST over existing messaging module (list threads, send/reply) + CSV exports over existing `csv_export.py` | MSG-01, MSG-02, EXP-01, EXP-02 |
| 117. OpenAPI Handoff + Milestone Gate | Additive `openapi.json` + `schema.d.ts` regen + `_v32Checks` guard + ≥1 real-backend contract test per new domain + full gate green | HND-01 |

**Coverage:** 13/13 v3.2 requirements mapped (112: 2 · 113: 2 · 114: 1 · 115: 3 · 116: 4 · 117: 1). **Execution order: 112 → 113 → 114 → 115 → 116 → 117.**

Note: Phase 114 has no dependency on 112/113 (pure FE wiring on existing backend) and can run in parallel in theory, but is sequenced after for simplicity. Phase 116 depends on 112 (RBAC/staffRequest patterns established).

## v3.1 Roadmap Summary (shipped 2026-06-15 — historical)

| Phase | Goal | Requirements |
|-------|------|--------------|
| 107. Admin FE Completion on Existing Backend | Plan create/edit + PT-package sell/cancel/refund + client-delete-from-hero — real reachable actions vs already-shipped endpoints; no backend/contract change | PLAN-01, PLAN-02, PTPKG-01, PTPKG-02, CLI-04 |
| 108. Editable Settings — Backend + Wiring | Gym card + working hours/breaks/closures + booking rules + notification matrix persist (new/extended backend) and are honored by schedule/booking-window/PWA/dispatcher | CFG-01, CFG-02, CFG-03, CFG-04 |
| 109. Profile & Security — Backend + Wiring | `PATCH /auth/me` (name/email/theme) + self password-change (revokes other sessions) — new endpoints | PROF-01, PROF-02 |
| 110. Live Verification — Deferred P102 | Booking lifecycle (create/cancel/complete) + payroll (comp-config→preview→run→paid) verified live on seeded data | VER-01, VER-02 |
| 111. OpenAPI Handoff + Milestone Gate | Additive (NOT byte-stable) `openapi.json` + `schema.d.ts` regen + `_v31Checks` guard; full gate green; 13/13 verified | HND-01 (handoff) |

**Coverage:** 13/13 v3.1 feature requirements mapped (107: 5 · 108: 4 · 109: 2 · 110: 2). Handoff HND-01 → Phase 111. **Execution order: 107 → 108 → 109 → 110 → 111.**

## v3.0 Roadmap Summary (shipped 2026-06-14 — historical)

| Phase | Goal | Requirements |
|-------|------|--------------|
| 100. Foundation + Auth | Workspace absorption, API client + CSRF + 401-redirect, zod seam, hide-for-future, staff login/session/role-gate | FND-01, FND-02, FND-03, FND-04, AUTH-01, AUTH-02, AUTH-03 |
| 101. Clients + Memberships | Full client-membership lifecycle on real data (list/detail/CRUD + plans + sell/freeze/renew/cancel) | CLI-01, CLI-02, CLI-03, MEM-01, MEM-02, MEM-03 |
| 102. Schedule + Trainers | Trainer slots/templates/time-off + bookings/PT-sessions + trainer catalog + payroll | SCH-01, SCH-02, TRN-01, TRN-02 |
| 103. Attendance + Finance | Check-in + visits load + cashbox + revenue/online-payments reports | ATT-01, ATT-02, FIN-01, FIN-02 |
| 104. Dashboard + Reports + Settings | Live KPI dashboard + all 4 reports + audit log + profile/sessions + user admin | RPT-01, RPT-02, RPT-03, SET-01, SET-02 |
| 105. admin-web Retirement + RBAC Re-home | Delete admin-web; re-home three-way RBAC parity; CI/workspace/drift-gate clean | ADMW-01, ADMW-02, ADMW-03 |
| 106. OpenAPI Handoff + Milestone Gate | Byte-stable contract; full milestone gate green (mypy+lint+pytest+admin-app+Redocly) | HND-01 |

**Coverage:** 30/30 v3.0 requirements mapped. Execution order: 100 → 101 → 102 → 103 → 104 → 105 → 106.

## Accumulated Context

### v3.2 Architecture Context (current milestone)

- **D-V32-SCOPE**: Prioritization по backend-готовности (probed 2026-06-15): `promo_codes` (v2.0), `messaging` (v2.5), `reports/visits` + `csv_export.py` (v1.8) — все готовы для FE-wiring. Дорогой full-stack (cohort/anomaly/risk, LiveNow) — Phase 115, после дешёвого Phase 114.
- **D-V32-CONTRACT-ADDITIVE**: новые маршруты (refund, role-change, promo CRUD, analytics, staff-messages) — additive, NOT byte-stable. Phase 117 регенерирует `openapi.json` + `schema.d.ts` + добавляет `_v32Checks` AssertNonNever guard для каждого нового path×method.
- **D-V32-DRIFT-LESSON**: обязателен ≥1 contract-тест на домен, парсящий РЕАЛЬНЫЙ ответ backend — закрывает v3.0/v3.1 mock↔real schema-drift (дважды прошёл формальный гейт, пойман только browser-UAT).
- **D-V32-RBAC**: REF-01 требует нового `Action.REFUND` (или re-use `Action.CREATE` на `Resource.PAYMENTS`); TEAM-01 требует `(EDIT, USERS_ROLE)` пары — оба owner-only. Extend `Resource`/`OWNER_ONLY` в `permissions.py` + `can.ts`/`registry.ts` (CISO-01 byte-parity). Конкретный дизайн — на планировании Phase 112.
- **D-V32-IDEMPOTENCY**: `POST /payments/{id}/refund` — категория-A (денежная мутация): per-attempt `Idempotency-Key` на FE, `idempotent_execute` orchestrator на backend.
- **D-V32-PROMO-REUSE**: `promo_codes` модуль уже есть (v2.0, `app/modules/promo_codes/`) — только staff-side CRUD endpoints нужны (client-side validate/redeem уже готовы). Admin CRUD был явно отложен в v2.0.
- **D-V32-MESSAGING-STAFF**: `messaging` модуль уже есть (v2.5, `app/modules/messaging/`) — только staff-side REST нужен (list threads, GET thread, POST message). Существующий WS/Telegram bridge остаётся без изменений.
- **D-V32-PHASE114-INDEPENDENT**: Phase 114 не имеет backend-зависимости (чистое FE-wiring на `GET /reports/visits`) — может выполняться параллельно с 112/113, но сиквенсирован после для простоты.
- **Backend discipline carried**: FastAPI modular monolith — raw-SQL reads / Protocol-slot writes (D-20-MODULE), LOCKED audit events pre-registered before any callsite (INFRA-15), Alembic migrations round-trip clean, money in integer kopecks, all dates/windows Europe/Moscow.
- **Frontend discipline carried**: per-domain Zod seam + TanStack Query + `staffRequest` (`cc_access`/`cc_refresh` cookies + `clubcore_csrf` → `X-CSRF-Token`) + `can()`-gating; per-attempt `Idempotency-Key` на денежных мутациях.
- **Cookie naming**: реальные staff cookies — `cc_access`/`cc_refresh` + `clubcore_csrf` (X-CSRF-Token) — старый roadmap prose иногда говорит `sz_*`; доверяй коду.

### v3.1 Architecture Context (pre-locked, carried)

- **D-V31-SCOPE**: v3.1 relaxes v3.0 `D-V30-SCOPE-WIRE` — new backend endpoints ARE allowed, but minimal + single-club; reuse existing where possible (v2.4 `gym` module `PUT /gym`, notification dispatcher, already-shipped PT-package hooks). Source of scope = the 2026-06-14 admin-app audit (`stubs` + `not-live-verified`).
- **D-V31-CONTRACT-ADDITIVE**: because new routes land (`PATCH /auth/me`, password-change, Settings persistence), the staff OpenAPI contract changes **additively — NOT byte-stable** (unlike v3.0). Phase 111 regenerates `openapi.json` + `schema.d.ts` and adds a `_v31Checks` `AssertNonNever` forward-guard for each new path×method; the staff drift-gate expects a non-empty additive diff, not zero-diff.
- **Handoff phase is NOT a no-op** (contrast Phase 106): Phase 111 must regenerate artifacts AND run the full gate (mypy --strict + lint-imports + pytest + admin-app check/test/build + Redocly + CISO-01 parity).
- **Backend discipline carried**: FastAPI modular monolith — raw-SQL reads / Protocol-slot writes (D-20-MODULE), RBAC byte-parity (CISO-01; extend `Resource`/`OWNER_ONLY` only if a new gated resource appears), LOCKED audit events pre-registered before any callsite (INFRA-15), Alembic migrations round-trip clean, money in integer kopecks, all dates/windows Europe/Moscow.
- **Frontend discipline carried**: per-domain Zod seam + TanStack Query + `staffRequest` (`cc_access`/`cc_refresh` cookies + `clubcore_csrf` → `X-CSRF-Token`) + `can()`-gating; per-attempt `Idempotency-Key` on sales.
- **Cookie naming reminder**: real staff cookies are `cc_access`/`cc_refresh` + `clubcore_csrf` (X-CSRF-Token) — some older roadmap prose says `sz_*`; trust the code (memory: staff-cookie-names-cc-not-sz).

### v3.0 Architecture Constraints (pre-locked)

- **D-V30-SCOPE-WIRE**: wire-only — no new backend domains/endpoints; every screen maps to an already-shipped endpoint
- **D-V30-BRANCH**: single-club; Branches/Branch-Settings/System-Settings are hidden-for-future (FND-04), not built
- **D-V30-ADMINWEB-DELETE**: admin-web deleted; RBAC re-home mechanic decided at Phase 100 plan (read real coupling first)
- **D-V30-VERSION**: v3.0 is the wiring milestone; production deploy/launch → v3.1+
- **Zod contract seam**: spike 010 Option A — per-domain zod layer adopted lazily as each screen is wired; mock `queryFn` removed when domain goes live
- **Staff principal**: `cc_*` cookies, `X-CSRF-Token` on mutating requests — not `cc_client_*`
- **RBAC decision deferred**: whether parity lives in admin-app `can.ts` vs backend-only authority is decided at Phase 100 plan after reading real coupling in `permissions.py`/`can.ts`/`registry.ts`

### Pending Todos

- v3.2 roadmap created (Phases 112–117). Next: `/gsd:plan-phase 112` (Critical Money & Access — arbitrary refund + role-change).
- Phase 112 plan must decide RBAC design: `Action.REFUND` vs re-use, exact `Resource` enum extension, `OWNER_ONLY` additions — read `permissions.py` + `can.ts` before building.
- Phase 115 plan must investigate window-function query design for cohort/anomaly/risk before building — verify `reports/` read-only discipline applies.
- Phase 117 contract-test requirement: plan must specify which ASGITransport integration test per domain parses a real backend response (not a mock fixture).

### Phase 101 Decisions

- **D-101-01-CLIENTPATH**: API path param is `client_id` (not `id`): `/api/v1/clients/{client_id}` per schema.d.ts
- **D-101-01-NOHOOKFORM**: `@hookform/resolvers` not installed in admin-app (only admin-web) — manual `ClientCreateSchema.safeParse()` used for modal validation
- **D-101-01-CLIENTFILTERTABS**: `ClientFilterTabs.tsx` kept on disk for type compatibility; NOT rendered in new ClientsPage
- **D-101-02-PLANPATH**: Path param is `plan_id` (not `id`): `/membership-plans/{plan_id}` and `/pt-package-plans/{plan_id}` per schema.d.ts
- **D-101-02-DURATIONIMMUTABLE**: MembershipPlanUpdateSchema.omit({durationDays}) prevents client-side send; backend extra=forbid is authority for 422
- **D-101-02-PTUPDATE-NAMEONLY**: PtPackagePlanUpdateSchema accepts only name — sessionCount/priceKopecks/validityDays immutable per backend contract
- **D-101-02-MOCKSTUBS**: Create/Edit plan modals are toast stubs (plan instructs no net-new modal family); delete fully wired; sales/promos/KPIs stay on mock
- **D-101-03-PATH-PARAMS**: Backend membership paths use {membership_id} not {id}; pt-package paths use {pt_package_id} — matched to schema.d.ts
- **D-101-03-RECEIPTX**: lucide-react 0.469 has no ReceiptX icon; used ReceiptText as functional equivalent for RefundScreen icon
- **D-101-03-HISTORY-STUB**: HistoryScreen remains on mock data; no dedicated history endpoint exists in Phase 101 scope
- **D-101-03-CANCEL-GATE**: SubscriptionModal dispatcher returns null for 'cancel' screen when can(role,'cancel','memberships') is false (reception role)
- **D-101-04-PER-TAB-HOOKS**: Hooks called inside each tab component (clientId prop), not lifted to ClientPage — preserves per-tab error isolation
- **D-101-04-TRAININGS-PTPKG**: TrainingsTab uses usePtPackagesByClient (101-03) — PT-package instances available in scope
- **D-101-04-MEMBERSHIPS-SECTION**: MembershipsSection rendered inline in ClientPage above tabs using useMembershipsByClient reuse

### Phase 103 Decisions

- **D-103-01-SESSION-FROM-CALLER**: useCheckIn receives currentUserId as a mutation var from caller rather than calling useSession() internally — avoids hook coupling in mutationFn, keeps hook context-free
- **D-103-01-LEGACY-USEREPORTS**: useReports() + reportsKeys preserved in reports/api.ts so ReportsPage (Phase 104 scope) builds without changes; reportsQueryKeys uses ['reports-data'] root to avoid key collision
- **D-103-01-NOSESSION-VISITS**: visits/api.ts does NOT import useSession — currentUserId is caller-provided via CheckInVars; payments/api.ts accepts role as explicit parameter
- **D-103-02-CHECKIN-RENAME**: Old mock CheckinModal.tsx (QR scanner) replaced/renamed to CheckInModal.tsx with real client-picker + 3-code 409 implementation; git mv used for proper case rename on macOS case-insensitive FS
- **D-103-02-ATTENDANCE-STATIC-RANGE**: AttendancePage uses static last-30-days range (no date picker); date-range filter UI deferred to Phase 103-03+ where cashbox/finance also need it (shared component)
- **D-103-02-CLIENTNAME-TODO**: VisitData does not embed clientName from server; VisitsList shows fallback label; N+1 client fetches avoided; wiring deferred to Phase 104
- **D-103-03-CASHBOX-HOOKS-SPLIT**: CashboxPage split into outer RBAC guard (useSession only) + inner CashboxPageContent (data hooks); same pattern for LoadPage — avoids conditional React hook calls
- **D-103-03-MSK-SLICE**: computeDailyTotals derives MSK date via receivedAt.slice(0,10) (ISO prefix) rather than TZ conversion; date-fns-tz not installed; backend stores MSK-anchored timestamps
- **D-103-03-LOAD-HEATMAP-SINGLE-ROW**: IntensityHeatmap shown with one row ('Часы') for the 24 hourly aggregate buckets; real data is single-period aggregate not a 7-day matrix
- **D-103-03-FAKEREFUND**: «Оформить возврат» dropdown removed from TransactionsCard — no /payments refund endpoint; refund rows are READ-ONLY per T-103-03-FAKEREFUND
- **D-103-04-FINANCE-SPLIT**: FinancePage split into outer RBAC guard (useSession only) + inner FinancePageContent (data hooks) — same pattern as D-103-03-CASHBOX-HOOKS-SPLIT; React Rules of Hooks safe
- **D-103-04-ALLZERO-EMPTYSTATE**: All-zero revenue buckets (after zero-fill) and all-empty online payments both render EmptyState inline — no flat-zero/NaN chart

### Phase 109 Decisions

- **D-109-01-CONFLICT**: duplicate email caught via IntegrityError on flush; re-raised as ConflictError with fields={'email':...}; route maps to 409 field error
- **D-109-01-NOOP-REVOKE**: revoke_other_sessions_on_password_change returns 0 when user has only one active family (idempotent)
- **D-109-01-NULL-HASH**: None password_hash takes same InvalidPassword raise path as mismatch (T-109-03 anti-oracle parity)
- **D-109-03-SESSIONS-KEY-INLINE**: sessions key `['auth','sessions']` inlined in features/auth/api.ts as literal — avoids cross-feature import (features/auth → features/settings), mirrors settingsKeys.sessions
- **D-109-03-NO-CONFIRM-ON-WIRE**: neither ProfileUpdateSchema nor ChangePasswordSchema has confirmPassword — confirm is UI-only (Plan 04)
- **D-109-03-NO-TOAST-IN-HOOKS**: useUpdateProfile/useChangePassword propagate ApiError to callers without swallowing into toasts — component decides UX
- **D-109-02-204-SHAPE**: change-password returns 204 No Content (response_model=None, status_code=HTTP_204_NO_CONTENT) — no ResponseEnvelope wrapper; FE 204 contract requires empty body
- **D-109-02-ALL-NONE-422**: PATCH /me with both full_name and email None raises ValidationAppError(422) inline in the route — a no-op PATCH is a client bug
- **D-109-02-NIL-UUID-FALLBACK**: if cc_refresh cookie is absent or unresolvable, effective_family_id falls back to UUID(int=0) — revoke-all fallback; extremely rare while access token was valid
- **D-109-04-PARTIAL-PATCH**: ProfileSection handleSave sends only changed fields to PATCH /auth/me by comparing against serverDataRef.current — avoids unnecessary full-body PATCH
- **D-109-04-INVALID-CREDS**: wrong current password discriminated by err.code === 'invalid_credentials' (HTTP 401) mapped to inline 'Неверный текущий пароль' (T-109-19 anti-oracle)
- **D-109-04-PROFILE-TOAST**: section-specific 'Профиль обновлён' toast in ProfileSection.handleSave onSuccess per UI-SPEC section A; SettingsPage aggregate toast still fires when multiple sections saved together

### Phase 104 Decisions

- **D-104-01-CSVLAYER**: csv.ts lives in api/ layer (not features/) to allow same-layer import of appendQuery/parseErrorBody from client.ts without ESLint boundary violation
- **D-104-01-EXPORT-APPEND**: appendQuery + parseErrorBody exported from client.ts by adding export keyword only — no signature/body changes, no callers broken
- **D-104-01-AUDITPAGE-STUB**: AuditPage.tsx updated minimally to compile with 2-arg useAuditLog (useSession for role, passes empty filter); renders EmptyState stub; Wave 2 (104-02) will wire full data rendering, filters, pagination, CSV, RBAC gate
- **D-104-04-MOCKCOMPAT**: useSettings renamed to useMockSettingsData (not deleted) — other sections (Branch/Hours/Booking/Payments/Notifications/App/Integrations/Billing) still need mock data; ProfileSection and SecuritySection are now self-fetching; TeamSection wired in 104-05
- **D-104-04-SELFREVOKE-AUTHBUS**: useRevokeCurrentSession calls publishSessionExpired() on 204 (not navigate()) — routes through RequireAuth authBus subscriber, same path as mid-session 401 (T-104-09 mitigation)
- **D-104-04-PROFILE-READONLY**: ProfileSection is fully read-only; PATCH /auth/me confirmed absent in backend; code comment added noting edit is deferred
- **D-104-05-ROLE-TONE**: ROLE_TONE updated from mock types (owner/admin/trainer/cashier) to API types (owner/reception); mock Role import removed from SectionsBottom.tsx
- **D-104-05-TEAM-COLS**: Simplified TeamSection grid (Сотрудник/Роль/Статус/Actions) — branch/2FA/last-login not in GET /api/v1/users response
- **D-104-05-TOKEN-ID**: useRevokeInvitation receives user.id as tokenId for pending_invitation rows
- **D-104-03-TABSGROUP**: Inline TabsGroup component (not imported from FinancePage parts) — avoids cross-page import, self-contained Reports module
- **D-104-03-CLIENTS-INLINE-KPI**: ClientsTab uses inline KpiCard instead of existing KpiTile — clients 3-scalar data doesn't match KpiTile's icon+delta contract
- **D-104-03-ACTIVITY-ICON-REUSE**: «Журнал действий» nav entry reuses already-imported Activity icon (consistent with Посещаемость entry)

### Phase 105 Decisions

- **D-105-01-GUARD-REPOINT**: CISO-01 byte-parity guard (`test_byte_parity.py`) repointed admin-web → admin-app; all assertions preserved (`.exists()`, `Role.CLIENT`, `| 'client'`); guard is LIVE (confirmed via python import + `.exists()` check)
- **D-105-02-DOCONLY**: config.py, loyalty/permissions.py, and api-client/README.md comment prose updated; NO config default values changed (frontend_base_url/ws_allowed_origins port numbers unchanged)
- **D-105-03-PARITY-INFRA**: `test_byte_parity.py` setup ERROR is pre-existing (SeaweedFS/S3 not running → lifespan timeout); test function logic correct; full-stack run deferred to Phase 106

### Phase 100 Decisions

- **D-100-04-OWNERFLAG**: Gate only Финансы+Отчёты via ownerOnly=true flag on NavItem; all other remaining items visible to all roles (UI-SPEC authoritative on nav visibility; can() matrix is still the single authority via ownerOnly check)
- **D-100-04-RBAC-REHOME**: admin-app is CISO-01 parity source; parity test repointed admin-web → admin-app; admin-web untouched (deleted Phase 105)
- **D-100-04-LEASTPRIV-DEFAULT**: sidebar role defaults to 'reception' while session.isPending; T-100-14 mitigation

### Blockers/Concerns

- **v3.1 milestone close PAUSED (2026-06-15, user choice).** All 5 phases (107–111) built, verified, and committed; milestone audit PASSED (13/13 reqs, full gate green, P102 live-verified incl. live-HTTP uvicorn smoke). Archival/tag/REQUIREMENTS.md-removal NOT done — deferred so the user can run browser-UAT first. **Resume:** run browser UAT then `/gsd-complete-milestone v3.1`.
  - Deferred browser-UAT (code-verified, browser-visual pending): Phase 107 (10), Phase 108 (13), Phase 109 (10) — see each `1NN-UAT.md`. Run `/gsd-verify-work 107` / `108` / `109`.
  - Dev stack left RUNNING for UAT: Postgres :5432 (clubcore, app/app, migrations 0001..0071), Redis :6379, SeaweedFS S3 :8333. Seed owner = `owner@clubcore.dev` / `ownerpass12345`; P102 walkthrough data seeded (`uv run python -m scripts.seed_p102_walkthrough`). Tear down with `docker compose down` (add `-v` to reset DB) in `apps/backend/`.
  - Tracked follow-up: gym-card field-coverage gap (capacity/description/amenities — spawned task), `can.ts` 2 dead duplicate entries, drop the new FE `as never` casts now that schema.d.ts is regenerated.
- Dev DB carry-over: stale `ix_referral_codes_client_id` (migration 0067 amended in place) + possibly polluted `referral_config`. Run `docker compose down -v` + migrate + seed before Phase 106 manual verification. (Non-blocking for test suites — they rebuild schema.)

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260614-hux | Fix v3.0 admin-app live-UAT bugs (8 FE schema/format/cache divergences + phone_exists localization) | 2026-06-14 | e7924fc4 | Verified (typecheck+lint+340 tests green; all 9 live-browser-verified) | [260614-hux-fix-v3-0-admin-app-live-uat-bugs-8-fe-sc](./quick/260614-hux-fix-v3-0-admin-app-live-uat-bugs-8-fe-sc/) |
| 260614-j2d | GAP-1 — reachable membership lifecycle UI entry points (sell/freeze/renew/cancel/refund) on client page | 2026-06-14 | 126dcb58 | Verified (typecheck+lint+router-smoke green; sell+freeze+RBAC live-verified) | [260614-j2d-wire-membership-lifecycle-ui-entry-point](./quick/260614-j2d-wire-membership-lifecycle-ui-entry-point/) |
| 260614-jt7 | REV-01 — revoke pending invitation (Variant B: surface invitationTokenId in GET /users + FE sends token id & body; revoke also soft-deletes the pending user) | 2026-06-14 | 83f054f9 | Verified (backend mypy+users-pytest 35 green, api-client+admin-app typecheck/lint/340 green; live-browser invite→revoke→204→row disappeared) | [260614-jt7-fix-rev-01-revoke-invitation-empty-body-](./quick/260614-jt7-fix-rev-01-revoke-invitation-empty-body-/) |

## Deferred Items

Carrying forward from v2.6 close (2026-06-08):

| Category | Item | Status |
|----------|------|--------|
| tech-debt | WARN-1 zeroed-referrer-bonus → permanent "pending" invitee under zero-config | deferred → post-v3.0 |
| human-verify | 98-HUMAN-UAT browser-only items (pixel parity, live deep-link round-trip, share chips) | pending — see 98-HUMAN-UAT.md |
| tech-debt | RCPT-02 typing indicator producer (WS consumer wired; no Telegram typing API) | deferred → future |
| human-verify | Phase 94 HUMAN-UAT residual (dark theme + physical-device camera) | pending |
| production | RUN-01 ЮKassa sandbox sale+refund walkthrough | N/A-until-production |
| production | RUN-02 RU email deliverability probe | N/A-until-production |
| security | Phase 70 CR-02/IN-01/IN-02 (proxy rate-limit, QR post-decode, cancel idempotency) | deferred → /gsd:secure-phase 70 |
| compliance | Phase 81 ФЗ-376 consent wording (concrete ₽ amount vs generic) | needs legal review |

v3.0 in-progress deferrals:

| Category | Item | Status |
|----------|------|--------|
| feature | P101 WR-01 — Plans create/edit form modals (list/gating/delete/API-hooks done; forms are toast stubs) | deferred → follow-up (user-accepted 2026-06-13) |
| human-verify | P100 — login round-trip + 401 redirect | ✅ validated live 2026-06-13 |
| human-verify | P101 — 9 live-backend UAT items (CRUD round-trips, sell/freeze/refund, role gating) | ✅ verified live 2026-06-14 (see v3.0-UAT-VERIFICATION-PASS.md) |
| human-verify | P102 — 5 live items (time-off force-cascade, booking-race, 24h cancel, payroll kopecks, reception zero-payroll-calls) | ⏳ data-setup-blocked (schedule renders post-BUG-4; payroll/booking seeding deferred) |
| human-verify | P103 — 6 live items (check-in + 409 states, reception zero owner-calls, cashbox refund rows, Load no-NaN, Finance tabs) | ✅ verified live 2026-06-14 (duplicate/outside-hours 409 by equivalence) |
| human-verify | P104 — 11 live items (dashboard KPIs+reception zero-calls, reports + CSV, audit filters/payload, sessions revoke, user invite/deactivate) | ✅ verified live 2026-06-14 (invite needed INV-01/02 fix; REV-01 revoke fixed — see below) |
| bug | REV-01 — revoke-invitation broken (FE no body → 422 + passes user.id not token id; list omits token id) | ✅ FIXED + live-verified 2026-06-14 (quick 260614-jt7: Variant B `invitationTokenId` in GET /users + `{reason}` body; revoke also soft-deletes the pending user; commit 83f054f9) |

**Acknowledged at v3.0 milestone close (2026-06-14):** the rows above are accepted as deferred tech-debt / future-milestone work. Outstanding live-UAT after close = P102 payroll/booking data-heavy set (data-setup-blocked, low marginal value over unit tests) + the `2026-06-02-future-milestones-sequence-post-v2-1.md` planning note. All v2.x carry-forwards remain as listed. Milestone audit: `.planning/milestones/v3.0-MILESTONE-AUDIT.md`.

## Session Continuity

Last session: 2026-06-15T08:06:57.605Z
Stopped at: Phase 112 executed — automated verify 8/8, 4 browser-UAT deferred
Resume: `/gsd:plan-phase 112` (Critical Money & Access — arbitrary payment refund + staff role-change).

## Operator Next Steps

- Complete v3.1 browser-UAT if desired, then `/gsd-complete-milestone v3.1`
- Start planning: `/gsd:plan-phase 112`
