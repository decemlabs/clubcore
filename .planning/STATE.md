---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Client PWA — Fill the Gaps
status: Awaiting next milestone
stopped_at: Phase 75 context gathered
last_updated: "2026-06-02T20:27:27.288Z"
last_activity: 2026-06-02 — Milestone v2.1 completed and archived
progress:
  total_phases: 9
  completed_phases: 4
  total_plans: 10
  completed_plans: 10
  percent: 44
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-02 — v2.1 Client PWA — Fill the Gaps opened)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 78 — pmem-notif-promo-frontend-surfacing

## Current Position

Phase: Milestone v2.1 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-06-02 — Milestone v2.1 completed and archived

## v2.1 Roadmap Summary

| Phase | Goal | Requirements |
|-------|------|--------------|
| 75. Backend Field Additions | `price_kopecks`/`auto_renew` in membership response; `notif_prefs` on `/client/me`; FIT15 seeded | PMEM-01, NOTIF-01, PROMO-01 |
| 76. PWA Wiring + Cleanup | Trainers/plans wired to newbie-Home; PersonalDataSheet on real API; mock chat badge removed | NHOME-01, NHOME-02, PDATA-01, PDATA-02, CLEAN-01 |
| 77. v2.0 Debt Closures | Cancel-booking E2E wired (WARNING-1); receipt-destination display reconciled (WARNING-2) | FIX-01, FIX-02 |

**Coverage:** 10/10 v2.1 requirements mapped (zero orphans, zero duplicates).

## v2.0 Roadmap Summary (archived for reference)

| Phase | Goal | Requirements |
|-------|------|--------------|
| 68. Client Auth Foundation | Isolated ClientPrincipal + OTP auth + two-principal isolation | CAUTH-01..06, CISO-01..05 |
| 69. Client Read Endpoints + PWA Alignment | All client reads IDOR-safe + pnpm/Vite-6/TS PWA build verified | CHOME-01..03, CHIST-01..03, CPLAN-01..03, PWA-01..04, PWA-06..07 |
| 70. Client Bookings + QR Self Check-In | Self-booking + cancellation + signed QR + anti-replay check-in | CBOOK-01..05, CCHK-01..03 |
| 71. Client Checkout + Full PWA Wiring | ЮKassa checkout (webhook-only activation) + all PWA screens on real backend | CPAY-01..05, PWA-05 |
| 72. OpenAPI Handoff + CI + E2E Verification | Client-Portal tag in spec, _v20Checks, PWA CI gates, drift gate green, live runbook gate | HND-01..03, VER-01..04 |

## Performance Metrics

**Velocity:**

- Total plans completed: 26
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
| Phase 999.4 P03 | 16m | 3 tasks | 10 files |
| Phase 999.4 P05 | 15min | 3 tasks | 5 files |
| Phase 999.5 P01 | 3min | 3 tasks | 3 files |
| Phase 999.5 P03 | 25min | 3 tasks | 6 files |
| Phase 999.5 P04 | 35 | 3 tasks | 7 files |
| Phase 999.5 P05 | 20min | 4 tasks | 6 files |
| Phase 74-downloads-profile-html-downloads-settings-html P02 | 4m | 2 tasks | 2 files |

## Accumulated Context

### v2.1 Scope Decisions

- No new backend domains — all Phase 75 additions are additive fields/seeds on existing tables/schemas (`ClientMembershipResponse`, `/client/me`)
- `auto_renew` open question: whether the memberships domain has an auto-renewal concept — Phase 75 discuss-phase resolves this; if no domain flag exists, show price only and drop the renewal line from the Profile UI
- `notif_prefs` storage: JSONB column on the `clients` table (or equivalent) — schema migration needed; client-portal `PATCH /client/me` accepts the new field; migration must be additive (nullable, no default constraint change)
- FIT15 seed: idempotent via `INSERT ... ON CONFLICT DO NOTHING`; mirrors the existing promo_codes seed discipline from Phase 999.4
- Phase 76 is pure frontend (flag-flips + query hook wiring) — depends on Phase 75 only for the new `notif_prefs` and membership fields being available
- Phase 77 (FIX-01/FIX-02) is independent of Phase 75/76 — both fixes touch existing hooks and UI files only; can run after Phase 74 baseline

### Key v2.0 Decisions (carry-forward, still locked)

- **D-20-PRINCIPAL**: Separate `ClientPrincipal` + `require_client()` + `aud:"client"` + distinct `cc_client_*` cookies — `Role.CLIENT` is BANNED
- **D-20-MODULE**: `app/modules/client_portal/` aggregator; raw-SQL reads (D-54-08 precedent); Protocol-slot writes; zero new `ignore_imports`
- **D-20-OPENAPI**: Single `openapi.json` extended additively — `Client-Portal` tag; staff paths byte-identical to `contract-freeze-v1.11.0`
- **D-20-IDOR**: Every client-scoped endpoint MUST carry mandatory `client_id` repo param + `assert_owns()` on get-by-ID → 404-collapse (anti-oracle)
- **D-999.5-03-B**: `_read_client_receipt_contact_or_raise` returns (email|None, phone); gate relaxed from email-required to email-OR-phone (D-10); phone is NOT NULL (OTP invariant), so gate never blocks

### Blockers/Concerns

None.

### Pending Todos

- **Future milestones sequence (post-v2.1)** (planning) — durable снимок плана дальнейших milestone'ов (Group-B домены + production + staff-side gate). См. `.planning/todos/pending/2026-06-02-future-milestones-sequence-post-v2-1.md`; канонический дом — PROJECT.md `## Next Milestone Goals`.

## Deferred Items

Items from v2.0 close that are **resolved by v2.1** (tracked here until phase closes):

| Category | Item | Status |
|----------|------|--------|
| integration | WARNING-1: cancel-booking not E2E-wired (BookingManageSheet → useCancelBooking) | ✅ RESOLVED Phase 77 / FIX-01 (wired + real booking threaded; CR-77-01 fixed) |
| integration | WARNING-2: receipt-destination chip removed vs 999.5-UI-SPEC D-09 | ✅ RESOLVED Phase 77 / FIX-02 (spec amended → no-chip declared accepted behavior) |

Items carried forward (not addressed in v2.1):

| Category | Item | Status |
|----------|------|--------|
| production | RUN-01 ЮKassa sandbox sale+refund walkthrough | N/A-until-production |
| production | RUN-02 RU email deliverability probe | N/A-until-production |
| backlog | RUN-05 trainer accrual scenario (D-67-03) | Phase 999.x / future |
| security | Phase 70 CR-02/IN-01/IN-02 (proxy rate-limit bucket, QR post-decode existence, cancel idempotency) | deferred → `/gsd:secure-phase 70` |
| backlog | Promo-code admin CRUD UI (999.4 — only seeded codes exist) | deferred (admin-web frozen) |
| production | RUN-01 live ЮKassa credentialed checkout leg (D-72-06) | OPERATOR-PENDING by design |
| tech-debt | Pre-existing `ruff I001` (import sort) in `client_portal/router.py` — present at v2.1 base `0f6b8927`, NOT introduced by Phase 75 (zero diff). Auto-fixable via `ruff check --fix`. | noted Phase 75 review — quick task or fold into Phase 77 |
| correctness | WR-75-02: receipt-lookup join in `get_client_payment_status` matches by `(plan_id, client_id)` + `ORDER BY created_at DESC LIMIT 1` — repeat same-plan purchases can surface wrong receipt (IDOR-safe). Pre-existing. | deferred — out of Phase 75 scope |
| human-verify | Phase 76 PDATA-02 live check (deferred by user 2026-06-02): start PWA+backend, edit profile in «Личные данные» → Сохранить → full reload → confirm persistence; and stop-backend → save → confirm error toast + field retained. 4/5 criteria code-verified; gates green. | deferred — validate before milestone ship |
| human-verify | Phase 78 live checks (deferred by user 2026-06-02): FIT15 recommended-promo chip surfaces + one-tap applies in BOTH subscription and PT checkout; a Settings notif toggle survives a full page reload (server-backed). 3/3 code-verified incl. 3 NOTIF race fixes; gates green. | deferred — validate before milestone ship |

## Quick Tasks Completed

| ID | Task | Date | Status |
|----|------|------|--------|
| 260601-luw | Remove client-pwa desktop device-frame wrapper — render full-bleed | 2026-06-01 | complete ✓ |
| 260601-oan | Apply v2 visual design to client-pwa newbie Home (live-bind + graceful fallback) | 2026-06-01 | complete ✓ (browser-verified) |
| 260601-sxf | Integrate "К оплате v2" checkout restyle into client-pwa (drop redundant PlanConfirm; hidden promo-chip + bonus scaffolding behind flags) | 2026-06-01 | complete ✓ (browser-verified) |
| 260601-vxr | "Plan Activated" success screen — restyle PaymentSucceededView 1:1 (real membership card via useClientMembership; achievement chip, validity bar, perks, receipt row; hide TabBar; layout/centering polish) | 2026-06-02 | complete ✓ (browser-verified) |
| 260602-xb2 | client-pwa v2.1 UI polish — newbie-Home tariff buttons data-driven from useClientPlans (name+price; dropped dummy 3-button selector + floating chip); CheckoutSheet scroller bottom padding clears the floating pay footer; suppress applied-coupon ticket-notch (fixes right-edge overflow) | 2026-06-03 | complete ✓ (browser-verified) |

## Session Continuity

Last session: 2026-06-02T16:06:03.489Z
Stopped at: Phase 75 context gathered
Resume: Run `/gsd:plan-phase 75` to begin planning the backend field additions phase

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
