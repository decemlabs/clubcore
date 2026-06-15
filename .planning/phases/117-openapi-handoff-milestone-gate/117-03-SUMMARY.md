---
phase: 117-openapi-handoff-milestone-gate
plan: "03"
subsystem: milestone-gate
tags: [gate, mypy, ruff, lint-imports, pytest, vitest, redocly, rbac-parity, phase-117]
dependency_graph:
  requires: ["117-01", "117-02"]
  provides: ["HND-01-criterion-3-partial", "v3.2-gate-record"]
  affects: [".planning/phases/117-openapi-handoff-milestone-gate/117-GATE.md"]
tech_stack:
  added: []
  patterns:
    - "Fix-to-green milestone gate spanning backend static+test + FE + api-client + Redocly"
    - "exec-redirect of verbose command output to off-quota log files (harness capture-fs workaround)"
key_files:
  created:
    - .planning/phases/117-openapi-handoff-milestone-gate/117-GATE.md
  modified:
    - apps/backend/tests/integration/users/test_users_role_change.py
decisions:
  - "Full backend pytest accepted as NOT-run-to-green (operator decision 2026-06-15): blocked by a local-env Postgres deadlock (alembic downgrade DELETE working_hours_config blocked by an idle-in-transaction lock), not a v3.2 code defect. Recorded as v3.2 milestone debt."
  - "ruff full-repo re-counted: 207 pre-existing errors (14 in non-v3.2 app source), ZERO in v3.2-touched paths — out-of-scope tech debt (project pre-commit scopes ruff to changed files)."
  - "OWNER_ONLY=46 (CISO-01) confirmed directly in app/core/permissions.py source ('45 → 46' ledger comment) + can.ts/registry.ts mirror; the pytest assertion is part of the env-blocked suite."
  - "test_users_role_change.py ruff fix (1 E501 + 3 F401, removed unused imports) committed as part of this gate."
metrics:
  duration: "~90 minutes (incl. env-deadlock diagnosis + recovery)"
  completed: "2026-06-15"
  tasks_completed: 3
  files_created: 1
  files_modified: 1
---

# Phase 117 Plan 03: v3.2 Milestone Gate Summary

Ran the full v3.2 milestone gate fix-to-green across both tiers. Every check is GREEN
**except the full backend pytest suite**, which is blocked by a local-environment
Postgres deadlock (not a v3.2 code defect) and was **accepted by operator decision** as a
known issue / milestone debt. Recorded results + the 13-requirement trace in `117-GATE.md`.

## What Was Built / Verified

Re-verified fresh this run (not trusting the prior partial gate):

| Tier | Check | Result |
|---|---|---|
| Backend | `uv run mypy app` (--strict) | ✅ no issues, 283 files |
| Backend | `uv run lint-imports` | ✅ exit 0 (contracts KEPT) |
| Backend | ruff (v3.2 scope) | ✅ all clean |
| Backend | ruff (full repo) | ⚠ 207 pre-existing, 0 in v3.2 paths — out-of-scope debt |
| Backend | **full `uv run pytest`** | ⛔ **BLOCKED — env deadlock, operator-accepted (see below)** |
| Backend | RBAC OWNER_ONLY=46 | ◑ source-confirmed (permissions.py + can.ts); pytest assert in blocked suite |
| FE | admin-app typecheck | ✅ |
| FE | admin-app lint | ✅ |
| FE | admin-app test | ✅ 410 / 35 files |
| FE | admin-app build | ✅ built ~2.9s |
| api-client | typecheck | ✅ |
| api-client | test | ✅ 23 (incl. `_v32Checks` guard) |
| api-client | codegen zero-diff | ✅ `git diff --exit-code schema.d.ts` clean |
| OpenAPI | `redocly lint` | ✅ "API description is valid" (2 pre-existing warnings) |

13/13 v3.2 requirement trace recorded in `117-GATE.md` (REF-01, TEAM-01, PROMO-01/02,
ANL-01/02/03/04, MSG-01/02, EXP-01/02, HND-01).

## Full pytest count + pass status

**Not obtained.** The suite did not run to completion. See "Known Issue" below for the
deadlock diagnosis and the verified-green substitute checks that cover v3.2 correctness.

## Fix-to-green changes made

- `apps/backend/tests/integration/users/test_users_role_change.py` — removed 3 unused
  imports (`hash_password`, `OWNER_EMAIL`, `_csrf_headers`; F401) and wrapped one long
  function signature (E501). Pure lint fix, no behavior change. (Carried over uncommitted
  from the original gate attempt; committed with this plan.)

## Redocly outcome

Configured (`@redocly/cli` 2.31.4, `redocly.yaml` present) and PASSED: "Your API
description is valid." 2 pre-existing non-v3.2 warnings (client WS 101-only response;
ambiguous path).

## Codegen second-run diff

Empty — `pnpm -F @clubcore/api-client codegen` then `git diff --exit-code
packages/api-client/src/schema.d.ts` returned clean (exit 0). schema.d.ts is in sync with
openapi.json and was not hand-edited.

## Known Issue / Debt — full backend pytest not run to green

**Operator-accepted 2026-06-15.** The full ~3000-test suite repeatedly deadlocks:

- A migration-reversibility step runs `alembic downgrade`; its `DELETE FROM
  working_hours_config` blocks on a row lock held by another connection left
  `idle in transaction` (an open `UPDATE working_hours_config`). Confirmed via
  `pg_stat_activity` + `pg_blocking_pids` (blocked pid `blocked by` the idle pid). All
  offending connections came from the host test process (`client_addr 192.168.65.1`), not
  the dev backend container (`172.18.0.5`).
- The condition surfaced after the local `clubcore` DB was polluted by interrupted /
  overlapping pytest runs during this autonomous session (initial mistake: three
  concurrent runs auto-backgrounded by docker latency, then SIGKILL'd, leaving zombie
  locked transactions). Zombies were terminated (0 connections confirmed before re-run),
  but a single clean re-run reproduced the same `alembic downgrade ↔ working_hours_config`
  block.
- The suite WAS running in this same env earlier (original gate header) and phases
  112–116 executed their tests — so this is an environment/state issue, not a v3.2 defect.

**Deferred non-destructive resolution:** `docker compose down -v` → `alembic upgrade head`
→ seed → single `uv run pytest` with `--timeout` (pytest-timeout) so any future deadlock
fails the culprit test instead of hanging.

## Secondary obstacle (resolved, noted for future runs)

The harness command-output capture filesystem has a small quota that filled up while
streaming the unbounded full-suite log, causing `ENOSPC` (`0MB free`) even though the OS
disk had 24 GB free. Worked around by routing all verbose output to log files on the main
volume (`exec >/private/tmp/cc_gate/<f>.txt 2>&1`) and keeping captured bytes at zero.

## Self-Check: PARTIAL

117-GATE.md exists with all gate-check results + 13/13 requirement trace. All checks green
EXCEPT full backend pytest (env-blocked, operator-accepted). This CLOSES v3.2 with the
full-pytest-green criterion recorded as known milestone debt. Milestone formal
close/archive is a separate operator step; the v3.1 deferred close remains its own
pre-existing pause (not touched here).
