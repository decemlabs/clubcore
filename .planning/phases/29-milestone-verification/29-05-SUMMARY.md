---
phase: 29-milestone-verification
plan: 05
status: complete
completed: 2026-05-14T09:42:00Z
requirements-completed: [DEBT-04]
must_haves_satisfied:
  - MH-29-04 (test suites + CI gates evidence captured in v1.3-VERIFICATION-LOG.md)
---

# Plan 29-05 — Test-suite + CI-gate evidence capture — Summary

## Outcome

| Suite/Gate | Threshold | Result |
|-----------|-----------|--------|
| Backend `pytest -q` | ≥ 600 | **729 passed / 0 failed** |
| admin-web `pnpm test` | ≥ 190 | **233 passed / 0 failed** (41 test files) |
| ruff | clean | ✓ pass (1 import-order auto-fix needed, committed `bb1190c`) |
| mypy --strict | clean | ✓ pass (73 files) |
| lint-imports | 0 broken | ✓ 3 kept, 0 broken |
| eslint | 0 errors | ✓ pass (2 non-blocking warnings) |
| openapi drift gate | byte-stable | ✓ pass |
| api-client schema drift gate | byte-stable | ✓ pass |

## Pivots that came up during the run

- **`SECRET_KEY` length:** dev `.env` has a 29-byte placeholder, and pyjwt raises `InsecureKeyLengthWarning` for keys < 32 bytes. Because `pyproject.toml` sets `filterwarnings = ["error", ...]`, this warning becomes a test error and 38 tests failed + 239 erorred on the first run. Re-ran with `SECRET_KEY=<48-byte secret>` → 729/729 pass. **Not a regression** — `.env` is a dev placeholder, prod uses a real key.
- **admin-web package name:** plan 29-05 originally referenced `@sportzal/admin-web` as the pnpm workspace name; actual name is `sportzal-adminka`. Used `cd apps/admin-web && pnpm test` instead.
- **CI workflow URL:** local repo has no git remote, so no GitHub Actions run URL available. Substitute: ran all 6 gates locally with identical commands to `.github/workflows/ci.yml`. Frontmatter records `workflow_url: "n/a — local repo has no git remote; CI gates run locally instead"`.
- **Ruff auto-fix:** import order in `apps/backend/scripts/run_expiring_cron_once.py` flagged (legacy of the REG-29-04 fix added imports out of order). Auto-fixed and committed (`bb1190c`).

## What's next

Plan 29-06 — finalize verification log, set `status: passed`, add `.gitignore` entry for evidence dir, update STATE.md, run `docker compose down -v` tear-down.
