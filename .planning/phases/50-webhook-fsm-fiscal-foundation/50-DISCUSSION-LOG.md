# Phase 50: Webhook FSM + Fiscal Foundation - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-05-22
**Phase:** 50-Webhook-FSM-Fiscal-Foundation
**Mode:** `--auto` (no interactive prompts; Claude auto-selected recommended defaults)
**Areas discussed:** Webhook router location, IP gate ordering, Redis dedup formula, re-fetch ordering, FSM transitions, atomic UoW shape, cancellation path, fiscal_receipts ORM + Alembic 0035, FISCAL-03 AST gate, activator body fills, post-commit notification seam, test strategy

---

## Webhook router placement

| Option | Description | Selected |
|--------|-------------|----------|
| `app/api/v1/_internal/yookassa/router.py` + `handlers.py` split | Mirror `_internal/email/router.py` structural template; router owns transport, handlers own business logic | ✓ |
| `app/modules/yookassa_webhook/router.py` as a new domain module | More symmetric with `online_payments`/`fiscal_receipts` | |
| Inline into `app/modules/online_payments/router.py` | Co-locate with the matching outbound POST endpoints | |

**Auto-selection rationale:** Phase 42 D-42-17 established the `_internal` namespace for transport-layer webhook surfaces. Webhook is NOT a domain module — it is a callback boundary. Co-locating with `online_payments/router.py` mixes inbound + outbound auth models (sell endpoints need RBAC + CSRF; webhook is anonymous + IP-gated).

**Notes (D-50-01..03):** Two-file split (router.py + handlers.py) keeps the ASGI route signature lean and makes per-event business-logic tests targetable.

---

## IP gate ordering

| Option | Description | Selected |
|--------|-------------|----------|
| `dependencies=[Depends(verify_yookassa_ip)]` on the route decorator | Resolves BEFORE body parse; matches `_internal/email/router.py:101` precedent | ✓ |
| Signature-level `Depends(verify_yookassa_ip)` in function args | More visible at function | |
| Middleware-based IP gate | More general-purpose | |

**Auto-selection rationale:** ROADMAP SC#1 + AST-gate test require IP dependency BEFORE body parse. Route-level `dependencies=[...]` is the only FastAPI mechanism that guarantees this ordering.

**Notes (D-50-04..06):** AST gate test ensures the literal `dependencies=[Depends(verify_yookassa_ip)]` form is present.

---

## Redis dedup key formula

| Option | Description | Selected |
|--------|-------------|----------|
| `sz:yookassa:webhook:{event_type}:{object_id}`, TTL 24h | PITFALLS line 64 — `(event_type, object.id)` is the natural key | ✓ |
| Just `object_id`, TTL 24h | Simpler | |
| Hash of full body, TTL 24h | Most defensive against ЮKassa retry variants | |

**Auto-selection rationale:** PITFALLS Pitfall 2 explicitly rejects option 2 (`payment.succeeded` and `payment.canceled` are distinct events for the same payment object). Option 3 is over-engineered; ЮKassa is deterministic on retries.

**Notes (D-50-07..10):** SET NX + EX in a single command; ttl 86400 matches ЮKassa's retry window. Dedup runs BEFORE re-fetch to save ЮKassa rate-budget.

---

## Re-fetch ordering (WH-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Call `GET /v3/payments/{id}` before any DB write; trust the re-fetch result, not the webhook body | PITFALLS Pitfall 1 — re-fetch is the cryptographic anchor | ✓ |
| Trust the webhook body status field directly | Simpler | |
| Re-fetch optionally based on `event_type` | Mixed model | |

**Auto-selection rationale:** PITFALLS Pitfall 1 is BLOCKER severity; SC#2 directly mandates this discipline. Option 2 enables spoof attacks (no HMAC on the webhook). Option 3 is unnecessary complexity.

**Notes (D-50-11..14):** Status-source-of-truth = `result.status`. Pending-status re-fetch returns 200 + no DB write (Redis dedup key still set — next retry hits the same key + short-circuits).

---

## Payment FSM declaration site

| Option | Description | Selected |
|--------|-------------|----------|
| `ONLINE_PAYMENT_STATUS_TRANSITIONS` in `app/modules/online_payments/constants.py`; `_assert_can_transition` guard in `app/api/v1/_internal/yookassa/handlers.py` | Domain constant in the domain module; webhook-specific guard in the webhook layer | ✓ |
| Both in `app/modules/online_payments/service.py` | Mirror Phase 49's sell flow location | |
| Both in `app/api/v1/_internal/yookassa/handlers.py` | Co-locate transition table + guard | |

**Auto-selection rationale:** The FSM is a domain truth (used by future read endpoints, dashboards); the guard is webhook-specific. Splitting matches the Phase 16 pattern where `MEMBERSHIP_STATUS_TRANSITIONS` lives in `memberships/constants.py:22` but `_assert_can_transition` lives in `memberships/service.py:208`.

**Notes (D-50-15..17):** Illegal transitions return HTTP 200 + structlog WARNING + audit row (NOT 4xx — avoids ЮKassa retry storm for unrecoverable states).

---

## Atomic UoW shape

| Option | Description | Selected |
|--------|-------------|----------|
| Single `async with session.begin()` covering all 7 steps (status update, ledger row, activator, fiscal-receipt INSERT, 2 audit emits) | Matches PITFALLS Pitfall 12 (atomic compliance) | ✓ |
| Two transactions: payment+ledger first, activator+fiscal second | Easier to debug | |
| Saga pattern with explicit rollback compensations | Most defensive | |

**Auto-selection rationale:** PITFALLS Pitfall 12 is explicit: "atomic UoW for multi-step online payment flow" — partial commits create silent compliance holes. ROADMAP SC#4 word "all in the same commit" locks the single-txn shape.

**Notes (D-50-18..21):** SELECT-FOR-UPDATE on the OnlinePayment row to serialize concurrent deliveries. Post-commit notification enqueue is a no-op stub for Phase 52 to fill.

---

## Cancellation path

| Option | Description | Selected |
|--------|-------------|----------|
| Atomic UoW: status update + `online_payment_canceled` audit emit; no activator, no fiscal-receipt | Per SC#5 — cancellation has no fiscal obligation | ✓ |
| Same as succeeded but with `status='canceled'` | Symmetric | |

**Auto-selection rationale:** Cancelled payments never produced fiscal obligation (no 54-ФЗ receipt needed). Activator must NOT run.

**Notes (D-50-25..27):** `cancellation_party` and `cancellation_reason` extracted from `body["object"]["cancellation_details"]` (both nullable per ЮKassa spec). NOT-05 DM enqueue deferred to Phase 52.

---

## `fiscal_receipts` placement

| Option | Description | Selected |
|--------|-------------|----------|
| New module `app/modules/fiscal_receipts/` (constants + models + repository, no router/service in Phase 50) | Matches v1.5+ module skeleton; Phase 51 fills router/service for dispatch | ✓ |
| Inline as ORM in `app/modules/online_payments/models.py` | Co-locate with related table | |
| `app/core/fiscal_receipts.py` flat file | Lightweight | |

**Auto-selection rationale:** Phase 51 will add ARQ dispatch + webhook handler + circuit breaker — those need a full module skeleton. Pre-building the directory shape avoids a Phase 51 refactor.

**Notes (D-50-28..32):** FK to `payments.id` (NOT `online_payments.id`) per FEATURES.md line 104. UNIQUE `(payment_id, kind)` allows both payment + refund receipts for the same ledger row but no duplicates.

---

## FISCAL-03 AST gate

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `tests/unit/test_locked_yookassa_constants_ast.py` with `payment_subject` + `payment_mode` literal gates | Phase 47/48 AST-gate file already exists; additive | ✓ |
| New test module | Cleaner separation | |
| Runtime check in `build_receipt_item` | Earlier failure | |

**Auto-selection rationale:** Phase 47/48 INFRA-15 established AST-gate-per-locked-constant discipline; additive extension is the established pattern. Runtime checks fire too late (would surface only at first sell).

**Notes (D-50-33..34):** Phase 49's `service.sell_*` already passes enum members; Phase 50's gate prevents Phase 51 refund / Phase 52 templates from drifting to non-literal callsites.

---

## Composition root edits

| Option | Description | Selected |
|--------|-------------|----------|
| Zero edits — activator bodies fill the Phase 49 stub functions in-place; registrations stay as-is | Phase 49 plan 49-06 already wired the registrations | ✓ |
| Re-register with new function references | Defensive | |

**Auto-selection rationale:** Phase 47 D-47-01 designed Protocol slots for body-fill workflow. Re-registering would be a no-op (function references are stable).

**Notes (D-50-36..38):** `FiscalReceiptDispatcher` stays as Phase 49's stub — Phase 50 writes fiscal-receipt rows directly inside the webhook UoW; ARQ dispatch is Phase 51.

---

## Wave / plan shape (D-50-44)

Suggested ordering for `gsd-plan-phase`:
- **Wave 1 (sequential):** 50-01 Alembic 0035 + fiscal_receipts module skeleton; 50-02 ONLINE_PAYMENT_STATUS_TRANSITIONS + 2 new LOCKED audit events + payloads.
- **Wave 2 (parallel after Wave 1):** 50-03 activator bodies; 50-04 webhook router + handlers; 50-05 FISCAL-03 AST gate.
- **Wave 3 (sequential after Wave 2):** 50-06 E2E integration tests + route-introspection exclusion.

Estimated plan count: 6.

---

## Claude's Discretion

Areas where downstream agents may settle without re-asking (full detail in CONTEXT.md `<decisions>` Claude's Discretion subsection):

- structlog logger naming convention (`api.v1._internal.yookassa`)
- Webhook body Pydantic shape (permissive `extra='allow'`)
- HTTP response shape (200 + plain-text "ok")
- Unsupported event type handling (no-op INFO log)
- PII discipline in log lines (no `customer_email` in structlog)
- `OnlinePayment.client.email` JOIN strategy (selectinload vs separate scalar)

## Deferred Ideas

Full list in CONTEXT.md `<deferred>`:

- `payment.waiting_for_capture` handling — Phase 53
- `refund.succeeded` handling — Phase 51
- `receipt.succeeded` / `receipt.canceled` — Phase 51
- ARQ dispatch + circuit breaker + cron — Phase 51
- Post-commit notification enqueue — Phase 52
- Operator runbook for cancellation enum values — Phase 53
- `yookassa_call_failed` audit event — deferred again to Phase 51 unless verification flags
- Pre-existing `test_alembic_clean` failure — Phase 53
- Orphan recovery cron — Phase 53
