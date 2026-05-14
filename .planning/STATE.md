---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Cash Sales + PT Packages
status: executing
stopped_at: Phase 31 UI-SPEC approved
last_updated: "2026-05-14T13:35:05.128Z"
last_activity: 2026-05-14 -- Phase 31 planning complete
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 6
  completed_plans: 4
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-14)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 30 — foundations-tech-debt-bedrock

## Current Position

Phase: 31
Plan: Not started
Status: Ready to execute
Last activity: 2026-05-14 -- Phase 31 planning complete

## v1.4 Milestone Plan

**Phases:** 30 (Foundations & Tech-Debt) → 31 (Trainers) → 32 (Payments + Refund) → 33 (PT-Package Plans + Instances) → 34 (PT-Sessions) → 35 (OpenAPI + admin-web wiring) → 36 (Milestone Verification)
**Cadence:** 6 feature phases + 1 verification phase (v1.3 cadence + 1 extra feature phase because PT-package plans/instances and PT-sessions cannot share one phase — sessions decrement instances and need them landed first).
**Requirements:** 69 mapped (8 INFRA/DEBT + 8 TRN + 18 PAY/REF + 13 PT-package + 9 PT-session + 9 FE + 4 VER); 100% coverage validated.

## v1.3 Milestone Summary (previous)

**Shipped:** 2026-05-14 (6 days, 199 commits, 45 feat)
**Phases:** 24 (Foundations & Tech-Debt) → 25 (Freeze) → 26 (Renewal) → 27 (Expiring-soon Telegram) → 28 (OpenAPI drift gate + admin-web wiring) → 29 (Milestone verification)
**Plans / tasks:** 33 / 29
**Tests:** backend 729 (95 files), admin-web 233 (41 files) — all green; 6/6 CI gates green
**Verification:** Phase 29 acted as the milestone audit — passed (7/7 human-verification scenarios + cross-phase smoke; 3 production-blocker regressions REG-29-01/03/04 found and fixed inline; 1 minor UX gap deferred to v1.4); operator sign-off in `.planning/milestones/v1.3-VERIFICATION-LOG.md`.
**Archive:** `.planning/milestones/v1.3-ROADMAP.md`, `.planning/milestones/v1.3-REQUIREMENTS.md`, `.planning/milestones/v1.3-VERIFICATION-LOG.md`.
**Tag:** `v1.3` (annotated; to be created during close sequence).

## Accumulated Context

### Decisions

Full decisions log lives in PROJECT.md Key Decisions table.

**v1.4 bedrock decisions (to be locked in Phase 30):**

- B-01 — `payments` table append-only (no soft-delete, no UPDATE; AST-enforced)
- B-02 — full-refund only in v1.4 (no pro-rata; defer to v1.5+)
- B-03 — `LOCKED_AUDIT_EVENTS` pre-registered in Phase 30 before any callsite
- B-04 — **PT-packages live in separate `pt_packages` module with dedicated tables** (variant B) — **CONFIRMED by user**
- B-05 — `trainer_name_snapshot` on PT-session (historical UI integrity)
- B-06 — no end-of-day cash-drawer close in v1.4 (deferred to v1.5)
- B-07 — **uniform reception refund (no 24h owner-approval split)** — **CONFIRMED by user**; H-13 mitigated by AlertDialog + confirm checkbox
- B-08 — refund of `frozen` membership → 409 `must_unfreeze_first`
- B-09 — refund of renewed-source → 409 `cannot_refund_renewed_source`
- B-10 — PT-package alone does NOT grant gym floor access
- B-11 — PT-session backdating: reception 7d / owner unlimited
- B-12 — PT-session cancellation: reception 24h / owner anytime; balance restored atomically

v1.3 added 12 locked decisions covering status taxonomy guard, resolver defence-in-depth filter, mock/http parity for `?expiring=`/`?within=`, freeze concurrency / day accounting, renewal date strategy + pricing + tiebreak, expiring-soon idempotency + cron ordering, `LOCKED_AUDIT_EVENTS` pre-registration discipline, and Phase 29 as milestone-verification-as-audit.

Locked v1.0–v1.3 invariants still hold (modular monolith with `core ⊥ modules` import-linter contract, Python package `app`, frontend integrity, inclusive `end_date`, `gym_date STORED + UNIQUE`, mandatory snapshot pricing, ARQ container `TZ=UTC` + `cron(unique=True, keep_result=60)`, cross-module Protocol callbacks via composition root, Telegram as separate long-polling worker, backend wire format camelCase via `BackendSchemaBase`, pagination `{items, total, page, pageSize}`).

- [Phase ?]: D-30-01..D-30-04 implemented in Plan 30-01: 17 Pydantic v2 audit payload schemas with extra='forbid', registry AUDIT_PAYLOAD_SCHEMAS in audit_payloads.py, emit() validates after locked-set check, payment_row_hash pattern ^sha256:[0-9a-f]{64}$ locked
- [Phase 30]: Plan 30-04 (DEBT-05): mock/memberships.list() expiring branch now respects query.status — closes v1.3 deferred mock-parity gap; in-code rationale comment documents bug-vs-verbatim-REQ semantic mismatch
- [Phase ?]: INFRA-18/19 (Plan 30-02): RBAC matrix extended +5 Resources / OWNER_ONLY 15->26 / no new Action — '(LIST, TRAINERS)' expressed via (VIEW, TRAINERS) outside OWNER_ONLY; three-way parity green (e8beda0, atomic per D-30-09)
- [Phase 30]: INFRA-20/21/22 (Plan 30-03): three architectural gates extended/added — .importlinter modules-independent +2 (payments, pt_packages); SVC001 walker scope 3→6 services; new test_payments_appendonly.py AST walker with import-tracking (_resolve_payment_binding) + 5 on-disk fixtures (4 violations caught: update/delete/on_conflict_do_update/session.delete; 1 clean-INSERT positive control); 6 module placeholders created; Alembic auto-discovery outcome MANUAL → UNCONDITIONAL Payment stub safe; BEFORE/AFTER versions count 10/10; alembic check reports no pending revisions (D-30-10 invariant preserved — Phase 32 PAY-01 owns 0012_payments.py). Commits be962d7 + 091c8ee.

### Pending Todos

- Run `/gsd-discuss-phase 31` to lock Phase 31 plan (Trainers Module — TRN-01..08).

### Blockers/Concerns

None blocking Phase 30 start. Open watch-items inherited from v1.3:

- v1.1 `06-HUMAN-UAT.md` and `08-HUMAN-UAT.md` advisory scenarios were not exercised in Phase 29 sweep — re-evaluate at Phase 36 verification if any touch user-facing flows.
- The `260501-ndi` orphan directory in `.planning/quick/` should be archived during a future `/gsd-cleanup` run.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260501-ndi | Migrate uv dev deps from `[tool.uv].dev-dependencies` to `[dependency-groups].dev` (PEP 735) | 2026-05-01 | 71f28de | [260501-ndi-fix-pyproject-toml-migrate-dev-deps-from](./quick/260501-ndi-fix-pyproject-toml-migrate-dev-deps-from/) |
| 260504-uws | Add root `.gitignore` (DS_Store/node_modules/.claude) + exclude `*.test.tsx` from TanStack Router scan | 2026-05-04 | 40a2b3c, 064b35e | [260504-uws-adminweb-cleanup](./quick/260504-uws-adminweb-cleanup/) |
| 260504-fst | Phase 12.1 fix: `await session.commit()` in clients/service.py write paths + persistence regression test; resolves Phase 11 SC #4 | 2026-05-04 | ba14aba | (inline /gsd-fast) |

## Deferred Items

Items carried into v1.4 from v1.3 close:

| Category | Item | Status | Source | Resolution |
|----------|------|--------|--------|-----------|
| verification_gap | Phase 28 — `apps/admin-web/src/shared/api/services/mock/memberships.ts` `list()` does not filter by `query.status` | resolved | v1.3 close | Closed by Phase 30 Plan 04 (commit dd69b21) — one-liner fix + 2 DEBT-05 vitest specs |
| quick_task | `260501-ndi` orphan in `.planning/quick/` from v1.0 era | acknowledged | v1.3 close | Defer to `/gsd-cleanup` |
| uat_gap | Phase 06 06-HUMAN-UAT.md (2 pending scenarios) | partial | v1.1 close | not exercised in Phase 29 sweep — re-evaluate if user-facing |
| uat_gap | Phase 08 08-HUMAN-UAT.md (2 pending scenarios) | partial | v1.1 close | not exercised in Phase 29 sweep — re-evaluate if user-facing |

## Session Continuity

Last session: 2026-05-14T13:15:59.382Z
Stopped at: Phase 31 UI-SPEC approved
Resume: Start Phase 31 (Trainers Module — TRN-01..08). Run `/gsd-discuss-phase 31` to lock context.
