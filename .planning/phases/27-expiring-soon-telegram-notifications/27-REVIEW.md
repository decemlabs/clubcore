---
phase: 27-expiring-soon-telegram-notifications
reviewed: 2026-05-09T00:00:00Z
depth: standard
files_reviewed: 24
files_reviewed_list:
  - apps/backend/alembic/versions/0010_notifications.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/integrations/telegram/bot.py
  - apps/backend/app/integrations/telegram/copy.py
  - apps/backend/app/modules/memberships/constants.py
  - apps/backend/app/modules/memberships/models.py
  - apps/backend/app/modules/memberships/repository.py
  - apps/backend/app/modules/memberships/service.py
  - apps/backend/app/workers/__init__.py
  - apps/backend/app/workers/scheduled/send_expiring_notifications.py
  - apps/backend/ruff.toml
  - apps/backend/tests/integration/notifications/__init__.py
  - apps/backend/tests/integration/notifications/conftest.py
  - apps/backend/tests/integration/notifications/test_expiring_7d_happy_path.py
  - apps/backend/tests/integration/notifications/test_frozen_skipped.py
  - apps/backend/tests/integration/notifications/test_idempotency_constraint.py
  - apps/backend/tests/integration/notifications/test_select_exclusions.py
  - apps/backend/tests/integration/notifications/test_send_403_retry.py
  - apps/backend/tests/integration/notifications/test_three_kinds_one_run.py
  - apps/backend/tests/unit/integrations/__init__.py
  - apps/backend/tests/unit/integrations/telegram/__init__.py
  - apps/backend/tests/unit/integrations/telegram/test_copy_render.py
  - apps/backend/tests/unit/integrations/telegram/test_copy_variant_selection.py
  - apps/backend/tests/unit/workers/test_worker_settings.py
findings:
  critical: 1
  warning: 9
  info: 3
  total: 13
status: issues_found
---

# Phase 27: Code Review Report

**Reviewed:** 2026-05-09
**Depth:** standard
**Files Reviewed:** 24
**Status:** issues_found

## Summary

Phase 27 ships expiring-soon Telegram DM notifications: a new `membership_notifications` idempotency table, an ARQ cron job at 06:15 MSK, locked Russian DM templates with deterministic A/B variant selection, and audit emission via three locked event names.

The locked decisions in CONTEXT.md are honoured at the call sites:

- `pick_variant` correctly uses `client_id.bytes[0] & 1` (NOT `hash()`); the anti-oracle invariant holds across processes (`copy.py:67`).
- `_emit_send_event` uses three explicit `if/elif/else` branches with literal event names — the AST literal-string audit gate passes (`service.py:1184–1221`).
- The repository SELECT uses `text()` raw SQL for the `clients` JOIN — no `from app.modules.clients` import in `repository.py` or `service.py`; the `import-linter` `modules-independent` contract is preserved (`repository.py:513–545`).
- Multi-session pattern: read session is closed before the send loop; per-success write session opens for INSERT + audit + commit (`service.py:1274–1332`).
- Cron schedule: `expire_memberships` at UTC 03:05 (MSK 06:05) → `send_expiring_notifications` at UTC 03:15 (MSK 06:15); 10-minute buffer present, `unique=True`, `keep_result=60` (`workers/__init__.py:88–103`).
- 403 / transient send failures both produce `expiring_notification_send_failed` WARNING with `reason` discriminator and skip row insertion — matching D-27-14 (`service.py:1291–1302`).

The single CRITICAL is the use of `assert` for control-flow validation of an unknown `kind` value in `_emit_send_event`: under `python -O` the assertion is stripped and an unintended `expiring_notification_sent_1d` audit event will be emitted for any non-7d/3d kind that slips through. WARNING-grade defects cluster around an untested `IntegrityError` race-recovery branch, an under-disciplined Bot lifecycle (no aiohttp cleanup), an inaccurate success counter under race conditions, and a few smaller test/doc consistency issues.

## Critical Issues

### CR-01: `assert` used as runtime control-flow guard for unknown `kind` in `_emit_send_event`

**File:** `apps/backend/app/modules/memberships/service.py:1208–1221`

**Issue:** The dispatcher's else-branch uses `assert kind == EXPIRING_KIND_1D, f"unknown kind {kind!r}"` and then unconditionally emits the `expiring_notification_sent_1d` audit event. Python `assert` is stripped under `python -O` (and by some PEX/pyinstaller bundlers). If a future migration adds a fourth kind (or a typo / corrupt DB row produces an unexpected `kind`), production will:

1. Silently bypass the assertion.
2. Emit `expiring_notification_sent_1d` for a row that was NOT a 1d expiring notification.
3. Insert a `MembershipNotification` row whose `kind` does NOT match the audit event suffix — corrupting forensic correlation between `audit_log` and `membership_notifications`.

This is also a hard `LOCKED_AUDIT_EVENTS` invariant violation by side effect: an event whose suffix `"_1d"` says "1-day" is being attached to a `kind="expiring_3d"` (or anything else) row.

The plan's stated intent (D-27-12) is explicit branching on the three known kinds. An `assert` is not the right mechanism — `assert` is for invariants the test suite proves to hold; misused as a runtime gate it disappears in `-O` mode.

**Fix:** Replace the `assert` with an explicit `raise` so the unknown-kind path fails LOUD in every runtime configuration, and so an unexpected fourth kind cannot accidentally fan out as `*_1d`:

```python
elif kind == EXPIRING_KIND_1D:
    await audit.emit(
        session,
        "expiring_notification_sent_1d",
        actor_user_id=None,
        resource_type="membership",
        resource_id=membership_id,
        client_id=str(client_id),
        telegram_chat_id=chat_id,
        kind="expiring_1d",
        channel="telegram",
    )
else:
    raise ValueError(f"unknown expiring kind: {kind!r}")
```

The repository populates `kind` from a `CASE WHEN m.end_date = ...` expression in raw SQL; an unmatched `end_date` would return `NULL` from the CASE (and so a `None` kind reaching this dispatcher), so the `ValueError` path is reachable in principle. The current `assert` masks that.

## Warnings

### WR-01: `IntegrityError` race-recovery branch in `_send_expiring_notifications` is untested

**File:** `apps/backend/app/modules/memberships/service.py:1322–1332`
**Tests under review:** `tests/integration/notifications/test_idempotency_constraint.py`

**Issue:** D-27-15 designates the `(membership_id, kind)` UNIQUE constraint as the cron's idempotency source of truth, with a documented IntegrityError catch on the write path for the rare two-worker race scenario. The catch block (`except IntegrityError: ... rollback + log.warning(... "expiring_notification_idempotency_conflict" ...)`) is reachable only when the SELECT-side `NOT EXISTS` subquery missed a concurrent insert.

`test_idempotency_constraint.py` proves only the *SELECT-side* filter (pre-inserted row → candidate excluded → sender never reached). It does NOT exercise the IntegrityError catch path: the row is filtered out before reaching the write session.

There is no test that:
1. Bypasses the SELECT filter (e.g., monkey-patches `find_expiring_candidates` to return a candidate whose corresponding `MembershipNotification` row was inserted between the SELECT and the write).
2. Asserts the `expiring_notification_idempotency_conflict` warning is emitted, no audit row is written, and the helper continues to the next candidate.

That branch is dead-on-arrival code from a coverage perspective: a regression that breaks rollback/continue (e.g., re-raising the IntegrityError, double-decrementing, double-emitting audit) would not surface in CI.

**Fix:** Add an integration test that pre-inserts the `MembershipNotification` row AFTER the helper has called `find_expiring_candidates` but BEFORE the per-candidate write session opens. One workable pattern: monkey-patch `repository.find_expiring_candidates` (or wrap it) to return a hand-built `ExpiringCandidate` whose row already exists in the table, then assert (a) `count == 0`, (b) sender WAS called once (DM was sent before the conflict was detected — that is the documented race semantic), (c) exactly one `MembershipNotification` row exists (the pre-inserted one), (d) zero `audit_log` rows for that membership/kind, (e) `expiring_notification_idempotency_conflict` warning was logged.

### WR-02: `_send_expiring_notifications` `sent` counter undercounts actual DM sends under race-duplicate

**File:** `apps/backend/app/modules/memberships/service.py:1305–1332`

**Issue:** Under the documented two-worker race (D-27-15), worker A and worker B can both call `sender.send_text_dm(...)` for the same `(membership_id, kind)` pair before either INSERT lands. Worker A wins the UNIQUE constraint; worker B catches `IntegrityError`, rolls back, and continues. But:

- Worker B already issued `bot.send_message` to the user — the client received a duplicate DM.
- Worker B's `sent` counter is NOT incremented (correct vis-à-vis row count).
- Worker B logs `expiring_notification_idempotency_conflict` — good for forensics.

The return value `sent` is documented as "count of successful DM sends" (worker docstring at line 53; service docstring at 1265–1266), but in this race it actually reports "count of successful row inserts." The DM send count is `sent + (race conflicts)`. ARQ writes `sent` to its result store; ops dashboards or audit summaries downstream that interpret it as "DMs sent" are subtly wrong.

The risk is small at pet-project scale (the CONTEXT calls it practically zero with `unique=True` and a single ARQ instance), but the docstring is misleading.

**Fix:** Either tighten the docstring on `_send_expiring_notifications` and the worker entry to clarify "count of successful idempotency-row commits (= count of distinct DM deliveries; race-duplicate sends are counted separately in `expiring_notification_idempotency_conflict` warnings)", or add a `conflicts` counter that is also returned / logged so the discrepancy is visible. Simpler: amend the docstring; the race is rare enough that a separate counter is over-engineering.

### WR-03: Bot instance constructed per cron tick with no aiohttp session cleanup

**File:** `apps/backend/app/integrations/telegram/bot.py:85–96`, `apps/backend/app/workers/scheduled/send_expiring_notifications.py:58`

**Issue:** `build_bot(token=...)` returns a fresh `telegram.Bot` per call, with no caching and no shutdown hook. `python-telegram-bot` 22's `Bot` lazily allocates an aiohttp `ClientSession` on first `send_message` and keeps it open for connection pooling; the bot is normally shut down via `await bot.shutdown()` (or via the Application lifecycle).

The Phase 27 worker:
1. Calls `build_bot(...)` at the top of every cron tick (once per day at 06:15 MSK).
2. Hands the Bot to `_send_expiring_notifications`, which uses it via `sender.send_text_dm` (which itself does not close anything).
3. Returns `count`. The Bot reference goes out of scope. The aiohttp session inside the Bot is not explicitly closed.

At one tick per day this leaks a connection per day until the worker process restarts. It is mostly harmless at pet-project scale (Python GC and aiohttp's `__del__` will eventually clean up, with warnings), but it produces "Unclosed client session" RuntimeWarnings in logs and slowly accumulates fd usage. The bot.py docstring even acknowledges this risk ("avoids cross-tick session leak risks") but the worker does not act on it.

**Fix:** Either (a) wrap Bot in an `async with`-shaped helper:

```python
# bot.py
@asynccontextmanager
async def bot_session(*, token: str) -> AsyncIterator[Bot]:
    bot = Bot(token=token)
    try:
        async with bot:
            yield bot
    finally:
        # bot.__aexit__ closes the underlying aiohttp session
        pass
```

then `async with bot_session(token=...) as bot:` in the worker; or (b) call `await bot.shutdown()` in a `try/finally` around `_send_expiring_notifications` in the worker. Option (a) is cleaner and matches PTB 22 idioms.

### WR-04: `_emit_send_event` is private (underscore-prefixed) but called from non-private siblings

**File:** `apps/backend/app/modules/memberships/service.py:1165, 1314`

**Issue:** `_emit_send_event` is `_`-prefixed (Python's "private" convention) and carries `# noqa: SVC001 caller-owns-txn`. Its only caller is the sibling `_send_expiring_notifications`, which is fine. But the rationale comment on the marker (lines 1180–1183) refers to the SVC001 walker's "private + noqa" exemption. The walker treats both functions as private helpers exempt from the public-must-commit rule. That is consistent.

The concern is review legibility: a reader landing on `_emit_send_event` sees `await audit.emit(session, ...)` followed by NO `await session.commit()`, and the docstring states "Caller (service `_send_expiring_notifications`) owns the per-send write session; this helper carries `# noqa: SVC001 caller-owns-txn` because it does NOT commit (its caller does after the audit row joins the UoW)." But the actual call chain is:

1. `_send_expiring_notifications` opens write_session.
2. Adds `MembershipNotification` to write_session.
3. Calls `_emit_send_event(write_session, ...)` — adds `AuditLog` to write_session.
4. `await write_session.commit()` — flushes both rows atomically.

That is correct, but the comment on `_emit_send_event` says "its caller does after the audit row joins the UoW" — slightly misleading: the caller commits, period; the audit row already joined the UoW via `session.add(...)` inside `audit.emit`.

**Fix:** Tighten the docstring on `_emit_send_event`: "Caller adds a `MembershipNotification` row to the same write_session BEFORE calling this helper; this helper enrols an `AuditLog` row via `audit.emit`; the caller's single `await write_session.commit()` flushes both rows atomically."

### WR-05: Test fixture `make_client_with_telegram` uses Python's salted `hash()` to derive distinct chat ids

**File:** `apps/backend/tests/integration/notifications/test_select_exclusions.py:62–63`

**Issue:** The parametrized test computes per-scenario `telegram_user_id` as `400_000 + hash(scenario) % 100_000`. `hash()` of a string is salted with `PYTHONHASHSEED` and changes between Python invocations. This is the same anti-pattern Phase 27 explicitly avoided in `pick_variant` (see CR-01-adjacent context: D-27-10 anti-oracle); using it in a test fixture for "uniqueness" is fine in practice (the seed is constant within one process), but:

1. It is stylistically inconsistent with the explicit anti-oracle decision in `copy.py`.
2. If `PYTHONHASHSEED=0` is set (sometimes done in CI for determinism), and another test in the suite happens to use the same seed-formula, chat_id collisions become possible (then the `clients.telegram_user_id UNIQUE` constraint fires and the test errors with an opaque IntegrityError instead of asserting).

**Fix:** Use a per-scenario static literal table or just append the parametrize index:

```python
_CHAT_IDS = {
    "status_cancelled": 400_001,
    "status_expired": 400_002,
    "telegram_unlinked": None,  # not used — make_client_no_telegram path
    "client_soft_deleted": 400_003,
}
...
client_id = await make_client_with_telegram(telegram_user_id=_CHAT_IDS[scenario])
```

### WR-06: `find_expiring_candidates` raw SQL does not bind `today_plus_*` as `Date` — relies on driver coercion

**File:** `apps/backend/app/modules/memberships/repository.py:541–545`

**Issue:** `bindparams(today_plus_1=today_plus_1, today_plus_3=today_plus_3, today_plus_7=today_plus_7)` — these values are `datetime.date` instances. `text(...).bindparams(...)` infers SQL type from Python type, which works for asyncpg + Postgres `DATE` columns in practice. But:

1. There is no explicit `bindparam("today_plus_1", type_=Date)`. A future change to one of the call sites (e.g., passing a `datetime` instead of `date`) silently coerces to `TIMESTAMP` and mismatches the `DATE` column comparison. The IN clause `m.end_date IN (:today_plus_1, ...)` would either fail-loud (good) or silently coerce in unexpected ways.
2. mypy strict cannot type-check the SQL string contents; a typo in `:today_plus_1` would only surface at runtime.

This is in the "WARNING — code quality" bucket, not a security or correctness bug today, but raw SQL with implicit type binding is brittle.

**Fix:** Either switch to SQLAlchemy Core constructs for the `memberships`-side and use a single `text()` only for the `clients` JOIN columns, or add explicit `bindparam` typing:

```python
from sqlalchemy import bindparam, Date
sql = text("...").bindparams(
    bindparam("today_plus_1", value=today_plus_1, type_=Date),
    bindparam("today_plus_3", value=today_plus_3, type_=Date),
    bindparam("today_plus_7", value=today_plus_7, type_=Date),
)
```

### WR-07: `_send_expiring_notifications` opens N+1 sessions; long candidate list quietly stresses pool

**File:** `apps/backend/app/modules/memberships/service.py:1274–1332`

**Issue:** D-27-07 pattern (b) is justified at pet-project scale (≤ ~50 candidates per run). But the implementation always opens a fresh write session even when ZERO candidates are eligible (the `for cand in candidates:` simply does not execute — that's fine), and does a session round-trip per success. At realistic peak load (e.g., 50 active memberships, all expiring in the same window) the cron will make 50 DB-connection acquisitions back-to-back. The `async_sessionmaker` default pool is finite; if the DB connection pool is sized to a few connections and the worker holds another session via `engine`, contention is possible.

This is documented as accepted in CONTEXT.md (D-27-07 rationale 4: "negligible at pet-project scale"). Flagging for visibility only — if v1.4 grows the gym beyond pet scale, batching successful inserts into a single session per chunk (e.g., 10 sends per write session) would amortise the overhead.

**Fix:** No change required for v1.3. Add a comment in `_send_expiring_notifications` referencing the D-27-07 trade-off so future scale-up reviews surface this trade-off:

```python
# D-27-07 pattern (b): one write session per success. Acceptable at pet-project
# scale (≤ ~50 candidates/run). If the gym grows, batch successes into chunked
# write sessions (e.g., 10 sends per session) to reduce pool churn.
```

### WR-08: Worker imports a private (`_`-prefixed) service helper across module boundary

**File:** `apps/backend/app/workers/scheduled/send_expiring_notifications.py:60`

**Issue:** `await memberships_service._send_expiring_notifications(...)` — the worker reaches into a `_`-prefixed (private-by-convention) symbol on `app.modules.memberships.service`. This is a documented intentional pattern (Phase 18 mirror; D-27-09 justifies the `_`-prefix because the SVC001 commit-gate walker exempts private helpers), but it intentionally breaks the encapsulation contract: a refactor inside `service.py` that renames or removes `_send_expiring_notifications` would silently break the worker (mypy will catch the call-site mismatch, but reviewers reading `service.py` in isolation may not notice the cross-module dependency).

**Fix:** Either (a) export an explicit public alias:

```python
# service.py
send_expiring_notifications_fanout = _send_expiring_notifications
__all__ = [..., "send_expiring_notifications_fanout"]
```

then worker uses the public name, or (b) leave the current pattern but add a `# noqa` style comment AT the import site in the worker:

```python
# We deliberately call the underscore-prefixed helper here — it is the public
# API for the worker (Phase 18 D-09 / Phase 27 D-27-09 cross-module exception).
count = await memberships_service._send_expiring_notifications(...)
```

Either makes the cross-boundary access intentional rather than incidental.

### WR-09: Migration downgrade does not drop the auto-generated unique-constraint index

**File:** `apps/backend/alembic/versions/0010_notifications.py:99–110`

**Issue:** `op.create_unique_constraint(...)` in Postgres implicitly creates a backing UNIQUE INDEX named after the constraint. `op.drop_constraint(..., type_="unique")` on Postgres drops both the constraint and the implicit index in one step (so this is correct in practice). However the docstring at lines 99–100 says "Reverse upgrade in reverse order" but the order is:

1. `drop_index(ix_membership_notifications_membership_id, ...)`
2. `drop_constraint(uq_membership_notifications_membership_kind, type_="unique")`
3. `drop_table(membership_notifications)`

That IS reverse order vs. upgrade (`create_table → create_unique_constraint → create_index`). Fine. But: `drop_table` also implicitly drops both indexes and the unique constraint. Steps 1 and 2 are technically redundant. Keeping them is fine for readability and matches Phase 25/26 convention, but the comment "drop_index → drop_constraint → drop_table" should explicitly note the redundancy is intentional ("explicit drops for forensic clarity even though `drop_table` would cascade").

**Fix:** Add a one-line clarifying comment:

```python
def downgrade() -> None:
    """Reverse upgrade in reverse order — disaster recovery only (D-27-03).

    Note: drop_table cascades the unique-constraint and index drops; the
    explicit drops below are intentional for forensic clarity (mirrors
    Phase 25/26 downgrade shape).
    """
```

## Info

### IN-01: `# noqa: RUF001` markers on locked DM strings — disciplinary tripwires

**File:** `apps/backend/app/integrations/telegram/copy.py:40–45`, `apps/backend/ruff.toml:38–44`

**Issue:** Each of the six locked Russian DM templates carries `# noqa: E501, RUF001` and `apps/backend/ruff.toml` `[lint.per-file-ignores]` entry for `app/integrations/telegram/copy.py = ["RUF100"]`. The shipped strings do not currently trigger RUF001 (the only Latin character is `{end_date}`, which RUF001 does not flag in placeholders), so the per-line `# noqa: RUF001` is redundant. The blanket `RUF100` ignore in `ruff.toml` is the workaround.

This is the documented intent (ruff.toml lines 38–44 explain it as a "disciplinary tripwire" against future ambiguous-Cyrillic edits). Acceptable — but noting that a future ruff version that promotes RUF001 to flag placeholder syntax could spuriously flag the lines, and the current `RUF100` allowance would mask both legitimate and spurious flags.

**Fix:** No change. Document is consistent with intent. Consider tightening to `# noqa: RUF001` only on the templates that genuinely contain ambiguous chars in a future cleanup pass.

### IN-02: `_format_ru_date` test asserts equality to "16 мая 2026 г." but the helper is private

**File:** `apps/backend/tests/unit/integrations/telegram/test_copy_render.py:32–34`

**Issue:** `from app.integrations.telegram.copy import _format_ru_date` — test imports a `_`-prefixed (private-by-convention) helper and asserts on its output format. If a future revision changes the format (e.g., drops the trailing "г." per a Russian-style guide update), the test breaks; that's the test's purpose (locked behaviour). Importing private helpers in tests is a common Python pattern, but it does introduce coupling.

**Fix:** No change. Locked-format tests are a justified exception to the private-helper-don't-import rule.

### IN-03: `expiring_notification_send_failed` log payload includes `error_msg=None` when `blocked=True`

**File:** `apps/backend/app/modules/memberships/service.py:1291–1301`

**Issue:** When `result.blocked=True`, `result.error` is `None` (per `SendResult` defaults in `sender.py`). The `log.warning(...)` payload always includes `error_msg=result.error`, so blocked-bot logs carry `error_msg=None`. This is harmless but slightly noisy in structured-log queries (`reason=bot_blocked AND error_msg=null` becomes the canonical filter; the `error_msg` field is redundant for that branch).

**Fix:** Conditionally include the field:

```python
log_kwargs: dict[str, Any] = {
    "reason": reason,
    "membership_id": str(cand.membership_id),
    "client_id": str(cand.client_id),
    "telegram_chat_id": cand.chat_id,
    "kind": cand.kind,
}
if result.error is not None:
    log_kwargs["error_msg"] = result.error
log.warning("expiring_notification_send_failed", **log_kwargs)
```

Optional polish.

---

_Reviewed: 2026-05-09_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
