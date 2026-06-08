---
gsd_state_version: 1.0
milestone: v2.6
milestone_name: Referral System
status: executing
stopped_at: Milestone v2.6 roadmap created (4 phases, 8/8 requirements mapped; ROADMAP.md + STATE.md + REQUIREMENTS.md updated).
last_updated: "2026-06-08T11:06:30.333Z"
last_activity: 2026-06-08 -- Phase 96 execution started
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 3
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 96 — referral-domain-backend

## Current Position

Phase: 96 (referral-domain-backend) — EXECUTING
Plan: 1 of 3
Status: Executing Phase 96
Last activity: 2026-06-08 -- Phase 96 execution started

```
[░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0%
Phase 96 ▸ 97 ▸ 98 ▸ 99
```

## v2.6 Roadmap Summary

| Phase | Goal | Requirements |
|-------|------|--------------|
| 96. Referral Domain Backend | Клиент получает персональный реф-код; друг привязывает реферера при онбординге; owner настраивает суммы | REFER-01, REFER-02 (backend), REFER-03, REFER-07 |
| 97. Reward Crediting | Двусторонний бонус через loyalty_ledger на payment.succeeded первой покупки; idempotent; co-transactional | REFER-04 |
| 98. PWA ReferralScreen | Graduate из D-71-09; pixel-perfect порт макета; список приглашённых; «Уже накоплено»; deep-link | REFER-02 (PWA), REFER-05, REFER-06 |
| 99. OpenAPI Handoff + Milestone Verification | Byte-stable openapi.json + schema.d.ts + _v26Checks + milestone gate зелёный | HND-01 |

**Coverage:** 8/8 v2.6 requirements mapped (zero orphans, zero duplicates). Execution order: 96 → 97 → 98 → 99.

<details>
<summary>v2.5 Roadmap Summary (shipped)</summary>

| Phase | Goal | Requirements |
|-------|------|--------------|
| 90. Messaging Domain + REST Foundation + WS Scaffold | DB schema + REST + WS + Redis pub/sub fan-out; all six WS invariants locked | MSG-01, MSG-02, MSG-03, MSG-04, RT-01, RT-02, RT-03, RT-04 |
| 91. Read Receipts + Typing Indicators | Per-message read status + typing presence over WS; reply-as-read semantics | RCPT-01, RCPT-02, RCPT-03 |
| 92. Photo Attachments | Authenticated upload + IDOR-safe serve; magic-byte validation; stored-XSS guards | ATT-01, ATT-02, ATT-03 |
| 93. Telegram Bridge | Client→staff DM via ARQ + reply routing via chat_forwarding_log + echo-loop prevention | BRDG-01, BRDG-02, BRDG-03 |
| 94. PWA ChatScreen Wiring | Graduate from D-71-09 ESLint zone; wire REST + WS + attachments; unread badge | PWA-01, PWA-02, PWA-03 |
| 95. OpenAPI Handoff + Milestone Verification | Byte-stable openapi.json + schema.d.ts + _v25Checks + milestone gate green | HND-01 |

</details>

## Accumulated Context

### v2.6 Architecture Constraints (pre-locked)

- **Staff-free**: всё реферальное под `require_client()`; `apps/admin-web` заморожен; owner-API только для конфига сумм
- **IDOR-safe**: `client_id` реферера — только из `require_client()` principal, никогда из тела запроса
- **Server-authoritative rewards**: бонус начисляется исключительно на `payment.succeeded` webhook, никогда на клиентский запрос
- **loyalty_ledger reuse**: нет параллельного bonus-store; реферальные бонусы — `entry_type='referral_accrual'` (или аналог) в существующем `loyalty_ledger`
- **Idempotency pattern**: UNIQUE partial index `(referral_id, online_payment_id WHERE entry_type='referral_accrual')` — тот же паттерн, что `record_loyalty_redemption` (Phase 83)
- **INFRA-15 discipline**: все новые LOCKED audit events (`referral_code_generated`, `referral_captured`, `referral_bonus_accrued`) регистрируются в `LOCKED_AUDIT_EVENTS` frozenset до первого callsite
- **One-bonus-per-referee**: бонус начисляется только на первую покупку абонемента рефери; повторные покупки не триггерят повторный бонус
- **D-71-09 graduation pattern**: de-listing ReferralSheet из ESLint zone = удалить из negated ignore (строка `'!src/screens/sheets/ReferralSheet.jsx'`) + удалить dedicated `files` block — точно как ChatScreen в Phase 94

### Key integration points (from code reading)

- **loyalty/service.py**: `accrue_welcome_bonus` и `owner_grant_loyalty` — переиспользуемые примитивы для Phase 97 (caller-owns-txn, flush-only)
- **handlers.py (payment.succeeded)**: Point of insertion for referral bonus crediting — inside `async with session.begin()`, after `record_loyalty_redemption`, before audit emits; follow the exact same RETURNING-gated pattern
- **eslint.config.js (D-71-09)**: Line 32 `'!src/screens/sheets/ReferralSheet.jsx'` + lines 71-109 dedicated block — both must be removed when graduating in Phase 98

### v2.6 Key Decisions (to be confirmed at phase planning)

- **Referral code format**: short alphanumeric slug (e.g. UUID prefix or name-based) — decide at Phase 96 plan
- **Deep-link route**: `/i/<code>` — served by client-pwa router (not backend redirect); backend `GET /referral/resolve/<code>` returns referrer info
- **Capture timing**: referral capture at onboarding step (Phase 68/73 pattern); `POST /client/referral/capture` called with referrer code; client_id from principal (IDOR-safe)
- **Referral config migration**: seed migration (same pattern as FIT15 promo in Phase 75) — no admin UI

### Pending Todos

- **v2.6 planning**: Start with `/gsd:plan-phase 96` (Referral Domain Backend)

### Blockers/Concerns

- None active.

## Deferred Items

Carrying forward from v2.5 close (2026-06-08):

| Category | Item | Status |
|----------|------|--------|
| v2.6 | RCPT-02 typing indicator producer — PWA consumer + WS fan-out wired, but no production `publish_typing` trigger (Telegram has no typing API; admin-web frozen) | deferred → v2.6 admin-web |
| bug→v2.6 | Typing indicator does NOT surface in the DOM despite correct React render — needs `/gsd:debug` + React DevTools fiber inspection when the v2.6 producer lands | deferred → v2.6 |
| human-verify | Phase 94 HUMAN-UAT: pixel-perfect parity + photo flow verified 2026-06-08. NOT exercised: dark theme, physical-device camera, full Telegram leg (operator-pending) | mostly done — see 94-HUMAN-UAT.md |
| advisory-ui | Phase 94 UI-review nits (hoist per-mount `<style>` to singleton; thread-bar online-dot; day-sep array keys) | deferred — see 94-UI-REVIEW.md |
| contract | Phase 92 WR-01 `MessageItem.body` `""` sentinel for attachment-only messages | deferred — contract owner decision |
| tracking | 13 stale prior-milestone quick-task artifacts (260529-*/260601-*, status `missing`) | acknowledged stale |
| tech-debt | Pre-existing: flaky test_freeze_race; promo F821 ruff debt; test_alembic_clean | carried forward |
| production | RUN-01 ЮKassa sandbox sale+refund walkthrough | N/A-until-production |
| production | RUN-02 RU email deliverability probe | N/A-until-production |
| security | Phase 70 CR-02/IN-01/IN-02 (proxy rate-limit, QR post-decode, cancel idempotency) | deferred → /gsd:secure-phase 70 |
| compliance | Phase 81 ФЗ-376 consent wording (concrete ₽ amount vs generic) | needs legal review |

## Session Continuity

Last session: 2026-06-08 (autonomous run)
Stopped at: Milestone v2.6 roadmap created (4 phases, 8/8 requirements mapped; ROADMAP.md + STATE.md + REQUIREMENTS.md updated).
Resume: `/gsd:plan-phase 96` to begin Phase 96 (Referral Domain Backend).

## Operator Next Steps

- Plan Phase 96: `/gsd:plan-phase 96`
