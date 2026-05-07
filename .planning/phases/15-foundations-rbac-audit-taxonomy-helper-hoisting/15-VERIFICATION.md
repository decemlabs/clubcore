---
phase: 15-foundations-rbac-audit-taxonomy-helper-hoisting
verified: 2026-05-07T00:00:00Z
status: passed_with_findings
score: 5/5 success criteria verified
overrides_applied: 0
findings:
  - kind: deferred_finding
    severity: medium
    location: apps/backend/app/modules/auth/service.py
    summary: |
      Out-of-scope finding logged in deferred-items.md during 15-04: `authenticate`
      (line 88) and `rotate_refresh` (line 271) match the SVC001 write-path-without-
      explicit-commit shape. `rotate_refresh` is a walker false positive (uses
      `async with session.begin():` which auto-commits on `__aexit__`).
      `authenticate`'s `login_failed` path may be a real Phase-12.1-class bug
      (audit row enrolled but commit relies on caller chain / lifecycle).
      This is correctly OUT OF SCOPE for Phase 15 (infra-only, regression bound
      narrowed to `clients/service.py` per acceptance criterion). Recommend
      opening a follow-up plan during Phase 16 hygiene to (a) reproduce the
      audit-row loss, (b) either add an explicit commit or refactor with SVC001
      marker, and (c) extend the live commit-gate scope to `auth/service.py`
      and/or extend the walker to recognise `async with session.begin():`.
    recommended_followup_phase: "Phase 16 hygiene OR a dedicated cleanup plan"
---

# Phase 15: Foundations — RBAC + audit taxonomy + helper hoisting — Verification Report

**Phase Goal:** Lock the v1.2 contract surface (RBAC enums byte-paritetic FE↔BE, audit event taxonomy, schema base, service-write commit gate, key decisions) so phases 16/17/19/22 build on a frozen foundation.

**Verified:** 2026-05-07
**Status:** PASSED WITH FINDINGS
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth (SC) | Status | Evidence |
|---|------------|--------|----------|
| SC-1 | RBAC byte-parity (Action.{CANCEL,CHECK_IN}, Resource.{MEMBERSHIPS,MEMBERSHIP_PLANS,VISITS}, OWNER_ONLY v1.2 pairs, 3-way parity test green) | VERIFIED | `app/core/permissions.py` exposes `Action.CANCEL='cancel'`, `Action.CHECK_IN='check_in'`, `Resource.MEMBERSHIPS='memberships'`, `Resource.MEMBERSHIP_PLANS='membership-plans'`, `Resource.VISITS='visits'`; `OWNER_ONLY` size = 15 (9 v1.1 + 6 v1.2); admin-web `registry.ts` Resource union and `can.ts` OWNER_ONLY mirror byte-for-byte; `tests/integration/test_rbac_parity.py` 4 tests PASS including `test_owner_only_count_is_fifteen` |
| SC-2 | escape_like_pattern hoisted to core/sql.py; clients import from there; v1.1 CR-01 regression suite green | VERIFIED | `app/core/sql.py:escape_like_pattern` exists (no leading underscore); `app/modules/clients/repository.py:36` imports `from app.core.sql import escape_like_pattern`; `tests/unit/clients/test_repository_escape.py:10` imports from new path (aliased); `tests/unit/test_core_sql.py` (6 cases) and `tests/unit/clients/test_repository_escape.py` (6 cases) all PASS; import-linter 3 contracts KEPT |
| SC-3 | audit.emit rejects pairs not in LOCKED_AUDIT_EVENTS; locked set lists every v1.2 event | VERIFIED | `app/core/audit.py:LOCKED_AUDIT_EVENTS` = frozenset of 28 entries (18 v1.1 + 10 v1.2); `class AuditEventNotLockedError(ValueError)` exists; `emit()` body raises BEFORE structlog/DB writes when pair not in set; all 10 v1.2 events present (`membership_plan_*` x3, `membership_*` x3, `visit_*` x4); `tests/unit/test_audit_taxonomy.py` 3 tests PASS (literal-only callsite + locked-pair + count==28) |
| SC-4 | BackendSchemaBase + BusinessService template + AST commit gate | VERIFIED | `app/core/schemas.py:BackendSchemaBase` config = `{alias_generator=to_camel, validate_by_name=True, validate_by_alias=True, extra='forbid'}` (no `populate_by_name` — D-07 honored); `app/core/services.py` is docstring-only (zero classes/defs); `tests/unit/test_service_commit_gate.py` 7 tests PASS including D-04 negative `test_synthetic_public_function_with_svc001_is_rejected` ("public service functions MUST commit") and synthetic missing-commit RED proof |
| SC-5 | PROJECT.md Key Decisions records 3 v1.2 decisions; REQUIREMENTS.md INFRA-12 wording uses validate_by_name + validate_by_alias | VERIFIED | `.planning/PROJECT.md` lines 165-167 contain 3 new rows: inclusive `end_date`, `gym_date = (checked_in_at AT TIME ZONE 'Europe/Moscow')::date STORED + UNIQUE`, accepted residual friend-fraud risk; `.planning/REQUIREMENTS.md:18` INFRA-12 uses `validate_by_name=True, validate_by_alias=True` (Pydantic 2.11+ canonical pair, replacing deprecated `populate_by_name`) |

**Score:** 5/5 truths verified

### Required Artifacts (existence + substantive + wired + data-flowing)

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/core/permissions.py` | v1.2 Actions + Resources + OWNER_ONLY | VERIFIED | All v1.2 enum members and 6 v1.2 OWNER_ONLY pairs present; verbatim mirror docstring intact |
| `apps/backend/app/core/sql.py` | escape_like_pattern (module-public) | VERIFIED | 41-line leaf module, zero `app.*` imports, verbatim hoist body |
| `apps/backend/app/core/audit.py` | LOCKED_AUDIT_EVENTS frozenset, AuditEventNotLockedError, pre-emit guard | VERIFIED | 28-entry frozenset, exception class subclasses `ValueError`, guard at line 158 raises BEFORE structlog/DB writes |
| `apps/backend/app/core/schemas.py` | BackendSchemaBase with v1.2 config | VERIFIED | Class at line 36, config matches D-07 exactly; `RequestContract` symbol absent across `apps/backend/` (grep ZERO_HITS) |
| `apps/backend/app/core/services.py` | Docstring-only template | VERIFIED | 102 lines, zero `class`/`def`/`async def`; covers SVC001 invariant, Phase 12.1 precedent, D-04 opt-out policy |
| `apps/backend/app/core/dependencies.py` | rbac_forbidden refactored to literal `'rbac'` | VERIFIED | Refactored per D-11; passes literal-only AST gate |
| `apps/admin-web/src/shared/session/registry.ts` | Resource type extended | VERIFIED | `'memberships' \| 'membership-plans' \| 'visits'` added; Action type extends with `'cancel' \| 'check_in'` |
| `apps/admin-web/src/shared/session/can.ts` | OWNER_ONLY 15 entries (mirror) | VERIFIED | 6 v1.2 entries appended in same order as backend frozenset |
| `apps/backend/tests/integration/test_rbac_parity.py` | 3-way parity at 15 entries | VERIFIED | `test_owner_only_count_is_fifteen` + 3 set-equality tests = 4 PASS |
| `apps/backend/tests/unit/test_core_sql.py` | Direct unit coverage | VERIFIED | 6 PASS (incl. order-check, mixed metacharacters, escape_like=False opt-out) |
| `apps/backend/tests/unit/clients/test_repository_escape.py` | Updated import path | VERIFIED | Imports `from app.core.sql import escape_like_pattern as _escape_like_pattern` (aliased to preserve test bodies); 6 PASS |
| `apps/backend/tests/unit/test_audit_taxonomy.py` | AST literal walker + locked-set + count | VERIFIED | 3 PASS |
| `apps/backend/tests/unit/test_service_commit_gate.py` | AST commit gate including D-04 negative | VERIFIED | 7 PASS; includes `test_synthetic_public_function_with_svc001_is_rejected` proving public+SVC001 = failure |
| `.planning/PROJECT.md` (Key Decisions) | 3 new v1.2 rows | VERIFIED | Rows present at lines 165-167 with `Phase 15` traceability tag |
| `.planning/REQUIREMENTS.md` (INFRA-12) | Wording uses validate_by_name+validate_by_alias | VERIFIED | Line 18 updated; `populate_by_name` mentioned only as historical/deprecated context |
| `.planning/phases/15-.../deferred-items.md` | Out-of-scope auth findings logged | VERIFIED | File present, documents authenticate + rotate_refresh findings with severity/recommended-next-step |

### Key Link Verification (Wiring)

| From | To | Via | Status |
|------|----|----|--------|
| `clients/repository.py` | `app.core.sql:escape_like_pattern` | `from app.core.sql import escape_like_pattern` (line 36); 2 callsites (lines 79, 92) | WIRED |
| `audit.emit()` body | `LOCKED_AUDIT_EVENTS` | Direct `if (event, resource_type) not in LOCKED_AUDIT_EVENTS: raise AuditEventNotLockedError(...)` at line 158 | WIRED |
| `core/dependencies.py` rbac_forbidden | `audit.emit("rbac_forbidden", ..., resource_type="rbac", target_resource=resource.value)` | Literal-only callsite per D-11 (refactored in 15-03) | WIRED |
| `tests/unit/test_service_commit_gate.py` live test | `apps/backend/app/modules/clients/service.py` | `_BACKEND_APP / "modules/clients/service.py"` direct path | WIRED (live regression bound; auth/service.py deferred per acceptance criterion) |
| `tests/integration/test_rbac_parity.py` | backend `permissions.py` + admin-web `registry.ts` + admin-web `can.ts` | 3-way set-equality + count belt | WIRED |
| `BackendSchemaBase` | All v1.2 inbound DTO consumers | `pagination.py`, `clients/schemas.py`, `auth/schemas.py` import + class base updated | WIRED (rename complete; ZERO_HITS for `RequestContract` in `apps/backend/`) |

### Anti-Pattern Scan

No blockers found. Out-of-scope finding (auth/service.py write-path) was correctly logged in deferred-items.md and explicitly excluded from Phase 15's INFRA-13 acceptance criterion (regression bound narrowed to `clients/service.py`).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend test suite green | `cd apps/backend && uv run pytest -x` | 216 passed, 121 skipped | PASS |
| Ruff clean | `cd apps/backend && uv run ruff check .` | All checks passed! | PASS |
| MyPy clean | `cd apps/backend && uv run mypy app` | Success: no issues found in 60 source files | PASS |
| Import-linter contracts kept | `cd apps/backend && uv run lint-imports` | 3 kept, 0 broken (`core ⊥ modules`, `modules-independent`, `integrations ⊥ modules`) | PASS |
| OpenAPI byte-stable | `git diff --exit-code apps/backend/openapi.json` | exit 0 (no contract drift) | PASS |
| Frontend typecheck | `pnpm --filter sportzal-adminka typecheck` | exit 0 (clean) | PASS |
| Frontend lint (no NEW errors) | `pnpm --filter sportzal-adminka lint` | 0 errors, 2 pre-existing warnings (`.codex/.../state.cjs`, `data-grid-table-virtual.tsx`) | PASS |
| Runtime verification of Phase 15 contracts | `python -c "from app.core.audit import LOCKED_AUDIT_EVENTS; from app.core.permissions import OWNER_ONLY, Action, Resource; from app.core.schemas import BackendSchemaBase; ..."` | LOCKED_AUDIT_EVENTS=28; OWNER_ONLY=15; v1.2 RBAC enums correct; BackendSchemaBase config matches D-07 (no populate_by_name) | PASS |

### Requirements Coverage

| Requirement | Phase 15 Plan | Description | Status | Evidence |
|-------------|---------------|-------------|--------|----------|
| INFRA-08 | 15-01 | Backend Action/Resource/OWNER_ONLY v1.2 | SATISFIED | `permissions.py` has all 3 new Resources, 2 new Actions, 6 new OWNER_ONLY pairs |
| INFRA-09 | 15-01 | Admin-web parity (registry.ts + can.ts) | SATISFIED | Type unions + can.ts OWNER_ONLY mirror; parity test green |
| INFRA-10 | 15-02 | Hoist escape_like_pattern → core/sql.py | SATISFIED | New module + import sites updated + tests green |
| INFRA-11 | 15-03 | LOCKED_AUDIT_EVENTS frozenset + emit guard | SATISFIED | 28-entry frozenset + AuditEventNotLockedError + pre-emit guard |
| INFRA-12 | 15-04, 15-05 | BackendSchemaBase rename + REQUIREMENTS.md wording fix | SATISFIED | Class renamed (D-07 honored); REQUIREMENTS.md line 18 updated |
| INFRA-13 | 15-04 | core/services.py docstring template + AST commit gate | SATISFIED | Docstring-only module + 7 commit-gate tests including D-04 negative |
| INFRA-14 | 15-05 | PROJECT.md 3 v1.2 Key Decisions | SATISFIED | Rows 165-167 of PROJECT.md |
| TESTS-08 | 15-01 | RBAC three-way parity sanity belt @ 15 | SATISFIED | `test_owner_only_count_is_fifteen` + 3 set-equality tests |
| TESTS-11 | 15-02 | Escape-like regression suite at relocated path | SATISFIED | `test_repository_escape.py` updated; new `test_core_sql.py` adds direct coverage |

All 9 phase requirements SATISFIED. No orphans (REQUIREMENTS.md INFRA-08…INFRA-14 + TESTS-08, TESTS-11 all claimed by 15-01..15-05 plans).

### Deferred / Out-of-Scope Items

The 15-04 executor logged a potential Phase 12.1-class bug in `apps/backend/app/modules/auth/service.py:authenticate` (login_failed audit-row loss) and a walker-false-positive in `rotate_refresh` (uses `async with session.begin():` which auto-commits) to `.planning/phases/15-.../deferred-items.md`. Both findings:

- Are **pre-existing** (not introduced by Phase 15).
- Are **explicitly out-of-scope** for Phase 15's INFRA-13 acceptance criterion (regression bound = `clients/service.py` only, post-12.1 fix).
- Are correctly **routed via the executor SCOPE BOUNDARY rule** (logged, not fixed).

**These do NOT block Phase 15 completion.** They are flagged here for orchestrator/planner pickup during Phase 16 hygiene or a dedicated follow-up plan.

### Human Verification Required

None. All Phase 15 deliverables are infrastructure (enums, frozensets, docstrings, AST gates, planning markdown) with full programmatic verification surface. No visual/UX/real-time/external-service behavior introduced.

### Gaps Summary

No blocking gaps. Phase 15 delivers its goal — the v1.2 contract surface is locked across all 5 Success Criteria, all 9 requirements are satisfied, all cross-cutting health checks (pytest, ruff, mypy, lint-imports, openapi byte-stability, FE typecheck/lint) pass.

One medium-severity follow-up finding (auth/service.py write-path semantics) is properly logged in deferred-items.md for Phase 16+ pickup; it does not block Phase 15 because (a) it's pre-existing, (b) Phase 15's regression bound was narrowed to clients/service.py per the acceptance criterion, and (c) integration tests pass under the current SAVEPOINT-based fixture (production behavior should be re-verified during the follow-up).

---

*Verified: 2026-05-07*
*Verifier: Claude (gsd-verifier, Opus 4.7)*

## VERIFICATION PASSED WITH FINDINGS
