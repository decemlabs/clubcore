---
phase: 105-admin-web-retirement
verified: 2026-06-13T23:55:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 105: admin-web Retirement + RBAC Re-home Verification Report

**Phase Goal:** apps/admin-web is deleted and the three-way RBAC-parity reference is re-homed so the chosen guard stays green — CI, workspace, and drift-gate stay valid after removal.
**Verified:** 2026-06-13T23:55:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                  | Status     | Evidence                                                                                                             |
|----|--------------------------------------------------------------------------------------------------------|------------|----------------------------------------------------------------------------------------------------------------------|
| 1  | git ls-files apps/admin-web returns 0 entries (directory fully removed from the repo)                  | VERIFIED   | `git ls-files apps/admin-web \| wc -l` == 0; no on-disk dir (ls returns MISSING_DIR)                                |
| 2  | pnpm-lock.yaml has no apps/admin-web: importer entry; pnpm install --frozen-lockfile is clean          | VERIFIED   | `grep -c 'apps/admin-web:' pnpm-lock.yaml` == 0; frozen-lockfile exits clean (5 workspace projects, no drift)       |
| 3  | The CISO-01 byte-parity guard (test_byte_parity.py) reads apps/admin-app/src/shared/session/can.ts    | VERIFIED   | `_CAN_TS_PATH` at line 29-37 resolves to admin-app path; no `admin-web` string remains in the file                  |
| 4  | The byte-parity guard is LIVE not vacuous: would FAIL if admin-app can.ts were missing                 | VERIFIED   | LIVE-guard proof: `_CAN_TS_PATH.exists()` == True, 'admin-app' in path, 'admin-web' not in path; `.exists()` assert preserved at line 121 |
| 5  | test_rbac_parity.py + reception-403 enumeration stay green (already read admin-app/backend authority)  | VERIFIED   | `pytest tests/integration/test_rbac_parity.py -q` → 4/4 passed in 0.02s; `pytest tests/integration/client_auth/test_byte_parity.py -q` → 3/3 passed in 0.70s |
| 6  | Backend mypy --strict, ruff, and lint-imports stay green (no import-linter zone references admin-web)  | VERIFIED   | mypy: 273 files, no issues; ruff on phase-modified files: all checks passed; lint-imports: 3 contracts KEPT, 0 BROKEN |
| 7  | Backend openapi.json is byte-unchanged (no contract drift)                                             | VERIFIED   | `git diff --exit-code apps/backend/openapi.json` → exit 0                                                            |
| 8  | Functional source-of-truth doc pointers say admin-app, not admin-web                                   | VERIFIED   | permissions.py lines 4-5,63,156: admin-app; loyalty/permissions.py lines 6,36: admin-app; config.py lines 76,130,144: admin-app; api-client/README.md: admin-app; CLAUDE.md line 17: admin-web retired in Phase 105 |
| 9  | admin-app typecheck/lint/test and client-pwa typecheck still pass (no cross-app import broke)           | VERIFIED   | admin-app: typecheck clean, lint clean, 337 tests 26 files all passed; client-pwa: typecheck clean (no errors)       |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact                                                                  | Expected                                                     | Status     | Details                                                                                                                                    |
|---------------------------------------------------------------------------|--------------------------------------------------------------|------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| `apps/backend/tests/integration/client_auth/test_byte_parity.py`         | Repointed CISO-01 guard reading admin-app can.ts             | VERIFIED   | `_CAN_TS_PATH` resolves to `apps/admin-app/src/shared/session/can.ts`; function renamed `test_admin_app_can_ts_unchanged`; all 3 assertions preserved |
| `pnpm-lock.yaml`                                                          | Workspace lockfile with admin-web importer removed            | VERIFIED   | No `apps/admin-web:` entry; `pnpm install --frozen-lockfile` clean; 5 remaining workspace projects intact                                  |

### Key Link Verification

| From                                      | To                                            | Via                                   | Status   | Details                                                                                 |
|-------------------------------------------|-----------------------------------------------|---------------------------------------|----------|-----------------------------------------------------------------------------------------|
| `test_byte_parity.py` `_CAN_TS_PATH`      | `apps/admin-app/src/shared/session/can.ts`    | `Path(__file__).resolve()` 6x parent  | WIRED    | grep confirms `admin-app` in path at lines 29-36; no `admin-web` string remains; file exists on disk |
| `pnpm-workspace.yaml` `apps/*` glob       | `apps/admin-app`, `packages/api-client`, `apps/client-pwa` | deletion auto-removes admin-web | WIRED  | `pnpm install --frozen-lockfile` confirms 5 workspace packages (no admin-web); workspace.yaml untouched |

### Data-Flow Trace (Level 4)

Not applicable — this is an infrastructure/deletion phase with no dynamic-data rendering artifacts.

### Behavioral Spot-Checks

| Behavior                                                        | Command                                                                                       | Result                                              | Status |
|-----------------------------------------------------------------|-----------------------------------------------------------------------------------------------|-----------------------------------------------------|--------|
| admin-web fully removed from git index                          | `git ls-files apps/admin-web \| wc -l`                                                        | 0                                                   | PASS   |
| pnpm frozen-lockfile drift gate                                 | `pnpm install --frozen-lockfile`                                                               | Done in 696ms, all 5 projects up to date            | PASS   |
| LIVE-guard proof: _CAN_TS_PATH resolves to real admin-app file  | `uv run python -c "... assert p.exists() and 'admin-app' in str(p) ..."`                       | LIVE: `.../apps/admin-app/src/shared/session/can.ts` | PASS  |
| Backend parity tests                                            | `pytest tests/integration/client_auth/test_byte_parity.py tests/integration/test_rbac_parity.py -q` | 3 passed + 4 passed                            | PASS   |
| mypy --strict on backend app                                    | `uv run mypy --strict app`                                                                     | 273 files, no issues                                | PASS   |
| lint-imports (3 contracts)                                      | `uv run lint-imports`                                                                          | 3 contracts KEPT, 0 BROKEN                          | PASS   |
| openapi.json drift gate                                         | `git diff --exit-code apps/backend/openapi.json`                                               | exit 0 (byte-unchanged)                             | PASS   |
| schema.d.ts codegen drift gate                                  | `pnpm -F @clubcore/api-client codegen` + `git diff --exit-code packages/api-client/src/schema.d.ts` | exit 0 (byte-unchanged)                       | PASS   |
| admin-app typecheck + lint + test                               | `pnpm -F @clubcore/admin-app typecheck && lint && test`                                         | clean / clean / 337 tests passed                    | PASS   |
| client-pwa typecheck                                            | `pnpm -F @clubcore/client-pwa typecheck`                                                        | clean, no errors                                    | PASS   |

### Probe Execution

Not applicable — no `probe-*.sh` scripts declared or conventional for this phase type.

### Requirements Coverage

| Requirement | Source Plan | Description                                                                                               | Status    | Evidence                                                                                                              |
|-------------|-------------|-----------------------------------------------------------------------------------------------------------|-----------|-----------------------------------------------------------------------------------------------------------------------|
| ADMW-01     | 105-01-PLAN | `apps/admin-web` removed; workspace entry, CI job, dangling references cleaned                             | SATISFIED | `git ls-files apps/admin-web` == 0; no on-disk dir; no `apps/admin-web:` in pnpm-lock.yaml; CI yml has 0 admin-web refs; no cross-app imports broken |
| ADMW-02     | 105-01-PLAN | Three-way RBAC-parity guard re-homed to admin-app; CISO-01 byte-guard green                               | SATISFIED | `test_byte_parity.py` reads admin-app can.ts; all 3 assertions preserved (`.exists()`, `Role.CLIENT`, `\| 'client'`); 3/3 passed; `test_rbac_parity.py` 4/4 passed |
| ADMW-03     | 105-01-PLAN | OpenAPI staff drift-gate + `@clubcore/api-client` codegen pipeline pass after admin-web removal            | SATISFIED | `openapi.json` byte-unchanged; codegen runs clean, `schema.d.ts` byte-unchanged after re-run; no consumer left dangling |

### Anti-Patterns Found

| File                                                     | Line | Pattern                                      | Severity | Impact                                                        |
|----------------------------------------------------------|------|----------------------------------------------|----------|---------------------------------------------------------------|
| `apps/backend/app/core/config.py`                        | 138  | `admin-web (port 5173)` comment mention       | INFO     | Informational comment describing why PWA uses port 5174; non-blocking per plan (Phase 106 milestone audit owns) |
| `apps/backend/app/integrations/yookassa/settings.py`     | 51   | `admin-web` comment reference                 | INFO     | Historical comment-only; non-blocking per plan                |
| `apps/backend/app/modules/pt_packages/schemas.py`        | 213  | `admin-web badge` comment                     | INFO     | Historical comment-only; non-blocking per plan                |
| `apps/backend/app/modules/messaging/service.py`          | 16,232,236 | `admin-web frozen → v2.6` comment       | INFO     | Historical comment-only; non-blocking per plan                |
| `apps/backend/tests/unit/test_permissions.py`            | 17,56 | `admin-web can.ts / registry.ts` comment     | INFO     | Historical comment-only; non-blocking per plan                |

All remaining `admin-web` references are comment-only, informational, and explicitly designated non-blocking in the PLAN. The plan declares these as Phase 106 milestone audit scope. No functional code paths or test assertions reference admin-web.

**ruff check full backend:** 182 errors found, all in `alembic/` migration files (line-length in migration docstring, unsorted import block) — pre-existing, unrelated to phase-modified files. Phase-modified files (`permissions.py`, `loyalty/permissions.py`, `config.py`, `test_byte_parity.py`) pass `ruff check` cleanly with no errors.

### Human Verification Required

None — this is a pure infrastructure/deletion phase. All success criteria are programmatically verifiable and have been verified.

### Gaps Summary

No gaps. All 9 must-have truths verified. All 3 requirements (ADMW-01, ADMW-02, ADMW-03) satisfied. All targeted gates green.

**Note on SUMMARY-reported issues vs. verification results:**
- SUMMARY reported `test_byte_parity.py` ERROR at setup (SeaweedFS not running during execution). Under verification with full docker stack (postgres + redis + s3), all 3 tests pass cleanly. This was a runtime environment issue during execution, not a code defect.
- SUMMARY reported `client-pwa typecheck` pre-existing failure (`Unused '@ts-expect-error'`). Under verification, `pnpm -F @clubcore/client-pwa typecheck` exits cleanly with no errors. Either the issue was resolved by the lockfile regeneration or it was a transient state during execution.

---

_Verified: 2026-06-13T23:55:00Z_
_Verifier: Claude (gsd-verifier)_
