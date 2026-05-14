---
phase: 29-milestone-verification
plan: 01
subsystem: infra
tags: [verification, seeding, sqlalchemy, postgres, docker-compose, operator-cli, runbook]

requires:
  - phase: 03-infra
    provides: docker-compose stack (backend, telegram-bot, arq-worker, migrate, postgres, redis)
  - phase: 05-auth
    provides: User model + Role enum (owner FK target for verification clients)
  - phase: 08-clients
    provides: Client model + telegram_user_id unique constraint
  - phase: 17-memberships
    provides: Membership + MembershipPlan models + snapshot pricing columns
  - phase: 25-memberships-freeze-backend
    provides: MembershipFreezePeriod (informs freezable fixture semantics)
provides:
  - apps/backend/scripts/seed_verification_fixtures.py (idempotent 5-client + 5-membership seeder)
  - .planning/phases/29-milestone-verification/29-RUNBOOK.md (10-section operator recipe)
  - TM-29-02 mitigation (DATABASE_URL localhost/postgres:5432 guard in source)
affects:
  - 29-02 (one-shot cron runner — runbook section 5 forward-references it)
  - 29-03 (DEBT-04 scenario execution — consumes fixtures + runbook)
  - 29-04 (cross-phase smoke — uses freezable fixture + DB-level UPDATE recipe from runbook section 6)
  - 29-05 (test-suite + CI gate evidence capture — runbook section 0 pre-flight)
  - 29-06 (hand-off — adds .gitignore entry referenced by runbook section 9)

tech-stack:
  added: []
  patterns:
    - operator-CLI seeder via `uv run python -m scripts.<name>` (mirrors seed_demo_data + export_openapi)
    - deterministic uuid5 IDs for idempotent fixture inserts (no natural unique key on Client.email or Membership)
    - Europe/Moscow ZoneInfo for fixture date arithmetic (CLAUDE.md "Dates" convention)
    - fail-fast guard on DATABASE_URL before any DB connection (TM-29-02)

key-files:
  created:
    - apps/backend/scripts/seed_verification_fixtures.py
    - .planning/phases/29-milestone-verification/29-RUNBOOK.md
  modified: []

key-decisions:
  - "Idempotency key = uuid5(NAMESPACE_DNS, email_key) for Client and uuid5(NAMESPACE_DNS, f'{email_key}-membership') for Membership — neither model has a natural unique constraint we can pivot on (Client.email is nullable+non-unique; Membership has no unique key)."
  - "MembershipPlan column is `freeze_days_limit` (no snapshot suffix); the plan's 29-PATTERNS.md excerpt referred to a snapshot-suffixed name on the plan model. Used the actual column name."
  - "Phone numbers for fixture clients are deterministic per email_key (+7999000000N pattern) so the partial-unique `uq_clients_phone_alive` index never collides on re-run with the same row (uuid5 keeps id stable; phone is bound to email_key)."
  - "Runbook documents TELEGRAM_SANDBOX_CHAT_ID as a forward-looking env var even though it is absent from .env.example today — Plan 29-02 introduces the cron runner that asserts on it (TM-29-03)."
  - "Runbook documents an inline psql INSERT for creating a MembershipPlan with freeze_days_limit >= 7 if seed_demo_data has not provisioned one — seed_demo_data currently only seeds the owner."

patterns-established:
  - "TM-29-02 guard idiom: `if 'localhost' not in db_url and 'postgres:5432' not in db_url: print(stderr); return 1` placed BEFORE any engine construction so it short-circuits without holding connections."
  - "Verification-only fixture script naming: `seed_verification_fixtures.py` suffix `_verification` signals 'throwaway during this phase' intent per D-29-02."
  - "Runbook 10-H2-section layout (0..9, Pre-flight → Evidence directory) — downstream verification runbooks can mirror this skeleton."

requirements-completed: [DEBT-04]

duration: 18min
completed: 2026-05-14
---

# Phase 29 Plan 01: Live Stack Setup Recipe Summary

**Idempotent uuid5-keyed verification seeder (5 clients + 5 memberships) and a 10-section operator runbook covering env vars, docker-compose boot/seed/tear-down, one-shot cron invocation, and DB-level cross-phase smoke recipe — all gated by a TM-29-02 localhost/postgres:5432 fail-fast guard.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-05-14T (worktree wave 1 start)
- **Completed:** 2026-05-14T (this commit)
- **Tasks:** 2
- **Files created:** 2

## Accomplishments

- `apps/backend/scripts/seed_verification_fixtures.py` — idempotent 5-fixture seeder (verify_7d / 3d / 1d / freezable / cancelled), lint-clean (ruff) and type-clean (mypy --strict), TM-29-02 localhost guard runs before any engine construction.
- `.planning/phases/29-milestone-verification/29-RUNBOOK.md` — 10 H2 sections (Pre-flight → Evidence directory) documenting the full live-stack lifecycle for plans 29-02..29-06; threat IDs TM-29-01/02/03 cited in operator prose for audit grep.
- MH-29-08 invariant preserved: zero modifications to `apps/backend/app/**` or `apps/admin-web/src/**`. Only `apps/backend/scripts/` and `.planning/` touched.

## Task Commits

Each task was committed atomically:

1. **Task 1: Author `apps/backend/scripts/seed_verification_fixtures.py`** — `bdcfe7f` (feat)
2. **Task 2: Author `29-RUNBOOK.md` (operator recipe)** — `0cfe08f` (docs)

_Plan metadata commit is owned by the orchestrator after this worktree merges (worktree mode — STATE.md / ROADMAP.md not modified here per parallel_execution rules)._

## Files Created/Modified

- `apps/backend/scripts/seed_verification_fixtures.py` — Operator CLI seeder: 5 clients + 5 memberships, idempotent via `ON CONFLICT (id) DO NOTHING` using deterministic `uuid5` IDs; fails fast if `DATABASE_URL` is non-local; selects first `MembershipPlan` with `freeze_days_limit >= 7` and the first `User` with `role=owner` as required pre-conditions.
- `.planning/phases/29-milestone-verification/29-RUNBOOK.md` — Markdown runbook with 10 H2 sections, env-var table, fixture table, and copy-pasteable `docker compose` + `uv run python -m` + `psql` snippets for every step of the Phase 29 verification flow.

## Decisions Made

- **Idempotency strategy = deterministic uuid5 on `id`.** Client.email is nullable and non-unique; Membership has no natural unique key. Both pivot on `id = uuid5(NAMESPACE_DNS, email_key)` (or `f'{email_key}-membership'`) so re-runs collide on the same primary key and `ON CONFLICT (id) DO NOTHING` is a true no-op. Deterministic uuid5 also keeps fixture rows stable across sessions for downstream plans (29-03..29-05) that may reference them by `uuid`.
- **Column name `freeze_days_limit` (not `freeze_days_limit_snapshot`) on `MembershipPlan`.** 29-PATTERNS.md hinted the plan column might be snapshot-suffixed; reading the actual model showed otherwise. Membership's snapshot column is `freeze_days_limit_snapshot` and inherits from the plan at insert time.
- **Fixture phone numbers are deterministic per email_key.** `+7 999 000 000 N` pattern keyed by the last digit of the telegram_user_id — keeps `uq_clients_phone_alive` collision-free on re-run because the `id` already matches and `ON CONFLICT DO NOTHING` fires before the phone uniqueness check.
- **`TELEGRAM_SANDBOX_CHAT_ID` documented as forward-looking.** Not in `.env.example` today; Plan 29-02 introduces the runner that reads it (TM-29-03 assertion). The runbook flags it as forward-looking but lists it in the env-var checklist so operators know to set it before running the cron smoke.
- **Runbook documents an inline `psql INSERT INTO membership_plans` recipe.** `seed_demo_data.py` currently only seeds the owner — no plans. To keep this plan self-contained, the runbook documents the manual one-liner so operators can satisfy the seeder's pre-condition without waiting for a future seed-plans script.

## Deviations from Plan

None - plan executed exactly as written.

The plan's `<interfaces>` skeleton was followed verbatim (import order, guard placement, `_run()`/`main()` shape, success-line copy). One ruff `I001` import-sort fix was auto-applied via `uv run ruff check --fix` — that is a formatter-driven re-order of the already-correct import groups, not a deviation in content.

## Issues Encountered

None — all acceptance criteria for both tasks passed on the first lint/typecheck run after the initial Write.

## User Setup Required

None at this stage. The runbook itself documents user setup required for downstream plans (env vars in `apps/backend/.env`, sandbox bot token, MembershipPlan seed via `psql`) — those are operator actions performed when executing plans 29-02..29-06, not setup for Plan 29-01 artifacts.

## Threat Surface Scan

No new threat surface introduced beyond what 29-01-PLAN.md's `<threat_model>` already enumerated. TM-29-02 mitigation is in source (TM-29-02 guard with `localhost`/`postgres:5432` check). TM-29-01 is mitigated in the runbook prose (operator instructed to confirm sandbox bot identity, never paste tokens into the log).

## Next Plan Readiness

- Plan 29-02 (one-shot cron runner) — can be authored against the runbook's section 5 forward-reference; the runbook documents the invocation surface (`uv run python -m scripts.run_expiring_cron_once`) and the expected output line, so 29-02's plan can lock those as acceptance criteria.
- Plans 29-03/29-04 (DEBT-04 + cross-phase smoke execution) — fixture data is reproducible, deterministic, and idempotent; operator can re-seed at any point without polluting the DB.
- Plan 29-06 (hand-off + `.gitignore`) — the runbook references `.planning/milestones/v1.3-verification-evidence/` as the local-only evidence directory; the `.gitignore` entry is forward-deferred to 29-06 per plan instructions.

## Self-Check: PASSED

Verified before SUMMARY commit:

- `[ -f apps/backend/scripts/seed_verification_fixtures.py ]` — FOUND
- `[ -f .planning/phases/29-milestone-verification/29-RUNBOOK.md ]` — FOUND
- `git log --oneline | grep bdcfe7f` — FOUND (Task 1 commit)
- `git log --oneline | grep 0cfe08f` — FOUND (Task 2 commit)
- All acceptance greps from both tasks pass (TM-29-02 strings present, all 5 fixture emails present, all 10 runbook H2 sections present, threat IDs cited).
- `uv run ruff check scripts/seed_verification_fixtures.py` exits 0
- `uv run mypy --strict scripts/seed_verification_fixtures.py` exits 0
- No file under `apps/backend/app/**` or `apps/admin-web/src/**` modified — MH-29-08 invariant preserved.

---

*Phase: 29-milestone-verification*
*Plan: 01*
*Completed: 2026-05-14*
