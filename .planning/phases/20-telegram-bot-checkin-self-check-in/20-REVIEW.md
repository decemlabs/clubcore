---
phase: 20-telegram-bot-checkin-self-check-in
reviewed: 2026-05-08T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - apps/backend/app/integrations/telegram/handlers.py
  - apps/backend/app/workers/telegram_bot.py
  - apps/backend/app/core/audit.py
  - apps/backend/tests/integration/telegram_bot/test_checkin_handler.py
  - apps/backend/tests/integration/telegram_bot/test_handler_context_shape.py
  - apps/backend/tests/integration/telegram_bot/test_worker_handlers_registered.py
  - apps/backend/tests/integration/telegram/test_handler_start.py
  - apps/backend/tests/unit/telegram_bot/test_format_gym_hours.py
  - apps/backend/tests/unit/telegram_bot/test_hash_telegram_user_id.py
  - apps/backend/tests/unit/test_audit_taxonomy.py
findings:
  blocker: 0
  warning: 3
  suggestion: 5
  total: 8
status: issues_found
---

# Phase 20: Code Review Report

**Reviewed:** 2026-05-08
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Implementation faithfully honors every locked CONTEXT decision (D-20-1..10):
in-handler Redis SET-NX-EX, fail-open path, silent replay, four locked Russian
DM constants verbatim, U+2013 EN DASH formatting, anti-oracle reuse of
`_DM_NO_MEMBERSHIP` for `ClientNotLinkedError`, handler-owned audit emit with
explicit commit on the unknown-checkin branch, `type(exc).__name__`
string-dispatch (no `app.modules.visits` import), sha256 hash of
`telegram_user_id` in audit + structlog. The audit taxonomy frozenset is
correctly extended and the AST walker count bumped 28→29.

No correctness or security BLOCKER was found. Three WARNING-class issues:
(1) one test contains a real wall-clock race (flaky once a day around midnight
MSK); (2) the handler's broad `except Exception` for the Redis dedup path
masks `BaseException`-adjacent failures during test stubbing in a way that
could hide a programmer error; (3) the duplicate-test path silently relies on
service-layer behavior that already commits the pre-seeded visit row,
producing a fragile coupling between the test fixture and the SAVEPOINT
infrastructure.

## Warnings

### WR-01: `test_checkin_outside_hours` is wall-clock-flaky once per day

**File:** `apps/backend/tests/integration/telegram_bot/test_checkin_handler.py:101-106, 341-376`
**Issue:** `_close_gym_hours` sets `gym_hours_end = time(0, 1)` and `gym_hours_start = time(0, 0)`. The Phase 19 boundary is `[start, end)` (`apps/backend/app/modules/visits/service.py:96`, exclusive end). Whenever the test runs with MSK wall-clock time in `[00:00:00, 00:01:00)` — i.e. for the first 60 seconds of every MSK day — the predicate `start <= now < end` is TRUE, the service does NOT raise `OutsideGymHoursError`, the happy-path branch fires, the handler sends `"✅ Отмечено"` and the assertion `assert stub_telegram_sender.text_calls == [(chat_id, expected_dm)]` fails. The plan does not pin time (no `freezegun`/`monkeypatch` of `_now_msk`).
**Fix:** Either pin a deterministic clock for this test (preferred) or pick a closed window that genuinely cannot contain wall-clock MSK during a CI/dev run, e.g. set `gym_hours_start=time(3, 0)` and `gym_hours_end=time(3, 1)` AND monkeypatch `app.modules.visits.service._now_msk` to a known value. The current sub-minute window plus reliance on real wall-clock time is the same anti-pattern called out by the project's own TESTING conventions (no `new Date(dateOnlyString)` / no implicit clock dependence). Example minimal fix:

```python
def _close_gym_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(3, 0))
    monkeypatch.setattr(settings, "gym_hours_end",   time(4, 0))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    # Pin the clock so the boundary is deterministic.
    from datetime import datetime
    fixed = datetime(2026, 5, 8, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    monkeypatch.setattr(svc_mod, "_now_msk", lambda: fixed)
```

### WR-02: `bot_redis_dedup_unavailable` catch is too broad — swallows programmer errors

**File:** `apps/backend/app/integrations/telegram/handlers.py:260-269`
**Issue:** The fail-open guard is `except Exception as exc:` — it catches `AttributeError`, `TypeError`, `NameError`, etc., not just real Redis transport errors (`redis.exceptions.RedisError`/`ConnectionError`/`TimeoutError`). A future regression where `ctx.redis` becomes `None` (start_handler test already passes `redis=cast(Any, None)` at `tests/integration/telegram/test_handler_start.py:122`) or where `ctx.redis.set` is replaced by something with the wrong signature would be silently swallowed and the handler would proceed under the false belief that "Redis is just down". The structlog WARN message is identical for both legitimate transport failures and programmer errors, defeating ops triage. D-20-3 specifies fail-open on `ConnectionError/TimeoutError/etc.` — the "etc." should be bounded to the redis-py error hierarchy.
**Fix:** Narrow the catch to the Redis exception hierarchy. `redis.exceptions.RedisError` is the documented base class for transport/protocol/server errors; everything outside that is a bug, not an outage.

```python
from redis.exceptions import RedisError

try:
    set_result: Any = await ctx.redis.set(dedup_key, "1", nx=True, ex=3600)
except RedisError as exc:  # fail-open per D-20-3 (transport/server errors only)
    logger.warning(
        "bot_redis_dedup_unavailable",
        update_id=update_id,
        chat_id=chat_id,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    set_result = "OK"
```

### WR-03: `test_checkin_duplicate` couples the SAVEPOINT fixture to service-layer commit semantics in a way that hides a real bug

**File:** `apps/backend/tests/integration/telegram_bot/test_checkin_handler.py:290-333`
**Issue:** The test seeds a `Visit` row at line 306-313 and then `await db_session.commit()` at line 314 — under the SAVEPOINT fixture this is an INNER savepoint commit, not a real commit. The handler then runs and `_create_visit_with_anti_fraud` performs `session.flush()` → `IntegrityError` → `session.rollback()` (visits/service.py:175-176), then emits the `visit_rejected_duplicate` audit and calls `session.commit()` (line 188). Because the test SAVEPOINT was rolled back by the service's `session.rollback()`, the originally-seeded `pre_visit` is GONE from the session view. The test then queries `select(AuditLog).where(AuditLog.action == "visit_rejected_duplicate")` and asserts `len(matching) == 1` — but it does NOT verify the pre-seeded visit still exists, nor does it verify only one Visit row total. If a regression causes the service to emit `visit_rejected_duplicate` without rolling back, the test still passes because the assertion is shape-only. The asymmetry between `test_checkin_duplicate` (does not assert visit count) and `test_checkin_redis_outage_fail_open` (does assert `len(visits) == 1`) lets a future bug slip through.
**Fix:** Add `assert len(visits) == 1` after the audit assertion (mirror test 7's pattern). Also assert the visit row's `id` matches the pre-seeded visit, not a freshly-inserted one, so the rollback path is observable:

```python
visits = (
    await db_session.scalars(select(Visit).where(Visit.client_id == client.id))
).all()
assert len(visits) == 1
assert visits[0].id == pre_visit.id  # rollback preserved the pre-seeded row
```

## Suggestions

### SU-01: `_format_gym_hours` defensive `RuntimeError` results in no DM — silent user failure

**File:** `apps/backend/app/integrations/telegram/handlers.py:112-127, 293-299`
**Issue:** If Phase 19 ever stops populating `fields={'open','close'}`, `_format_gym_hours` raises `RuntimeError("...Phase 19 regression")` from inside the `except Exception as exc:` block at handler line 282-316. The `RuntimeError` propagates up, escapes the `async with ctx.session_factory()` context, and lands in ptb's `_global_error_handler` — but the user receives NO DM at all. Defensive design is correct (better than malformed DM); however, the user UX is "bot is silent during outside-hours regression". An ops-targeted observation, not a correctness bug.
**Fix (optional):** Catch the `RuntimeError` in the `OutsideGymHoursError` branch and fall back to a generic DM — but this would conflict with D-20-7's "exactly four locked strings, no fifth string". The current behavior is the lesser-of-two-evils; document the trade-off in the docstring of `_format_gym_hours` (currently says "Defensive: raises RuntimeError" — add "callers must accept that the user gets no DM in this regression scenario").

### SU-02: `_format_gym_hours` does not validate input shape strictly

**File:** `apps/backend/app/integrations/telegram/handlers.py:119-126`
**Issue:** `fields = getattr(exc, "fields", None) or {}` followed by `fields["open"][:5]`. If `fields["open"]` is something other than a string — say `None` (intermediate regression where Phase 19 sends `fields={'open': None, 'close': '23:00:00'}`) — `None[:5]` raises `TypeError`, which IS caught and re-raised as the `RuntimeError`. Good. But if `fields["open"]` is e.g. `time(7, 0)` (the `time` object itself rather than its `isoformat()` result), `[:5]` raises `TypeError` → also caught. So the helper is actually robust. **No code change needed.** Suggestion: add a unit test for the `None` and non-str cases to lock the behavior:

```python
def test_format_gym_hours_none_raises() -> None:
    exc = OutsideGymHoursError("outside_gym_hours", fields={"open": None, "close": "23:00:00"})
    with pytest.raises(RuntimeError, match="Phase 19 regression"):
        _format_gym_hours(exc)
```

### SU-03: Audit walker count test message is now slightly stale

**File:** `apps/backend/tests/unit/test_audit_taxonomy.py:164-176`
**Issue:** The docstring/error message says "18 v1.1 + 11 v1.2 = 29 locked pairs". Counting the frozenset definition (`apps/backend/app/core/audit.py:78-122`) yields 18 v1.1 entries (lines 84-108) and 11 v1.2 entries (lines 110-121). The total of 29 matches the assertion. The breakdown is therefore correct. However, the error message says "expected 29 (18 v1.1 + 11 v1.2)" — if a future phase adds another `v1.2` entry without updating this message, the diff will be confusing. Cosmetic.
**Fix:** Consider switching the assertion message to a relative form ("expected exactly N entries; current frozenset definition is the source of truth"). Low priority.

### SU-04: Worker handler-list ordering depends on a comment, not a test

**File:** `apps/backend/app/workers/telegram_bot.py:74`
**Issue:** `handlers=[("start", start_handler), ("checkin", checkin_handler)]` — CONTEXT line 116 documents "Order is `[start, checkin]` for diff-stability; ptb's `Application.add_handler` is order-independent for `CommandHandler` so the cosmetic order doesn't affect routing." The shape regression test (`test_worker_handlers_registered.py`) only verifies set-membership, not order. If the worker's order silently flips, no test fails. Probably acceptable since order genuinely doesn't affect routing, but the regression-guard comment is load-bearing without enforcement.
**Fix:** Either remove the "for diff-stability" justification (let order drift) or add a single-line assertion that pins the order in the worker construction test. Low priority.

### SU-05: `_PLACEHOLDER_TELEGRAM_BOT_TOKEN` constant duplicated between worker and config

**File:** `apps/backend/app/workers/telegram_bot.py:41`
**Issue:** The placeholder string literal `"placeholder-telegram-bot-token-not-real"` is hardcoded in the worker. CONTEXT mentions it comes "from app/core/config.py". If the config changes the default but the worker constant doesn't, the worker would fail to detect the new placeholder and would silently start with an invalid token. Out-of-scope churn for Phase 20 (existing Phase 7 code) but worth a follow-up.
**Fix (deferred):** Import the placeholder from `app.core.config` rather than re-declaring it locally. Phase 21+ cleanup.

---

_Reviewed: 2026-05-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
