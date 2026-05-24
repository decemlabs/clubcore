---
status: resolved
trigger: "Fix pre-existing backend test-suite debt (v1.9 DEFER-36-04-A/DEFER-46-04). uv run pytest green. Baseline 12 failed + 14 errors + 1967 passed. Classes A (stale tests), B (DB pollution), C (investigate)."
created: 2026-05-23
updated: 2026-05-23
---

## Current Focus

hypothesis: Reproduce baseline first
test: full suite run
expecting: 12 failed + 14 errors
next_action: run full suite to capture baseline

## Symptoms

expected: uv run pytest green
actual: 12 failed + 14 errors + 1967 passed
errors: |
  Class A: HandlerContext.__new__() missing bookings_service/schedule_service; AuditLog has no attribute event_name
  Class B: order-dependent DB pollution (trainers crud, refresh inactive, rbac owner_only)
  Class C: alembic clean, migration 0033, bookings no_direct_schedule_import, create_booking_via_bot pt_package expired, slot_cancel_cascade rollback
reproduction: cd apps/backend && uv run pytest -p no:cacheprovider
started: pre-existing debt

## Eliminated

## Evidence

## Resolution

root_cause: |
  Class A (STALE): HandlerContext gained bookings_service/schedule_service (Phase 40);
    AuditLog.event_name renamed to .action; WorkerSettings.functions grew to 11
    (Phase 52 dispatch_payment_notification); route introspection EXCLUDED_PATHS
    missed Phase 44 RESET-01/02/04 anonymous endpoints.
  Class C (mixed): test_repository_no_direct_schedule_import naive substring matched
    its own docstring (STALE); create_booking_via_bot expired fixture used past
    end_date so package was inactive -> wrong error (STALE); 0033 test asserted a
    fixed head revision (STALE). REAL: alembic env.py never imported
    online_refunds.models (autogenerate wanted to DROP the table); clients model
    missing the lower(email) partial-UNIQUE Index from migration 0033.
  Class B (ISOLATION, root cause): build_yookassa_client ran a real network probe
    (GET api.yookassa.ru/v3/me) on EVERY app-lifespan startup. One create_app() +
    LifespanManager per test -> accumulated/throttled probe latency intermittently
    exceeded asgi-lifespan's 5s startup timeout -> non-deterministic "ERROR at setup".
fix: |
  - tests: HandlerContext placeholders; AuditLog.action; worker count 11; route
    EXCLUDED_PATHS; AST-based import check; relative expired-before-slot fixture;
    history-based 0033 revision check.
  - app/alembic: register online_refunds model in env.py; declare
    ix_clients_email_lower_unique Index on clients model.
  - app: skip yookassa boot probe when settings.sandbox is True.
verification: |
  Full suite: 1992 passed, 6 skipped, 0 failed, 0 errors (was 11 failed + 17 errors
  + 1964 passed). alembic check clean. ruff + mypy clean on edited files. Runtime
  7:45 -> 3:37 (probe network calls removed).
files_changed:
  - tests/integration/telegram/test_handler_start.py
  - tests/integration/memberships/test_freeze_resolver.py
  - tests/integration/telegram_bot/test_book_callback.py
  - tests/unit/workers/test_worker_settings.py
  - tests/integration/test_route_introspection.py
  - tests/integration/bookings/test_bookings_router_smoke.py
  - tests/integration/bookings/test_create_booking_via_bot.py
  - tests/integration/alembic/test_migration_0033_clients_email.py
  - alembic/env.py
  - app/modules/clients/models.py
  - app/integrations/yookassa/factory.py
