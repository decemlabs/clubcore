---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: Email channel + Multi-user admin
status: shipped
stopped_at: v1.6 shipped 2026-05-21. Awaiting /gsd-new-milestone to open v1.7.
last_updated: "2026-05-21T11:00:00Z"
last_activity: 2026-05-21 — Milestone v1.6 completed and archived
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 82
  completed_plans: 82
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-21 after v1.6 milestone close)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Planning next milestone (v1.7 Online Payments + 54-ФЗ).

## Current Position

Phase: — (v1.6 shipped)
Plan: —
Status: Awaiting next milestone
Last activity: 2026-05-21 — Milestone v1.6 completed and archived

## Accumulated Context

### Decisions

Full decisions log lives in PROJECT.md Key Decisions table. v1.6 added new decisions (D-41-NN..D-46-NN) — all archived in `.planning/milestones/v1.6-ROADMAP.md` and per-phase `*-CONTEXT.md` files.

### Blockers/Concerns

None outstanding for the closed milestone. v1.6 operator follow-ups (VER-12 live RU email-deliverability probe + VER-14 15-template owner countersign) carry forward as DEFER-46-01/02 — see Deferred Items.

## Deferred Items

Items carried forward into the next milestones at v1.6 close on 2026-05-21:

| Category | Item | Status | Source | Resolution |
|----------|------|--------|--------|-----------|
| verification_gap | **DEFER-46-01** — VER-12 live RU email-deliverability probe (yandex.ru + mail.ru + rambler.ru `Authentication-Results` headers). Probe script `apps/backend/scripts/verify/v1_6_email_probe.py` ready; needs real Yandex Postbox API key + owner's personal RU aliases + manual header capture. | acknowledged at v1.6 close | Phase 46 / Plan 46-13 | v1.7 production hardening — one-shot operator task |
| sign_off_gap | **DEFER-46-02** — VER-14 15-template owner formal countersign (`LOCKED_EMAIL_TEMPLATES`). Structural attestation by `claude-opus-4-7` covers regression-relevant invariants (all 15 render OK, Russian content, NBSP discipline, footer, subject alignment with D-46-25). Owner formal ratification remains open. | acknowledged at v1.6 close | Phase 46 / Plan 46-13 | v1.7 — owner sets `signed_off_at` after visual sanity check |
| verification_gap | **DEFER-46-03** — VER-09 scenario 08 (cron-chain circuit-breaker open-state) recorded PARTIAL. Cron chain in-window, but breaker open-state not exercised due to fixture gap (no candidate to fanout under mocked 5xx). | acknowledged at v1.6 close | Phase 46 | v1.9 hardening — add fixture that triggers fanout, re-run scenario 08 |
| ci_tech_debt | **DEFER-46-04** — 3 CI gates carry pre-existing tree-wide tech debt that pre-dates Phase 46: ruff 79 errors / ruff format 205 files / mypy attr-defined warnings. None trace to v1.6 commits. | acknowledged at v1.6 close | Phase 46 | v1.9 doc-debt + test-debt sweep |
| runbook_optional | **DEFER-46-05** — VER-09 MailHog inbox assertions skipped because docker-compose.yml has no MailHog service. Scenarios 01/03/05/06 verified HTTP contract + DB rows + audit_log + enqueue logs, but actual SMTP/Postbox-sandbox delivery is not asserted. | acknowledged at v1.6 close | Phase 46 | v1.9 optional — add MailHog `--profile dev` service or rely on VER-12 live probe |
| verification_gap | **DEFER-40-01** — Full v1.5 operator runbook (6 curl + 2 Telegram sandbox + 2 cron + 5 CI gate URLs); `run.sh` needs 2+ remaining hotfixes (wrong RBAC actor on POST /trainer-slots; missing X-CSRF-Token header on mutating endpoints). | unchanged from v1.5 | Phase 40 | v1.9 (API Handoff + Production Hardening) |
| verification_gap | Phase 38 verification gaps (38-VERIFICATION.md status: gaps_found) | unchanged from v1.5 | Phase 38 | v1.9 audit sweep |
| pytest_failures | DEFER-36-04-A — 11 remaining failures from v1.4 (7 pt_sessions MissingGreenlet + 3 pt_packages validation_error envelope drift + 1 test_revert_predicate logic bug) | unchanged from v1.4 | Phase 36.1 | v1.9 doc-debt + test-debt sweep |
| lint_format | DEFER-36-04-B — `ruff format --check` red on 123 files | unchanged from v1.4 | Phase 36-04 | v1.9 doc-debt sweep (now subsumed by DEFER-46-04) |
| verification_gap | Phase 31 admin-web browser checks (2 scenarios) | unchanged from v1.3 | Phase 31 | v2.0 Frontend Integration milestone scope |
| quick_task | `260501-ndi` orphan in `.planning/quick/` | unchanged from v1.0 | v1.0 | Defer to `/gsd-cleanup` |
| uat_gap | Phase 06 + Phase 08 HUMAN-UAT.md pending scenarios | unchanged from v1.1 | v1.1 | v2.0 Frontend Integration milestone scope |

Known deferred items at v1.6 close: 11 (5 v1.6-native DEFER-46-01..05 + 6 carry-over from v1.5/earlier).

## Session Continuity

Last session: 2026-05-21T11:00:00Z
Stopped at: v1.6 milestone shipped and archived.
Resume: — (start next milestone via `/gsd-new-milestone`)

## Operator Next Steps

- Start the next milestone with `/gsd-new-milestone` (v1.7 Online Payments + 54-ФЗ).
- During v1.7: complete DEFER-46-01 (live RU email-deliverability probe) + DEFER-46-02 (15-template owner countersign).
