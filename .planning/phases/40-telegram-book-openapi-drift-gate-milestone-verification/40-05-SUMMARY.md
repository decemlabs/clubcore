---
phase: 40-telegram-book-openapi-drift-gate-milestone-verification
plan: 05
subsystem: milestone-verification
status: provisional
tags: [milestone-verification, v1.5, telegram-book, operator-driven, partial-execution]
requires: [40-01, 40-02, 40-03, 40-04]
provides:
  - "v1.5 verification log scaffold (10 scenarios, 4 race tests, 5 CI gates, 2 deferred items)"
  - "v1.5 operator runbook for 6 curl scenarios (chmod +x, idempotent)"
affects:
  - ".planning/milestones/v1.5-VERIFICATION-LOG.md"
  - ".planning/milestones/v1.5-verification-evidence/run.sh"
tech-stack:
  added: []
  patterns:
    - "Plan-time race-test pre-discovery (WARNING-3 fix) — discovery happens in scaffold task, not finalize task"
    - "Operator-driven verification with autonomous scaffolding — auto tasks ship template + runbook, human-action tasks capture live-stack evidence"
key-files:
  created:
    - ".planning/milestones/v1.5-VERIFICATION-LOG.md"
    - ".planning/milestones/v1.5-verification-evidence/run.sh"
  modified: []
decisions:
  - "Race-test BOOK-TEST-01 path: apps/backend/tests/integration/bookings/test_booking_race.py (discovered at scaffold time; plan suggested test_booking_create_race.py but only test_booking_race.py exists in the repo — no DEFER-40-NN needed)"
  - "All 3 v1.4 carry-forward race test files confirmed present at scaffold time; no DEFER-40-NN required"
  - "DEFER-36-04-A + DEFER-36-04-B pre-populated in deferred_items per D-40-18 (rolled to v1.9)"
  - "run.sh uses --env-driven config (DATABASE_URL, BASE_URL, RECEPTION_EMAIL, OWNER_EMAIL) — no hard-coded fixture UUIDs; resolved at runtime via psql"
metrics:
  duration: "≈30 minutes (auto-task scaffolding only; Tasks 3-10 await operator)"
  completed: "2026-05-18 (Tasks 1-2 only; Tasks 3-10 deferred to operator)"
---

# Phase 40 Plan 05: v1.5 Milestone Verification — PROVISIONAL Summary

**One-liner:** Auto-scaffolded v1.5 verification log + 6-scenario operator runbook; Tasks 3-10 await operator-driven execution against `docker compose up`.

## Status: PROVISIONAL (Tasks 1-2 of 10 complete)

**This plan is `autonomous: false`** — it has 3 auto tasks (1, 2, 9) and 7
`checkpoint:human-action` tasks (3, 4, 5, 6, 7, 8, 10). The executor agent completes
the 2 setup auto tasks atomically, then yields to the operator for the live-stack
evidence-capture loop (Tasks 3-8). Task 9 (`auto`, fills `actual:` fields from
operator-captured evidence) and Task 10 (`human-action`, final sign-off) close the loop.

**Tasks 3-10 will be filled in by a subsequent run after the operator has executed
the runbook and captured the 14 evidence files.** This SUMMARY.md will be replaced
or extended at that time.

## Tasks Completed in This Wave

| Task | Name                                           | Commit   | Files                                                                       |
| ---- | ---------------------------------------------- | -------- | --------------------------------------------------------------------------- |
| 1    | Scaffold v1.5-VERIFICATION-LOG.md              | `9c260be` | `.planning/milestones/v1.5-VERIFICATION-LOG.md` (382 lines)                 |
| 2    | Operator runbook for 6 curl scenarios          | `5364ca8` | `.planning/milestones/v1.5-verification-evidence/run.sh` (executable; 379 lines) |

## Tasks Deferred to Operator (3-10)

| Task | Type                         | What the operator does                                                                                          |
| ---- | ---------------------------- | --------------------------------------------------------------------------------------------------------------- |
| 3    | checkpoint:human-action      | `docker compose up`, run `bash .../run.sh` → 6 curl HTTP transcripts in `verification-evidence/curl/`           |
| 4    | checkpoint:human-action      | Telegram sandbox happy path: 2 redacted screenshots (`01_happy_path_keyboard.png` + `02_happy_path_confirmed.png`) |
| 5    | checkpoint:human-action      | Telegram sandbox anti-oracle: 1 redacted screenshot + byte-exact DM comparison against `notifications.py:35`    |
| 6    | checkpoint:human-action      | VER-07a: `uv run python -m scripts.run_no_show_cron_once` → `crons/run_no_show.log`                             |
| 7    | checkpoint:human-action      | VER-07b: 2× `uv run python -m scripts.run_booking_reminders_once` (idempotency proof `delta_dms=0`)             |
| 8    | checkpoint:human-action      | Push branch, capture 5 GHA CI gate URLs pinned to HEAD into `ci-gates.md`                                       |
| 9    | auto                         | Fill all `actual:` fields, `evidence_tail:`, pytest counts, race-test pytest run, deferred-items count refresh  |
| 10   | checkpoint:human-action      | YAML `signed_off_by` + `signed_off_at` + `### Final disposition` H3 body + secrets/PII grep gates + commit      |

## Race-Test Pre-Discovery (Task 1 step 0 — WARNING-3 fix)

```
$ find apps/backend/tests -name 'test_*race*.py' -o -name 'test_*concurrent*.py'
apps/backend/tests/integration/pt_packages/test_pt_package_refund_race.py
apps/backend/tests/integration/bookings/test_booking_race.py
apps/backend/tests/integration/pt_sessions/test_pt_session_record_race.py
apps/backend/tests/integration/payments/test_payments_refund_race.py
apps/backend/tests/integration/visits/test_visits_concurrent.py
apps/backend/tests/integration/memberships/test_freeze_race.py
```

- **BOOK-TEST-01**: `apps/backend/tests/integration/bookings/test_booking_race.py` (discovered — plan suggested `test_booking_create_race.py` but only `test_booking_race.py` exists; no DEFER-40-NN filed)
- **v1.4 carry-forward** (all confirmed present):
  - `apps/backend/tests/integration/payments/test_payments_refund_race.py`
  - `apps/backend/tests/integration/pt_packages/test_pt_package_refund_race.py`
  - `apps/backend/tests/integration/pt_sessions/test_pt_session_record_race.py`

No race-test file was missing at scaffold time → **no DEFER-40-NN race-test entry filed**.

## Deviations from Plan

### Auto-applied minor adjustments

**1. [Rule 3 — Blocking discovery resolution] BOOK-TEST-01 file path**

- **Found during:** Task 1 step 0 (WARNING-3 race-test pre-discovery)
- **Issue:** Plan referenced `apps/backend/tests/integration/bookings/test_booking_create_race.py` as the canonical BOOK-TEST-01 path, but `find` returned only `apps/backend/tests/integration/bookings/test_booking_race.py`
- **Fix:** Recorded the discovered path (`test_booking_race.py`) in the scaffold's `race_tests:` block per the WARNING-3 fix protocol; no DEFER-40-NN needed since a booking race test exists at the discovered path
- **Files modified:** `.planning/milestones/v1.5-VERIFICATION-LOG.md` (Task 1 scaffold)
- **Commit:** `9c260be`

**2. [Decision] Two atomic commits instead of one for Tasks 1+2**

- **Reason:** The per-task commit protocol mandates one commit per task. Tasks 1 + 2 produce two independent artifacts (scaffold + runbook); split into atomic commits `9c260be` (Task 1) + `5364ca8` (Task 2) so each commit is independently revertable and the audit trail mirrors the task structure.

## Acceptance Criteria Status

### Task 1 acceptance — ALL MET

- [x] `.planning/milestones/v1.5-VERIFICATION-LOG.md` exists
- [x] 10 `- test:` entries under `human_verification:` (one per scenario 01..10; verified via `grep -cE '^  - test:'`)
- [x] YAML frontmatter has `milestone: v1.5` line
- [x] All required H2 sections present: `## Operator scenarios`, `## Race tests`, `## CI gates`, `## admin-web canary (informational)`, `## Test suites`, `## Deferred items`, `## Handoff artifacts (committed in own commit per D-36-20)`, `## Hand-off`, `## Recipe (manual verification sweep)`
- [x] `### Final disposition (operator andre.shipunov@icloud.com)` H3 exists (placeholder for Task 10)
- [x] DEFER-36-04-A and DEFER-36-04-B entries present in `deferred_items:` per D-40-18
- [x] All `actual:` fields empty (Task 9 populates)
- [x] `signed_off_by:` and `signed_off_at:` empty (Task 10 populates)

### Task 2 acceptance — ALL MET

- [x] `.planning/milestones/v1.5-verification-evidence/run.sh` exists and is executable
- [x] Script contains exactly 6 scenario blocks numbered `01_publish_list_slot` through `06_pt_session_completes_booking`
- [x] Script has `set -euo pipefail` preamble
- [x] Script grep-asserts 3 locked error codes (`slot_not_available`, `cancel_window_exceeded`, `outstanding_booking_must_cancel_first`) so a regression fails the script
- [x] Script writes each scenario's transcript to `EVIDENCE_DIR/0N_*.http`
- [x] Script is idempotent (psql DELETE cleanup at the top of each scenario block per v1.4 recipe pattern)
- [x] `bash -n` syntax check passes

### Task 3-10 acceptance — DEFERRED TO OPERATOR

See the operator runbook in the `## Operator Runbook (Next Steps)` section below.

## Operator Runbook (Next Steps)

```bash
# 1. Bring up the live stack (clean DB)
docker compose -f apps/backend/docker-compose.yml down -v
docker compose --env-file .env.compose.verification \
  -f apps/backend/docker-compose.yml up -d
# Wait until: docker compose ps shows backend + postgres + redis + telegram-bot + arq-worker all Up

# Capture verified_started timestamp for Task 9
date -u +"%Y-%m-%dT%H:%M:%SZ"

# 2. Seed fixtures
cd apps/backend && uv run python -m scripts.seed_v1_4_verification_fixtures && cd ../..

# 3. Run the 6 curl scenarios (Task 3)
bash .planning/milestones/v1.5-verification-evidence/run.sh
# Writes 6 transcripts under verification-evidence/curl/0N_*.http; exits 0 only on full PASS

# 4-5. Telegram sandbox (Tasks 4, 5)
# - From the linked test account, send /book → capture 01_happy_path_keyboard.png + 02_happy_path_confirmed.png
# - From a second account (or after UPDATE pt_packages SET sessions_remaining=0), send /book → capture 03_anti_oracle_denied.png
# - Redact 9-10-digit chat IDs in all 3 PNGs

# 6. No-show cron (Task 6)
cd apps/backend && uv run python -m scripts.run_no_show_cron_once
# (See plan Task 6 for full seed + PRE/POST psql diff capture into crons/run_no_show.log)

# 7. Reminder cron + idempotency proof (Task 7)
cd apps/backend && uv run python -m scripts.run_booking_reminders_once   # first run
cd apps/backend && uv run python -m scripts.run_booking_reminders_once   # second run (must show delta_dms=0)
# Capture stdout + DB diff into crons/run_reminders.log

# 8. CI gates (Task 8)
git push
# Wait for GHA → capture 5 gate URLs pinned to HEAD into ci-gates.md (see plan Task 8 for the template)

# 9-10. Resume the executor (Task 9 fills actual: fields; Task 10 signs off)
# Either:
#   - Run /gsd-verify-work 40 to validate
#   - Or paste outputs and resume the plan with a continuation agent
```

## Known Stubs / Provisional Items

| Stub               | File / Section                                                  | Reason                                                                                                                      |
|--------------------|-----------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| All `actual:` fields | `v1.5-VERIFICATION-LOG.md` `human_verification:` 10 items     | Plan-intended placeholders awaiting operator execution (Tasks 3-8) and Task 9 fill                                          |
| All `result:` fields | `v1.5-VERIFICATION-LOG.md` `human_verification:` + race_tests + ci_gates | Plan-intended placeholders                                                                                                  |
| `signed_off_by`, `signed_off_at`, `status: in_progress` | `v1.5-VERIFICATION-LOG.md` YAML frontmatter | Plan-intended placeholders — Task 10 is the operator sign-off step                                                          |
| Final disposition H3 body | `v1.5-VERIFICATION-LOG.md` body | Plan-intended placeholder for Task 10 operator sign-off                                                                     |
| Evidence directories  | `verification-evidence/{curl,telegram,crons}/`, `ci-gates.md`  | Operator-produced artifacts (Tasks 3-8)                                                                                     |

**These stubs are NOT bugs** — they are the deliberate hand-off seam between the
auto-scaffold half of the plan and the operator-driven half. The plan's `autonomous: false`
declaration is the contract.

## Threat Flags

None. This plan only creates planning/evidence-template files. No new network endpoints,
auth paths, file access patterns, or schema changes at trust boundaries were introduced.
The verification log + runbook will be exercised against existing surfaces; the threat
model in the 40-05-PLAN.md `<threat_model>` block (T-40-21..25) is enforced at Tasks 3-10
runtime (operator phase), not at scaffold time.

## Self-Check: PASSED

- `[ -f .planning/milestones/v1.5-VERIFICATION-LOG.md ]` → FOUND
- `[ -x .planning/milestones/v1.5-verification-evidence/run.sh ]` → FOUND + executable
- `git log --oneline | grep -q 9c260be` → FOUND
- `git log --oneline | grep -q 5364ca8` → FOUND
- `grep -cE '^  - test:' .planning/milestones/v1.5-VERIFICATION-LOG.md` → `10` (matches plan's 10 scenarios)
- `bash -n .planning/milestones/v1.5-verification-evidence/run.sh` → exit 0 (no shell syntax errors)

## Commits

- `9c260be` — `docs(40-05): scaffold v1.5-VERIFICATION-LOG.md mirroring v1.4 structure (Task 1)`
- `5364ca8` — `docs(40-05): operator runbook for 6 curl scenarios (Task 2)`
- (this commit) — provisional SUMMARY.md
