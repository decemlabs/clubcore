---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: Schedule + Bookings (PT slots)
status: planning
last_updated: "2026-05-17T11:05:40.194Z"
last_activity: 2026-05-17
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-14)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 36 — milestone-verification-backend-only — COMPLETE; ready for `/gsd-complete-milestone v1.4`

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-17 — Milestone v1.5 started

## v1.4 Milestone Plan

**Phases:** 30 (Foundations & Tech-Debt) → 31 (Trainers) → 32 (Payments + Refund) → 33 (PT-Package Plans + Instances) → 34 (PT-Sessions) → 35 (OpenAPI backend-only handoff) → 36 (Backend-only Milestone Verification) — **all 7 phases complete (2026-05-16)**
**Cadence:** 6 feature phases + 1 verification phase (v1.3 cadence + 1 extra feature phase because PT-package plans/instances and PT-sessions cannot share one phase — sessions decrement instances and need them landed first).
**Requirements:** 61 in-scope mapped (8 INFRA/DEBT + 8 TRN + 18 PAY/REF + 13 PT-package + 9 PT-session + 1 FE + 4 VER); 100% coverage validated. *FE-11..18 (8 reqs) deferred to v2.0 Frontend Integration milestone per 2026-05-15 frontend pivot — design team owns production admin + client apps externally.*

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
- [Phase ?]: Plan 35-02: Forward-guard extended with v1.4 surface block (36 AssertNonNever assertions); README extended with v1.4 changelog + Auth quick-start pointer sections
- [Phase 36]: VER-01..04 closed; 8/8 operator scenarios pass; 5 race-test logical groups green (20/20 individual tests); 4 backend CI gates + admin-web canary captured. 5 REG-36-XX regressions fixed inline (at D-36-17 hard cap of 5; healthy). 44 pre-existing pytest failures (DEFER-36-04-A) rolled forward to Phase 36.1 hot-fix / v1.4.1 cleanup wave — pt_packages UUID stringify is highest-leverage single fix (~28 of 44). Handoff drafts committed: `.planning/handoff/v1.4-postman.json` (55 endpoints, auto-derived) + `.planning/handoff/v1.4-auth-runbook.md` (145 lines, 5 sections). Operator sign-off delegated to Claude Code autonomous orchestrator per user instruction "сделай это сам" on 2026-05-16; recorded verbatim in `v1.4-VERIFICATION-LOG.md` sign_off block.

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

Items acknowledged at v1.4 milestone close on 2026-05-16:

| Category | Item | Status | Source | Resolution |
|----------|------|--------|--------|-----------|
| pytest_failures | DEFER-36-04-A — was 44 pre-existing pytest failures; pre-v1.5 hot-fix (commit `118eb70`) cleared 33 of 44 via 4 mechanical fixes (pt_packages UUID stringify ×3, alembic env import, RBAC count assert refresh, test_revert_predicate column cleanup). Remaining 11 require deeper investigation. | partial-resolved | Phase 36-04 → Phase 36.1 pre-v1.5 hot-fix | **Remaining 11 failures** (recommended Phase 36.2 or v1.5 sub-cycle): (a) 7 pt_sessions MissingGreenlet — async/sync IO mismatch in test fixture or route handler greenlet context (DEFER-36-03-A original cluster); (b) 3 pt_packages test_pt_package_sale validation_error envelope drift — tests expect specific error codes per D-33-16/17 + D-32-10 but service returns generic Pydantic envelope; contract-vs-impl reconciliation needs proper design decision; (c) 1 test_revert_predicate logic bug — `uq_pt_packages_active_per_client` partial UNIQUE violation; test creates 2 active packages for same client; needs redesign with distinct clients. |
| lint_format | DEFER-36-04-B — `ruff format --check` red on 123 files (pre-existing, out of D-36-12 plan gate scope; only `ruff check .` is the gate) | acknowledged | Phase 36-04 | Defer to follow-up format-cleanup cycle. |
| verification_gap | Phase 31 `31-VERIFICATION.md` `human_needed` — 2 admin-web browser-level UI checks for `/trainers` (owner CRUD + reception redirect) | acknowledged | Phase 31 close (2026-05-14) | Out of v1.4 scope per 2026-05-15 pivot (admin-web frozen mock-reference); rolls to v2.0 Frontend Integration milestone. |
| verification_gap | Phase 33 `33-VERIFICATION.md` `human_needed` — 6 items: PT-12 cron + REF-TEST-02 race + PT-07 sale orchestrator (3 closed by Phase 36 race-test sweep + scenario 04); CR-01/02/02b idempotency-key hardening (3 remain) | partial | Phase 33 close (2026-05-15) | 3 closed by Phase 36 verification; CR-01/02/02b deferred to v1.5 idempotency hardening cycle. |
| quick_task | `260501-ndi` orphan in `.planning/quick/` from v1.0 era | acknowledged | v1.0 close, carried since | Defer to `/gsd-cleanup` (carried unchanged from v1.1/v1.2/v1.3 close). |
| uat_gap | Phase 06 06-HUMAN-UAT.md (2 pending scenarios) | partial | v1.1 close | Admin-web UI flows; v2.0 Frontend Integration milestone scope. |
| uat_gap | Phase 08 08-HUMAN-UAT.md (2 pending scenarios) | partial | v1.1 close | Admin-web UI flows; v2.0 Frontend Integration milestone scope. |
| docs | Scenario 07 documented as HTTP 422 (actual) not 409 (CONTEXT.md-stated) — `TrainerInactiveError` extends `ValidationAppError` per source | acknowledged | Phase 36-02 | Source is authoritative; v1.5 may harmonize CONTEXT/SPEC/RFC if a unified error-envelope discipline lands. |
| handoff | Newman CLI runner + curated Postman environments + pre-request login scripts | acknowledged | Phase 36-05 (CONTEXT.md `<deferred>`) | v1.5 API Handoff milestone — turns the auto-generated draft collection into an executable contract test. |
| feature | `GET /api/v1/audit-log` read API (owner-only) + UI consumption | acknowledged | CONTEXT.md `<deferred>` | v1.6 Reports + Audit Log milestone. |
| feature | End-of-day cash drawer reconciliation; pro-rata refunds; bot extensions for PT-packages | acknowledged | CONTEXT.md `<deferred>` (B-02/B-06 amendments) | v1.5+ scope per long-term roadmap. |
| doc_debt | Stale `Phase 35 UI` / `FE-13 in Phase 35` doc-strings in `memberships/router.py` + `payments/router.py` (comments only, not contracts) | acknowledged | Phase 35 close | v1.5 cleanup wave. |
| packaging | `@sportzal/api-client` package.json version bump (`0.0.0` → `0.1.0`); auto-publishing `openapi.json` to versioned URL; OpenAPI tag curation + operationId discipline | acknowledged | Phase 35 close | v1.5 publish prep. |

## Session Continuity

Last session: 2026-05-16 — v1.4 milestone archived + tagged v1.4 locally + pre-v1.5 Phase 36.1 hot-fix landed (commit `118eb70`, 33 of 44 DEFER-36-04-A failures cleared; clean-DB pytest now 1060/11). Live docker stack torn down. Working tree clean.
Stopped at: v1.4 archived + tagged + Phase 36.1 hot-fix complete; awaiting next milestone
Resume: Start the v1.5 API Handoff milestone with `/gsd-new-milestone v1.5`. The 11 remaining DEFER-36-04-A failures (7 MissingGreenlet + 3 validation_error envelope drift + 1 test_revert_predicate partial-UNIQUE logic bug) are tracked in `## Deferred Items` for the v1.5 cycle to plan around. No git remote configured — `v1.4` tag is local only.

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
