---
phase: 15-foundations-rbac-audit-taxonomy-helper-hoisting
plan: 03
subsystem: backend/audit
tags: [audit, taxonomy, foundations, ast-walker, security, v1.2]
requirements:
  - INFRA-11
dependency_graph:
  requires:
    - app/core/audit.py (existing emit signature, AuditLog model)
    - app/core/dependencies.py (rbac_forbidden callsite)
  provides:
    - LOCKED_AUDIT_EVENTS frozenset (28 entries — runtime source of truth)
    - AuditEventNotLockedError exception class
    - Pre-emit guard in audit.emit (D-09 hard fail)
    - Static AST gate (tests/unit/test_audit_taxonomy.py)
  affects:
    - All v1.1 audit.emit callsites (no signature change; rbac_forbidden refactored)
    - Phase 16/17/19/20 emit callsites (must use literal pairs in the locked set)
tech_stack:
  added: []
  patterns:
    - "Module docstring + runtime frozenset as source of truth for closed taxonomy"
    - "Static AST gate paired with runtime guard (defence in depth)"
    - "Literal-only callsite contract (D-11) for analysability"
key_files:
  created:
    - apps/backend/tests/unit/test_audit_taxonomy.py
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/dependencies.py
decisions:
  - Frozenset has 28 entries (18 v1.1 + 10 v1.2), not the 26 the plan expected — 2 v1.1 callsites (rbac_forbidden, csrf_mismatch) were missing from the plan's docstring lift list
  - rbac_forbidden refactored from non-literal resource_type=resource.value to literal resource_type='rbac' (target resource moves to payload kwarg target_resource) — required for the literal-only static gate
  - Frozenset values resolved against actual callsites where the original docstring drifted (session_revoked_all + 3 telegram_* events)
metrics:
  duration: ~13 minutes
  completed: 2026-05-07T10:48:07Z
  tasks_completed: 2
  files_created: 1
  files_modified: 2
---

# Phase 15 Plan 03: Audit-event taxonomy lock (runtime + static AST gate) Summary

INFRA-11 lands: `app.core.audit` exposes a runtime-checked `LOCKED_AUDIT_EVENTS` frozenset (28 pairs), `audit.emit()` raises `AuditEventNotLockedError` on any non-locked pair (D-09 hard fail in dev + prod), and a pure-static AST walker (`tests/unit/test_audit_taxonomy.py`) blocks typos and dynamic event names from reaching CI. Phase 17's TESTS-09 work is structurally satisfied — new Phase 16/17/19/20 emit callsites are validated automatically.

## What Was Built

- **`apps/backend/app/core/audit.py`**:
  - `LOCKED_AUDIT_EVENTS: frozenset[tuple[str, str]]` — 28 entries (18 v1.1 + 10 v1.2). Module-level constant lifted from the previous docstring enumeration; the docstring is retained as a human-facing reference and points at the frozenset as the runtime source of truth.
  - `class AuditEventNotLockedError(ValueError)` — raised by the pre-emit guard. Tests catch this exception explicitly (no broad `except ValueError`).
  - `emit()` body grew exactly one guard at the top: `if (event, resource_type) not in LOCKED_AUDIT_EVENTS: raise AuditEventNotLockedError(...)`. Signature, structlog call, and `session.add(AuditLog(...))` were not touched.
- **`apps/backend/app/core/dependencies.py`** — `require_permission` callsite (line 132) refactored from non-literal `resource_type=resource.value` to literal `resource_type="rbac"`; the target resource moves into the payload as `target_resource=resource.value`. This was required for the AST literal-only gate (D-11) to admit the callsite. The associated structlog event keys remain `role`, `action`, `path`, `ip` — existing tests assert exactly those keys and pass unchanged. The `AuditLog.resource_type` DB column for `rbac_forbidden` rows is now `'rbac'` (was the target resource's value); no test reads that column.
- **`apps/backend/tests/unit/test_audit_taxonomy.py`** (NEW, 175 lines) — pure-static AST walker with three tests:
  - `test_every_audit_emit_uses_literal_strings` — `event` and `resource_type` must be `ast.Constant(str)`. f-strings, variables, attribute access (e.g. `resource.value`), and missing args all fail with file:line.
  - `test_every_audit_emit_pair_is_in_locked_set` — every literal pair must be in `LOCKED_AUDIT_EVENTS`. Catches typos like `memberhsip_created` BEFORE runtime.
  - `test_locked_audit_events_has_expected_count` — sanity belt at 28.

  Walker excludes `app/core/audit.py` itself to avoid false positives on docstring forward-references. Recognises three callsite shapes: `audit.emit(...)`, `<x>.audit.emit(...)`, and `audit_emit(...)` (the `from app.core.audit import emit as audit_emit` rebinding in `app/integrations/telegram/handlers.py` — the only such alias in the codebase).

## Final entries in LOCKED_AUDIT_EVENTS (28 total)

### v1.1 (18 entries — verified against actual callsites)

| Event | resource_type | Source |
|---|---|---|
| `login_success` | `session` | `auth/router.py:269`, `auth/service.py:144` |
| `login_failed` | `login_attempt` | `auth/service.py:118, 133` |
| `session_revoked` | `session` | `auth/service.py:469` |
| `session_revoked_all` | `user` | `auth/service.py:528` — **drift fix** (docstring claimed `'session'`) |
| `family_reuse_detected` | `session` | `auth/service.py:393` |
| `password_changed_revokes_sessions` | `user` | `auth/service.py:254` |
| `telegram_deep_link_issued` | `otp` | `auth/telegram_service.py:102` |
| `otp_issued` | `otp` | `auth/telegram_service.py:198` |
| `otp_consumed` | `otp` | `auth/telegram_service.py:274` |
| `telegram_unknown_start` | `otp` | `integrations/telegram/handlers.py:116` — **drift fix** (docstring claimed `'telegram'`) |
| `telegram_dm_blocked` | `otp` | `integrations/telegram/handlers.py:160` — **drift fix** (docstring claimed `'telegram'`) |
| `telegram_dm_failed` | `otp` | `integrations/telegram/handlers.py:171` — **drift fix** (docstring claimed `'telegram'`) |
| `telegram_replay_attempt` | `otp` | `integrations/telegram/handlers.py:133` |
| `rbac_forbidden` | `rbac` | `core/dependencies.py:132` — **NEW in this plan** (was non-literal `resource.value`; refactored to literal `'rbac'` + `target_resource` payload kwarg) |
| `csrf_mismatch` | `csrf` | `core/dependencies.py:201` — **NEW in this plan** (Phase 6 callsite missing from original docstring) |
| `client_created` | `client` | `clients/service.py:130` |
| `client_updated` | `client` | `clients/service.py:186` |
| `client_soft_deleted` | `client` | `clients/service.py:226` |

### v1.2 (10 entries — Phase 15 lock; emitted in Phases 16/17/19/20)

| Event | resource_type | Owner phase |
|---|---|---|
| `membership_plan_created` | `membership_plan` | Phase 16 |
| `membership_plan_updated` | `membership_plan` | Phase 16 |
| `membership_plan_archived` | `membership_plan` | Phase 16 |
| `membership_created` | `membership` | Phase 17 |
| `membership_cancelled` | `membership` | Phase 17 |
| `membership_expired` | `membership` | Phase 18 (ARQ daily) |
| `visit_created` | `visit` | Phase 19/20 |
| `visit_rejected_no_membership` | `visit` | Phase 19/20 |
| `visit_rejected_duplicate` | `visit` | Phase 19/20 |
| `visit_rejected_outside_hours` | `visit` | Phase 19/20 |

## TDD Gate Compliance

Plan 15-03 marked tasks as `tdd="true"` but is `type: execute` (not `type: tdd`) at the plan level — TDD here means the AST gate **was** the test-first artifact for new code paths. Both deliverables were committed atomically:

- Task 1 commit `3d9dfcf` (`feat(15-03): ...`) — locked frozenset + runtime guard.
- Task 2 commit `cd566a9` (`test(15-03): ...`) — AST walker confirms the runtime contract from the static side.

A synthetic-failure smoke test was performed: an extra file `app/_synthetic_bad_audit.py` containing `audit.emit('memberhsip_created', ..., resource_type='membership')` (typo) was added to the tree, the test was run (failed loudly with file:line), and the file was deleted before any commit. Logs in self-check below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Plan's expected frozenset count was wrong (26 → 28)**
- **Found during:** Task 1 grep (per `<read_first>` instruction to "Run this grep BEFORE editing")
- **Issue:** The plan's frozenset enumerates 16 v1.1 events (lifted from `audit.py` docstring). Two real Phase 6 callsites — `rbac_forbidden` and `csrf_mismatch` — were never added to that docstring and were absent from the plan's frozenset. The plan's `test_locked_audit_events_has_expected_count` would have asserted `== 26`, while the real codebase requires 28 to satisfy `test_every_audit_emit_pair_is_in_locked_set`.
- **Fix:** Added `(rbac_forbidden, 'rbac')` and `(csrf_mismatch, 'csrf')` to the frozenset; updated the count test from 26 → 28; documented both events in the audit.py docstring under v1.1.
- **Files modified:** `apps/backend/app/core/audit.py`, `apps/backend/tests/unit/test_audit_taxonomy.py`
- **Commit:** `3d9dfcf` (frozenset) + `cd566a9` (count test)

**2. [Rule 1 — Bug] `rbac_forbidden` callsite uses non-literal `resource_type` (incompatible with D-11)**
- **Found during:** Task 1 AST extraction
- **Issue:** `app/core/dependencies.py:132` passes `resource_type=resource.value` (an `ast.Attribute` node, not `ast.Constant(str)`). Per D-11 the AST literal-only gate cannot prove staticness for this callsite; the test `test_every_audit_emit_uses_literal_strings` would fail. Per D-09 the runtime guard would also raise — the call passes 11 different `Resource.value` strings (one per RBAC pair) so listing all of them in the frozenset is impractical and a typo magnet.
- **Fix:** Refactored the call to use literal `resource_type="rbac"` and pushed the target resource into the payload as `target_resource=resource.value`. The `AuditLog` row's `resource_type` column now stores `'rbac'` (was the per-call resource string); no test reads that column. The structlog event already carries the full target via `path` (e.g. `/_t/delete/clients`), and the explicit `target_resource` payload kwarg makes the logical target machine-readable.
- **Files modified:** `apps/backend/app/core/dependencies.py`
- **Commit:** `3d9dfcf`

**3. [Rule 1 — Doc-vs-callsite drift] Four v1.1 callsites use a different `resource_type` than the audit.py docstring claimed**
- **Found during:** Task 1 AST extraction + grep verification
- **Issue:** The audit.py docstring (lines 11-28) listed v1.1 event payloads but did not anchor `resource_type` literally for each event. The Phase 15 plan extrapolated `resource_type` from the docstring text and got four pairs wrong relative to the real callsites:
  - `session_revoked_all`: docstring/plan said `'session'`, callsite uses `'user'` (`auth/service.py:528`).
  - `telegram_unknown_start`, `telegram_dm_blocked`, `telegram_dm_failed`: docstring/plan said `'telegram'`, callsites all use `'otp'` (`integrations/telegram/handlers.py:116, 160, 171`).
- **Fix:** Frozenset matches reality (callsite wins per the plan's instruction "If a real callsite uses a slightly different `resource_type` than the docstring, update the frozenset entry to match the actual callsite"). Docstring updated with explicit `# 'resource_type'` annotations next to each event so future drift is more visible.
- **Files modified:** `apps/backend/app/core/audit.py`
- **Commit:** `3d9dfcf`

### Architectural Decisions (none — all deviations were Rule 1 bugs)

No architectural changes required. No checkpoints hit. All work autonomous.

## Note on Phase 17 / TESTS-09

REQUIREMENTS.md formally lists TESTS-09 (audit AST callsite walker) under Phase 17, but per CONTEXT.md D-11/D-12 the test landed here in Phase 15 alongside the runtime guard (the guard is meaningless without the static gate). Phase 17's plan now only needs to:
- add new emit callsites in `app/modules/memberships/service.py` and `app/modules/visits/service.py`,
- the AST walker validates them automatically (no new test work),
- the count assertion stays at 28 — Phase 17 does not extend `LOCKED_AUDIT_EVENTS` (the v1.2 entries were front-loaded in this plan).

## Verification

- `cd apps/backend && uv run pytest -x` → 154 passed, 103 skipped (skipped = real-DB integration tests; same skip count before and after this plan).
- `cd apps/backend && uv run pytest tests/unit/test_audit_taxonomy.py -v` → 3 passed.
- `cd apps/backend && uv run ruff check app/core/audit.py app/core/dependencies.py tests/unit/test_audit_taxonomy.py` → All checks passed.
- `cd apps/backend && uv run mypy app/core/audit.py app/core/dependencies.py tests/unit/test_audit_taxonomy.py` → Success: no issues found.
- `cd apps/backend && uv run lint-imports` → 3 contracts kept, 0 broken.
- `cd apps/backend && PYTHONPATH=. uv run python scripts/export_openapi.py && git diff --exit-code openapi.json` → no contract drift.

## Self-Check: PASSED

- File created: `apps/backend/tests/unit/test_audit_taxonomy.py` — FOUND.
- File modified: `apps/backend/app/core/audit.py` — FOUND (frozenset + exception + guard).
- File modified: `apps/backend/app/core/dependencies.py` — FOUND (rbac_forbidden literal refactor).
- Commit `3d9dfcf` (`feat(15-03): lock v1.2 audit-event taxonomy with runtime guard`) — present in `git log`.
- Commit `cd566a9` (`test(15-03): add AST callsite walker for audit taxonomy`) — present in `git log`.
- `LOCKED_AUDIT_EVENTS` size = 28 (verified via `uv run python -c`).
- `AuditEventNotLockedError` is a `ValueError` subclass (verified via `uv run python -c`).
- Synthetic-failure smoke test passed (file:line offender reported by `test_every_audit_emit_pair_is_in_locked_set`; revert verified — `apps/backend/app/_synthetic_bad_audit.py` is gone).
