---
phase: 03-tests-dev-infrastructure-documentation
plan: 03
subsystem: infra
tags: [scripts, bash, pg_dump, placeholder, gitignore]

# Dependency graph
requires:
  - phase: 02-backend-skeleton-with-quality-tooling
    provides: apps/backend/ Python package layout (uv-managed, pyproject.toml, ruff/mypy strict)
provides:
  - apps/backend/scripts/seed_demo_data.py — Phase A placeholder seeder (INFRA-03)
  - apps/backend/scripts/backup_db.sh — working pg_dump against compose-network Postgres (INFRA-04)
  - apps/backend/.gitignore exclusion for backups/ output directory
affects: [phase-03-plan-05-compose, phase-B-plan-real-seeders, future-ops-plans]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase A placeholder script: pure stdlib + 'from __future__ import annotations' for forward-ref ergonomics"
    - "Dev-ops bash script: shebang + set -euo pipefail + UTC timestamp + portable stat fallback"
    - "docker compose exec -T pg_dump pattern (host doesn't need pg_dump installed)"

key-files:
  created:
    - apps/backend/scripts/seed_demo_data.py
    - apps/backend/scripts/backup_db.sh
  modified:
    - apps/backend/.gitignore

key-decisions:
  - "Implemented D-13 verbatim — no creative rewrites"
  - "Backup script targets compose-network Postgres (not host pg_dump) — works regardless of host install state"
  - "Backups/ excluded from git via apps/backend/.gitignore — never commit DB dumps"

patterns-established:
  - "Phase A placeholder script idiom: docstring naming the phase + main() -> int + raise SystemExit(main())"
  - "Bash dev-script idiom: env-bash shebang + set -euo pipefail + UTC ISO8601-like compact timestamp + BSD/GNU stat portability"

requirements-completed: [INFRA-03, INFRA-04]

# Metrics
duration: ~3min
completed: 2026-05-01
---

# Phase 03 Plan 03: Utility Scripts (seed + backup) Summary

**Two utility scripts for the Phase A backend: a pure-stdlib placeholder seeder that prints the exact INFRA-03 string, and a working pg_dump-via-compose backup script with a `.gitignore` carve-out for the output directory.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-01T09:21:00Z
- **Completed:** 2026-05-01T09:24:17Z
- **Tasks:** 2
- **Files modified:** 3 (2 created + 1 modified)

## Accomplishments

- `apps/backend/scripts/seed_demo_data.py` — pure-Python placeholder, imports nothing from `app.*`, prints exactly `Phase A: no data to seed`, exits 0; mypy strict + ruff clean
- `apps/backend/scripts/backup_db.sh` — bash script with `set -euo pipefail`, UTC-timestamped default output to `./backups/sportzal-<UTC>.sql.gz`, gzip-compressed pg_dump piped through `docker compose exec -T postgres`, portable size reporting via `stat -f%z` (BSD/macOS) || `stat -c%s` (GNU/Linux); committed executable (mode 100755 verified via `git ls-files --stage`)
- `apps/backend/.gitignore` — appended `backups/` exclusion so dump artifacts never enter the repo
- INFRA-03 + INFRA-04 closed; ROADMAP Phase 3 SC #3 first half (seed) verified locally

## Task Commits

Each task was committed atomically:

1. **Task 1: scripts/seed_demo_data.py — Phase A placeholder** — `3d0a7b2` (feat)
2. **Task 2: scripts/backup_db.sh + .gitignore backups/ exclusion** — `da481a3` (feat)

_Note: SUMMARY.md is committed separately by the orchestrator after this agent returns._

## Files Created/Modified

- `apps/backend/scripts/seed_demo_data.py` (created) — INFRA-03 placeholder seeder. 11 lines. Module docstring naming Phase A, `from __future__ import annotations`, `def main() -> int` returning 0 after printing exact INFRA-03 string, `if __name__ == "__main__": raise SystemExit(main())`. Verified: stdout matches exact string, exit 0, mypy strict clean, ruff clean, no `from app` / `import app` imports.
- `apps/backend/scripts/backup_db.sh` (created, mode 0755) — INFRA-04 backup script. 19 lines. `#!/usr/bin/env bash`, `set -euo pipefail`, `OUT="${1:-./backups/sportzal-$(date -u +%Y%m%dT%H%M%SZ).sql.gz}"`, `mkdir -p "$(dirname "$OUT")"`, `docker compose exec -T postgres pg_dump -U app -d sportzal | gzip > "$OUT"`, portable `stat -f%z 2>/dev/null || stat -c%s` size echo. Verified: shebang exact, all literal D-13 commands present, executable bit set in git index (`100755 ...`).
- `apps/backend/.gitignore` (modified) — appended blank line, `# Local DB dumps (created by scripts/backup_db.sh)` comment, and `backups/` exclusion. Verified: `grep -c '^backups/$'` returns 1.

## Decisions Made

None — D-13 (CONTEXT.md) was implemented verbatim for both scripts. The leading `from __future__ import annotations` line was already part of the plan-spec literal in 03-03-PLAN.md (forward-ref/mypy ergonomics rationale stated in plan), so no deviation from D-13 line-for-line.

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria pass on first verification:

- Task 1: stdout-exact match `Phase A: no data to seed`, exit 0, mypy strict clean (`Success: no issues found in 1 source file`), ruff clean (`All checks passed!`), no `app.*` imports.
- Task 2: shebang `#!/usr/bin/env bash` exact, `set -euo pipefail` present, all five required literal patterns present (`docker compose exec -T postgres pg_dump`, `date -u +%Y%m%dT%H%M%SZ`, `| gzip`, `stat -f%z`, `stat -c%s`), file executable in git index (`100755`), `.gitignore` carries `^backups/$`.

shellcheck is not installed locally — non-blocking per Task 2 Step 4; static checks above already enforce shape.

## Issues Encountered

None. Both tasks executed first-try.

Two minor shell-state observations during verification (informational only, no impact on output):
1. The Bash tool resets cwd between calls, so `cd apps/backend && uv run ...` works in one call but a follow-up `cd apps/backend && ...` fails because the previous cwd persisted into the same subshell on the second part of a chained command. Switched to absolute paths and worktree-rooted commands to verify.
2. `uv` emits a deprecation warning about `[tool.uv] dev-dependencies` → `[dependency-groups.dev]`. Phase 02 D-15 (LOCKED) explicitly defers this migration; warning is informational. Not relevant to this plan's surfaces.

## User Setup Required

None — no external service configuration required. End-to-end backup smoke is deferred to Plan 03-05 (compose stack required for `docker compose exec -T postgres pg_dump` to actually execute).

## Threat Surface

The plan's `<threat_model>` covers all four threats (T-03-11..14). No new threat surface was introduced beyond those:

- **T-03-11 mitigated:** `apps/backend/.gitignore` carries `backups/` (verified `grep -c '^backups/$'` returns 1); script's default output is inside `./backups/`.
- **T-03-12 accepted:** `${1:-...}` flows directly into `mkdir -p "$(dirname ...)"` and the redirect target. Quoting `"$OUT"` prevents IFS splitting; full sanitization deferred to Phase X+ per pet-project scope.
- **T-03-13 accepted:** No retention/disk-bound logic — local dev only.
- **T-03-14 mitigated:** Docstring labels Phase A explicitly; `print` output literal `Phase A: no data to seed` cannot be confused for a real seeder.

No threat flags raised — surfaces match the plan-defined boundaries.

## Next Phase Readiness

- INFRA-03 and INFRA-04 closed; downstream Plan 03-05 (compose) will retire ROADMAP Phase 3 SC #3 second half via `bash apps/backend/scripts/backup_db.sh /tmp/sportzal-test.sql.gz` against running `postgres:16` service.
- Phase B+ will replace `seed_demo_data.py` with a real seeder once business modules land — placeholder-script docstring already names this transition.

## Self-Check: PASSED

Verified files exist:
- FOUND: `apps/backend/scripts/seed_demo_data.py`
- FOUND: `apps/backend/scripts/backup_db.sh` (executable, mode 100755)
- FOUND: `apps/backend/.gitignore` (modified — `backups/` line present)

Verified commits exist on `worktree-agent-a33d221f871036ca7`:
- FOUND: `3d0a7b2` — feat(03-03): add Phase A placeholder seed script
- FOUND: `da481a3` — feat(03-03): add backup_db.sh + .gitignore backups/ exclusion

---
*Phase: 03-tests-dev-infrastructure-documentation*
*Completed: 2026-05-01*
