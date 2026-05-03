---
phase: 08-clients-module-audit-log
plan: 02
subsystem: infra
tags: [audit, structlog, sqlalchemy-async, async, transactions]

requires:
  - phase: 05-user-schema-email-password-auth
    provides: structlog `audit.emit()` sync stub + locked event-name registry (D-21)
  - phase: 07-telegram-otp-channel
    provides: locked Telegram event names (telegram_deep_link_issued, otp_*, telegram_*) consumed by emit's docstring contract
  - phase: 08-clients-module-audit-log
    provides: AuditLog ORM model from Plan 01 (Wave 1, parallel) — imported as `from app.core.audit_models import AuditLog`
provides:
  - "async def emit(session, event, *, actor_user_id, resource_type, resource_id=None, **payload) — co-transactional structlog INFO + DB INSERT (D-04)"
  - "Caller-owned-transaction contract (D-03): emit() never calls session.commit() / session.flush()"
  - "Phase 8 event-name additions in docstring: client_created, client_updated, client_soft_deleted"
affects:
  - "08-03 (clients service-layer) — will await audit.emit(...) for client_* events"
  - "08-04 (clients router/schemas) — indirect; relies on service-layer audit calls"
  - "08-05 (call-site migration) — owns the rewrite of all 15 existing emit(...) call-sites in auth/service.py, auth/router.py, telegram_service.py, telegram/handlers.py"
  - "08-08 (tests) — DB-row visibility tests rely on this co-transactional INSERT"

tech-stack:
  added: []
  patterns:
    - "Co-transactional audit pattern: caller's AsyncSession enrolls AuditLog row in same transaction (atomic with mutation)"
    - "Structured async logging primitive: signature forces actor + resource taxonomy at every call-site"

key-files:
  created: []
  modified:
    - "apps/backend/app/core/audit.py — sync passthrough → async + DB INSERT"

key-decisions:
  - "D-03 satisfied: emit() body has zero session.commit()/session.flush() calls (verified via AST)"
  - "D-04 satisfied: signature matches locked spec verbatim (5 typed params, **payload kwargs)"
  - "Module-level __all__ NOT added — current file did not export it; preserved existing surface"

patterns-established:
  - "Pattern: Audit primitive lives in `app.core.*` and imports its ORM peer from a sibling `app.core.audit_models` (keeps `core ⊥ modules` import-linter contract intact while allowing structured DB writes)"
  - "Pattern: Audit emit() docstring is the single source of truth for the locked event-name registry (Phase 5 D-21 + Phase 7 D-04/D-11 + Phase 8 D-04)"

requirements-completed: [AUDIT-01, AUDIT-02]

duration: ~3min
completed: 2026-05-03
---

# Phase 08 Plan 02: Async audit.emit with co-transactional DB INSERT — Summary

**`app/core/audit.py:emit()` rewritten from sync structlog passthrough to `async def` that performs `structlog.info(...)` + `session.add(AuditLog(...))` in the caller's transaction (D-03, D-04).**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-03T08:40:00Z (approx)
- **Completed:** 2026-05-03T08:43:24Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- `emit()` is now `async def emit(session: AsyncSession, event: str, *, actor_user_id: UUID | None, resource_type: str, resource_id: UUID | None = None, **payload: Any) -> None`.
- Body performs `structlog.get_logger("audit").info(event, **payload)` then `session.add(AuditLog(...))` — no commit/flush.
- AuditLog imported from `app.core.audit_models` (sibling module produced by Plan 01 in Wave 1).
- Docstring updated with the three Phase 8 events (`client_created`, `client_updated`, `client_soft_deleted`) added to the existing Phase 5/7 locked event registry.
- Architectural constraint preserved: `app.core.audit` does not import from `app.modules.*` (import-linter `core-not-depend-on-modules` contract intact).

## Task Commits

1. **Task 1: Refactor app/core/audit.py:emit() to async + DB INSERT (D-04)** — `2b0913c` (refactor)

## Files Created/Modified

- `apps/backend/app/core/audit.py` — Rewrote module: added `from uuid import UUID`, `from sqlalchemy.ext.asyncio import AsyncSession`, `from app.core.audit_models import AuditLog`; replaced sync `emit()` with async coroutine that enrolls AuditLog in caller's transaction; expanded docstring to enumerate all 16 locked event names (13 Phase 5/7 + 3 Phase 8).

## Final emit() Signature

```python
async def emit(
    session: AsyncSession,
    event: str,
    *,
    actor_user_id: UUID | None,
    resource_type: str,
    resource_id: UUID | None = None,
    **payload: Any,
) -> None:
    structlog.get_logger("audit").info(event, **payload)
    session.add(
        AuditLog(
            action=event,
            actor_user_id=actor_user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            payload=payload,
        )
    )
```

## D-03 Compliance: No commit/flush leak

AST scan of the produced file confirmed there are **zero** `session.commit()` or `session.flush()` calls in the function body. The two textual matches a naive `grep` reports are inside docstrings (lines 7 and 54), where they describe the contract — not invoke it. Verified via:

```python
import ast
tree = ast.parse(open('app/core/audit.py').read())
# walk Call nodes for session.commit/flush — result: 0 hits
```

## Verification Results

| Check | Status |
|-------|--------|
| `grep -q "async def emit("` | PASS |
| `grep -q "session: AsyncSession"` | PASS |
| `grep -q "actor_user_id: UUID \| None"` | PASS |
| `grep -q "resource_type: str"` | PASS |
| `grep -q "resource_id: UUID \| None = None"` | PASS |
| `grep -q "from app.core.audit_models import AuditLog"` | PASS |
| `grep -q "session.add("` | PASS |
| AST scan for `session.commit()`/`session.flush()` calls | PASS (0 hits) |
| `uv run ruff check app/core/audit.py` | PASS |
| `uv run mypy --strict app/core/audit.py` | EXPECTED-MISS — `[import-not-found]` for `app.core.audit_models` (Plan 01 produces it in parallel; resolves after orchestrator merges Wave 1) |
| `inspect.iscoroutinefunction(emit)` | EXPECTED-MISS — same root cause (cannot import file because `audit_models` not in this worktree) |

The two EXPECTED-MISS rows are explicitly anticipated by the plan's Wave-1 design (PLAN frontmatter `wave: 1` for both 08-01 and 08-02; orchestrator merges Wave 1 worktrees before Wave 2 runs). The plan's acceptance criteria explicitly allow downstream import errors at this stage.

## Decisions Made

- Followed plan exactly. The locked target body, signature, and docstring additions were authoritative — no judgement calls beyond preserving the existing module-level export shape (no `__all__` was present; none added).

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- **`audit_models.py` not present in this worktree.** This is the documented Wave 1 parallelism: Plan 01 (which creates `audit_models.py`) runs in a sibling worktree concurrently. The orchestrator merges all Wave 1 outputs before Wave 2 starts, at which point the import resolves and `mypy --strict app/` becomes clean.
- **Naive grep for `session.commit\|session.flush` matches docstring text** describing the contract. Used AST walk to confirm zero actual call expressions. Documented above under "D-03 Compliance".

## Call-site Migration Status

**Out of scope for this plan.** The 15 existing `audit.emit(...)` call-sites in `auth/service.py`, `auth/router.py`, `telegram_service.py`, and `telegram/handlers.py` will not compile against this new signature. Plan 05 (Wave 2, `depends_on: [02]`) owns that migration. This is the documented expected state during the gap between Wave 1 and Wave 2.

## Next Phase Readiness

- Plans 03/04/05 (Wave 2) can rely on the new async signature — they were planned against it.
- After Wave 1 merge: `app.core.audit_models.AuditLog` becomes resolvable, `mypy --strict app/core/audit.py` will clear, and only the 15 call-sites remain to migrate (Plan 05).

## Self-Check: PASSED

- File `apps/backend/app/core/audit.py` exists and contains `async def emit(`. Verified.
- Commit `2b0913c` exists in `git log --oneline -5` of this worktree branch. Verified.
- SUMMARY.md path `.planning/phases/08-clients-module-audit-log/08-02-SUMMARY.md` written. Verified.

---
*Phase: 08-clients-module-audit-log*
*Plan: 02*
*Completed: 2026-05-03*
