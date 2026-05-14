---
phase: 30-foundations-tech-debt-bedrock
plan: 03
subsystem: infra
tags:
  - architecture
  - importlinter
  - ast-walker
  - backend
  - bedrock
  - payments
  - append-only
  - svc001

requires:
  - phase: 30-foundations-tech-debt-bedrock (Plan 02 — RBAC bedrock)
    provides: Resource enum (PAYMENTS, TRAINERS, PT_PACKAGE_PLANS, PT_PACKAGES, PT_SESSIONS) and OWNER_ONLY entries needed before module-shell guards are sanity-checked downstream.
provides:
  - Three architectural bedrock gates extended for v1.4 module materialisation (Phases 31/32/33):
    - `.importlinter` `modules-independent` contract recognises `app.modules.payments` + `app.modules.pt_packages` (`trainers` was already present).
    - SVC001 commit-gate walker scope extended `_INSPECTED_SERVICES` 3 → 6 (added trainers/payments/pt_packages service.py placeholders).
    - New `test_payments_appendonly.py` AST walker (INFRA-22 / B-01) — forbids UPDATE/DELETE/on_conflict_do_update/session.delete against `Payment` in any `modules/**/service.py`; on-disk fixtures cover 4 violation shapes + 1 clean-INSERT positive control.
  - 6 module placeholder files materialised: `app/modules/payments/{__init__,service,models}.py`, `app/modules/pt_packages/{__init__,service}.py`, `app/modules/trainers/service.py`.
affects:
  - Phase 31 (Trainers — TRN-01..08) — SVC001 walker live-asserts `trainers/service.py` write paths from first commit.
  - Phase 32 (Payments + Refund — PAY-01..10, REF-01..08) — append-only walker live-asserts `payments/service.py` write paths from first commit; `0012_payments.py` migration ALTERs the existing UUIDPkMixin-derived `payments` stub (no Phase 30 CREATE migration was emitted, so PAY-01 owns table creation).
  - Phase 33 (PT-Package plans + instances) — SVC001 walker live-asserts `pt_packages/service.py` write paths from first commit.

tech-stack:
  added:
    - pytest-parametrize fixture-on-disk pattern for AST walkers (D-30-07 — on-disk over inline string fixtures)
  patterns:
    - "Append-only AST gate: import-tracking via `_resolve_payment_binding` resolves `from app.modules.payments.models import Payment` (also aliased `Payment as X`); walker flags AST `Call` nodes against bound names only — no string-grep false positives on docstrings (mirrors SVC001 D-30-06 lesson)."
    - "Three-layer chained call unwrapping for `on_conflict_do_update` detection: walks Attribute → Call chain until it finds `insert(Payment)` at the root or exhausts the chain (handles `insert(P).values().on_conflict_do_update(...)`)."
    - "Alembic discovery MANUAL pattern: `apps/backend/alembic/env.py` lists `import app.modules.X.models` explicitly per module — adding a new declarative `Payment` class does NOT auto-join `target_metadata` unless its module is added to the env.py list. Phase 32 PAY-01 owns that addition + migration."

key-files:
  created:
    - apps/backend/app/modules/payments/__init__.py
    - apps/backend/app/modules/payments/service.py
    - apps/backend/app/modules/payments/models.py
    - apps/backend/app/modules/pt_packages/__init__.py
    - apps/backend/app/modules/pt_packages/service.py
    - apps/backend/app/modules/trainers/service.py
    - apps/backend/tests/unit/test_payments_appendonly.py
    - apps/backend/tests/unit/fixtures/__init__.py
    - apps/backend/tests/unit/fixtures/payments_violation_update.py
    - apps/backend/tests/unit/fixtures/payments_violation_delete.py
    - apps/backend/tests/unit/fixtures/payments_violation_on_conflict_update.py
    - apps/backend/tests/unit/fixtures/payments_violation_session_delete.py
    - apps/backend/tests/unit/fixtures/payments_violation_clean_insert.py
  modified:
    - apps/backend/.importlinter
    - apps/backend/tests/unit/test_service_commit_gate.py
    - apps/backend/pyproject.toml

key-decisions:
  - "Alembic auto-discovery outcome = MANUAL: env.py contains explicit `import app.modules.{auth,clients,memberships,visits}.models` block; `app.modules.payments.models` is NOT in the list, so `Base.metadata` does NOT collect a `payments` table during `alembic upgrade` / `alembic check`. Consequence: UNCONDITIONAL `class Payment(UUIDPkMixin, Base)` stub is safe — no Alembic migration emitted in Phase 30."
  - "Payment class strategy = UNCONDITIONAL declarative class (`class Payment(UUIDPkMixin, Base): __tablename__ = 'payments'`). Verified empirically: BEFORE_VERSIONS=10, AFTER_VERSIONS=10; `alembic check` reports `No new upgrade operations detected`. TYPE_CHECKING-guard NOT needed; cleaner code, house-style consistent."
  - "INSERT-only policy (D-30-08): walker forbids `on_conflict_do_update(Payment)` (formally UPDATE); `on_conflict_do_nothing()` permitted. Concurrent-refund races handled by PAY-02 partial UNIQUE → IntegrityError, not on_conflict UPSERT."
  - "Session.delete predicate is conservative: any `session.delete(name)` in a file that imports Payment is flagged. False-positive risk is bounded (non-Payment instance in a Payment-importing module) — acceptable for B-01 defence-in-depth."

patterns-established:
  - "On-disk AST fixture pattern (D-30-07): synthetic violation/positive-control fixtures live in `tests/unit/fixtures/payments_violation_*.py` and are parsed by `ast.parse()` directly. Real-file fixtures preserve linenumbers and avoid linecache injection complexity used by SVC001 in-memory strings."
  - "pyproject.toml fixture exclusion stanza: `[tool.ruff.lint.per-file-ignores]` for `tests/unit/fixtures/payments_violation_*.py` (F401/F841/ANN/ARG001 — intentional untyped/unused), plus `[[tool.mypy.overrides]]` `module = 'tests.unit.fixtures.*'` `ignore_errors = true`. Pattern reusable for any future AST-walker fixture set."
  - "Module placeholder shape: `__init__.py` one-line docstring referencing materialising phase + locked invariant; `service.py` empty body with docstring listing the invariants future write paths MUST honour; `models.py` minimal `UUIDPkMixin + Base` subclass with `__tablename__` only. Substantive columns/constraints land via ALTER in the materialising phase, not by stub replacement."

requirements-completed:
  - INFRA-20
  - INFRA-21
  - INFRA-22

# Metrics
duration: ~30min
completed: 2026-05-14
---

# Phase 30 Plan 03: Architectural bedrock (INFRA-20/21/22) Summary

**Three CI-enforced architectural gates extended/added before Phases 31/32/33 materialise new modules: `.importlinter` modules-independent contract recognises payments + pt_packages; SVC001 commit-gate walker scope grows 3 → 6 services; new `test_payments_appendonly.py` AST walker forbids UPDATE/DELETE/on_conflict_do_update/session.delete against `Payment` (B-01 defence-in-depth) — backed by 5 on-disk fixtures (4 violations caught, 1 clean-INSERT passes).**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-05-14T12:25:00Z (approx)
- **Completed:** 2026-05-14T12:51:39Z
- **Tasks:** 2
- **Files created:** 13
- **Files modified:** 3

## Accomplishments

- Three top-level `.importlinter` contracts remain UNCHANGED in shape; `modules-independent` modules list extended by 2 entries (`app.modules.payments`, `app.modules.pt_packages`). `app.modules.trainers` was already present from v1.0.
- SVC001 commit-gate live scope extended from 3 inspected services (clients/memberships/auth) to 6 (added trainers/payments/pt_packages placeholders). Placeholders contain zero functions → pass the gate trivially; Phases 31/32/33 cannot land service code without the commit-gate exercising their write paths.
- New AST walker `test_payments_appendonly.py` with 7 test cases: 1 live (against real codebase, 0 offenders), 1 scope-sanity, 4 parametrized violation fixtures, 1 clean-INSERT positive control. All 7 pass.
- 6 module placeholder files created (payments/{__init__, service, models}, pt_packages/{__init__, service}, trainers/service); `Payment` class stub is a minimal `UUIDPkMixin + Base` subclass parseable by `ast.parse()` for the walker's import-tracking resolution.
- D-30-10 invariant preserved: `apps/backend/alembic/versions/` count UNCHANGED (BEFORE=10, AFTER=10); `alembic check` reports `No new upgrade operations detected`. Phase 32 PAY-01 owns `0012_payments.py` table creation as planned.
- Full backend unit suite: 403 passed (no regressions).

## Task Commits

1. **Task 1: Module placeholders + extend `.importlinter` + extend SVC001 walker scope** — `be962d7` (feat)
2. **Task 2: `test_payments_appendonly.py` AST walker + 5 fixtures + pyproject fixture exclusions** — `091c8ee` (feat)

## Files Created/Modified

### Created (13)
- `apps/backend/app/modules/payments/__init__.py` — module docstring, references INFRA-20 + B-01 invariant.
- `apps/backend/app/modules/payments/service.py` — empty placeholder; lists append-only invariant in docstring (target for SVC001 walker).
- `apps/backend/app/modules/payments/models.py` — UNCONDITIONAL `class Payment(UUIDPkMixin, Base)` stub with `__tablename__ = "payments"`; minimum required for the append-only walker's `_resolve_payment_binding` import-tracking target.
- `apps/backend/app/modules/pt_packages/__init__.py` — module docstring, references INFRA-20 + B-04.
- `apps/backend/app/modules/pt_packages/service.py` — empty placeholder.
- `apps/backend/app/modules/trainers/service.py` — empty placeholder (trainers/__init__.py existed pre-Phase-30).
- `apps/backend/tests/unit/test_payments_appendonly.py` — new AST walker test (4 predicates: `_is_forbidden_sql_against_payment`, `_is_on_conflict_do_update_against_payment`, `_is_session_delete_of_payment`, `_function_violates_appendonly`; entry points: `_resolve_payment_binding`, `_iter_functions_in_file`; 7 tests).
- `apps/backend/tests/unit/fixtures/__init__.py` — package marker.
- `apps/backend/tests/unit/fixtures/payments_violation_update.py` — `update(Payment).where(...).values(...)` violation.
- `apps/backend/tests/unit/fixtures/payments_violation_delete.py` — `delete(Payment).where(...)` violation.
- `apps/backend/tests/unit/fixtures/payments_violation_on_conflict_update.py` — `insert(Payment).values().on_conflict_do_update(...)` violation.
- `apps/backend/tests/unit/fixtures/payments_violation_session_delete.py` — `session.delete(payment)` violation.
- `apps/backend/tests/unit/fixtures/payments_violation_clean_insert.py` — positive control (`session.add(Payment())` + `session.execute(insert(Payment).values())`).

### Modified (3)
- `apps/backend/.importlinter` — added `app.modules.payments` + `app.modules.pt_packages` to `modules-independent` contract modules list. Three top-level contracts unchanged in shape (`grep -c '^\[importlinter:contract:'` returns exactly 3).
- `apps/backend/tests/unit/test_service_commit_gate.py` — `_INSPECTED_SERVICES` tuple grown 3 → 6; constants `_TRAINERS_SERVICE`, `_PAYMENTS_SERVICE`, `_PT_PACKAGES_SERVICE` added; live-test docstring extended with Phase 30 INFRA-21 paragraph.
- `apps/backend/pyproject.toml` — added `[tool.ruff.lint.per-file-ignores]` stanza for `tests/unit/fixtures/payments_violation_*.py` (`F401`, `F841`, `ANN`, `ARG001`) and `[[tool.mypy.overrides]]` `module = "tests.unit.fixtures.*"` `ignore_errors = true`.

## Alembic D-30-10 Audit Trail (BLOCKER #1)

### Alembic discovery outcome: MANUAL

**Evidence (`apps/backend/alembic/env.py` lines 21-26):**
```python
# Register all ORM models with Base.metadata for autogenerate (TEST-08 / Phase 5 INFRA-03).
import app.modules.auth.models
import app.modules.clients.models
import app.modules.memberships.models
import app.modules.visits.models
import app.core.audit_models  # noqa: F401
```

`target_metadata = Base.metadata` (env.py line 41), but the imports are explicit per-module — no `pkgutil.walk_packages` / `importlib.import_module` loop. `app.modules.payments.models` is NOT in the list, so adding a declarative `Payment` class does NOT populate `Base.metadata` at migration time. Phase 32 PAY-01 will add `import app.modules.payments.models` to env.py as part of the migration plan.

### Chosen `Payment` class strategy: UNCONDITIONAL

The class is declared unconditionally as `class Payment(UUIDPkMixin, Base)` — no `TYPE_CHECKING` guard needed. Rationale:
- The MANUAL discovery outcome means Base.metadata is not contaminated even though the class subclasses Base.
- House-style consistency (clients/memberships use unconditional declarative classes).
- The AST walker uses `ast.parse(file.read_text())`, so the class is detectable regardless of guard strategy — UNCONDITIONAL is simpler.

### Alembic versions count invariance

- **BEFORE_VERSIONS:** 10 (`0001_auth.py` … `0010_notifications.py`)
- **AFTER_VERSIONS:** 10 (unchanged — no migration emitted)

### `alembic check` output (verbatim trailing lines after task completion)

```
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.types
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.constraints
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.defaults
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.comments
No new upgrade operations detected.
```

Required `alembic check` to run against a live Postgres 16 — a temporary Docker container (`sportzal-pg-check`) was spun up with `app/app/sportzal` credentials, baseline upgraded to head, then checked. Container removed after verification.

### Note for Phase 32 planner

Migration `0012_payments.py` ships in Phase 32 PAY-01 with **CREATE TABLE payments** (not ALTER) — because Phase 30 deliberately did NOT push the `payments` table into `Base.metadata` (it would have required a corresponding migration). When Phase 32 adds `import app.modules.payments.models` to `alembic/env.py`, autogenerate will see a brand-new table and emit the full CREATE — matching the existing PAY-01 plan exactly. No accidental ALTER-vs-CREATE mismatch risk.

## Decisions Made

- **MANUAL Alembic discovery → UNCONDITIONAL Payment class.** Bedrock-level decision (see audit trail above). Alternative (TYPE_CHECKING-guarded) was unnecessary given MANUAL discovery.
- **On-disk fixtures over inline AST strings (D-30-07).** SVC001 inline-string pattern uses `linecache.cache` injection — fine for short snippets but harder to read. New walker uses real files; trade-off is `pyproject.toml` exclusion stanza but readability win.
- **Conservative `session.delete` predicate.** Walker flags any `session.delete(name)` in a file that imports Payment, without attempting type inference. Documented in walker docstring as B-01 defence-in-depth trade-off.
- **on_conflict_do_update chained-call unwrap (3-level Attribute chain).** Handles `insert(P).values().on_conflict_do_update(...)`, `insert(P).on_conflict_do_update(...)`, and intermediate chains. Walker stops at the first `insert(Payment)` root or chain end.

## Deviations from Plan

None - plan executed exactly as written.

The plan's Step 0a/0b/0c discovery sequence was followed verbatim. Alembic discovery outcome (MANUAL) selected the UNCONDITIONAL Payment-class branch in Task 1 Step 2(c). All acceptance criteria passed first-attempt; no retries; no Rule 1/2/3 auto-fixes.

## Issues Encountered

- **`alembic check` requires live Postgres.** Initial `alembic check` invocation failed with `OSError: Connect call failed (::1:5432, 127.0.0.1:5432)` because no Postgres was running locally. Resolved by starting a temporary `postgres:16` Docker container (`sportzal-pg-check`) with credentials `app/app/sportzal`, running `alembic upgrade head` to baseline, then `alembic check`. Container removed after verification. This is an environmental, not code, issue — the BLOCKER #1 invariant assertion (`alembic check` reports no diff) was correctly satisfied.

## User Setup Required

None - no external service configuration required for this plan. (The temporary Postgres container for verification was an executor-side action, not a user dependency.)

## Verification Output

```
$ cd apps/backend && uv run lint-imports
Contracts: 3 kept, 0 broken.

$ cd apps/backend && uv run pytest tests/unit/test_service_commit_gate.py tests/unit/test_payments_appendonly.py -q
..............                                                           [100%]
14 passed in 0.03s

$ cd apps/backend && uv run pytest tests/unit/ -q
403 passed in 0.60s

$ cd apps/backend && uv run mypy --strict app/modules/payments/ app/modules/pt_packages/ tests/unit/test_payments_appendonly.py
Success: no issues found in 7 source files (combined across calls)

$ cd apps/backend && uv run ruff check app/modules/payments/ app/modules/pt_packages/ app/modules/trainers/service.py tests/unit/test_payments_appendonly.py tests/unit/fixtures/
All checks passed!

$ ls apps/backend/alembic/versions/ | grep -v __pycache__ | wc -l
10  (== BEFORE; D-30-10 invariant preserved)

$ cd apps/backend && uv run alembic check
… No new upgrade operations detected.
```

## Next Phase Readiness

- **Phase 31 (Trainers — TRN-01..08)**: SVC001 walker live-asserts `trainers/service.py` from first commit; `.importlinter` permits `app.modules.trainers` in `modules-independent`. Ready.
- **Phase 32 (Payments + Refund — PAY-01..10, REF-01..08)**: Both gates (SVC001 + append-only) live-assert `payments/service.py` from first commit. `Payment` model stub is a starting point — PAY-01 will replace it with the substantive declarative shape (signed `amount_kopecks`, CHECK on `subject_kind`, partial UNIQUE on `refund_of`, `payment_row_hash`, audit cols). Migration `0012_payments.py` will CREATE the table fresh once `app.modules.payments.models` is added to `alembic/env.py`. Ready.
- **Phase 33 (PT-Package plans + instances)**: SVC001 walker live-asserts `pt_packages/service.py` from first commit; `.importlinter` permits `app.modules.pt_packages`. Ready.

## Self-Check: PASSED

Verified:
- `apps/backend/app/modules/payments/__init__.py` FOUND
- `apps/backend/app/modules/payments/service.py` FOUND
- `apps/backend/app/modules/payments/models.py` FOUND (contains `class Payment` — `ast.parse` confirmed)
- `apps/backend/app/modules/pt_packages/__init__.py` FOUND
- `apps/backend/app/modules/pt_packages/service.py` FOUND
- `apps/backend/app/modules/trainers/service.py` FOUND
- `apps/backend/tests/unit/test_payments_appendonly.py` FOUND
- `apps/backend/tests/unit/fixtures/__init__.py` FOUND
- All 5 fixtures FOUND
- Commit `be962d7` FOUND in git log
- Commit `091c8ee` FOUND in git log

---
*Phase: 30-foundations-tech-debt-bedrock*
*Plan: 03*
*Completed: 2026-05-14*
