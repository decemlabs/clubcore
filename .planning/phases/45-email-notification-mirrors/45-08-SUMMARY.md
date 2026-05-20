---
phase: 45-email-notification-mirrors
plan: 08
subsystem: notifications
tags: [bookings, email, cross-channel, fanout, alembic-migration, fsm-hooks, idempotency]

# Dependency graph
requires:
  - phase: 41-infra-bedrock-anti-oracle-scaffold
    provides: EmailDispatcher Protocol slot (D-41-24); LOCKED_EMAIL_TEMPLATES frozenset (D-41-11); channel discriminator on booking_notifications (Migration 0024)
  - phase: 45-email-notification-mirrors
    provides: EMAIL_BOOKING_* template registry (Plan 45-05); dispatcher walker extension (Plan 45-06b); enqueue_booking_email_fallback helper (Task 1 of this plan); booking_notifications.kind widened CHECK + column (Task 2 of this plan)
provides:
  - "Cross-channel booking notification fanout at 5 production callsites (create_booking, cancel_booking owner + reception branches, schedule.cancel_slot cascade, _send_booking_reminders cron)"
  - "_dispatch_booking_lifecycle_notification helper — Telegram-first + email-fallback for FSM lifecycle hooks"
  - "enqueue_booking_email_fallback helper with 4 literal template_id branches (D-45-22)"
  - "Alembic Migration 0032 — booking_notifications kind column widened to VARCHAR(32) + CHECK widened to 4 lifecycle kinds"
  - "Integration test suite (5 scenarios: 4 positive per-kind + 1 negative Telegram-success)"
affects: [Plan 45-10 booking reminder worker, Plan 45-11 cleanup cron, Phase 46 milestone verification, future email-channel observability work]

# Tech tracking
tech-stack:
  added: []  # No new libraries
  patterns:
    - "5-callsite cross-channel fanout (3 FSM hooks + 1 cron + 1 cascade)"
    - "Telegram-first then email-fallback decision tree (blocked-or-unlinked AND email-present)"
    - "4-literal kind branches at the helper (AST gate parity with D-45-22)"
    - "Migration drop-and-recreate CHECK with column-type widening in same migration"

key-files:
  created:
    - "apps/backend/alembic/versions/0032_booking_notifications_widen_kind.py"
    - "apps/backend/tests/integration/test_booking_email_fallback.py"
    - "apps/backend/tests/unit/test_booking_email_fallback_helper.py"
  modified:
    - "apps/backend/app/modules/bookings/notifications.py"
    - "apps/backend/app/modules/bookings/models.py"
    - "apps/backend/app/modules/bookings/service.py"
    - "apps/backend/app/modules/schedule/service.py"
    - ".planning/phases/45-email-notification-mirrors/deferred-items.md"

key-decisions:
  - "D-45-08-A (Rule-4 deviation): Original plan said `apps/backend/app/modules/bookings/repository.py` would host a `find_booking_reminder_candidates` function with an extendable dataclass. Reality: no such function exists; the candidate SELECT lives inline in `bookings/service.py::_send_booking_reminders` as a raw `sa.text(...)` block (Phase 39 D-39-08). Per resumption-context Option C: edited the inlined SELECT directly in service.py instead of fabricating a repository function — fewer code-paths, same outcome."
  - "D-45-08-B (Rule-4 deviation): Original plan assumed `booking_notifications.kind` already admitted lifecycle kinds. Reality: Migration 0020 landed both a single-element CHECK (`kind IN ('reminder_24h')`) AND a too-narrow VARCHAR(16) column type — `cancelled_by_client` (19 chars) overflows. Authored Migration 0032 widening BOTH the CHECK predicate (4-kind set) AND the column type (VARCHAR(32)). Drop-and-recreate-CHECK pattern mirrored from 0024."
  - "D-45-08-C: Per WARNING-2 confirmed and resumption-context note — no `booking_*_notification_sent` audit payload schemas registered in AUDIT_PAYLOAD_SCHEMAS. Followed D-39-14 'row IS the audit' discipline: the `booking_notifications` row with `channel='email'` is the audit record for the email-fallback path; NO new audit.emit calls added for the 3 lifecycle email-fallback paths."
  - "D-45-08-D: Schedule cancel-slot cascade also dispatches lifecycle DMs (5th callsite, not in plan). Mitigated for symmetry: updated `app/modules/schedule/service.py:579` to route through the new `_dispatch_booking_lifecycle_notification` helper with `kind='cancelled_by_owner'` (cascade is owner-initiated by definition)."
  - "D-45-08-E: Preserved Phase 39 log-event names (`booking_dm_skipped_unlinked`, `booking_dm_send_failed`) in the new lifecycle helper so existing integration test assertions (`test_create_sends_dm`, `test_cancel_sends_dm`) continue to match. The Phase 45 email-fallback is strictly ADDITIVE to the Phase 39 observability contract — no rename, no rewrite."

patterns-established:
  - "Pattern: post-commit lifecycle fanout helper. `_dispatch_booking_lifecycle_notification` accepts (booking, kind literal, template, bot, sender, session) and handles Telegram-first + email-fallback + INSERT booking_notifications row in one place. All FSM callsites pass their OWN kind literal — no shared variable."
  - "Pattern: inline SELECT widening for cross-channel candidates. The `_send_booking_reminders` SELECT projects `c.email + c.last_name` and relaxes the WHERE to `(telegram_user_id IS NOT NULL OR email IS NOT NULL)`. Channel-agnostic NOT EXISTS predicate per D-45-14 preserves the single-shot-per-kind invariant ACROSS channels."
  - "Pattern: 4-literal kind branches at the helper. `enqueue_booking_email_fallback` has 4 explicit `if/elif kind == '...'` branches, each calling `dispatcher(template_id='EMAIL_BOOKING_...')` with a LITERAL string. AST gate at `tests/unit/test_locked_email_templates_ast.py:42-46` is satisfied by construction."
  - "Pattern: migration with column widening + CHECK rewrite in one migration. Order matters: widen column type FIRST (so the new CHECK can refer to the new wider values), then drop+recreate CHECK with widened predicate. Downgrade reverses: restore CHECK first, then narrow the column."

requirements-completed: [NOTIFY-09, NOTIFY-10, NOTIFY-06]

# Metrics
duration: ~30min
completed: 2026-05-20
---

# Phase 45 Plan 08: Booking Email-Fallback Wiring Summary

**Cross-channel email fallback for 4 booking notification kinds (3 FSM lifecycle hooks + 1 reminder cron), wired at 5 production callsites with a new module-local lifecycle helper and Migration 0032 widening the kind constraint to admit the 3 lifecycle literals.**

## Performance

- **Duration:** ~30 minutes (executor wall time, post-checkpoint resumption with approved Option C)
- **Started:** 2026-05-20T10:23:39Z (resumption commit time)
- **Completed:** 2026-05-20T10:50Z
- **Tasks:** 3/3 (TDD RED + GREEN per task)
- **Files modified:** 5 (3 modified prod, 1 new migration, 2 new tests)

## Accomplishments

- 4-literal-branch `enqueue_booking_email_fallback` helper landed in `bookings/notifications.py` per D-45-22 — AST gate green by construction (NO f-strings, NO variable interpolation in `template_id`).
- Alembic Migration 0032 ships TWO coupled DDL ops: widen `booking_notifications.kind` column type (VARCHAR(16) → VARCHAR(32)) AND widen the CHECK predicate to the 4 lifecycle kinds. Drop-and-recreate-CHECK pattern mirrored from 0024. Round-trip clean (upgrade → downgrade → upgrade); `alembic check` produces empty diff.
- Cross-channel email fanout wired at 5 production callsites (4 originally planned + 1 schedule cascade discovered during execution). Each callsite passes its OWN literal kind string (D-45-22 contract preserved).
- Integration test coverage: 5 new tests in `tests/integration/test_booking_email_fallback.py` (4 positive per-kind + 1 negative Telegram-success) — all green. 5 new unit tests in `tests/unit/test_booking_email_fallback_helper.py` — all green.
- Phase 39 observability contract preserved (existing `booking_dm_skipped_unlinked` / `booking_dm_send_failed` log event names continue to fire from the new helper) — no test-assertion drift.

## Task Commits

Each task was committed atomically per TDD RED → GREEN discipline:

1. **Task 1 RED — failing tests for enqueue_booking_email_fallback helper** — `3586441` (test)
2. **Task 1 GREEN — enqueue_booking_email_fallback with 4 literal template_id branches** — `698c7d1` (feat)
3. **Task 2 — Migration 0032 + models.py kind widening (Rule-4 deviation)** — `b5ddbd7` (feat)
4. **Task 3 RED — failing integration tests for booking email-fallback fanout** — `9a50c84` (test)
5. **Task 3 GREEN — wire email-fallback at 5 callsites (4 FSM + reminder cron)** — `eb077bf` (feat)

**Plan metadata commit:** to follow this SUMMARY.

_Note: Task 2 has no RED phase — it is a pure DDL/ORM-schema change with no behavior-only failing-test entry point. The alembic round-trip + `alembic check` clean serves as its acceptance signal._

## Files Created/Modified

### Created

- `apps/backend/alembic/versions/0032_booking_notifications_widen_kind.py` — Migration widening booking_notifications.kind column + CHECK.
- `apps/backend/tests/integration/test_booking_email_fallback.py` — 5-test cross-channel fanout integration suite (self-contained fixtures, mirrors Plan 45-07's test_expiring_email_fallback.py shape).
- `apps/backend/tests/unit/test_booking_email_fallback_helper.py` — 5-test unit suite pinning the 4-literal-branch contract on the helper.

### Modified

- `apps/backend/app/modules/bookings/notifications.py` — Added `enqueue_booking_email_fallback` async helper with 4 literal `template_id` branches (one per booking kind). NEW import of `get_email_dispatcher`, `UUID`, `uuid4`, `Literal`.
- `apps/backend/app/modules/bookings/models.py` — Widened `kind: Mapped[str]` from `String(16)` to `String(32)`; widened `__table_args__.CheckConstraint` predicate from single-kind set to 4-kind set.
- `apps/backend/app/modules/bookings/service.py` — NEW `_dispatch_booking_lifecycle_notification` helper. UPDATED `_send_booking_reminders`: widen inline SELECT (project `c.email` + `c.last_name`; relax WHERE `(telegram_user_id IS NOT NULL OR email IS NOT NULL)`); per-row loop branches on Telegram outcome with email-fallback. UPDATED `create_booking` step 9.5 + `cancel_booking` step 9.5 to route through the lifecycle helper with kind literals.
- `apps/backend/app/modules/schedule/service.py` — UPDATED `cancel_slot` cascade DM dispatch (line 579) to route through the new lifecycle helper with `kind='cancelled_by_owner'` (5th callsite — symmetry mitigation).
- `.planning/phases/45-email-notification-mirrors/deferred-items.md` — Documented 2 new pre-existing failures discovered (booking router-smoke docstring grep + booking_via_bot expired-package test fixture).

## Decisions Made

See frontmatter `key-decisions` (D-45-08-A through D-45-08-E). The 5 decisions cover:

1. Why the plan's "repository.py" task became "service.py inline SELECT" (no repository function existed).
2. Why Migration 0032 widens BOTH column type AND CHECK (single-element CHECK was the smaller half of the surprise — VARCHAR(16) was the load-bearing constraint).
3. Why no new `audit.emit` calls landed (D-39-14 row-is-audit + WARNING-2 no-schemas-registered branch).
4. Why the schedule cascade callsite was added to scope (symmetry with the other 4 lifecycle callsites — a Phase 39 dispatch point that also benefits from email-fallback).
5. Why Phase 39 log-event names were preserved (test-assertion stability — 4 pre-existing tests assert these literals).

## Plan vs Reality

This plan went through a checkpoint earlier in execution (the prior executor's checkpoint return triggered the resumption-context Option C narrative). The plan-frontmatter `files_modified` list deviated as follows:

| Plan said | Reality | Why |
|-----------|---------|-----|
| `apps/backend/app/modules/bookings/repository.py` (modified) | **Not modified.** The plan assumed a `find_booking_reminder_candidates` function existed in repository.py; it does not. The candidate SELECT lives inline in `service.py::_send_booking_reminders`. | Discovered at executor-time — Option C resolution. |
| (not listed) | `apps/backend/alembic/versions/0032_booking_notifications_widen_kind.py` (NEW) | Migration 0020's column type was VARCHAR(16) and the CHECK was single-element; both needed widening. Rule-4 deviation surfaced at first INSERT attempt. |
| (not listed) | `apps/backend/app/modules/schedule/service.py` (modified) | 5th callsite of Telegram lifecycle DM — symmetry mitigation, not separately worth its own plan. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 4 — Architectural] booking_notifications.kind column too narrow + CHECK too narrow**
- **Found during:** Task 3 (first integration test run after Task 3 GREEN landed the service.py changes)
- **Issue:** `cancelled_by_client` (19 chars) and `cancelled_by_owner` (18 chars) overflow `VARCHAR(16)`; the original CHECK only admits `'reminder_24h'`.
- **Fix:** Authored Alembic Migration 0032 widening both. Updated ORM model `kind: Mapped[str] = mapped_column(String(32), ...)` and `__table_args__` CheckConstraint to mirror.
- **Files modified:** `apps/backend/alembic/versions/0032_booking_notifications_widen_kind.py`, `apps/backend/app/modules/bookings/models.py`.
- **Verification:** `alembic upgrade head` + downgrade -1 + upgrade head all clean; `alembic check` produces empty diff; all 5 integration tests green.
- **Committed in:** `b5ddbd7` (Task 2 commit).

**2. [Rule 3 — Blocking] No `find_booking_reminder_candidates` in repository.py**
- **Found during:** Task 2 read-first pass.
- **Issue:** Plan referenced a function that does not exist in `bookings/repository.py`. The candidate SELECT is inlined in `bookings/service.py:_send_booking_reminders` as a raw `sa.text(...)` block.
- **Fix:** Skipped repository changes per Option C; edited the inlined SELECT directly in service.py.
- **Files modified:** `apps/backend/app/modules/bookings/service.py` (lines ~535-560 inline SELECT widening).
- **Verification:** Plan acceptance criteria met by alternative path; test coverage validates end-to-end.
- **Committed in:** `eb077bf` (Task 3 commit).

**3. [Rule 2 — Missing functionality] Schedule cancel-slot cascade omitted from plan scope**
- **Found during:** Task 3 implementation grep for `_dispatch_booking_dm` consumers.
- **Issue:** `app/modules/schedule/service.py:579` also dispatches booking lifecycle DMs (cascade owner-cancellation). Without the email-fallback hook there, the cascade path would still be Telegram-only — observability inconsistency.
- **Fix:** Updated the cascade callsite to route through `_dispatch_booking_lifecycle_notification` with `kind='cancelled_by_owner'`.
- **Files modified:** `apps/backend/app/modules/schedule/service.py`.
- **Verification:** `tests/integration/bookings/test_cancel_sends_dm.py::test_slot_cancel_cascade_sends_owner_dm_per_booking` still passes (Telegram-happy path); my new fallback paths covered by `test_booking_cancelled_by_owner_fanouts_email`.
- **Committed in:** `eb077bf` (Task 3 commit).

**4. [Rule 1 — Bug] Reception cancel test fixture used 24h offset (window-edge collision)**
- **Found during:** First GREEN run of `test_booking_cancelled_by_client_fanouts_email`.
- **Issue:** Reception-actor cancel has a 24h window guard (`CANCEL_WINDOW_HOURS_RECEPTION`); a slot exactly 24h out triggered `CancelWindowExpiredError` before the email-fallback fired.
- **Fix:** Test fixture changed to `start_offset=timedelta(hours=48)`.
- **Files modified:** `apps/backend/tests/integration/test_booking_email_fallback.py`.
- **Verification:** Test green after fixture change.
- **Committed in:** `eb077bf` (Task 3 commit).

## Threat Surface Scan

Reviewed all 5 modified/created production files for new security-relevant surface. No new endpoints, no auth-path changes, no schema changes at trust boundaries. The `_dispatch_booking_lifecycle_notification` helper consumes the same Protocol-slot dispatcher as all other Phase 45 email paths — no new outbound surface. Plan's `<threat_model>` block (3 STRIDE entries: T-45-08-01 .. -03) all green:

- **T-45-08-01 (Tampering):** `kind` passed as variable would bypass AST gate. ✅ Mitigated — 4 LITERAL kind strings at the 5 callsites (verified via `grep -c 'kind="confirmed"\|kind="cancelled_by_client"\|kind="cancelled_by_owner"\|kind="reminder_24h"'` = 6 in service.py / 1 in schedule/service.py).
- **T-45-08-02 (DoS):** Concurrent reminder cron ticks double-INSERT. ✅ Mitigated — UNIQUE `uq_booking_notifications_booking_kind_channel` from Migration 0024 catches the second; rolled-back write session + INFO-log `booking_reminder_idempotency_collision` (existing Phase 39 pattern extended).
- **T-45-08-03 (Information disclosure):** `trainer_name` in email body. ✅ Accepted per the threat-model disposition (business signal).

No new threat flags to register.

## Known Stubs

None. All wiring is live and exercised by the integration test suite.

## Self-Check: PASSED

- **File `apps/backend/alembic/versions/0032_booking_notifications_widen_kind.py`:** FOUND
- **File `apps/backend/tests/integration/test_booking_email_fallback.py`:** FOUND
- **File `apps/backend/tests/unit/test_booking_email_fallback_helper.py`:** FOUND
- **Commit `3586441` (test 45-08 RED helper):** FOUND
- **Commit `698c7d1` (feat 45-08 GREEN helper):** FOUND
- **Commit `b5ddbd7` (feat 45-08 Migration 0032):** FOUND
- **Commit `9a50c84` (test 45-08 RED integration):** FOUND
- **Commit `eb077bf` (feat 45-08 GREEN 5-callsite wiring):** FOUND
