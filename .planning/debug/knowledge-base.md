---
status: complete
type: knowledge-base
note: Not an active debug session — this file is the permanent registry of resolved debug patterns used by gsd-debugger to surface known-pattern hypotheses on new investigations. The `status: complete` frontmatter suppresses audit-open false-positives.
---

# GSD Debug Knowledge Base

Resolved debug sessions. Used by `gsd-debugger` to surface known-pattern hypotheses at the start of new investigations.

---

## test-debt-sweep-v19 — backend test-suite debt sweep (stale tests, model/migration drift, lifespan probe pollution)
- **Date:** 2026-05-24
- **Error patterns:** HandlerContext missing bookings_service schedule_service, AuditLog has no attribute event_name, ERROR at setup TimeoutError asgi_lifespan, alembic check detected drift remove_table online_refunds remove_index ix_clients_email_lower_unique, PtPackageNotActiveError vs PtPackageExpiredBeforeSlotError, WorkerSettings.functions len assert, route missing require_permission gate, repository must NOT import schedule, alembic head revision mismatch
- **Root cause:** (A) tests referenced old code shape after Phase 40/44/52 changes. (C) alembic env.py never imported online_refunds.models + clients model missing lower(email) partial-UNIQUE Index = real model/migration drift; other Class C items were stale tests (substring-matched own docstring; past end_date fixture; fixed-head-revision assert). (B) build_yookassa_client made a real network /v3/me boot probe on every app-lifespan startup; per-test create_app()+LifespanManager accumulated latency exceeded asgi-lifespan's 5s startup timeout -> non-deterministic setup ERRORs.
- **Fix:** Updated stale tests to current shape; AST-parse imports instead of substring; relative expired-before-slot fixture; history-based revision check. Registered online_refunds model in alembic/env.py + declared ix_clients_email_lower_unique on clients model. Skip yookassa boot probe when settings.sandbox is True.
- **Files changed:** tests/integration/telegram/test_handler_start.py, tests/integration/memberships/test_freeze_resolver.py, tests/integration/telegram_bot/test_book_callback.py, tests/unit/workers/test_worker_settings.py, tests/integration/test_route_introspection.py, tests/integration/bookings/test_bookings_router_smoke.py, tests/integration/bookings/test_create_booking_via_bot.py, tests/integration/alembic/test_migration_0033_clients_email.py, alembic/env.py, app/modules/clients/models.py, app/integrations/yookassa/factory.py
---
