---
phase: 79-payment-methods-foundation-card-on-file
plan: 03
subsystem: backend-payments
tags: [fastapi, sqlalchemy, yookassa, payment-methods, webhook, integration-test, raw-sql]

# Dependency graph
requires:
  - phase: 79-01
    provides: client_payment_methods table + save_payment_method column on online_payments
  - phase: 79-02
    provides: payment_methods module (repository/service/schemas)
provides:
  - YooKassaPaymentMethodInfo frozen dataclass (id/last4/card_type/expiry)
  - payment_method field on YooKassaPaymentResult populated by get_payment parse
  - save_payment_method flag propagated: checkout body -> router -> service -> invoke_client_checkout_core -> _sell_subject_core -> online_payments row -> create_payment
  - webhook step 8.5: raw-SQL upsert into client_payment_methods on payment.succeeded (idempotent)
  - 3 integration tests: save=true row, save=false no row, replay idempotency
affects:
  - 79-04 — client_portal router endpoints for payment-method GET/DELETE/PATCH can now read tokens saved via this step

# Tech tracking
tech-stack:
  added: []
  patterns:
    - save_payment_method flag: kwargs-only default-False threading through 4-layer call chain
    - get_payment bank_card parse: pm.get("card") sub-object with int(expiry_month/year) guards
    - ON CONFLICT (client_id) WHERE unlinked_at IS NULL: partial index predicate form (not ON CONSTRAINT)
    - step 8.5 raw-SQL upsert inside existing async with session.begin() block — atomic with UoW

key-files:
  modified:
    - apps/backend/app/integrations/yookassa/types.py
    - apps/backend/app/integrations/yookassa/client.py
    - apps/backend/app/modules/client_portal/schemas.py
    - apps/backend/app/modules/client_portal/router.py
    - apps/backend/app/modules/client_portal/service.py
    - apps/backend/app/modules/online_payments/service.py
    - apps/backend/app/modules/online_payments/repository.py
    - apps/backend/app/api/v1/_internal/yookassa/handlers.py
  created:
    - apps/backend/tests/integration/client_portal/test_payment_method_webhook_save.py

key-decisions:
  - "ON CONFLICT (client_id) WHERE unlinked_at IS NULL instead of ON CONFLICT ON CONSTRAINT: partial unique indexes are not pg_constraint entries in PostgreSQL — the predicate form is required"
  - "Payment method field on YooKassaPaymentResult uses from __future__ import annotations so forward-ref string annotation not needed (UP037)"
  - "insert_online_payment repository updated to accept save_payment_method param (always written, not conditional), consistent with other columns"

# Metrics
duration: 30min
completed: 2026-06-03
---

# Phase 79 Plan 03: Checkout + Webhook Save Step Summary

**save_payment_method flag wired end-to-end (checkout body -> yookassa create_payment -> online_payments row -> webhook step 8.5 raw-SQL upsert into client_payment_methods); 3 integration tests pass including replay idempotency**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-06-03T13:00:00Z
- **Completed:** 2026-06-03T13:11:40Z
- **Tasks:** 3
- **Files modified:** 8
- **Files created:** 1

## Accomplishments

- `YooKassaPaymentMethodInfo` frozen dataclass added to `types.py` (id/last4/card_type/expiry_month/expiry_year; cloudpickle-safe, no app.modules import)
- `payment_method: YooKassaPaymentMethodInfo | None` appended to `YooKassaPaymentResult`
- `create_payment` gains `save_payment_method: bool = False`; sets `body["save_payment_method"] = True` only when True (body byte-identical when False)
- `get_payment` parses `payment_method.type == "bank_card"` into `YooKassaPaymentMethodInfo`; card fields never logged (T-79-08)
- `ClientCheckoutRequest` gains `save_payment_method: bool = False` (wire: `savePaymentMethod`)
- Both checkout handler call sites in `client_portal/router.py` pass `save_payment_method=payload.save_payment_method`
- Both `client_checkout_membership` + `client_checkout_pt_package` in `client_portal/service.py` accept and forward `save_payment_method` into `invoke_client_checkout_core`
- `_sell_subject_core` accepts `save_payment_method`, passes to both `create_payment` calls and to `insert_online_payment`
- `insert_online_payment` repository accepts `save_payment_method`; always writes it to the `OnlinePayment` row
- Webhook `handle_payment_succeeded` step 8.5: raw-SQL upsert into `client_payment_methods` with `ON CONFLICT (client_id) WHERE unlinked_at IS NULL DO UPDATE`; `payment_method_saved` log event carries only `client_id` + `online_payment_id` (no card fields, T-79-08)
- 3 integration tests: save=True row saved with correct fields; save=False no row; replay exactly 1 active row
- ruff + mypy + lint-imports all 0 (3 contracts kept, 0 broken); zero new ignore_imports edges

## Files Created/Modified

- `apps/backend/app/integrations/yookassa/types.py` — YooKassaPaymentMethodInfo dataclass + payment_method field on YooKassaPaymentResult
- `apps/backend/app/integrations/yookassa/client.py` — save_payment_method kwarg on create_payment; bank_card parse in get_payment
- `apps/backend/app/modules/client_portal/schemas.py` — save_payment_method field on ClientCheckoutRequest
- `apps/backend/app/modules/client_portal/router.py` — pass save_payment_method at both checkout call sites
- `apps/backend/app/modules/client_portal/service.py` — save_payment_method threaded through both checkout functions
- `apps/backend/app/modules/online_payments/service.py` — save_payment_method in _sell_subject_core + both create_payment calls + insert_online_payment call
- `apps/backend/app/modules/online_payments/repository.py` — save_payment_method param in insert_online_payment
- `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — webhook step 8.5 card upsert (ON CONFLICT partial index form)
- `apps/backend/tests/integration/client_portal/test_payment_method_webhook_save.py` — 3 integration tests (save/no-save/replay)

## Decisions Made

- `ON CONFLICT (client_id) WHERE unlinked_at IS NULL` (partial index predicate form) instead of `ON CONFLICT ON CONSTRAINT` — PostgreSQL partial unique indexes created with `CREATE INDEX ... WHERE ...` are not entries in `pg_constraint`; the `ON CONSTRAINT` clause requires a named constraint object
- `YooKassaPaymentMethodInfo` defined AFTER `YooKassaPaymentResult` in types.py — safe because `from __future__ import annotations` makes all annotations lazily evaluated; ruff UP037 auto-fix removed the string quote wrapper
- `save_payment_method` always written in `insert_online_payment` (not conditional like `promo_code_id`) — it has a server_default of false, so explicit False is safe and simplifies the kwargs dict

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ON CONFLICT ON CONSTRAINT syntax for partial unique index**
- **Found during:** Task 3 (first pytest run)
- **Issue:** The PATTERNS.md step 8.5 template used `ON CONFLICT ON CONSTRAINT uq_client_payment_methods_client_id_alive`. In PostgreSQL, partial unique indexes (created via `CREATE INDEX ... WHERE ...`) are NOT named constraints in `pg_constraint`. The `ON CONSTRAINT` form only works with constraint objects (UNIQUE constraints declared in DDL). The migration used `op.create_index(...)` not `op.create_unique_constraint(...)`.
- **Error:** `asyncpg.exceptions.UndefinedObjectError: constraint "uq_client_payment_methods_client_id_alive" for table "client_payment_methods" does not exist`
- **Fix:** Changed to `ON CONFLICT (client_id) WHERE unlinked_at IS NULL DO UPDATE` — the partial index predicate form, which matches how the index was created in migration 0052
- **Files modified:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py`
- **Commit:** 92b5488a

**2. [Rule 1 - Bug] Removed forward-ref string quotes from YooKassaPaymentMethodInfo annotation**
- **Found during:** Task 1 (ruff UP037)
- **Issue:** The PATTERNS.md template used string-quoted annotation for YooKassaPaymentMethodInfo; ruff UP037 rejects it when `from __future__ import annotations` is present (all annotations are already strings)
- **Fix:** Changed `"YooKassaPaymentMethodInfo | None"` to `YooKassaPaymentMethodInfo | None`
- **Files modified:** `apps/backend/app/integrations/yookassa/types.py`
- **Commit:** be576685

## Threat Surface Scan

No new threat surface beyond the plan's threat model:
- T-79-07: Token captured ONLY from get_payment re-fetch (PAYM-01 / D-06 / D-50-18); never from webhook body
- T-79-08: payment_method_saved log event emits only client_id + online_payment_id; no card fields in any structlog event
- T-79-09: ON CONFLICT partial-index upsert — replay updates single active row; test 3 asserts idempotency
- T-79-10: Only token + last4/brand/expiry stored; full PAN/CVV never present in YooKassaPaymentMethodInfo or the upsert

## Known Stubs

None. All data wiring is complete for the save path. The client-readable payment method endpoints (GET/DELETE/PATCH) are in plan 79-04 and intentionally out of scope.

## Self-Check: PASSED

Files verified:
- apps/backend/app/integrations/yookassa/types.py: FOUND
- apps/backend/app/integrations/yookassa/client.py: FOUND
- apps/backend/app/modules/client_portal/schemas.py: FOUND
- apps/backend/app/modules/client_portal/router.py: FOUND
- apps/backend/app/modules/client_portal/service.py: FOUND
- apps/backend/app/modules/online_payments/service.py: FOUND
- apps/backend/app/modules/online_payments/repository.py: FOUND
- apps/backend/app/api/v1/_internal/yookassa/handlers.py: FOUND
- apps/backend/tests/integration/client_portal/test_payment_method_webhook_save.py: FOUND

Commits verified:
- be576685 (task 1 — yookassa types + client): FOUND
- 32035174 (task 2 — propagation chain + webhook step 8.5): FOUND
- 92b5488a (task 3 — integration tests + ON CONFLICT fix): FOUND
