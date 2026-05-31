---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Frontend Integration — Client PWA
status: executing
stopped_at: Phase 999.4 UI-SPEC approved
last_updated: "2026-05-31T15:26:33.640Z"
last_activity: 2026-05-31
progress:
  total_phases: 9
  completed_phases: 6
  total_plans: 34
  completed_plans: 32
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-29 — v2.0 Frontend Integration — Client PWA opened)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 999.4 — client-pwa-checkout-visual-restyle

## Current Position

Phase: 999.4 (client-pwa-checkout-visual-restyle) — EXECUTING
Plan: 4 of 5
Status: Ready to execute
Last activity: 2026-05-31

Progress: [█████████░] 94%

## v2.0 Roadmap Summary

| Phase | Goal | Requirements |
|-------|------|--------------|
| 68. Client Auth Foundation | Isolated ClientPrincipal + OTP auth + two-principal isolation | CAUTH-01..06, CISO-01..05 |
| 69. Client Read Endpoints + PWA Alignment | All client reads IDOR-safe + pnpm/Vite-6/TS PWA build verified | CHOME-01..03, CHIST-01..03, CPLAN-01..03, PWA-01..04, PWA-06..07 |
| 70. Client Bookings + QR Self Check-In | Self-booking + cancellation + signed QR + anti-replay check-in | CBOOK-01..05, CCHK-01..03 |
| 71. Client Checkout + Full PWA Wiring | ЮKassa checkout (webhook-only activation) + all PWA screens on real backend | CPAY-01..05, PWA-05 |
| 72. OpenAPI Handoff + CI + E2E Verification | Client-Portal tag in spec, _v20Checks, PWA CI gates, drift gate green, live runbook gate | HND-01..03, VER-01..04 |

**Coverage:** 47/47 v2.0 requirements mapped (zero orphans, zero duplicates).

## Performance Metrics

**Velocity:**

- Total plans completed: 22
- Average duration: ~6m
- Total execution time: ~18m

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 68-client-auth-foundation P68-01 | 10min | 3 tasks | 5 files |
| Phase 68-client-auth-foundation P68-02 | 4m | 2 tasks | 1 files |
| Phase 68-client-auth-foundation P68-03 | 4m | 2 tasks | 2 files |
| Phase 68-client-auth-foundation P68-04 | 15m | 3 tasks | 3 files |

*Updated after each plan completion*
| Phase 68-client-auth-foundation P68-05 | 4m | 2 tasks | 4 files |
| Phase 68-client-auth-foundation PP68-06 | 45m | 3 tasks | 10 files |
| Phase 70-client-bookings-qr-self-check-in P01 | 15min | 3 tasks | 9 files |
| Phase 70-client-bookings-qr-self-check-in P02 | 12m | 3 tasks | 6 files |
| Phase 71-client-checkout-full-pwa-screen-wiring P01 | 5min | 2 tasks | 3 files |
| Phase 71-client-checkout-full-pwa-screen-wiring P02 | 4min | 2 tasks | 4 files |
| Phase 71-client-checkout-full-pwa-screen-wiring P03 | 9min | 2 tasks | 2 files |
| Phase 71 P04 | 9min | 3 tasks | 11 files |
| Phase 71 P06 | 7min | 2 tasks | 7 files |
| Phase 72 P01 | 5min | 2 tasks | 3 files |
| Phase 72-openapi-handoff-ci-e2e-verification P02 | 8min | 2 tasks | 2 files |
| Phase 72 P04 | 10m | 3 tasks | 2 files |
| Phase 999.3 P01 | 4min | 3 tasks | 4 files |
| Phase 999.3 P02 | 7min | 3 tasks | 6 files |
| Phase 999.4 P01 | 15min | 3 tasks | 5 files |
| Phase 999.4 P04 | 12min | 2 tasks | 4 files |
| Phase 999.4 P02 | 12min | 2 tasks | 5 files |

## Accumulated Context

### Roadmap Evolution

- Phase 999.3 added: client-pwa Home newbie (no-subscription) state — UI, frontend-only
- Phase 999.4 added: client-pwa Checkout visual restyle — UI, ЮKassa redirect unchanged (D-71-04), no in-app card form

### Key v2.0 Decisions (pre-locked from research)

- **D-20-PRINCIPAL**: Separate `ClientPrincipal` + `require_client()` + `aud:"client"` + distinct `cc_client_*` cookies — `Role.CLIENT` is BANNED in `permissions.py` (breaks staff byte-parity with frozen admin-web)
- **D-20-COOKIES**: Client cookies: `cc_client_access` + `cc_client_refresh`, `Path=/api/v1/client`; staff cookies unchanged; no mutual overwrite on same origin
- **D-20-MODULE**: `app/modules/client_portal/` aggregator; raw-SQL reads (D-54-08 precedent); Protocol-slot writes; zero new `ignore_imports`
- **D-20-OTP**: Telegram-OTP-only for v2.0; SMS (SMS Aero / SMSC.ru / МТС Exolve) deferred to SMS-01 future req
- **D-20-OPENAPI**: Single `openapi.json` extended additively — `Client-Portal` tag + `client_` operationId prefix; staff paths byte-identical to `contract-freeze-v1.11.0`
- **D-20-PWA-ROUTER**: react-router v6 is KEPT in `client-pwa` — no TanStack Router migration
- **D-20-IDOR**: Every client-scoped endpoint MUST carry mandatory `client_id` repo param + `assert_owns()` on get-by-ID → 404-collapse (anti-oracle); IDOR parametrized sweep covers all owned resource types

- **D-68-04-SENDER**: `register_client_otp_sender` composition-root slot — bot sender None until plan 05 wires it; service silently skips DM in test mode
- **D-999.4-02-A**: fiscal_receipts D-11 join goes via memberships.plan_id/pt_packages.plan_id (2-hop JOIN through memberships/pt_packages→payments→fiscal_receipts) — no direct online_payments→fiscal_receipts link exists
- **D-999.4-02-B**: PromoNotFoundError etc. are local ValidationAppError subclasses in promo_codes/service.py with stable code= attributes (bounded to promo domain, not in app.core.exceptions)
- **D-999.4-02-C**: validate_promo_code uses integer floor division only (no float); percentage discount_value=percent*100; fixed caps at plan price; 6 D-09 error codes

### Blockers/Concerns

None.

## Deferred Items

Items carried forward from v1.11 close (2026-05-29) — all non-blocking for v2.0 execution:

| Category | Item | Status |
|----------|------|--------|
| production | RUN-01 ЮKassa sandbox sale+refund walkthrough | N/A-until-production |
| production | RUN-02 RU email deliverability probe | N/A-until-production |
| backlog | RUN-05 trainer accrual scenario (D-67-03) | Phase 999.x / future |
| v2.0 | Newman as blocking CI gate (D-11-NEWMAN-LOCAL) | v2.0 scope — plan in Phase 72 |
| v2.0 | SMTP adapter for Mailpit (aiosmtplib) | INFRA-02 — deferred |

## Session Continuity

Last session: 2026-05-31T15:26:33.636Z
Stopped at: Phase 999.4 UI-SPEC approved
Resume: Execute 68-05-PLAN.md next.
