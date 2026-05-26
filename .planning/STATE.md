---
gsd_state_version: 1.0
milestone: v1.10
milestone_name: clubcore Rebrand + API Handoff + Production Hardening
status: planning
last_updated: "2026-05-26T09:00:00.000Z"
last_activity: 2026-05-26
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-26 — v1.10 clubcore Rebrand + API Handoff + Production Hardening opened)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** v1.10 roadmap defined — 6 phases (62-67), 32 requirements mapped. Awaiting `/gsd-plan-phase 62` to begin rebrand.

## Current Position

Phase: Not started (roadmap defined, awaiting phase planning)
Plan: —
Status: Roadmap defined — ready for `/gsd-plan-phase 62`
Last activity: 2026-05-26 — v1.10 ROADMAP.md authored; 32 requirements mapped to 6 phases (62-67); REQUIREMENTS.md traceability updated

## v1.10 Roadmap Summary

**Phases (continuing from v1.9 → start at Phase 62):**

| Phase | Goal | Requirements |
|-------|------|--------------|
| 62. clubcore Rebrand | `sportzal → clubcore` package names + storage + Redis + docs; smoke green | REB-01..08 |
| 63. Tech-Debt Sweep | DEFER-46-04 ruff/format/mypy + DEFER-36-04-B + DEFER-40-01 run.sh closed | DEBT-01..05 |
| 64. Contract Freeze — OpenAPI Curation | explicit `operation_id` + `tags` + spec hygiene + drift gate baseline | FRZ-01..05 |
| 65. Handoff Artifacts | Postman v2.1 + Newman + auth runbook + private OpenAPI doc-site | HND-01..04 |
| 66. Idempotency Hardening | CR-01/02/02b closed; standardized `Idempotency-Key` semantics + tests | IDM-01..04 |
| 67. Operator-Pending Runbook Execution | v1.7 VER-03 + CARRY-01/02 + v1.8 VER-01 + v1.9 D-61-12 + MailHog | RUN-01..06 |

**Coverage:** 32/32 v1.10 requirements mapped ✓ (zero orphans, zero duplicates).

**Ordering rationale:**
- 62 first — rebrand goes BEFORE everything else so all subsequent handoff artifacts (Postman / OpenAPI doc-site / contract freeze / runbooks) are created under the `clubcore` name, never under `sportzal`.
- 63 second — tech-debt sweep runs on the already-renamed tree before contract-freeze artefacts so byte-stable regen is achievable on clean code.
- 64 third — OpenAPI curation must precede HND (Phase 65) because Postman + doc-site are generated FROM the curated spec.
- 65 after 64 — handoff artefacts consume curated spec.
- 66 after 64 — Idempotency-Key reusable parameter добавляется в OpenAPI; ordering prevents drift re-regeneration.
- 67 last — operator walkthroughs require stable backend + curated OpenAPI + handoff artefacts ready.

## Milestone Close — v1.9 Trainers Complete

**Status:** v1.9 milestone complete (shipped 2026-05-26)
**Green-state baseline:** `.planning/phases/60-trainer-usage-report/60-VERIFICATION.md` —
Phase 60 (final feature phase) verification report; all v1.9 payroll +
recurring-schedule + trainer-report surface shipped and exercised.
**Milestone-close artifacts (Phase 61 SUMMARYs):**

- `.planning/phases/61-openapi-handoff-milestone-verification/61-01-SUMMARY.md` — openapi.json + schema.d.ts regen + drift-gate lockstep
- `.planning/phases/61-openapi-handoff-milestone-verification/61-02-SUMMARY.md` — `_v19Checks` AssertNonNever forward-guards + count assertion
- `.planning/phases/61-openapi-handoff-milestone-verification/61-03-SUMMARY.md` — `.planning/handoff/v1.9-trainers-runbook.md` authored (sectioned format mirroring v1.8 precedent)
- `.planning/phases/61-openapi-handoff-milestone-verification/61-04-SUMMARY.md` — milestone-gate verification pass (8/8 green: parity + introspection + reception-403 + full pytest + frontend typecheck/test + lint-imports + drift gates + no-edit guard)

**Milestone-gate verifications (all green at 2026-05-26):**

- `pytest tests/integration/test_rbac_parity.py` — 4 passed (D-61-05)
- `pytest tests/integration/test_route_introspection.py` — 3 passed (D-61-06)
- `pytest tests/integration/rbac/test_owner_only.py` — 121 passed (D-61-06)
- `pytest -q` (full backend suite) — 2181 passed, 6 skipped (D-61-10)
- `pnpm --filter @sportzal/api-client typecheck` — exit 0 (compile-time `_v19Checks`)
- `pnpm --filter @sportzal/api-client test` — 16 passed (runtime `toHaveLength` count)
- `uv run lint-imports` — 3 kept, 0 broken (D-61-10 / RPT-04)
- `git diff --exit-code` on `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` — clean (D-61-10 drift gate)
- `git diff` on permissions.py / can.ts / registry.ts — empty (D-61-08 no-edit guard)

## Performance Metrics

| Metric | v1.7 | v1.8 actual | v1.9 actual | v1.10 planned |
|--------|------|-------------|-------------|---------------|
| Phases | 7 | 4 | 4 | 6 (62-67) |
| Plans | 47 | 10 | 22 | TBD |
| Requirements | 48/51 delivered | 30/30 delivered | 15/15 delivered | 32 mapped |
| Phase range | 47-53 | 54-57 | 58-61 | 62-67 |

## Accumulated Context

### Decisions

Full decisions log in PROJECT.md. Key v1.9 locked decisions carried forward:

- **D-PAYROLL-LEDGER**: new `trainer_payroll_accruals` (NOT reuse `payments`); append-only v1.4 discipline; SVC001 commit-gate covers payroll service.
- **D-PAYROLL-RATE-SNAPSHOT**: comp rate snapshotted into accrual row; past accruals are immutable.
- **D-PAYROLL-ROUNDING**: integer `math.ceil` in trainer's favor (ratified 2026-05-25).
- **D-PAYROLL-CLAWBACK**: PT-package refund after accrual → append-only negative adjustment row in same UoW.
- **D-SLOT-GENERATE-AHEAD**: recurring patterns materialized by ARQ cron; NOT expand-on-read.
- **D-TIMEOFF-CONFLICT**: time-off over booked slot → 409 + slot IDs; `?force=true` cascades booking FSM cancellation + DM.
- **D-REPORT-READONLY**: trainer-report in `app/modules/reports/` under D-54-07/08 (raw-SQL, no models.py, zero writes, zero new import-linter ignores).
- **D-AUDIT-PREREG**: new LOCKED_AUDIT_EVENTS pre-registered BEFORE callsites (INFRA-15).
- **D-RBAC-VERIFY**: implementor MUST read permissions.py + can.ts first before adding pairs.

**v1.10 locked decisions (at roadmap creation 2026-05-26):**

- **D-62-FIRST**: Phase 62 rebrand MUST be first — contract freeze under correct name requires all subsequent artefacts (Postman, OpenAPI doc-site, runbooks) created under `clubcore`.
- **D-10-NO-PUBLISH**: Личный коммерческий проект — никакой публикации в npm/PyPI; `@clubcore/api-client` остаётся internal workspace package; OpenAPI doc-site остаётся приватным артефактом.
- **D-10-BACKEND-ONLY**: `apps/admin-web` остаётся frozen-as-of-v1.3 mock reference; rebrand обновляет package names + storage keys внутри, но UI/логика не трогается.
- **D-10-NO-NEW-BUSINESS**: Никаких новых бизнес-фич / новых ORM моделей / новых `LOCKED_AUDIT_EVENTS` / новых `OWNER_ONLY` pairs.
- **D-10-BACK-COMPAT**: localStorage + Redis + env prefix миграции имеют back-compat read из старых ключей ровно один релиз (с deprecated-warning); удаление в v1.11.

### Blockers/Concerns

None blocking v1.10. Carry-over operator-pending items now scheduled into Phase 67 (RUN-01..06) rather than acknowledged-as-deferred.

## Deferred Items

Items acknowledged and scheduled into v1.10 (status: now in scope, scheduled into Phase 67 + Phase 63):

| Category | Item | v1.10 Phase |
|----------|------|-------------|
| operator-pending | DEFER-46-01/CARRY-01 — live RU email-deliverability probe | Phase 67 / RUN-02 |
| operator-pending | DEFER-46-02/CARRY-02 — 15-template owner countersign (extended to 19) | Phase 67 / RUN-03 |
| operator-pending | VER-03 — ЮKassa sandbox walkthrough | Phase 67 / RUN-01 |
| operator-pending | VER-04/D-12 — live docker-compose v1.8 reports runbook walkthrough | Phase 67 / RUN-04 |
| operator-pending | D-61-12 — v1.9 trainers runbook live walkthrough | Phase 67 / RUN-05 |
| ci_tech_debt | DEFER-46-04 — ruff 79 errors / format 205 / mypy attr-defined | Phase 63 / DEBT-01..03 |
| runbook | DEFER-40-01 — full v1.5 operator runbook + run.sh hardening | Phase 63 / DEBT-05 |
| lint_format | DEFER-36-04-B — ruff format 123 residual files | Phase 63 / DEBT-04 |
| infra | DEFER-46-05 — MailHog `--profile dev` integration | Phase 67 / RUN-06 |

All v1.9 audit-open items resolved 2026-05-26. `gsd-sdk query audit-open` → 0/0/0/0/0 (debug, quick, uat, verification, context).

## Session Continuity

Last session: 2026-05-26T09:00:00.000Z
Stopped at: v1.10 ROADMAP.md authored — 6 phases (62-67), 32 requirements mapped, traceability updated in REQUIREMENTS.md.
Resume: `/gsd-plan-phase 62` to begin decomposing Phase 62 (clubcore Rebrand) into executable plans.

## Operator Next Steps

- Review `.planning/ROADMAP.md` (v1.10 section) and `.planning/REQUIREMENTS.md` Traceability table
- Run `/gsd-plan-phase 62` to decompose Phase 62 (clubcore Rebrand) into plans
