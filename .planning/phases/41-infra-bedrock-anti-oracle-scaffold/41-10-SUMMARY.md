---
phase: 41-infra-bedrock-anti-oracle-scaffold
plan: 10
subsystem: infra
tags: [infra, bedrock, protocol-slots, import-linter, svc001, user-hoist]
requirements: [INFRA-40]
dependency_graph:
  requires:
    - "Phase 5 User ORM (app.modules.auth.models.User — hoisted, shim preserved)"
    - "Phase 32 PaymentRecorder defensive-raise pattern (mirrored for new slots)"
    - "Phase 30 INFRA-21 / Phase 37 INFRA-29 SVC001 placeholder pattern"
  provides:
    - "app.core.models.User (canonical User ORM location)"
    - "EmailDispatcher Protocol slot (consumed by Phase 42 email-channel wiring)"
    - "UserSessionInvalidator Protocol slot (consumed by Phase 43 multi-user admin + Phase 44 password-reset)"
    - "app.modules.users package — SVC001-pinned and importlinter-contracted (Phase 43 substrate)"
    - "app.modules.auth.password_reset_service.py SVC001 pin (Phase 44 substrate)"
  affects:
    - "All ~51 existing `from app.modules.auth.models import User` callsites (no change — shim re-exports identical class)"
tech-stack:
  added: []
  patterns:
    - "One-milestone deprecation shim (User hoist; v1.7 DEFER-41-shim removes)"
    - "Defensive-raise accessor (RuntimeError on unregistered slot — mirrors get_payment_recorder)"
    - "REG-29-03 double-wire (EmailDispatcher will register from create_app AND WorkerSettings.on_startup in Phase 42)"
    - "SVC001 placeholder pin (anti-silent-drop guarantee)"
key-files:
  created:
    - apps/backend/app/core/models.py
    - apps/backend/app/modules/users/__init__.py
    - apps/backend/app/modules/users/service.py
    - apps/backend/app/modules/auth/password_reset_service.py
  modified:
    - apps/backend/app/modules/auth/models.py
    - apps/backend/app/core/dependencies.py
    - apps/backend/.importlinter
    - apps/backend/tests/unit/test_service_commit_gate.py
decisions:
  - "D-41-01 — User hoist target is a new `app/core/models.py` file (one cohesive concern per file; audit_models.py stays separate)"
  - "D-41-02 — Shim is byte-identity re-export, not subclass; v1.7 DEFER-41-shim does the mechanical sed-pass removal"
  - "D-41-24/25 — Both new slots use defensive-raise accessor pattern (missing slot = hard misconfig, not silent-None)"
  - "D-41-28 — Empty placeholder service files satisfy the walker's existence assertion AND trivially pass the SVC001 gate (no functions → no offenders), matching the Phase 30 INFRA-21 pattern"
metrics:
  duration: "~10 min"
  completed: 2026-05-18
  tasks_completed: 3
  files_created: 4
  files_modified: 4
---

# Phase 41 Plan 10: INFRA-40 — User Hoist + 2 Protocol Slots + .importlinter + SVC001 Summary

INFRA-40 closes three mechanical bedrock items in one zero-business-logic commit pass — User ORM hoist with one-milestone shim, two new Protocol slots (EmailDispatcher + UserSessionInvalidator), and the import-linter + SVC001 scope extensions that pin Phase 43/44's future write-path service.py files against silent-drop and cross-module shortcut violations.

## What Was Built

Three mechanical bedrock changes, each prerequisites for v1.6 feature plans without shipping any business logic itself:

1. **D-41-01/02 User ORM hoist + shim** — `class User` moved verbatim from `app.modules.auth.models` to a new `app.core.models` module. The original location is now a one-line re-export shim (`from app.core.models import User  # noqa: F401`) so every existing callsite (~51 sites) keeps working byte-equal; v1.7 milestone runs the mechanical sed-pass removal under DEFER-41-shim. The new home reserves `app.core.models` for shared ORM with the "needed by ≥2 modules" justification only; `audit_models.py` stays separate per the cohesive-concern rule.

2. **D-41-24/25 Protocol slot declarations** — `EmailDispatcher` (template_id / to / audit_correlation_id / **template_vars) and `UserSessionInvalidator` (session / user_id / reason: Literal['deactivated','password_reset','soft_deleted'] → int) added to `app/core/dependencies.py` with mirror-of-existing `register_*` setters and defensive-raise `get_*` accessors. Phase 41 ships only the slot declarations — Phase 42 wires the real email-dispatcher implementation across both the FastAPI composition root and the ARQ worker startup (REG-29-03 double-wire parity); Phase 43 wires the session-invalidator from `app.main.create_app`; Phase 44 reuses the same invalidator slot for password-reset/confirm.

3. **D-41-27/28 import-linter + SVC001 scope extensions** — `.importlinter` `modules-independent` contract gains `app.modules.users` (forces Phase 43 users.service to interact with other modules through Protocol slots only). The SVC001 commit-gate walker's `_INSPECTED_SERVICES` tuple gains `modules/users/service.py` and `modules/auth/password_reset_service.py`. Both targets ship as empty module-docstring-only placeholder files at Phase 41 — they pass the SVC001 gate trivially (zero functions → zero offenders), and the pinning is the anti-silent-drop guarantee D-41-28 requires: Phase 43/44 cannot land write-path service code that bypasses SVC001 because both files are already in scope before the first feature commit.

## Tasks Completed

| # | Task | Files | Commit |
|---|------|-------|--------|
| 1 | Hoist User ORM to `app/core/models.py` + shim in `auth/models.py` | `app/core/models.py` (new), `app/modules/auth/models.py` (shim) | `1b63d83` |
| 2 | Declare EmailDispatcher + UserSessionInvalidator Protocol slots | `app/core/dependencies.py` | `68286b8` |
| 3 | `.importlinter` + SVC001 walker scope + 2 placeholder service files | `.importlinter`, `tests/unit/test_service_commit_gate.py`, `app/modules/users/__init__.py`, `app/modules/users/service.py`, `app/modules/auth/password_reset_service.py` | `0024a24` |

## Verification Results

- `uv run python -c "from app.core.models import User as A; from app.modules.auth.models import User as B; assert A is B"` — **identical class object** (shim is byte-identity re-export).
- `uv run python -c "from app.core.dependencies import EmailDispatcher, UserSessionInvalidator, register_email_dispatcher, get_email_dispatcher, register_user_session_invalidator, get_user_session_invalidator"` — all 6 names importable.
- `get_email_dispatcher()` pre-registration → raises `RuntimeError` (defensive accessor) ✓
- `get_user_session_invalidator()` pre-registration → raises `RuntimeError` (defensive accessor) ✓
- `uv run mypy app/core/models.py app/modules/auth/models.py app/core/dependencies.py` → **Success: no issues found in N source files** ✓
- `uv run lint-imports --config .importlinter` → **3 contracts kept, 0 broken** (core-not-depend-on-modules KEPT; modules-independent KEPT with `app.modules.users` newly listed; integrations-not-depend-on-modules KEPT) ✓
- `uv run pytest tests/unit/test_service_commit_gate.py -x -q` → **7 passed** (live gate plus 6 synthetic-source tests) ✓
- `uv run pytest tests/unit/ -q --deselect tests/unit/test_permissions.py` → **370 passed, 249 deselected** ✓
  - Note: `tests/unit/test_permissions.py` was already failing on `master` before Plan 41-10 (4 failures, all `OWNER_ONLY` / action / resource enum drift unrelated to the User hoist / slot declarations / SVC001 extension). Pre-existing failure verified via `git stash` round-trip; logged to `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md`.

## Deviations from Plan

None — plan executed exactly as written. The one out-of-scope finding (pre-existing `test_permissions.py` failures) was logged to `deferred-items.md` per the SCOPE BOUNDARY rule and is not a Plan 41-10 regression.

## Decisions Made

- **D-41-01 confirmed in code.** The hoist moves only `class User`; `RefreshToken` and `OtpCode` stay in `app/modules/auth/models.py` (auth-only concerns, no other module imports them). The new `app/core/models.py` contains User and only User; future additions land here only if they have the same "shared between auth and another module" justification.
- **D-41-02 shim is byte-identity, not subclass.** A `from app.core.models import User` re-export gives `app.modules.auth.models.User is app.core.models.User` — every isinstance check, every SQLAlchemy registry lookup, every `Mapper[User]` reference works without change. A subclass would have split the ORM mapper across two `Mapper` instances and broken the alembic autogenerate.
- **D-41-24/25 defensive-raise mirrors `get_payment_recorder` precedent.** Both new slots' `get_*` accessors raise `RuntimeError` when unregistered (vs. the `resolve_active_membership` silent-None pattern at line 117 of `dependencies.py`). The choice tracks the consumer's failure semantics: email-issuing flows and user-deactivation flows cannot proceed silently without their slot — a missing registration is misconfiguration, not an expected zero-result case. Mirrors D-32-14's PaymentRecorder pattern.
- **D-41-28 placeholder files are module-docstring only.** No `def _phase_41_placeholder() -> None: pass` stub function — the existing walker (`_iter_functions_in_file`) yields nothing for docstring-only files, so `_check_function` is never invoked and the gate passes trivially. This matches the documented Phase 30 INFRA-21 pattern ("A zero-function service passes the gate trivially (no functions → no offenders)") — the walker already handles empty-file admit without code changes.

## Known Stubs

Two intentional stubs are introduced at Phase 41 — both are SVC001 anti-silent-drop pins, not regressions:

- `apps/backend/app/modules/users/service.py` — module-docstring only. Phase 43 USERS-01 fills this with multi-user admin CRUD (create/update/deactivate/reactivate/soft-delete/list). The placeholder is required by D-41-28 so the SVC001 walker can include the path in its scope before the first write-path commit lands.
- `apps/backend/app/modules/auth/password_reset_service.py` — module-docstring only. Phase 44 RESET-01/02/03 fills this with password-reset request / confirm / invitation accept / invitation revoke. Same D-41-28 anti-silent-drop justification.

Both are explicitly documented in their module docstrings with the future phase reference; neither is wired into any consumer at Phase 41 (no routers, no main.py imports). They are scope-pins only.

## Threat Flags

None — Plan 41-10 introduces no new network endpoints, no auth paths, no file-access patterns, and no schema changes. The `<threat_model>` block in 41-10-PLAN.md anticipated the three threats (rogue late-arriving register_* call, cross-module direct ORM import, SVC001 placeholder hiding future drift); none of them are activated at Phase 41 (no register_* callsite, no users.service code, both placeholders are AST-empty).

## Self-Check: PASSED

Files verified to exist:
- `apps/backend/app/core/models.py` ✓
- `apps/backend/app/modules/auth/models.py` (shim) ✓
- `apps/backend/app/core/dependencies.py` (with new slots) ✓
- `apps/backend/.importlinter` (with `app.modules.users` listed) ✓
- `apps/backend/tests/unit/test_service_commit_gate.py` (with extended `_INSPECTED_SERVICES`) ✓
- `apps/backend/app/modules/users/__init__.py` ✓
- `apps/backend/app/modules/users/service.py` ✓
- `apps/backend/app/modules/auth/password_reset_service.py` ✓
- `.planning/phases/41-infra-bedrock-anti-oracle-scaffold/deferred-items.md` ✓

Commits verified to exist:
- `1b63d83` refactor(41-10): hoist User ORM to app.core.models with auth shim ✓
- `68286b8` feat(41-10): declare EmailDispatcher + UserSessionInvalidator Protocol slots ✓
- `0024a24` chore(41-10): extend importlinter + SVC001 scope for users + password-reset ✓
