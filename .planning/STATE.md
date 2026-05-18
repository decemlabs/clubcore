---
gsd_state_version: 1.0
milestone: v1.6
milestone_name: Email channel + Multi-user admin
status: completed
stopped_at: Completed 41-08-PLAN.md
last_updated: "2026-05-18T19:36:30.341Z"
last_activity: 2026-05-18 -- Phase 41 marked complete
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 11
  completed_plans: 11
  percent: 17
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-18)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 41 — infra-bedrock-anti-oracle-scaffold

## Current Position

Phase: 41 — COMPLETE
Plan: 11 of 11
Status: Phase 41 complete
Last activity: 2026-05-18 -- Phase 41 marked complete

## v1.6 Milestone Plan

**Status:** Phase 41 complete

**Phase structure:**

| Phase | Goal | Requirements (count) |
|-------|------|----------------------|
| 41. INFRA Bedrock + Anti-Oracle Scaffold | Pre-register audit events, RBAC, schema migrations, Protocol slots, anti-oracle test BEFORE feature code | INFRA-34..40 + RESET-06 (8) |
| 42. Email Transport Layer + Email OTP Fallback | Provider adapter + ARQ dispatch + DNS + circuit breaker + bounce webhook + email OTP fallback | EMAIL-01..07 + AUTH-EM-01..04 (11) |
| 43. Multi-User Admin Module | New `app/modules/users/` — owner CRUD + deactivate + soft-delete + multi-user audit | USERS-01..07 (7) |
| 44. Invitation + Password-Reset Flow | Anti-oracle `password-reset/request`, atomic-consume confirm, invite-accept INSERT-only, revoke | RESET-01..05 (5) |
| 45. Email Notification Mirrors | Email fallback for expiring + booking reminders + payment-receipt; locked Russian templates | NOTIFY-06..14 (9) |
| 46. OpenAPI Handoff + Milestone Verification | Byte-stable spec regen + live-stack runbook + race tests + deliverability probe + owner sign-off | HANDOFF-03..04 + VER-09..14 (8) |

**Coverage:** 48/48 v1.6 requirements mapped, no orphans, no duplicates.

**Phase numbering:** continues from v1.5 — Phase 41 is the first phase of v1.6 (v1.5 ended at Phase 40).

**Execution order:** 41 → 42 → 43 → 44 → 45 → 46. The dependency graph forks after Phase 41 (Phases 42 and 43 are independent) and reconverges at Phase 44; plan-phase will resolve parallel-eligible plans within each phase.

**Critical-invariant ordering preserved:**

- INFRA bedrock (Phase 41) lands FIRST — cannot start any feature work without it
- `test_password_reset_no_oracle.py` (RESET-06) lands in Phase 41 BEFORE any reset endpoint per Pitfall 1
- Cross-channel `channel`-column migration (INFRA-* / NOTIFY-06) lands in Phase 41 BEFORE any NOTIFY-* phase
- OpenAPI drift gate (HANDOFF-03..04) bundled with verification (VER-09..14) in Phase 46 as the serialization point AFTER all feature phases

**Open conflicts (resolve at discuss-phase per scope):**

1. Email provider (Yandex Cloud Postbox primary vs Unisender Go fallback) — Phase 42 discuss
2. Reset-token storage (itsdangerous stateless vs DB `password_reset_tokens` table) — Phase 44 discuss
3. `notifications` module status (placeholder vs resurrect) — Phase 45 discuss (synthesizer leans placeholder)
4. Template engine (Jinja2 SandboxedEnvironment vs `Final[str]` f-string) — Phase 42 / 45 discuss
5. `User` ORM ownership (hoist to `core/models.py` vs `UserLookup` Protocol slot) — Phase 41 discuss
6. Phase numbering — RESOLVED here: 6 phases (41-46)
7. Email-verify policy for owner-added accounts (trust vs click-to-verify) — Phase 43 discuss

## Accumulated Context

### Decisions

Full decisions log lives in PROJECT.md Key Decisions table. v1.5 added 18 new decisions (D-37-01..D-40-18) — all archived in `.planning/milestones/v1.5-ROADMAP.md` and per-phase `*-CONTEXT.md` files. v1.6 decisions will land at each phase's discuss-phase as `D-41-NN..D-46-NN`.

**Phase 41 Plan 01 (2026-05-18):** LOCKED_AUDIT_EVENTS extended 58 → 69 (+11 v1.6 pairs per D-41-19). Plan must_haves drift ("56 → 67") resolved in favour of D-41-19 source-of-truth — the codebase already had 58 pairs (Phase 20 D-20-10 + Phase 23 D-23-10 drift adds not in the planner's mental count); the 11-pair v1.6 delta is what INFRA-34 requires; final cardinality is 69. Synthetic-violation runtime test established as first such test in the codebase (prior tests were all AST-walker-based). See `41-01-SUMMARY.md`.

- [Phase ?]: Plan 41-03: LOCKED_EMAIL_TEMPLATES frozenset (15 v1.6 template identifiers) + AST walker enforcing literal-only template_id at every get_email_dispatcher() callsite (D-41-11/12/13)
- [Phase ?]: Plan 41-04: Action.UPDATE added to backend Action StrEnum (D-41-22 verb). OWNER_ONLY 29 -> 33 with 4 USERS pairs. Three-way RBAC parity green at 33.
- [Phase 41]: Plan 41-05: Alembic 0022 ships users.deleted_at TIMESTAMPTZ + partial UNIQUE INDEX uq_users_email_active ON users (lower(email)) WHERE deleted_at IS NULL (drops uq_users_email from 0001_auth.py). Revision id shortened to `0022_users_soft_delete_unique` (29 chars) to fit alembic_version VARCHAR(32). Round-trip clean. uq_users_email_active added to env.py _include_object skiplist (D-25-05 lineage). INFRA-38 partially progressed (schema half of 0022 done; 0024 + 0025 land in plans 41-08 + 41-09).
- [Phase 41]: D-41-01/02 User ORM hoisted to app.core.models with one-milestone shim at app.modules.auth.models (v1.7 DEFER-41-shim removes)
- [Phase 41]: D-41-24/25 EmailDispatcher + UserSessionInvalidator Protocol slots declared with defensive-raise accessors
- [Phase 41]: D-41-27/28 .importlinter modules-independent gains app.modules.users; SVC001 walker scope gains modules/users/service.py + modules/auth/password_reset_service.py (anti-silent-drop pin)
- [Phase ?]: Plan 41-11 (2026-05-18): RESET-06 anti-oracle xfail-strict test landed at apps/backend/tests/integration/auth/test_password_reset_no_oracle.py. 4-case identical-202 + identical-body + 100ms bounded-timing contract documented as code; xfail(strict=True) per D-41-17 ensures Phase 44 RESET-01 cannot ship the endpoint without satisfying the contract or breaking CI.
- [Phase ?]: Plan 41-02: 11 v1.6 Pydantic payload schemas registered in AUDIT_PAYLOAD_SCHEMAS with extra='forbid' + audit_correlation_id: UUID | None per D-41-20; PasswordResetRequestedPayload.target_user_id is Optional to support the anti-oracle unknown-email branch (D-41-10)
- [Phase ?]: Migration 0023 alters fk_audit_log_actor_user_id_users from ON DELETE RESTRICT to SET NULL via drop+recreate (no Postgres ALTER CONSTRAINT for ondelete); pairs with new actor_email_snapshot TEXT NULL column for forensic continuity past user hard-deletes (D-41-08/09/10 schema half).
- [Phase ?]: Phase 41 Plan 07: Wired ContextVar runtime half of INFRA-39 — actor_context_var + ActorContextMiddleware (baseline-None envelope) + get_current_user.set_actor() write site + audit.emit() reads contextvar with T-41-07-02 defensive identity check + ARQ on_job_start/on_job_end job envelope. ARQ 0.28 ctx limitation (no job kwargs surfaced) → jobs needing attribution call set_actor() in body. CurrentUser Protocol gained email: str.
- [Phase ?]: [Phase 41 Plan 08]: Alembic 0024 channel discriminator on membership_notifications + booking_notifications — channel TEXT NOT NULL DEFAULT 'telegram' CHECK channel IN ('telegram','email'); UNIQUE recreated to include channel. Zero-row backfill (D-41-15 precedent). CK names wrapped in op.f() so project naming_convention does not double-prefix (caught + fixed pre-commit). Round-trip clean. INFRA-38 still progressing — 0025 lands in Plan 09.
- [Phase ?]: Plan 41-09: INFRA-38 closed — Alembic 0025 ships password_reset_tokens (purpose discriminator + partial UNIQUE (user_id,purpose) WHERE consumed_at IS NULL + non-unique token_hash idx for atomic-consume); PasswordResetToken ORM + alembic/env.py registration; REG-29-04 eager-import discipline pinned in tests/unit/test_workers_eager_import.py (new file — no prior eager-import test existed). All 4 v1.6 INFRA-bedrock migrations in. Pre-existing 41-05/41-08 ORM drift catalogued in deferred-items.md (owned by Phases 43/45).

### Pending Todos

- `/gsd-discuss-phase 41` — resolve open conflict #5 (`User` ORM ownership), draft Phase 41 plan structure for INFRA bedrock + anti-oracle scaffold
- After Phase 41 lands: `/gsd-discuss-phase 42` (resolves conflict #1 provider + #4 template engine) and `/gsd-discuss-phase 43` (resolves #7 email-verify) — can be drafted in parallel

### Blockers/Concerns

None blocking. Deferred items from prior milestones remain tracked below; none gate v1.6 start. The DEFER-40-01 lesson (v1.5 verification runbook scaffolding needed 4 hotfixes) is explicitly budgeted in Phase 46's verification scope.

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

Last session: 2026-05-18T19:30:03.819Z
Stopped at: Completed 41-08-PLAN.md
Resume: `/gsd-execute-phase 41` (next plan: 41-10 User hoist+shim or 41-11 RESET-06 anti-oracle test — both Wave 1)
