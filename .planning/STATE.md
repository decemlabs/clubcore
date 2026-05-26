---
gsd_state_version: 1.0
milestone: v1.10
milestone_name: clubcore Rebrand
status: executing
stopped_at: Phase 62 context gathered
last_updated: "2026-05-26T10:13:08.227Z"
last_activity: 2026-05-26 -- Phase 62 execution started
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 7
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-26 — v1.10 narrowed to Phase 62 (clubcore Rebrand) per D-10-SPLIT; Phases 63-67 → v1.11)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 62 — clubcore-rebrand

## Current Position

Phase: 62 (clubcore-rebrand) — EXECUTING
Plan: 1 of 7
Status: Executing Phase 62
Last activity: 2026-05-26 -- Phase 62 execution started

## v1.10 Roadmap Summary

**Single-phase milestone (narrowed 2026-05-26 per D-10-SPLIT):**

| Phase | Goal | Requirements |
|-------|------|--------------|
| 62. clubcore Rebrand | `sportzal → clubcore` code identifiers (packages + storage + Redis + docs) + operator-tier renames (Postgres DB rename + `CLUBCORE_EMAIL_FROM` env с deprecated-warning fallback + DNS/DKIM checklist + `CLUB_BRAND` constant extraction); smoke green; forward-only `.planning/` rewrite | REB-01..08 |

**Coverage:** 8/8 v1.10 requirements mapped ✓ (zero orphans, zero duplicates).

**Rationale for D-10-SPLIT (2026-05-26):**

- /gsd:discuss-phase 62 revealed Phase 62 scope expansion beyond "code-only rename" to include operator-tier infrastructure work (DB rename via pg_dump/restore, email FROM env wiring, DNS/DKIM checklist, FLUSHDB cutover step, CLUB_BRAND constant extraction).
- Mixing code-only rename and operator infra cutover in one phase made verification heterogeneous and risky.
- Splitting preserves D-62-FIRST: v1.10 ships as "полная переименовка"; v1.11 builds handoff artefacts under clean clubcore name.
- Trade-off accepted: extra milestone-overhead (complete-milestone + new milestone setup) is cheaper than coupling two distinct risk profiles in one phase.

## Milestone Close — v1.9 Trainers Complete

**Status:** Executing Phase 62
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

| Metric | v1.7 | v1.8 actual | v1.9 actual | v1.10 planned | v1.11 planned |
|--------|------|-------------|-------------|---------------|---------------|
| Phases | 7 | 4 | 4 | 1 (Phase 62) | 5 (Phases 63-67) |
| Plans | 47 | 10 | 22 | TBD | TBD |
| Requirements | 48/51 delivered | 30/30 delivered | 15/15 delivered | 8 mapped (REB:8) | 24+2 snapshot (DEBT:5 + FRZ:5 + HND:4 + IDM:4 + RUN:6 + 2 v1.10-shim-removal) |
| Phase range | 47-53 | 54-57 | 58-61 | 62 | 63-67 |

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

**v1.10 locked decisions (at roadmap creation 2026-05-26; updated post-D-10-SPLIT):**

- **D-62-FIRST**: Phase 62 rebrand MUST be first — contract freeze under correct name requires all subsequent v1.11 artefacts (Postman, OpenAPI doc-site, runbooks) created under `clubcore`.
- **D-10-NO-PUBLISH**: Личный коммерческий проект — никакой публикации в npm/PyPI; `@clubcore/api-client` остаётся internal workspace package; OpenAPI doc-site остаётся приватным артефактом.
- **D-10-BACKEND-ONLY**: `apps/admin-web` остаётся frozen-as-of-v1.3 mock reference; rebrand обновляет package names + storage keys внутри, но UI/логика не трогается.
- **D-10-NO-NEW-BUSINESS**: Никаких новых бизнес-фич / новых ORM моделей / новых `LOCKED_AUDIT_EVENTS` / новых `OWNER_ONLY` pairs. `CLUB_BRAND` constant extraction — pure refactor (value неизменно "Sportzal" placeholder).
- **D-10-BACK-COMPAT**: localStorage `copy-on-read + delete old key` (Zustand `version: 1 → 2` + `migrate` callback); Redis cutover — operator FLUSHDB at deploy (нет runtime fallback, заголовок в operator-runbook); env `CLUBCORE_EMAIL_FROM → SPORTZAL_EMAIL_FROM (legacy, deprecated-warning) → hardcoded default` chain; удаление в v1.11 / Phase 67.
- **D-10-SPLIT** (2026-05-26, during /gsd:discuss-phase 62): v1.10 narrowed to Phase 62 only. Phase 62 scope expansion beyond pure code-rename (DB rename, CLUBCORE_EMAIL_FROM env, DNS/DKIM, FLUSHDB, CLUB_BRAND extraction) made the original 6-phase milestone too heterogeneous. Phases 63-67 → v1.11 API Handoff + Production Hardening.
- **D-10-BRAND-DISTINCTION**: clubcore = product/project name (codebase namespace), NOT gym brand. Gym brand = per-installation operator config (future phase). Hardcoded "Sportzal" в email_templates — placeholder для per-club brand, НЕ переименовывается на "clubcore"; extracted в `CLUB_BRAND` constant в Phase 62.
- **D-10-HISTORY-IMMUTABLE**: `.planning/phases/47-61/*` + `.planning/audits/*` — immutable как audit trail (Forward-only `.planning/` rewrite + `.planning/HISTORICAL_NOTE.md` объясняет почему grep всё ещё находит 'sportzal' в historical artifacts).

### Blockers/Concerns

None blocking v1.10. Carry-over operator-pending items now scheduled into Phase 67 (v1.11), not Phase 67 (v1.10) — renumbering only affects bucket, not phase number.

## Deferred Items

Items acknowledged and re-scheduled into v1.11 (status: out of scope for v1.10 per D-10-SPLIT; scheduled into Phases 63-67 in v1.11 milestone — not yet opened):

| Category | Item | Target |
|----------|------|--------|
| operator-pending | DEFER-46-01/CARRY-01 — live RU email-deliverability probe | v1.11 / Phase 67 / RUN-02 |
| operator-pending | DEFER-46-02/CARRY-02 — 15-template owner countersign (extended to 19) | v1.11 / Phase 67 / RUN-03 |
| operator-pending | VER-03 — ЮKassa sandbox walkthrough | v1.11 / Phase 67 / RUN-01 |
| operator-pending | VER-04/D-12 — live docker-compose v1.8 reports runbook walkthrough | v1.11 / Phase 67 / RUN-04 |
| operator-pending | D-61-12 — v1.9 trainers runbook live walkthrough | v1.11 / Phase 67 / RUN-05 |
| ci_tech_debt | DEFER-46-04 — ruff 79 errors / format 205 / mypy attr-defined | v1.11 / Phase 63 / DEBT-01..03 |
| runbook | DEFER-40-01 — full v1.5 operator runbook + run.sh hardening | v1.11 / Phase 63 / DEBT-05 |
| lint_format | DEFER-36-04-B — ruff format 123 residual files | v1.11 / Phase 63 / DEBT-04 |
| infra | DEFER-46-05 — MailHog `--profile dev` integration | v1.11 / Phase 67 / RUN-06 |
| v1.10-shim | sportzal:* localStorage migration logic + SPORTZAL_EMAIL_FROM env fallback removal | v1.11 / Phase 67 / RUN-07 (new) |
| v1.10-evidence | DB rename pg_dump/restore evidence + DNS/DKIM Authentication-Results | v1.11 / Phase 67 / RUN-08 (new) |

All v1.9 audit-open items resolved 2026-05-26. `gsd-sdk query audit-open` → 0/0/0/0/0 (debug, quick, uat, verification, context).

## Session Continuity

Last session: 2026-05-26T09:18:27.900Z
Stopped at: Phase 62 context gathered
Resume: `/gsd:plan-phase 62` to decompose Phase 62 (clubcore Rebrand) into executable plans, using 62-CONTEXT.md decisions.

## Operator Next Steps

- Review `.planning/ROADMAP.md` (v1.10 + v1.11 sections) and `.planning/REQUIREMENTS.md` Traceability table
- Review `.planning/phases/62-clubcore-rebrand/62-CONTEXT.md` (4 area decisions + canonical refs + deferred items)
- Run `/gsd:plan-phase 62` to decompose Phase 62 (clubcore Rebrand) into plans
- After v1.10 ships: `/gsd:new-milestone v1.11` to formally open API Handoff + Production Hardening milestone
