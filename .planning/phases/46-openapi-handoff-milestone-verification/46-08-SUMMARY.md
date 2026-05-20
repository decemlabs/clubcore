---
phase: 46-openapi-handoff-milestone-verification
plan: 08
subsystem: testing
tags: [email, webhook, hmac, race, postgres, asyncio, integration-test, ver-10, d-46-14, d-42-17]

# Dependency graph
requires:
  - phase: 42-email-transport-layer-email-otp-fallback
    provides: HMAC-signed bounce webhook (D-42-17) + EmailSendLog (D-42-18) + EmailDispatcher Protocol (D-42-25)
  - phase: 45-email-notification-mirrors
    provides: real_commit_engine race-test pattern (D-45-28 / test_payment_receipt_race.py)
provides:
  - VER-10 race test #4 — concurrent bounce-webhook + active-send invariant
  - No-cross-row-cancellation invariant locked in CI
  - HMAC-signed (NOT bearer) webhook auth pattern reused in new race tests
affects: [46-09, 46-10, 46-11, 46-13]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase 45 D-45-28 real_commit_engine fixture reused for cross-session race"
    - "Phase 42 D-42-17 _sign() helper pattern reused for race test HMAC signing"
    - "asgi-lifespan LifespanManager wraps create_app() so router Depends(get_db) sees app.state.sessionmaker"

key-files:
  created:
    - apps/backend/tests/integration/test_bounce_webhook_active_send_race.py
  modified: []

key-decisions:
  - "Simulate the 'fresh active send' half via a direct INSERT in an independent session — byte-for-byte what the ARQ worker writes after a successful provider ack (per app/integrations/email/dispatcher.py + app/workers/tasks.py). Avoids standing up an in-process ARQ worker for the race assertion while keeping the cross-row-cancellation invariant honest at the DB layer."
  - "Used LifespanManager around create_app() so the webhook handler's Depends(get_db) sees a bound sessionmaker; the webhook commits via its OWN engine while the verify session reads back under READ COMMITTED isolation — the standard ASGITransport + lifespan pattern from tests/conftest.py."
  - "Patched app.api.v1._internal.email.router.get_settings to inject a known webhook secret; same pattern as test_webhook_hmac_and_routing.py:39-62 — avoids invalidating lru_cache on the real settings."

patterns-established:
  - "Pattern: race tests that need an HTTP route + a parallel DB write reuse the real_commit_engine fixture + LifespanManager to compose a real-COMMIT engine for the test-owned session and a route-owned session simultaneously."

requirements-completed: [VER-10]

# Metrics
duration: ~12min
completed: 2026-05-20
---

# Phase 46 Plan 08: Bounce-webhook + active-send race test Summary

**Real-Postgres asyncio.gather race asserting that an HMAC-signed bounce webhook UPDATE on email_send_log.id=X does NOT cancel a concurrent fresh send to the same recipient — second row lands as 'sent' independently.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 1
- **Files created:** 1
- **Lines:** 349

## Accomplishments

- New `tests/integration/test_bounce_webhook_active_send_race.py` covering VER-10 race test #4 from `46-CONTEXT.md` D-46-14.
- Asserts the no-cross-row-cancellation invariant: bounce on one row + concurrent fresh send to the same recipient → two independent rows, neither cancelled.
- Uses **HMAC-SHA256 signature** over the raw body (Phase 42 D-42-17), header `X-Email-Webhook-Signature` — NOT bearer-token. Sign helper mirrors the canonical `_sign()` from `tests/integration/email_webhook/test_webhook_hmac_and_routing.py:65`.
- Uses the **`real_commit_engine`** local fixture (Phase 45 D-45-28 pattern) for true cross-session race; default SAVEPOINT-wrapped `db_session` would serialise the race and mask the invariant.
- Verifies forensic chain: both `audit_correlation_id`s persist; `bounce_type='hard'` on the bounced row.

## Task Commits

1. **Task 1: Author test file** — `3fd8a13` (test)

## Files Created/Modified

- `apps/backend/tests/integration/test_bounce_webhook_active_send_race.py` — new race test (349 lines).

## Decisions Made

- **Active-send simulation via direct INSERT:** Dispatcher (`app/integrations/email/dispatcher.py`) only ENQUEUEs to ARQ; the worker (`app/workers/tasks.py`) writes the `email_send_log` row. For the race-invariant assertion we don't need a live ARQ worker — we simulate the same post-ack INSERT in an independent session. Plan 46-08 §5 explicitly accepted this option (`status IN ('sent', 'queued')`).
- **LifespanManager:** Required so `app.state.sessionmaker` is bound for the webhook route's `Depends(get_db)`. The webhook commits via its own engine; the verify session uses our `real_commit_engine` factory and reads back the UPDATE under READ COMMITTED.
- **Recipient uniqueness via `uuid4().hex[:8]`:** Each test run gets a fresh recipient string to avoid collision with any residual rows the TRUNCATE teardown might miss on partial-failure paths.

## Deviations from Plan

None — plan executed exactly as written. The plan anticipated the dispatcher-vs-worker split in §5 and pre-approved both the ARQ-stub and direct-INSERT options; we chose direct-INSERT for the cleanest race surface.

## Issues Encountered

- **Initial run failed:** `'State' object has no attribute 'sessionmaker'` — `create_app()` does not run lifespan, so `app.state.sessionmaker` was unset. **Fix:** wrap the `asyncio.gather` block in `async with LifespanManager(app):` (the standard `tests/conftest.py:48-53` pattern). One-line change; test then passed in 0.20s.
- **Ruff lint:** Initial `# noqa: BLE001` was unused (the project's ruff config doesn't enable `BLE001` for tests). Removed the directive.

## Acceptance Gate Verification

All acceptance criteria from the plan satisfied:

| Gate                                         | Required | Got |
| -------------------------------------------- | -------- | --- |
| `asyncio.gather`                             | ≥1       | 2   |
| `real_commit_engine`                         | ≥1       | 4   |
| `_internal/email/webhook`                    | ≥1       | 3   |
| `hmac\|signature\|_sign(`                    | ≥1       | 13  |
| `Authorization: Bearer`                      | ==0      | 0   |
| `Bearer` (any)                               | n/a      | 0   |
| `x-email-webhook-signature` (any case)       | ≥1       | 2   |
| `'bounced'`                                  | ≥1       | 6   |
| `'sent'\|'queued'`                           | ≥1       | 11  |
| `TRUNCATE email_send_log`                    | ≥1       | 1   |
| `pytest ...` → `1 passed` or `1 skipped`     | required | **1 passed** in 0.20s |
| ≥130 lines                                   | required | 349 |

Sibling-suite regression: `tests/integration/email_webhook/test_webhook_hmac_and_routing.py` → **12 passed** in 0.96s — the autouse `_patch_webhook_secret` fixture in our new file is scoped to the test module and does not leak.

## Self-Check: PASSED

- File `apps/backend/tests/integration/test_bounce_webhook_active_send_race.py` exists (verified).
- Commit `3fd8a13` exists in git log (verified).

## Next Plan Readiness

- VER-10 test #4 is in place; one of the remaining four VER-10 race tests in Wave 3 (Plans 46-09 / 46-10 / 46-11 / 46-13 per the wave layout in `46-CONTEXT.md` §186) can now build on the same `real_commit_engine` + `_sign()`-helper pattern.
- No blockers for the Wave 3 cohort.

---
*Phase: 46-openapi-handoff-milestone-verification*
*Completed: 2026-05-20*
