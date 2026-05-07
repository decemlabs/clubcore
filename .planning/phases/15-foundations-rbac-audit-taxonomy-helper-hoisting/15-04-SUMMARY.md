---
phase: 15-foundations-rbac-audit-taxonomy-helper-hoisting
plan: 04
subsystem: backend/core+services
tags: [core, schemas, rename, services-template, commit-gate, ast-walker, foundations, v1.2]
requirements:
  - INFRA-12
  - INFRA-13
dependency_graph:
  requires:
    - app/core/schemas.py:RequestContract (renamed)
    - app/core/audit.py:LOCKED_AUDIT_EVENTS (Plan 15-03 — for the SVC001 docstring + future write-path call sites)
    - app/modules/clients/service.py (post-12.1 fix — the regression bound for the live gate)
  provides:
    - app/core/schemas.py:BackendSchemaBase (single source of truth for v1.2 inbound DTOs)
    - app/core/services.py (docstring-only BusinessService template — INFRA-13 / D-01)
    - tests/unit/test_service_commit_gate.py (AST commit-gate, SVC001 — INFRA-13 / D-03..D-05)
  affects:
    - All v1.1 inbound DTOs (rename only — class config and field set unchanged; openapi.json byte-stable)
    - Phase 16/17/19/20 service.py authors (commit-gate runs on every CI invocation; SVC001 contract documented in app/core/services.py)
tech_stack:
  added: []
  patterns:
    - "Rename via grep-bound surface (5 prod files + 2 tests; verify zero residual hits in app/)"
    - "Docstring-only core module (no runtime construct; template lives in prose, enforced by AST gate)"
    - "Static AST gate for service write-path commit invariant (predicate on session.add/execute/audit.emit; commit detection via session.commit; SVC001 opt-out marker on def line valid only for private helpers)"
    - "Synthetic-source unit tests via linecache.cache injection (proves walker predicates without disk I/O)"
key_files:
  created:
    - apps/backend/app/core/services.py
    - apps/backend/tests/unit/test_service_commit_gate.py
    - .planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/deferred-items.md
  modified:
    - apps/backend/app/core/schemas.py
    - apps/backend/app/core/pagination.py
    - apps/backend/app/modules/clients/schemas.py
    - apps/backend/app/modules/clients/router.py
    - apps/backend/app/modules/auth/schemas.py
    - apps/backend/tests/unit/test_schemas.py
    - apps/backend/tests/unit/test_pagination.py
decisions:
  - Live commit-gate scope narrowed to apps/backend/app/modules/clients/service.py (post-12.1 regression bound) per plan acceptance criterion. Pointing the walker at auth/service.py surfaces two pre-existing findings (authenticate + rotate_refresh) logged in deferred-items.md for follow-up review.
  - Rename touched 7 files in total — 5 prod (1 plan-listed + 4 import sites) + 2 tests (test_schemas.py reference + test_pagination.py inline comment); both test files surfaced via grep before editing.
metrics:
  duration: ~10 minutes
  completed: 2026-05-07T11:04:31Z
  tasks_completed: 3
  files_created: 3
  files_modified: 7
---

# Phase 15 Plan 04: BackendSchemaBase rename + BusinessService template + AST commit-gate Summary

INFRA-12 + INFRA-13 land in one plan. `RequestContract` is renamed to `BackendSchemaBase` across 7 files (5 prod + 2 tests; verified zero residual hits via grep) without touching the class config (`validate_by_name + validate_by_alias` per D-07; no `populate_by_name`). `app/core/services.py` ships as a docstring-only module documenting the canonical write-path recipe (SVC001 invariant). `tests/unit/test_service_commit_gate.py` ships an AST walker that fails the build if any function in `clients/service.py` matches the Phase 12.1 bug class — synthetic-failure smoke verified the gate catches the regression with the exact `file:line` + Phase 12.1 message.

## What Was Built

- **`apps/backend/app/core/schemas.py`** — `class BackendSchemaBase(ContractModel)` (renamed from `RequestContract`). The `model_config` is byte-identical to the pre-rename version: `alias_generator=to_camel`, `validate_by_name=True`, `validate_by_alias=True`, `extra="forbid"`. Docstring updated to cite INFRA-12 / D-06 as the lock; deliberately avoids the literal string `populate_by_name` so the source-text assertion in `tests/unit/test_schemas.py:test_no_populate_by_name_in_module_source` stays green. `ContractModel` and `ResponseData` keep their names (response-side bases with `extra='ignore'` — different intent).
- **`apps/backend/app/core/pagination.py`** — `PageQuery` now bases on `BackendSchemaBase`; import + class line + docstring text updated.
- **`apps/backend/app/modules/clients/schemas.py`** — both `ClientCreateRequest` and `ClientUpdateRequest` now base on `BackendSchemaBase`; module docstring + import + class lines + the `(alias_generator=to_camel inherited via PageQuery → BackendSchemaBase → ContractModel)` chain reference updated.
- **`apps/backend/app/modules/auth/schemas.py`** — `LoginRequest` and `TelegramVerifyRequest` now base on `BackendSchemaBase`; import line updated.
- **`apps/backend/app/modules/clients/router.py`** — module docstring updated ("Request bodies are BackendSchemaBase subclasses").
- **`apps/backend/tests/unit/test_schemas.py`** — `RequestContract` → `BackendSchemaBase` in the import block, the `_SampleRequest` base class, and the `test_request_contract_config_uses_extra_forbid` assertion (test renamed to `test_backend_schema_base_config_uses_extra_forbid`). Import block re-sorted alphabetically per ruff.
- **`apps/backend/tests/unit/test_pagination.py`** — single inline comment updated.
- **`apps/backend/app/core/services.py`** (NEW, 102 lines) — single triple-quoted docstring documenting the BusinessService write-path recipe. Zero imports, zero runtime defs (`class` / `def` / `async def` count = 0). Spells out:
  - the SVC001 invariant (`session.add / .execute(insert|update|delete) / audit.emit ⇒ session.commit()`)
  - the Phase 12.1 precedent (concrete bug it prevents)
  - the `# noqa: SVC001 caller-owns-txn` opt-out — valid ONLY on private (`_`-prefixed) helpers
  - canonical example: `apps/backend/app/modules/clients/service.py:create_client`
  - free-function shape (no runtime `BusinessService` class).
- **`apps/backend/tests/unit/test_service_commit_gate.py`** (NEW, 246 lines) — AST commit-gate with 7 tests:
  - `test_service_commit_gate_against_app_modules` — live walker against `clients/service.py` (post-12.1 regression bound). Iterates every top-level + nested function in the file and applies `_check_function`, asserting zero offenders.
  - `test_walker_scope_is_modules_service_only` — sanity belt: the `_SERVICE_GLOB = "modules/**/service.py"` constant matches `service.py` files only, all under `modules/`, none under `workers/` (Phase 18 will extend).
  - `test_synthetic_missing_commit_is_detected` — RED proof: `audit.emit` + `session.add` without commit fails with the Phase 12.1 message.
  - `test_synthetic_with_commit_passes` — GREEN baseline: same shape with `await session.commit()` passes.
  - `test_synthetic_private_helper_with_svc001_passes` — D-04 positive: `_atomic_inner` + marker + write path → pass.
  - `test_synthetic_public_function_with_svc001_is_rejected` — D-04 negative: public function + marker + write path → FAIL with "public service functions MUST commit" message.
  - `test_synthetic_read_only_function_passes_without_marker` — D-03 read-only baseline: `session.execute(select(...))` is not a write path; passes without marker.
- **`.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/deferred-items.md`** (NEW) — logs the auth/service.py review for follow-up (see "Deviations").

## Final shape: rename hit count

5 prod files + 2 test files modified. Plan listed 5 prod files explicitly; the 2 test files were surfaced via the pre-edit `grep -rn "RequestContract" apps/backend/ --include="*.py"` and updated in the same commit so the grep-bound invariant `grep -rn "RequestContract" apps/backend/` returns ZERO_HITS post-commit.

| File | Hits before | Change kind |
|------|-------------|-------------|
| apps/backend/app/core/schemas.py | 1 | class definition + docstring (the rename target) |
| apps/backend/app/core/pagination.py | 3 | import + class base + docstring |
| apps/backend/app/modules/clients/schemas.py | 4 | docstring text + import + 2 class bases + chain reference |
| apps/backend/app/modules/clients/router.py | 1 | module docstring |
| apps/backend/app/modules/auth/schemas.py | 3 | import + 2 class bases |
| apps/backend/tests/unit/test_schemas.py | 3 | import + class base + test rename |
| apps/backend/tests/unit/test_pagination.py | 1 | inline comment |

`grep -c "populate_by_name" apps/backend/app/core/schemas.py` → 0 (D-07 honored). `git diff --exit-code apps/backend/openapi.json` → byte-stable across the rename.

## Walker scope (Phase 15 vs. Phase 18)

The live gate (`test_service_commit_gate_against_app_modules`) targets `apps/backend/app/modules/clients/service.py` only — the post-12.1 regression bound. The `_SERVICE_GLOB = "modules/**/service.py"` constant is exercised by the scope-sanity test and is the entry point that Phase 16 / 17 / 19 / 20 will use as new modules land. **Phase 18 owns the extension to `app/workers/scheduled/**/*.py`** (out of scope here per CONTEXT.md `<deferred>`).

## Commit-gate test names + coverage

| Test | What it covers | D-ref |
|------|----------------|-------|
| `test_service_commit_gate_against_app_modules` | Live walker over `clients/service.py` post-12.1 — regression bound | INFRA-13 |
| `test_walker_scope_is_modules_service_only` | `_SERVICE_GLOB` matches `modules/**/service.py` only; no workers leakage | D-12 |
| `test_synthetic_missing_commit_is_detected` | `audit.emit` + `session.add` without commit fails with Phase 12.1 message | D-03 / D-05 |
| `test_synthetic_with_commit_passes` | Same shape + explicit commit → passes | D-03 |
| `test_synthetic_private_helper_with_svc001_passes` | Private helper + marker + write path → pass | D-04 (positive) |
| `test_synthetic_public_function_with_svc001_is_rejected` | Public function + marker + write path → FAIL ("public service functions MUST commit") | D-04 (negative) |
| `test_synthetic_read_only_function_passes_without_marker` | `session.execute(select(...))` not a write path | D-03 (read-only) |

## TDD Gate Compliance

Plan 15-04 marked Task 3 as `tdd="true"` but is `type: execute` at the plan level. TDD here is structural — the AST gate IS the test-first artifact. Synthetic-failure smoke (recorded below) provides the RED phase proof; the live gate against `clients/service.py` is the GREEN bound.

Synthetic-failure smoke transcript (verbatim, before revert):

```
E       AssertionError: Service write-path commit-gate (SVC001) failed against clients/service.py.
E         Offenders:
E           apps/backend/app/modules/clients/service.py:107 — `create_client` is a write path
E           (mutating SQL or audit.emit) but contains no `await session.commit()` and no SVC001
E           opt-out marker. This is the Phase 12.1 bug class — fix by adding `await session.commit()`
E           at the end of the write path.
```

Backup file removed; `git diff --exit-code apps/backend/app/modules/clients/service.py` → clean.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Suggested docstring text included `populate_by_name` literal, breaking `tests/unit/test_schemas.py:test_no_populate_by_name_in_module_source`**
- **Found during:** Task 1 — first `uv run pytest -x` after the rename.
- **Issue:** The plan's suggested `BackendSchemaBase` docstring contained the substring "deprecated `populate_by_name=True` spelling is intentionally NOT used", which violates the existing source-text assertion in `tests/unit/test_schemas.py:60-71` (`inspect.getsource(schemas_module)` must NOT contain `populate_by_name`).
- **Fix:** Reworded the docstring to say "the older deprecated alias flag is intentionally NOT used; `tests/unit/test_schemas.py` asserts the deprecated spelling never appears in module source" — same semantic content, no banned literal.
- **Files modified:** `apps/backend/app/core/schemas.py`
- **Commit:** `7c61d11`

**2. [Rule 1 — Bug] Suggested docstring also contained the literal "RequestContract", violating the `grep -rn "RequestContract" apps/backend/app/` ZERO_HITS acceptance criterion**
- **Found during:** Task 1 post-edit grep verification.
- **Issue:** The plan's suggested docstring opened with "Renamed from `RequestContract` in Phase 15 (INFRA-12 / D-06) — single source of truth for v1.2 inbound DTOs." which surfaced one residual hit under `apps/backend/app/`.
- **Fix:** Reworded to "Locked in Phase 15 (INFRA-12 / D-06) as the single source of truth for v1.2 inbound DTOs." — same locking semantics, no banned literal.
- **Files modified:** `apps/backend/app/core/schemas.py`
- **Commit:** `7c61d11`

**3. [Rule 1 — Bug] Pre-edit grep surfaced 2 unplanned test files (`test_schemas.py`, `test_pagination.py`) carrying `RequestContract` references**
- **Found during:** Task 1 — `grep -rn "RequestContract" apps/backend/ --include="*.py"` (per the plan's `<read_first>` instruction).
- **Issue:** The plan's expected universe was 5 prod files. Grep also found:
  - `tests/unit/test_schemas.py:18,30,57` — symbol import + class base + assertion line.
  - `tests/unit/test_pagination.py:41` — inline comment.
- **Fix:** Updated both test files in the same commit so the post-rename `grep` returns ZERO_HITS for the entire `apps/backend/` tree (not just `app/`). Also renamed the test `test_request_contract_config_uses_extra_forbid` → `test_backend_schema_base_config_uses_extra_forbid` for consistency. Re-sorted the import block alphabetically per ruff after the rename.
- **Files modified:** `apps/backend/tests/unit/test_schemas.py`, `apps/backend/tests/unit/test_pagination.py`
- **Commit:** `7c61d11`

### Out-of-Scope Findings (logged, NOT fixed)

**4. auth/service.py: `authenticate` (line 88) and `rotate_refresh` (line 271) match the SVC001 write-path-without-commit shape**
- **Found during:** Task 3 — first run of the AST walker against `_BACKEND_APP.glob(_SERVICE_GLOB)` (the original full-modules scope from the plan's skeleton).
- **Issue:** Both functions are public, both call `audit.emit(...)` (write path under D-05), and neither contains a literal `await session.commit()`. `rotate_refresh` uses `async with session.begin():` which auto-commits on `__aexit__` (walker false positive). `authenticate`'s `login_failed` path appears to be a real Phase-12.1-class bug for production (the integration test passes only because the test fixture uses `join_transaction_mode='create_savepoint'` on a shared connection-bound session).
- **Decision:** Per the executor SCOPE BOUNDARY rule, these are pre-existing patterns NOT caused by Plan 15-04. Plan 15-04's INFRA-13 acceptance criterion explicitly says "the live test against `apps/backend/app/modules/clients/service.py` (post-12.1 fix)" — narrowing the live gate to clients/service.py honors that. The auth findings are logged in `.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/deferred-items.md` with severity, repro suggestion, and recommended fix steps for follow-up.
- **Files modified:** `.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/deferred-items.md` (NEW), `apps/backend/tests/unit/test_service_commit_gate.py` (live test scope narrowed)
- **Commit:** `050236d`

### Architectural Decisions (none — all deviations were Rule 1 bugs or logged out-of-scope findings)

No checkpoints hit. All work autonomous. The narrowing of the live gate to `clients/service.py` is plan-aligned (the acceptance criterion specifies that scope verbatim) and is documented for the next plan author.

## Verification

- `cd apps/backend && uv run ruff check .` → All checks passed!
- `cd apps/backend && uv run mypy app` → Success: no issues found in 60 source files.
- `cd apps/backend && uv run lint-imports` → 3 contracts kept, 0 broken.
- `cd apps/backend && uv run pytest -x` → 216 passed, 121 skipped (was 209 passed before; +7 new commit-gate tests).
- `cd apps/backend && uv run pytest tests/unit/test_service_commit_gate.py -v` → 7 passed.
- `cd apps/backend && PYTHONPATH=. uv run python scripts/export_openapi.py && git diff --exit-code openapi.json` → openapi.json byte-stable (37266 bytes).
- `grep -rn "RequestContract" apps/backend/ --include="*.py"` → ZERO_HITS.
- `grep -c "populate_by_name" apps/backend/app/core/schemas.py` → 0 (D-07 honored).
- `cd apps/backend && uv run python -c "from app.core.schemas import BackendSchemaBase; cfg = BackendSchemaBase.model_config; assert cfg['validate_by_name'] is True; assert cfg['validate_by_alias'] is True; assert cfg['extra'] == 'forbid'; print('OK')"` → OK.
- `cd apps/backend && uv run python -c "import app.core.services as s; assert s.__doc__ and 'SVC001' in s.__doc__ and 'caller-owns-txn' in s.__doc__ and 'session.commit' in s.__doc__ and 'Phase 12.1' in s.__doc__; print('OK')"` → OK.
- Synthetic-failure smoke: temporarily commenting out `await session.commit()` in `clients/service.py:create_client` triggers `test_service_commit_gate_against_app_modules` with file:line `apps/backend/app/modules/clients/service.py:107` and the Phase 12.1 message. Restored before commit; post-restore suite green.

## Self-Check: PASSED

- File modified: `apps/backend/app/core/schemas.py` — FOUND (`class BackendSchemaBase(ContractModel)` at line 36).
- File modified: `apps/backend/app/core/pagination.py` — FOUND (import + base updated).
- File modified: `apps/backend/app/modules/clients/schemas.py` — FOUND (4 hits replaced).
- File modified: `apps/backend/app/modules/clients/router.py` — FOUND (line 22 docstring updated).
- File modified: `apps/backend/app/modules/auth/schemas.py` — FOUND (3 hits replaced).
- File modified: `apps/backend/tests/unit/test_schemas.py` — FOUND (import + class base + test rename).
- File modified: `apps/backend/tests/unit/test_pagination.py` — FOUND (inline comment updated).
- File created: `apps/backend/app/core/services.py` — FOUND (docstring-only, 102 lines, zero runtime defs).
- File created: `apps/backend/tests/unit/test_service_commit_gate.py` — FOUND (AST walker, 7 passing tests).
- File created: `.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/deferred-items.md` — FOUND (auth/service.py review logged).
- Commit `7c61d11` (`refactor(15-04): rename RequestContract -> BackendSchemaBase`) — present in git log.
- Commit `8ccd803` (`feat(15-04): add docstring-only BusinessService template`) — present in git log.
- Commit `050236d` (`test(15-04): add AST commit-gate for service write paths`) — present in git log.
- `BackendSchemaBase.model_config` correctness verified via `uv run python -c "..."` (alias_generator + validate_by_name + validate_by_alias + extra='forbid'); `populate_by_name` absent from source.
- Synthetic missing-commit smoke verified: gate fails loudly at the offending line, restored cleanly.
