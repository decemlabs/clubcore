---
phase: 19-visits-db-reception-check-in-backend
plan: "02"
subsystem: backend
tags: [cross-module-resolver, protocol-pattern, composition-root, visits, clients]
dependency_graph:
  requires:
    - "17-04 (register_active_membership_resolver pattern established)"
    - "Phase 5 (register_user_loader pattern established)"
  provides:
    - "ClientByTelegram Protocol + resolver slot in core/dependencies.py"
    - "resolve_client_by_telegram_user_id in clients/service.py"
    - "Composition-root wiring in app/main.py (third carve-out)"
  affects:
    - "19-03 (visits/service.py consumes resolve_client_by_telegram_user_id via slot)"
    - "Phase 20 (bot /checkin handler uses visits.service.create_visit_self_checkin)"
tech_stack:
  added: []
  patterns:
    - "Third cross-module Protocol resolver slot (mirrors Phase 5 UserLoader + Phase 17 ActiveMembershipResolver)"
    - "Composition-root local import inside create_app() body"
key_files:
  created: []
  modified:
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/modules/clients/service.py
    - apps/backend/app/main.py
decisions:
  - "D-02 (Phase 19): ClientByTelegramResolver Protocol pattern — third cross-module resolver after Phase 5/17"
  - "Client imported at runtime in clients/service.py for resolve_client_by_telegram_user_id (deviation from previous 'never import Client ORM' note — documented in module docstring)"
  - "Local import inside create_app() body for clients_service (ruff I001 fix required parenthesized form)"
metrics:
  duration: "4min"
  completed: "2026-05-07"
  tasks_completed: 2
  files_modified: 3
---

# Phase 19 Plan 02: ClientByTelegram Protocol Resolver Summary

ClientByTelegram Protocol + setter + consumer in core/dependencies.py plus alive-client resolver in clients/service.py, wired at composition root as the third cross-module resolver slot.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | ClientByTelegram Protocol + slot + setter + consumer in core/dependencies.py | 0a3c3c6 | app/core/dependencies.py |
| 2 | clients/service.py resolver function + app/main.py wiring | 00d5434 | app/modules/clients/service.py, app/main.py |

## What Was Built

### Task 1 — core/dependencies.py extension (5 new top-level names)

Appended immediately after the existing `resolve_active_membership` consumer (lines 119+):

1. **`class ClientByTelegram(Protocol)`** — narrow structural type exposing ONLY `id: UUID`. Phase 19 visits service consumes only `.id` (passes it to `_create_visit_with_anti_fraud`). Deliberately narrow: adding attributes here expands the cross-module surface area.

2. **`ClientByTelegramResolver`** — type alias `Callable[[AsyncSession, int], Awaitable[ClientByTelegram | None]]`. The `int` parameter is `telegram_user_id` (Telegram user IDs are BigInt); returns `None` when no alive Client matches.

3. **`_client_by_telegram_resolver: ClientByTelegramResolver | None = None`** — module-level slot, default `None`. Test-stub-friendly: unset slot returns `None` from the consumer, which visits.service treats as "unknown caller" → `ClientNotLinkedError`.

4. **`register_client_by_telegram_resolver(resolver)`** — idempotent composition-root setter. Explicitly documented as "third loader slot after `register_user_loader` (Phase 5 D-15) and `register_active_membership_resolver` (Phase 17 D-18)".

5. **`async def resolve_client_by_telegram_user_id(session, telegram_user_id)`** — consumer entry point. Returns `None` when slot is unset; otherwise delegates to `_client_by_telegram_resolver(session, telegram_user_id)`. Used by `app.modules.visits.service` in Phase 19.

### Task 2 — clients/service.py: resolve_client_by_telegram_user_id

New function placed at the bottom of `app/modules/clients/service.py` alongside other service helpers:

```python
async def resolve_client_by_telegram_user_id(
    session: AsyncSession,
    tg_user_id: int,
) -> Client | None:
    stmt = select(Client).where(
        Client.telegram_user_id == tg_user_id,
        Client.deleted_at.is_(None),   # alive-only — T-19-02-01 mitigated
    )
    result: Client | None = await session.scalar(stmt)
    return result
```

Both filters are required:
- `Client.telegram_user_id == tg_user_id` — Telegram identity match
- `Client.deleted_at.is_(None)` — alive-only guard (STRIDE T-19-02-01: soft-deleted clients are invisible)

Imports added: `select` from `sqlalchemy`, `Client` from `app.modules.clients.models` (moved from `TYPE_CHECKING` to runtime import — necessary for `select(Client)` query construction). Module docstring updated to document this exception to the previous "never import Client ORM" invariant.

### Task 2 — app/main.py composition-root wiring

Added immediately after `register_active_membership_resolver(resolve_active_membership_by_client)`:

```python
# Phase 19 D-02: third composition-root carve-out
from app.modules.clients import (
    service as clients_service,
)

register_client_by_telegram_resolver(
    clients_service.resolve_client_by_telegram_user_id,
)
```

Import uses parenthesized form (ruff I001 requirement for local imports inside function bodies). Added `register_client_by_telegram_resolver` to the top-of-file import from `app.core.dependencies`.

Module docstring updated with "Phase 19 additions" section. `create_app()` docstring composition order updated to reflect step 8 (third slot).

## Alive-Client Filter (Threat Mitigation)

T-19-02-01 (Information Disclosure): `resolve_client_by_telegram_user_id` queries BOTH `telegram_user_id == tg_user_id` AND `deleted_at IS NULL`. Soft-deleted clients with a previously-linked Telegram account are structurally invisible — no code path can return a deleted client through this resolver. This is consistent with the `clients.repository.get_alive` pattern.

T-19-02-02 (Tampering — cross-module import bypass): `lint-imports` passes with all 3 contracts KEPT. The `visits.service → core.dependencies` edge is modules→core (allowed); `app.main → app.modules.clients` is a composition-root exception (same precedent as Phase 17's `app.main → app.modules.memberships`).

## Verification Results

| Check | Result |
|-------|--------|
| `grep -c 'class ClientByTelegram(Protocol):'` | 1 (exactly one) |
| `grep -c 'class ActiveMembership(Protocol):'` | 1 (unchanged) |
| Smoke test (stub resolver injection via slot) | OK |
| `create_app()` slot registration smoke test | OK (`_client_by_telegram_resolver is not None`) |
| `uv run lint-imports` | Contracts: 3 kept, 0 broken |
| `uv run ruff check` (3 files) | All checks passed |
| `uv run mypy` (3 files, strict) | Success: no issues found |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mypy `no-any-return` on session.scalar()**
- **Found during:** Task 2 verification
- **Issue:** `session.scalar(stmt)` returns `Any` in mypy's SA 2.0 stubs; assigning directly to the return annotation triggered `Returning Any from function declared to return "Client | None"`.
- **Fix:** Added explicit typed intermediate: `result: Client | None = await session.scalar(stmt)` then `return result`. Standard pattern already used throughout `memberships/repository.py`.
- **Files modified:** `apps/backend/app/modules/clients/service.py`
- **Commit:** 00d5434 (included in same task commit)

**2. [Rule 1 - Bug] Ruff I001 + E501 on local import in create_app()**
- **Found during:** Task 2 verification
- **Issue:** `from app.modules.clients import service as clients_service  # comment` triggered `I001 Import block is un-sorted` and `E501 Line too long (101 > 100)`.
- **Fix:** `uv run ruff check --fix` reformatted to parenthesized multi-line form: `from app.modules.clients import (\n    service as clients_service,\n)`. This is the ruff-canonical form for local imports inside function bodies.
- **Files modified:** `apps/backend/app/main.py`
- **Commit:** 00d5434 (included in same task commit)

**3. [Rule 2 - Missing Critical Functionality] Module docstring drift**
- **Found during:** Task 2 implementation
- **Issue:** `clients/service.py` module docstring stated "The runtime module never imports the `Client` ORM" — this became false when the new function required `Client` at runtime for `select(Client)`.
- **Fix:** Updated docstring to document the exception (Phase 19 D-02 carve-out) so future contributors understand the intent.
- **Files modified:** `apps/backend/app/modules/clients/service.py`
- **Commit:** 00d5434 (included in same task commit)

## Known Stubs

None. All new code is fully functional with no placeholder values.

## Threat Flags

None. All new network surface is constrained to the existing `POST /api/v1/visits` path (Phase 19-03+). The new resolver slot introduces no new HTTP endpoints or auth paths. The alive-client filter directly mitigates T-19-02-01.

## Self-Check: PASSED

- `apps/backend/app/core/dependencies.py` — exists, contains all 5 new names
- `apps/backend/app/modules/clients/service.py` — exists, contains `resolve_client_by_telegram_user_id`
- `apps/backend/app/main.py` — exists, contains `register_client_by_telegram_resolver` call
- Task 1 commit `0a3c3c6` — verified in git log
- Task 2 commit `00d5434` — verified in git log
