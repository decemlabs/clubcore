---
phase: 20-telegram-bot-checkin-self-check-in
plan: 01
subsystem: integrations.telegram + core.audit
tags:
  - telegram
  - bot
  - checkin
  - audit
  - anti-oracle
dependency_graph:
  requires:
    - apps/backend/app/integrations/telegram/handlers.py (Phase 7)
    - apps/backend/app/integrations/telegram/sender.py (Phase 7)
    - apps/backend/app/modules/visits/service.py:create_visit_self_checkin (Phase 19)
    - apps/backend/app/core/exceptions.py:{NoActiveMembershipError,DuplicateCheckinError,OutsideGymHoursError,ClientNotLinkedError} (Phase 19)
    - apps/backend/app/core/audit.py:LOCKED_AUDIT_EVENTS (Phase 15)
  provides:
    - HandlerContext 5-field shape (session_factory, telegram_service, sender, visits_service, redis)
    - 4 locked Russian DM constants in handlers.py
    - _hash_telegram_user_id helper (PII minimization)
    - _format_gym_hours helper (U+2013 EN DASH range)
    - checkin_handler (Redis dedup -> service call -> string-name dispatch -> DM)
    - ('telegram_unknown_checkin', 'visit') in LOCKED_AUDIT_EVENTS (29 entries total)
  affects:
    - apps/backend/app/workers/telegram_bot.py (Plan 20-02 will construct HandlerContext with new fields and register checkin_handler)
    - apps/backend/tests/integration/telegram_bot/* (Plan 20-03 will exercise the handler)
tech_stack:
  added:
    - redis.asyncio.Redis (already a transitive dep; first direct import in integrations/telegram)
  patterns:
    - String-name exception dispatch (mirror of Phase 7 D-04/D-20)
    - Redis SET-NX-EX dedup (single atomic call, fail-open per D-20-3)
    - Handler-owned audit emit + commit on the unknown-checkin path (D-20-10)
    - Anti-oracle DM reuse (D-20-9 ClientNotLinkedError -> _DM_NO_MEMBERSHIP)
key_files:
  created: []
  modified:
    - apps/backend/app/integrations/telegram/handlers.py
    - apps/backend/app/core/audit.py
    - apps/backend/tests/unit/test_audit_taxonomy.py
decisions:
  - D-20-1 in-handler dedup honoured (no global ptb middleware, no decorator)
  - D-20-2 Redis client arrives via HandlerContext field (not app.state)
  - D-20-3 fail-open on Redis errors (DB UNIQUE is the real anti-replay backstop)
  - D-20-4 silent on dedup hit (structlog DEBUG only)
  - D-20-5 single SET NX EX atomic redis-py call
  - D-20-6 keyspace sz:bot:update:{update_id} TTL 3600s
  - D-20-7 4 locked Russian DM constants verbatim from AUTH-TG-11
  - D-20-8 _format_gym_hours joins HH:MM with U+2013 EN DASH
  - D-20-9 ClientNotLinkedError reuses _DM_NO_MEMBERSHIP (anti-oracle)
  - D-20-10 telegram_unknown_checkin pair on resource_type='visit'
metrics:
  duration_minutes: 5
  completed_date: 2026-05-08
  tasks_completed: 3
  files_changed: 3
---

# Phase 20 Plan 01: Telegram /checkin handler + audit lock Summary

One-liner: Extend HandlerContext with `visits_service` + `redis` fields, ship the `/checkin` handler with Redis SET-NX-EX dedup and string-name visit-exception dispatch, and lock the `telegram_unknown_checkin` audit pair (D-20-10).

## What Changed

### `apps/backend/app/integrations/telegram/handlers.py`

| Surface | Lines | Notes |
|---------|-------|-------|
| `from redis.asyncio import Redis` import | 25 (re-sorted by ruff into the `redis` block alongside structlog) | New direct import |
| `HandlerContext` NamedTuple | 49–66 | Now 5 fields: `session_factory, telegram_service, sender, visits_service, redis` |
| 4 locked Russian DM constants | 77–80 | `_DM_CHECKIN_OK`, `_DM_NO_MEMBERSHIP` (with `# noqa: RUF001` on line 78), `_DM_DUPLICATE`, `_DM_OUTSIDE_HOURS` |
| `_hash_telegram_user_id` | 103–110 | sha256 hex helper for PII minimization in audit payload |
| `_format_gym_hours` | 112–127 | Returns `'HH:MM–HH:MM'` joined by U+2013 EN DASH; defensive `RuntimeError` on missing fields. `# noqa: RUF001` on the f-string return at line 127 |
| `checkin_handler` | 234–322 | Defensive guard, Redis dedup, service call, exception-name ladder over 4 visit-exception class names, anti-oracle DM reuse for `ClientNotLinkedError` + handler-owned audit emit |
| Module docstring | extended (top of file) | New "/checkin handler" step ladder paragraph (lines ~17–28) |

### `apps/backend/app/core/audit.py`

- Docstring inventory: added a `## v1.2 (Phase 20 — bot self check-in unknown-tg)` block under the existing v1.2 visit lines listing `telegram_unknown_checkin {chat_id, telegram_user_id_hash}` -> `'visit'`.
- `LOCKED_AUDIT_EVENTS` frozenset: appended `("telegram_unknown_checkin", "visit"),` after the existing `("visit_rejected_outside_hours", "visit"),`. Frozenset count moved **28 -> 29**.

### `apps/backend/tests/unit/test_audit_taxonomy.py`

- `test_locked_audit_events_has_expected_count` updated: docstring now reads `18 v1.1 + 11 v1.2 = 29` and the assertion checks `len(LOCKED_AUDIT_EVENTS) == 29`. Test passes.

## U+2013 EN DASH confirmation

- The literal U+2013 character is present in `_format_gym_hours` at line 127 inside `f"{open_t}–{close_t}"`.
- `python3 -c "import unicodedata; print(unicodedata.name('–'))"` prints `EN DASH`.
- The runtime smoke `_format_gym_hours(OutsideGymHoursError('outside_gym_hours', fields={'open': '07:00:00', 'close': '23:00:00'}))` returns `'07:00–23:00'` (verified via the Task 1 automated verify command).

## RUF001 noqa lines added

| File | Line | Reason |
|------|------|--------|
| `apps/backend/app/integrations/telegram/handlers.py` | 78 | Cyrillic `У` in `_DM_NO_MEMBERSHIP` |
| `apps/backend/app/integrations/telegram/handlers.py` | 127 | U+2013 EN DASH in `f"{open_t}–{close_t}"` (D-20-8) |

The `_format_gym_hours` docstring originally contained a U+2013 (RUF002) but the noqa-on-docstring approach interacts badly with multi-line docstrings; the docstring was rephrased to use ASCII hyphen while the f-string body keeps the U+2013 EN DASH. The locked pattern (`'07:00–23:00'` runtime output) is unaffected.

## Verification

| Check | Command | Result |
|-------|---------|--------|
| Ruff (handlers + audit + tests) | `cd apps/backend && uv run ruff check app/integrations/telegram/handlers.py app/core/audit.py tests/unit/test_audit_taxonomy.py` | All checks passed |
| mypy strict (handlers + audit) | `cd apps/backend && uv run mypy app/integrations/telegram/handlers.py app/core/audit.py` | Success: no issues found in 2 source files |
| import-linter | `cd apps/backend && uv run lint-imports` | 3 kept, 0 broken |
| pytest taxonomy | `cd apps/backend && uv run pytest tests/unit/test_audit_taxonomy.py -q` | 3 passed |
| Runtime smoke | `python -c "from app.integrations.telegram.handlers import …; print('ok')"` | `ok` |
| Frozenset assertion | `len(LOCKED_AUDIT_EVENTS) == 29` and `('telegram_unknown_checkin', 'visit') in LOCKED_AUDIT_EVENTS` | both true |

## Anti-oracle Invariants Preserved

- `ClientNotLinkedError` -> `_DM_NO_MEMBERSHIP` (the SAME constant `NoActiveMembershipError` uses). A stranger sending `/checkin` from an unbound chat sees the same DM as a linked-but-no-membership client. The dispatch ladder carries an inline comment forbidding "fixing" this to a 5th honest-UX string.
- The 4 locked DM constants are verbatim per AUTH-TG-11 (D-20-7) — no interpolation on success (`"✅ Отмечено"`), `{hours}` is the only interpolation on the outside-hours path.
- No `from app.modules.*` and no `from app.core.exceptions import` in `handlers.py` — verified by `^from` start-of-line grep returning zero matches; `lint-imports` exits 0 with `integrations must not import modules KEPT`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reorder `redis.asyncio` import to satisfy ruff I001**
- **Found during:** Task 1 (`uv run ruff check` after first add)
- **Issue:** Plan suggested placing `from redis.asyncio import Redis` directly under `import hashlib`, which produced `I001 Import block is un-sorted or un-formatted` because `redis.asyncio` is a third-party import that must group with `structlog`/`sqlalchemy`, not with stdlib `hashlib`/`types`/`typing`.
- **Fix:** Moved `from redis.asyncio import Redis` into the third-party block (alongside `structlog` and `sqlalchemy.ext.asyncio`).
- **Files modified:** `apps/backend/app/integrations/telegram/handlers.py`
- **Commit:** 7b2b7dd

**2. [Rule 3 - Blocking] Replace U+2013 EN DASH in `_format_gym_hours` docstring with ASCII hyphen**
- **Found during:** Task 1 (`uv run ruff check` after adding helpers)
- **Issue:** RUF002 fires on EN DASH inside docstrings. Putting `# noqa: RUF002` on the line of the docstring text was treated as docstring content, not a noqa directive; placing it on the `def` line yielded `RUF100 Unused noqa`.
- **Fix:** Rephrased the docstring summary to spell out "joined by U+2013 EN DASH" using ASCII hyphens, while keeping the literal U+2013 in the runtime f-string return at line 127 (that line carries `# noqa: RUF001`). The locked output `'07:00–23:00'` (D-20-8) is unaffected.
- **Files modified:** `apps/backend/app/integrations/telegram/handlers.py`
- **Commit:** 7b2b7dd

**3. [Rule 3 - Blocking] Drop `# noqa: BLE001` directives ruff flagged as non-enabled**
- **Found during:** Task 2 (`uv run ruff check` after adding `checkin_handler`)
- **Issue:** Plan suggested `except Exception as exc:  # noqa: BLE001 …`, but the project's ruff config does NOT enable `BLE001`, so the noqa was reported as `RUF100 Unused noqa directive (non-enabled: BLE001)`.
- **Fix:** Removed the `noqa: BLE001` directives, kept the inline rationale comment (`# fail-open per D-20-3`, `# string-name dispatch (integrations perp modules)`).
- **Files modified:** `apps/backend/app/integrations/telegram/handlers.py`
- **Commit:** e4417c8

**4. [Rule 3 - Blocking] Wrap long docstring lines in `checkin_handler` module paragraph**
- **Found during:** Task 2 (`uv run ruff check`)
- **Issue:** Several lines of the new "/checkin handler" docstring paragraph exceeded the 100-char limit and tripped E501.
- **Fix:** Re-wrapped at 100 chars while preserving the step ladder content verbatim.
- **Files modified:** `apps/backend/app/integrations/telegram/handlers.py`
- **Commit:** e4417c8

**5. [Rule 3 - Blocking] Wrap audit.py docstring inventory line for v1.2 Phase 20 entry**
- **Found during:** Task 3 (`uv run ruff check app/core/audit.py`)
- **Issue:** The single-line `- telegram_unknown_checkin    {chat_id, telegram_user_id_hash}    # 'visit' (Phase 20 D-20-10)` exceeded 100 chars (E501).
- **Fix:** Split the comment onto a continuation line; payload + resource description still readable.
- **Files modified:** `apps/backend/app/core/audit.py`
- **Commit:** f6fa4f4

All five fixes are formatting/lint-tooling adjustments that preserve the locked invariants (D-20-* and the verbatim Russian DM strings). No semantic deviation from the plan.

## Commits

| Task | Commit | Subject |
|------|--------|---------|
| 1 | 7b2b7dd | feat(20-01): extend HandlerContext + locked DM constants + helpers in handlers.py |
| 2 | e4417c8 | feat(20-01): add checkin_handler with Redis dedup and exception-name dispatch |
| 3 | f6fa4f4 | feat(20-01): lock telegram_unknown_checkin audit pair (D-20-10) |

## Self-Check: PASSED

- File `apps/backend/app/integrations/telegram/handlers.py` exists (322 lines).
- File `apps/backend/app/core/audit.py` exists with 29-entry frozenset.
- File `apps/backend/tests/unit/test_audit_taxonomy.py` exists with `== 29` assertion (count `== 28` returns 0).
- Commits 7b2b7dd, e4417c8, f6fa4f4 exist in `git log --oneline`.
- All overall verifications (`ruff`, `mypy`, `lint-imports`, `pytest tests/unit/test_audit_taxonomy.py`) exit 0.
- Final smoke import `from app.integrations.telegram.handlers import HandlerContext, _DM_CHECKIN_OK, …, checkin_handler, …` succeeds and prints `ok`.
