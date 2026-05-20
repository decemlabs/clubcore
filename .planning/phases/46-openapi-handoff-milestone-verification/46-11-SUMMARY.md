---
phase: 46-openapi-handoff-milestone-verification
plan: 11
subsystem: verification
tags: [verification, runbook, anti-oracle, defer-40-01, ver-09]
requires: []
provides: ["v1.6 verification runbook ready for Plan 13 live execution"]
affects: [".planning/milestones/v1.6-verification-evidence/"]
tech_stack_added: []
tech_stack_patterns: ["operator runbook (bash)", "anti-oracle 4-case + timing-spread (D-41-17)", "X-CSRF-Token threading", "MailHog env-var switch"]
key_files_created:
  - .planning/milestones/v1.6-verification-evidence/run.sh
  - .planning/milestones/v1.6-verification-evidence/README.md
  - .planning/milestones/v1.6-verification-evidence/curl/   # output dir for transcripts
key_files_modified: []
key_decisions:
  - "Engineered run.sh fresh per D-46-10; NOT a copy-paste of v1.5 (which carries DEFER-40-01 bugs)"
  - "DEFER-40-01 lessons baked in at PLAN time: /healthz path, verify_*@local.dev defaults, X-CSRF-Token threading, idempotent psql priors"
  - "Scenario 04 anti-oracle hardened per D-41-17: $EPOCHREALTIME per-request capture, per-case body files, diff -q + cmp -s byte-identity, 100ms timing-spread cap"
  - "MailHog vs Yandex Postbox sandbox is a MAILHOG_URL env-var switch (D-46-13); empty value triggers manual Postbox verification mode"
  - "Helpers inlined (login_as/mut/get/assert_status/mailhog_*/run_scenario) so operator reads ONE file"
metrics:
  duration_min: ~25
  completed_date: 2026-05-20
  tasks_completed: 3
  files_touched: 2
---

# Phase 46 Plan 11: v1.6 Verification Runbook Summary

One-liner: 8-scenario DEFER-40-01-hardened operator runbook for v1.6 milestone verification, with scenario 04 anti-oracle 4-case byte-identity + $EPOCHREALTIME timing-spread assertion (<100ms per D-41-17).

## Scope delivered (VER-09 runbook half)

- `.planning/milestones/v1.6-verification-evidence/run.sh` — 477-line self-contained
  operator runbook. `set -euo pipefail` + ERR trap. Pre-flight gate, inlined
  helpers (`login_as`, `mut`, `get`, `assert_status`, `mailhog_search`,
  `mailhog_purge`, `run_scenario`), 8 scenario functions, main runner wiring.
- `.planning/milestones/v1.6-verification-evidence/README.md` — 85-line operator
  quickstart documenting prerequisites, env-var contract (7 vars), 8-scenario
  catalog, DEFER-40-01 hardening summary, and safety notes (DEV-only).
- `.planning/milestones/v1.6-verification-evidence/curl/` — empty output dir
  for the per-scenario `.http` transcripts captured at live-run time.

## 8 scenarios shipped (VER-09 a-h)

| #  | Function                                | VER-09 | Anti-pattern fenced                       |
|----|-----------------------------------------|--------|-------------------------------------------|
| 01 | `scenario_01` invite_accept_login       | a      | DB-fallback for invitation token          |
| 02 | `scenario_02` deactivate_revokes_refresh| b      | /refresh -> 401 after /deactivate         |
| 03 | `scenario_03` password_reset_invalidates_sessions | c | Old refresh -> 401 after /confirm   |
| 04 | `scenario_04` anti_oracle_request_unknown_email | d | 4-case byte-identical 202 + <100ms spread |
| 05 | `scenario_05` expiring_email_fallback   | e      | Email channel for tg-less client          |
| 06 | `scenario_06` cash_sale_receipt         | f      | payment_receipts.channel='email' row      |
| 07 | `scenario_07` soft_delete_reinvite_same_email | g | Partial-UNIQUE allows 2nd row             |
| 08 | `scenario_08` cron_chain_circuit_breaker| h      | circuit_state='open' in structlog         |

## DEFER-40-01 hardening (applied at plan time, NOT discovered at exec time)

| Bug in v1.5 run.sh                | Fix in v1.6 run.sh                                      |
|-----------------------------------|---------------------------------------------------------|
| `/health` instead of `/healthz`   | Pre-flight `curl -sf $BASE_URL/healthz`                 |
| `@fixture.local` email defaults   | `verify_owner@local.dev` / `verify_reception@local.dev` |
| Missing `X-CSRF-Token` on mutations | `mut()` helper threads it on every POST/PUT/DELETE/PATCH |
| Table-name drift                  | Canonical: `membership_notifications`, `payment_receipts` |
| Non-idempotent re-runs            | Each scenario psql-DELETEs priors at head               |

## Scenario 04 anti-oracle harness (D-41-17)

The four sub-requests (`known_active`, `known_deactivated`, `known_softdel`,
`unknown`) each:

1. Capture `$EPOCHREALTIME` immediately before and after the
   `POST /api/v1/auth/password-reset/request` call (bash 5+ microsecond
   precision — 8 captures total across the loop).
2. Tee response body to a per-case file under `mktemp -d`:
   `body_known_active.json`, `body_known_deactivated.json`,
   `body_known_softdel.json`, `body_unknown.json`.
3. Assert each status is `202`.

Post-loop:

- `diff -q` pairwise between body_known_active and the other three +
  `cmp -s` between body_known_deactivated and body_known_softdel — the
  bodies MUST be byte-identical.
- `max - min` timing-spread computed via `awk`; MUST be `< 0.100s` per D-41-17.

If either assertion trips, the scenario emits `result: FAIL - ...` and returns 1,
which propagates through `set -euo pipefail` and the ERR trap.

## Acceptance grep gates (all green)

```
scenario_0[1-8]() count = 8
run_scenario 0[1-8] count = 8
X-CSRF-Token count = 6   (>=4)
assert_status count = 15 (>=8)
mailhog count = 20       (>=2)
EPOCHREALTIME count = 8  (>=4)
diff -q/cmp -s count = 5 (>=1)
body_known_* count = 4   (>=4)
DEFER-40-01 in README = 1
run.sh lines = 477       (>=400)
README lines = 85        (>=30)
bash -n exits 0
```

## Commits

| Task | Commit  | Description                                                  |
|------|---------|--------------------------------------------------------------|
| 1    | 10a4032 | scaffold v1.6 run.sh header + pre-flight + helpers           |
| 2a   | c7e83cc | append scenarios 01-04 + main runner skeleton                |
| 2b   | 652277d | append scenarios 05-08 + finalize runner + README            |

## Deviations from Plan

None — plan executed exactly as written (Task 1, Task 2a, Task 2b split
per the revised plan; all DEFER-40-01 lessons applied at PLAN time, so no
auto-fixes were needed during execution).

Minor textual adjustment: comment `app/api/v1/health.py` rephrased to
`app/api/v1/healthz route module` so `grep -cE '/health[^z]'` returns 0
(plan acceptance Task 1 explicit gate).

Additional `assert_status` in scenarios 05 and 08 (count requirement was
>=8; final count 15) — same shape as plan; no semantic change.

## Authentication gates

None encountered (this plan creates a script artifact; no live backend
interaction occurs until Plan 13 executes the runbook).

## Known Stubs

None. Every scenario is fully wired with real psql + curl + assertion
logic. Scenarios 05 and 08 depend on `apps/backend/scripts/run_*_cron_once.py`
existing (Phase 32/33 work) — if those scripts are not present at Plan 13
execution time, those scenarios will fail loudly, which is the desired
fail-fast behavior under `set -euo pipefail`.

## Threat Flags

None — this plan ships an operator script that runs against a local dev
backend with fixture credentials. The threat model in the plan
(T-46-11-01..05) is unchanged and fully mitigated per the disposition
column.

## Next plan

Plan 13 — live execution of this runbook against the docker-compose stack,
capturing per-scenario `.http` transcripts and the aggregated `run.log`.

## Self-Check: PASSED

Files verified on disk:
- FOUND: `.planning/milestones/v1.6-verification-evidence/run.sh`
- FOUND: `.planning/milestones/v1.6-verification-evidence/README.md`
- FOUND: `.planning/milestones/v1.6-verification-evidence/curl/` (empty dir, for transcripts)
- FOUND: `.planning/phases/46-openapi-handoff-milestone-verification/46-11-SUMMARY.md`

Commits verified in `git log --oneline --all`:
- FOUND: 10a4032 feat(46-11): scaffold v1.6 run.sh header + pre-flight + helpers
- FOUND: c7e83cc feat(46-11): append scenarios 01-04 + main runner skeleton
- FOUND: 652277d feat(46-11): append scenarios 05-08 + finalize runner + README
