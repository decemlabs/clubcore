# Requirements: clubcore — v3.1 Admin — Fill the Gaps

**Defined:** 2026-06-14
**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

**Milestone goal:** Довести staff-админку до полнофункционального состояния — закрыть FE-заглушки на текущем backend, проверить вживую отложенный P102, и добавить минимальный backend для редактируемых Настроек (зал/график/запись/уведомления) + профиля.

**Scope principle:** v3.1 сознательно ослабляет v3.0 `D-V30-SCOPE-WIRE` (wire-only) — **новые backend-эндпоинты разрешены**, но минимальны и в рамках single-club; переиспользовать существующее где можно (v2.4 `gym` модуль, notification-диспетчер, уже-готовые PT-package хуки). Источник скоупа — аудит admin-app 2026-06-14 (`🩹 Заглушки` + `🟡 не проверено вживую`).

---

## v3.1 Requirements

### PLAN — Тарифы (create/edit)

> Сейчас кнопки «Создать»/«Редактировать» — toast-заглушки; backend (`/membership-plans`, `/pt-package-plans` POST/PATCH) уже существует.

- [x] **PLAN-01**: Owner can create AND edit a membership plan through a real form modal (`POST` / `PATCH /api/v1/membership-plans`), with Zod validation, immutable-field rules (durationDays/freezeDaysLimit), and 422 field-error mapping — replacing the toast stub.
- [x] **PLAN-02**: Owner can create AND edit a PT-package plan through a real form modal (`POST` / `PATCH /api/v1/pt-package-plans`), name editable + other fields immutable per backend contract — replacing the toast stub.

### PTPKG — PT-пакеты (instances)

> Хуки `useSellPtPackage` / `useCancelPtPackage` / `useRefundPtPackage` уже бьют в реальные эндпоинты; отсутствует только UI.

- [x] **PTPKG-01**: Staff can sell a PT-package to a client from the admin (cash, per-attempt `Idempotency-Key`) via a reachable UI (PtPackageScreen in SubscriptionModal or equivalent), surfacing the `amount_mismatch` 422.
- [x] **PTPKG-02**: Staff can cancel and refund a client's PT-package from the admin (refund owner-only + required reason), wiring the existing cancel/refund hooks into reachable actions in TrainingsTab.

### CLI — Clients (continues v3.0 CLI-01..03)

- [x] **CLI-04**: Staff can delete a client directly from the client-page hero action — a real owner-gated soft-delete (`DELETE /api/v1/clients/{id}`) with confirm — replacing the current `toast.info('Удаление доступно из карточки редактирования')` stub.

### CFG — Настройки (persist; новый/расширенный backend)

- [x] **CFG-01**: Owner can edit the gym card (name, address, coordinates, contacts, description, amenities, capacity) and changes persist; reception is 403. Reuse/extend the v2.4 `gym` module (`PUT /gym`) where possible.
- [x] **CFG-02**: Owner can edit working hours + technical breaks + holiday/closure dates and they persist; the schedule / booking window respects them.
- [x] **CFG-03**: Owner can edit online-booking rules (schedule step, booking-ahead window, booking cutoff, cancel/reschedule policy + no-show penalty, group limit + waitlist, PT self-booking flags) and they persist + apply to the client PWA.
- [x] **CFG-04**: Owner can edit the client-notification matrix (per-trigger × per-channel toggles) + sender signature + quiet hours; the settings persist and are honored by the notification dispatcher.

### PROF — Профиль & безопасность

- [ ] **PROF-01**: Staff can edit their own profile (full name, email, theme) via a new `PATCH /api/v1/auth/me` — replacing the read-only profile.
- [ ] **PROF-02**: Staff can change their own password from Settings (current + new password, validated; revokes other sessions per existing discipline).

### VER — Live-верификация отложенного P102

- [ ] **VER-01**: The booking lifecycle (create / cancel / complete via pt-sessions) is verified working live against the running stack on seeded data (closes the P102 `data-setup-blocked` deferral).
- [ ] **VER-02**: Trainer payroll (comp-config → accrual preview → run → pending→paid) is verified working live on seeded data.

---

## Future Requirements

Deferred — later milestone / needs more backend. Tracked, not in this roadmap.

### Settings — heavier / system
- **CFG-PAY-01**: Payments/acquiring settings (ЮKassa/Тинькофф provider config, currency/VAT, 54-ФЗ fiscalization toggles) — partly in `.env`/code today.
- **CFG-BILL-01**: clubcore SaaS billing/tariff section (subscription, invoices, payment method).
- **CFG-INTEG-01**: Integrations management (1С / Telegram / СКУД / API keys).
- **CFG-BRAND-01**: Client-app branding (logo, accent color, modules, client-addressing).

### Security
- **PROF-2FA-01**: Two-factor authentication (SMS or TOTP) + backup codes for staff login.

### Client-facing admin surfaces
- **MSGADM-01**: Staff Messages inbox (staff-side REST over the v2.5 messaging domain) + client Notes backend.

### Multi-branch (D-V30-BRANCH)
- **BRANCH-01**: Branches / Branch-Settings / System-Settings — require backend multi-tenancy.

---

## Out of Scope

Explicitly excluded for v3.1. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Production deploy / hardening (k8s / CI-CD deploy / live ЮKassa off-session leg / RU email-SMS deliverability / secrets + monitoring) | Separate concern from "finish the admin"; pushed to v3.2+ (the original D-V30-VERSION production line). |
| Payments-acquiring / Billing / Integrations / client-app Branding settings | Heavier / system-level; not needed to make single-club gym ops fully editable. Tracked in Future. |
| 2FA (two-factor auth) | Substantial security feature; profile-edit + password-change cover the v3.1 profile gap. Tracked in Future. |
| Client Chat / Notes admin surfaces | Need new backend (staff-side messaging REST + notes store). Tracked in Future (MSGADM-01). |
| Multi-branch (Branches / Branch-Settings / System-Settings) | Backend is single-club by design; hide-for-future (D-V30-BRANCH). |
| New net-new business domains | v3.1 completes existing screens + minimal settings/profile backend — not a new-domain milestone. |

---

## Traceability

Which phases cover which requirements. Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLAN-01 | Phase 107 | Complete |
| PLAN-02 | Phase 107 | Complete |
| PTPKG-01 | Phase 107 | Complete |
| PTPKG-02 | Phase 107 | Complete |
| CLI-04 | Phase 107 | Complete |
| CFG-01 | Phase 108 | Complete |
| CFG-02 | Phase 108 | Complete |
| CFG-03 | Phase 108 | Complete |
| CFG-04 | Phase 108 | Complete |
| PROF-01 | Phase 109 | Pending |
| PROF-02 | Phase 109 | Pending |
| VER-01 | Phase 110 | Pending |
| VER-02 | Phase 110 | Pending |

> **Handoff (not one of the 13):** HND-01 (OpenAPI regen + full milestone gate) → **Phase 111**. v3.1 adds new routes (`PATCH /auth/me`, password-change, Settings persistence), so the contract changes additively (NOT byte-stable) — Phase 111 regenerates `openapi.json` + `schema.d.ts` with a `_v31Checks` forward-guard and runs the full gate.

**Coverage:**
- v3.1 requirements: 13 total
- Mapped to phases: 13 ✅ (107: 5 · 108: 4 · 109: 2 · 110: 2)
- Unmapped: 0
- Each requirement → exactly one phase (no orphans, no duplicates)
- Handoff HND-01 → Phase 111 (milestone-discipline requirement, tracked separately)

---
*Requirements defined: 2026-06-14*
*Last updated: 2026-06-14 — v3.1 requirements defined (13 reqs: PLAN/PTPKG/CLI/CFG/PROF/VER); roadmap created — all 13 mapped to Phases 107–110, handoff HND-01 → Phase 111*
