---
phase: 17-membership-instances-resolver-backend
plan: 02
subsystem: backend/core
tags: [core, dependencies, protocol, resolver, composition-root]
requirements: [MEM-05]
dependency_graph:
  requires:
    - "Phase 4 D-24 register_user_loader composition-root carve-out (precedent template)"
    - "apps/backend/.importlinter — core-not-depend-on-modules contract"
  provides:
    - "ActiveMembership Protocol (structural type, 4 attrs)"
    - "ActiveMembershipResolver type alias"
    - "register_active_membership_resolver(resolver) — idempotent setter"
    - "resolve_active_membership(session, client_id) — None-on-unset consumer"
  affects:
    - "Plan 17-03 service.py — will use ActiveMembership as return-type annotation"
    - "Plan 17-04 main.py — will import register_active_membership_resolver and wire the resolver"
tech_stack:
  added: []
  patterns:
    - "Composition-root loader slot (mirror of Phase 4 D-24 register_user_loader)"
    - "Structural typing via typing.Protocol (no app.modules.* imports)"
key_files:
  created: []
  modified:
    - "apps/backend/app/core/dependencies.py — appended 4 new public symbols + date import"
decisions:
  - "Returns None on unset slot (D-16/CD-06) instead of defensive raise like _user_loader — visits service cannot distinguish 'no resolver registered' from 'no active membership' and that's the correct semantic"
  - "Protocol exposes EXACTLY 4 attrs (id, client_id, end_date, status) per D-18 — no snapshot fields, no plan_id, no audit timestamps"
  - "Inserted new block AFTER register_user_loader setter (line 61) and BEFORE get_current_user — keeps the user-loader/resolver setter pair contiguous; consumer functions then follow"
metrics:
  duration_seconds: 86
  completed: "2026-05-07"
  task_count: 1
  file_count: 1
---

# Phase 17 Plan 02: Composition-root resolver slot Summary

Added the second composition-root loader slot to `app/core/dependencies.py`: `ActiveMembership` Protocol, `ActiveMembershipResolver` type alias, idempotent `register_active_membership_resolver` setter, and `resolve_active_membership` consumer (returns None when slot unset). Verbatim mirror of the Phase 4 D-24 `register_user_loader` pattern.

## What was built

A 58-line append to `apps/backend/app/core/dependencies.py` plus one new import (`from datetime import date`):

| Symbol                                | Kind      | Purpose                                                                                                |
| ------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------ |
| `ActiveMembership`                    | Protocol  | Structural type with 4 attrs: `id: UUID, client_id: UUID, end_date: date, status: str` (per D-18)      |
| `ActiveMembershipResolver`            | TypeAlias | `Callable[[AsyncSession, UUID], Awaitable[ActiveMembership \| None]]`                                  |
| `_active_membership_resolver`         | global    | Module-level slot, initialised to `None`                                                               |
| `register_active_membership_resolver` | setter    | Idempotent — re-registering replaces (Phase 4 D-24 pattern; tests can inject stubs)                    |
| `resolve_active_membership`           | consumer  | Plain awaitable (NOT FastAPI Depends per D-16); returns `None` when slot unset (per CONTEXT.md L224)   |

Block placement: between the existing `register_user_loader` setter and the existing `get_current_user` consumer — keeps the two setter declarations contiguous in the file.

## Verification gates

| Gate                               | Result                                                                              |
| ---------------------------------- | ----------------------------------------------------------------------------------- |
| `uv run lint-imports`              | ✅ 3/3 contracts kept (incl. `core-not-depend-on-modules`)                          |
| `uv run mypy app/core/dependencies.py` | ✅ Success: no issues found                                                     |
| `uv run ruff check ...`            | ✅ All checks passed                                                                |
| `uv run python -c "<structural>"`  | ✅ `OK` — Protocol has exactly 4 attrs; None on unset; idempotent re-registration   |
| `uv run pytest tests/unit/ -q`     | ✅ 229 passed (no regressions)                                                      |

Acceptance grep checks (all from PLAN):
- `class ActiveMembership(Protocol):` — present
- `ActiveMembershipResolver = Callable[` — present
- `_active_membership_resolver: ActiveMembershipResolver | None = None` — present
- `def register_active_membership_resolver` — present
- `async def resolve_active_membership` — present
- `from datetime import date` — present
- `from app.modules.*` import count: **0** (importlinter `core-not-depend-on-modules` contract preserved)
- user-loader removal count in diff: **0** (no existing symbols modified)

## Tasks completed

| #   | Task                                                                                  | Commit    | Files                                  |
| --- | ------------------------------------------------------------------------------------- | --------- | -------------------------------------- |
| 1   | Add ActiveMembership Protocol + resolver slot to core/dependencies.py                 | `f5b2863` | apps/backend/app/core/dependencies.py |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None — Protocol surface is intentionally narrow (D-18 mitigates T-17-06); module-level mutable global is the same accepted pattern as `_user_loader` (T-17-05); None-on-unset is the intended semantic (T-17-07); no `app.modules.*` imports added (T-IMPORTLINTER mitigated).

## Known Stubs

None.

## Self-Check: PASSED

- `apps/backend/app/core/dependencies.py` — FOUND (modified)
- Commit `f5b2863` — FOUND in `git log`
- `.planning/phases/17-membership-instances-resolver-backend/17-02-SUMMARY.md` — FOUND
