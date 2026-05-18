---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: Email channel + Multi-user admin
status: planning
last_updated: "2026-05-18T14:18:15.871Z"
last_activity: 2026-05-18
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-18)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** v1.6 milestone planning — Email channel + Multi-user admin

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-18 — Milestone v1.6 started

## v1.6 Milestone Plan

**Status:** Speccing in progress — research → requirements → roadmap.

**Working scope (from PROJECT.md Current Milestone block):**

- Email provider integration (Resend / SES / Mailgun — selection TBD post-research)
- Email templates: OTP fallback + expiring-soon (mirror Telegram) + payment-receipt + booking confirm + booking reminder (locked Russian copy + owner sign-off)
- Multi-user admin: `POST /api/v1/users` (owner-only) + PATCH deactivate + soft-delete; reset-password flow
- Multi-user audit traceability across module boundaries
- OpenAPI drift gate refresh for new user-management paths

**Phase numbering:** continues from v1.5 — first phase is **Phase 41**.

## Accumulated Context

### Decisions

Full decisions log lives in PROJECT.md Key Decisions table. v1.5 added 18 new decisions (D-37-01..D-40-18) — all archived in `.planning/milestones/v1.5-ROADMAP.md` and per-phase `*-CONTEXT.md` files.

### Pending Todos

- v1.6 spec in progress (running `/gsd-new-milestone`): domain research → REQUIREMENTS.md → ROADMAP.md.

### Blockers/Concerns

None blocking. Deferred items from prior milestones remain tracked below; none gate v1.6 start.

## Deferred Items

Items carried forward from v1.5 milestone close on 2026-05-18:

| Category | Item | Status | Source | Resolution |
|----------|------|--------|--------|-----------|
| verification_gap | **DEFER-40-01** — Full v1.5 operator runbook (6 curl + 2 Telegram sandbox + 2 cron + 5 CI gate URLs); `run.sh` needs 2+ remaining hotfixes (wrong RBAC actor on POST /trainer-slots; missing X-CSRF-Token header on mutating endpoints). Phase 40 minimal verification PASSED via `scripts/verify_40_create_booking_via_bot.py`; full ritual deferred. | acknowledged | Phase 40 | v1.9 (API Handoff + Production Hardening) — rerun against the stack after `run.sh` hardening |
| verification_gap | Phase 38 verification gaps (38-VERIFICATION.md status: gaps_found) | acknowledged at v1.5 close | Phase 38 | v1.9 audit sweep, or address during v1.6 if cheap |
| pytest_failures | DEFER-36-04-A — 11 remaining failures from v1.4 (7 pt_sessions MissingGreenlet + 3 pt_packages validation_error envelope drift + 1 test_revert_predicate logic bug) | unchanged from v1.4 | Phase 36.1 | v1.9 doc-debt + test-debt sweep |
| lint_format | DEFER-36-04-B — `ruff format --check` red on 123 files | unchanged from v1.4 | Phase 36-04 | v1.9 doc-debt sweep |
| verification_gap | Phase 31 admin-web browser checks (2 scenarios) | unchanged from v1.3 | Phase 31 | v2.0 Frontend Integration milestone scope |
| quick_task | `260501-ndi` orphan in `.planning/quick/` | unchanged from v1.0 | v1.0 | Defer to `/gsd-cleanup` |
| uat_gap | Phase 06 + Phase 08 HUMAN-UAT.md pending scenarios | unchanged from v1.1 | v1.1 | v2.0 Frontend Integration milestone scope |

## Session Continuity

Last session: 2026-05-18T14:18:00.000Z
Stopped at: v1.6 milestone spec in progress — research running
Resume: `/gsd-discuss-phase 41` (after research → requirements → roadmap complete)
