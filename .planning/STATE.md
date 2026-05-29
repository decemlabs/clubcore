---
gsd_state_version: 1.0
milestone: v1.11
milestone_name: API Handoff + Production Hardening
status: Awaiting next milestone
stopped_at: Phase 67 COMPLETE (5/5 plans, VERIFICATION passed 5/5 success criteria). v1.11 milestone fully executed (phases 63,64,66,65,67 all complete). Operator evidence real & captured; 2 backlog items (999.1 WR-06, 999.2 online-payment email wiring).
last_updated: "2026-05-29T12:15:04.465Z"
last_activity: 2026-05-29 — Milestone v1.11 completed and archived
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 26
  completed_plans: 26
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-26 — v1.11 API Handoff + Production Hardening opened)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Planning next milestone (v1.11 shipped 2026-05-29; backend feature-complete, contract frozen for v2.0)

## Current Position

Phase: Milestone v1.11 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-05-29 — Completed backlog 999.2 (wired 4 online-payment email templates into dispatcher; email channel no longer silently no-ops; 5/5 verified). Both v1.11 backlog items (999.1 + 999.2) now closed.

## v1.11 Roadmap Summary

**Execution order: 63 → 64 → 66 → 65 → 67** (Phase 65 executes after 66 — Postman/Newman/runbook must reflect post-66 spec including `components.parameters.IdempotencyKey`)

| Phase | Goal | Requirements |
|-------|------|--------------|
| 63. Tech-Debt Sweep | CI tree green: ruff + mypy exit 0; v1.5 run.sh hardened | DEBT-01..05 |
| 64. Contract Freeze — OpenAPI Curation | Curated spec under clubcore name; Redocly 7th CI gate | FRZ-01..08 |
| 66. Idempotency Hardening | User-scoped verify_idempotency; 86400s TTL; IdempotencyKey in spec | IDM-01..07 |
| 65. Handoff Artifacts | Postman + Newman + auth runbook + private doc-site (post-66 spec) | HND-01..06 |
| 67. Operator Runbook Execution | 4 walkthroughs executed + evidence; Mailpit --profile dev | RUN-00..07 |

**Coverage:** 34/34 v1.11 requirements mapped (zero orphans, zero duplicates).

## Performance Metrics

| Metric | v1.10 actual | v1.11 planned |
|--------|-------------|---------------|
| Phases | 2 (62 + 62.1) | 5 (63-67) |
| Plans | 16 | TBD |
| Requirements | 10/10 | 34 mapped |
| Phase 63 P01 | 25min | 2 tasks | 297 files |
| Phase 63 P02 | 40min | 2 tasks | 36 files |
| Phase 63 P03 | 30min | 3 tasks | 7 files |
| Phase 63 P04 | ~15min | 2 tasks | 1 files |
| Phase 64-contract-freeze-openapi-curation P04 | 25 | 3 tasks | 2 files |
| Phase 64 P05 | 20min | 3 tasks | 4 files |
| Phase 64-contract-freeze-openapi-curation P06 | 25 | 3 tasks | 4 files |
| Phase 64 P07 | 5 | 3 tasks | 2 files |
| Phase 66-idempotency-hardening P02 | 65min | 3 tasks | 8 files |
| Phase 66-idempotency-hardening P03 | 30min | 2 tasks | 16 files |
| Phase 66-idempotency-hardening P04 | ~10min | 2 tasks | 3 files |
| Phase 66-idempotency-hardening P05 | 18min | 3 tasks | 5 files |

## Accumulated Context

### Key v1.11 Decisions (locked 2026-05-26)

- **D-11-OPID**: operation IDs cleaned via `generate_unique_id_function` suffix-strip (not explicit per-route)
- **D-11-IDM-USER**: `verify_idempotency` binds to `current_user.id` in Redis key — security fix for cross-user replay
- **D-11-IDM-WEBHOOK**: ЮKassa webhook uses separate `cc:yk:webhook:*` dedup — NOT affected by user-scoping
- **D-11-CSRF-DEFER**: `sportzal_csrf` cookie name retained in v1.11; rename to `clubcore_csrf` deferred to v2.0
- **D-11-RUN-AUDIT**: Phase 67 plan 1 = staleness audit of all 4 runbooks before any live walkthrough
- **D-11-NEWMAN-LOCAL**: Newman is local handoff smoke, NOT a CI gate (7th CI gate = Redocly lint)
- **D-11-DOCS-PRIVATE**: Redocly doc-site is private/gitignored — no public publish
- **D-11-MAILPIT-PROFILE**: Mailpit added to docker-compose profiles: ["dev"] only; no SMTP adapter in v1.11

### Blockers/Concerns

None.

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260529-ll9 | Purge residual sportzal-era technical naming (auth cookies sz_*/sportzal_csrf → cc_*/clubcore_csrf, email domain → clubcore.ru + DNS zone, ContextVar, YooKassa UA, docstrings); regen frozen openapi.json + schema.d.ts; brand "Sportzal" kept per D-62-02 | 2026-05-29 | 406dc8de | Verified | [260529-ll9-purge-sportzal-cookies-domain](./quick/260529-ll9-purge-sportzal-cookies-domain/) |
| 260529-ny2 | Backlog 999.1 / WR-06 — consumption-keyed PT-session credit restore on owner force-cancel (both cancel_slot + time-off-force cascades); new pt_session_credit_restored audit event; idempotent, no over-credit; NOTE WR-06 removed | 2026-05-29 | e59ec464 | Verified | [260529-ny2-restore-pt-credit-owner-cancel](./quick/260529-ny2-restore-pt-credit-owner-cancel/) |
| 260529-olc | Backlog 999.2 / RUN-03-F1 — wire 4 online-payment EmailTemplate records (owner-signed-off copy) into the dispatcher `_resolve_template`; email channel no longer silently no-ops; +21 resolve/render tests | 2026-05-29 | 762947fe | Verified | [260529-olc-wire-online-payment-emails](./quick/260529-olc-wire-online-payment-emails/) |

## Deferred Items

Items acknowledged and deferred at v1.11 milestone close on 2026-05-29:

| Category | Item | Status |
|----------|------|--------|
| ~~uat~~ DONE | Phase 65 — doc-site renders (HND-06) | ✅ Closed 2026-05-29 — live-verified; fixed broken `pnpm docs` (`preview-docs`→`build-docs`, Redocly v2). Evidence: `.planning/handoff/v1.11-phase65-live-verification-evidence.md` |
| ~~uat~~ DONE | Phase 65 — auth/CSRF auto-wiring (HND-02) | ✅ Closed 2026-05-29 — live-verified via curl + Newman (cc_access/clubcore_csrf cookies, X-CSRF-Token double-submit, POST 201) |
| ~~uat~~ DONE | Phase 65 — `pnpm newman` exits 0 vs seeded stack (HND-04) | ✅ Closed 2026-05-29 — 14/14 requests exit 0; wrong password → exit 1; fixed 2 collection bugs (login assertion shape, reports missing fromDate/toDate) |
| ~~v2.0~~ DONE | `sportzal_csrf` → `clubcore_csrf` + `sz_*` → `cc_*` cookie rename (D-11-CSRF-DEFER / NAME-01) | ✅ Closed 2026-05-29 by quick task 260529-ll9 (commit 97e1fc1b) — done early since no live frontend yet |
| v2.0 | Newman as blocking CI gate (D-11-NEWMAN-LOCAL) | v2.0 |
| v2.0 | SMTP adapter for Mailpit (aiosmtplib) | INFRA-02 |
| production | RUN-01 ЮKassa sandbox sale+refund walkthrough | N/A-until-production (no sandbox creds) |
| production | RUN-02 RU email deliverability probe | N/A-until-production (no prod domain) |
| backlog | RUN-05 trainer accrual-population scenario (deviation, D-67-03) | Phase 999.x / future |
| backlog | WR-06 PT session credit restore on owner force-cancel | Phase 999.1 |
| backlog | Online-payment EMAIL templates wiring (Finding RUN-03-F1) | Phase 999.2 |

> ✅ 2026-05-29: the 3 Phase-65 live-stack checks were **executed and PASSED** on a live `docker compose up` stack (3 handoff-package bugs found + fixed in the process). Evidence: `.planning/handoff/v1.11-phase65-live-verification-evidence.md`. No longer outstanding.

## Session Continuity

Last session: 2026-05-29T11:53:03.765Z
Stopped at: Phase 67 COMPLETE (5/5 plans, VERIFICATION passed 5/5 success criteria). v1.11 milestone fully executed (phases 63,64,66,65,67 all complete). Operator evidence real & captured; 2 backlog items (999.1 WR-06, 999.2 online-payment email wiring).
Resume: v1.11 milestone complete + archived + tagged. Run `/gsd-new-milestone` to open the next cycle (v2.0 Frontend Integration candidate) — REQUIREMENTS.md will be recreated fresh.

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
