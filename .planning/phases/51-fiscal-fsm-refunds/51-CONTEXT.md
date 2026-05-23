# Phase 51: Fiscal FSM + Refunds — Context

**Gathered:** 2026-05-23
**Status:** Ready for planning
**Mode:** `--auto` (recommended defaults applied; decisions logged inline)

<domain>
## Phase Boundary

Phase 51 closes the v1.7 online-payment loop by shipping:

1. **Fiscal receipt FSM dispatch + monitoring** — the `fiscal_receipts(status='sent')` rows that Phase 50 inserts atomically inside the `payment.succeeded` UoW are now picked up by an ARQ task, posted to ЮKassa 54-ФЗ `/receipts`, retried with backoff under a circuit breaker, transitioned to `succeeded` / `failed` via webhook (`receipt.succeeded` / `receipt.canceled`), and reconciled by a stale-pending cron.
2. **Online refunds** — operator can call `POST /api/v1/online-payments/memberships/{id}/refund` (and the PT-package analogue); the endpoint creates a tracked refund request, calls ЮKassa `POST /v3/refunds`, returns **202**, then the inbound `refund.succeeded` webhook completes the refund atomically: writes the signed `payments` ledger row, transitions the membership / PT-package to a refunded terminal state (Phase 32 sentinel reuse), INSERTs a `fiscal_receipts(kind='refund', status='sent')` row, and enqueues notifications. A second cron `poll_pending_refunds` reconciles refunds whose webhook never arrived.

Requirements covered: **FISCAL-04, FISCAL-05, FISCAL-06, FISCAL-07 + REFUND-01, REFUND-02, REFUND-03, REFUND-04** (8 reqs). 6 success criteria locked by ROADMAP.md.

**Out of phase (explicit):**
- Telegram / email notifications for refund + fiscal-failure events — Phase 52 NOTIFY-01..05 fills the `_post_commit_enqueue` stub Phase 50 shipped.
- DEFER-46-03 cron-chain circuit-breaker re-run — Phase 53 (will exercise the new `sz:yookassa:circuit:receipts` breaker naturally).
- Operator runbook for cancellation enum values / sandbox walkthrough — Phase 53 VER-01..03.
- `payment.waiting_for_capture` handler — DEFER-50-01, Phase 53.
- Orphan recovery cron `reconcile_orphan_yookassa_payments` — DEFER-50-02, Phase 53.
- v1.4 partial-refund (B-02) — still deferred to v1.8+; Phase 51 ships full refund only.

Phase 47 / 48 / 49 / 50 carry-forward:
- `YooKassaClient.create_refund(...)` + `get_refund(...)` (Phase 48 ADAPTER-02; `apps/backend/app/integrations/yookassa/client.py:350` + `:445`) — refund endpoint + reconciliation cron call these directly.
- `YooKassaSettings.tax_system_code` + `YooKassaSettings.default_vat_code` (Phase 47 FISCAL-07 prerequisites; `apps/backend/app/integrations/yookassa/settings.py:50-51`) — Phase 51 dispatch task consumes them.
- `FiscalReceiptDispatcher` Protocol slot (`apps/backend/app/core/dependencies.py:1019-1066`) — Phase 49 wired stub raising `NotImplementedError`; **Phase 51 ships the real implementation** that enqueues `dispatch_fiscal_receipt` ARQ task.
- All v1.7 LOCKED audit events already pre-registered by Phase 47 INFRA-35: `fiscal_receipt_dispatched`, `fiscal_receipt_succeeded`, `fiscal_receipt_failed`, `online_payment_refunded` (`apps/backend/app/core/audit.py:343-360`). **Phase 51 only emits; never declares.**
- `fiscal_receipts` table + UNIQUE `(payment_id, kind)` (Phase 50 Alembic 0035) — Phase 51 ARQ task updates rows in place; `kind='refund'` insertion path is exercised in the refund UoW.
- `FISCAL_RECEIPT_STATUS_TRANSITIONS` constant (Phase 50 D-50-32, `apps/backend/app/modules/fiscal_receipts/constants.py`) already defines `sent → succeeded | failed` transitions — Phase 51 webhook handler + ARQ task USE this; no FSM constant edits.
- `ONLINE_PAYMENT_STATUS_TRANSITIONS` (Phase 50 D-50-15) — Phase 51 does NOT modify; refund flow does not transition `online_payments` itself (refund-of-refund handled by a sibling table; see D-51-04).
- `_internal/yookassa/router.py` + `handlers.py` (Phase 50 D-50-01) — Phase 51 ADDS three new handlers (`handle_receipt_succeeded`, `handle_receipt_canceled`, `handle_refund_succeeded`) and extends the event-type dispatch chain in `router.py`.
- Phase 32 / 33 offline refund precedent (`refund_membership` / `refund_pt_package`) — provides the CANCELLATION_REASON_REFUNDED sentinel, the `PaymentRefunder` Protocol slot, and the `membership_refunded` / `pt_package_refunded` audit events that Phase 51 webhook handler reuses verbatim.

</domain>

<decisions>
## Implementation Decisions

### Module layout — split refund request (transport) from refund completion (webhook)

- **D-51-01:** Refund request endpoint lives in a **new** `apps/backend/app/api/v1/online_payments/` package (sibling of `_internal/yookassa/`), creating the user-facing surface for the Phase 49 online-payment module:
  ```
  apps/backend/app/api/v1/online_payments/
  ├── __init__.py           # module marker
  ├── router.py             # POST /memberships/{id}/refund + POST /pt-packages/{id}/refund (REFUND-01)
  └── schemas.py            # OnlineRefundRequest / OnlineRefundResponse Pydantic shapes
  ```
  Mounted in `app/api/v1/router.py` at `prefix="/online-payments"`, `tags=["online-payments"]`. Full paths: `POST /api/v1/online-payments/memberships/{id}/refund` and `POST /api/v1/online-payments/pt-packages/{id}/refund`.
- **D-51-02:** Refund **webhook** handlers stay in the Phase 50 `_internal/yookassa/handlers.py` namespace — three new functions `handle_refund_succeeded`, `handle_receipt_succeeded`, `handle_receipt_canceled` added to that file. Rationale: keeps the entire ЮKassa webhook event-dispatch table in one module (router.py's `if event == ...` chain stays cohesive); each handler shares the dedup + chain-correlation discipline already shipped.
- **D-51-03:** Three new event-type branches added to `app/api/v1/_internal/yookassa/router.py` event dispatch chain (after Phase 50's `payment.succeeded` / `payment.canceled`):
  ```python
  elif event_type == "refund.succeeded":
      await handle_refund_succeeded(session, yookassa_client, body=body)
  elif event_type == "receipt.succeeded":
      await handle_receipt_succeeded(session, body=body)
  elif event_type == "receipt.canceled":
      await handle_receipt_canceled(session, body=body)
  ```
  Re-fetch policy applies ONLY to `refund.succeeded` (financial state change requires authoritative re-read per Phase 50 D-50-12). `receipt.succeeded` / `receipt.canceled` accept the webhook body as authoritative because receipt status is informational (no money moves); a re-fetch would still be against the ЮKassa receipt object whose state is what triggered the webhook — adds latency without changing trust posture.

### New `online_refunds` request-tracking table — separate from `payments` ledger

- **D-51-04:** New table `online_refunds` mirrors `online_payments` shape but tracks the **refund request lifecycle** (pending → succeeded / canceled). This is **not** a ledger row — the `payments` table (with signed `amount_kopecks < 0` + `refund_of=<original_payment_id>` + partial UNIQUE) remains the canonical refund ledger row, written by the webhook UoW. The new table tracks the ЮKassa-side async request that may or may not settle.

  Columns:
  ```
  id                      UUID PK (UUIDv4 app-side default)
  online_payment_id       UUID FK online_payments.id ON DELETE RESTRICT
  original_payment_id     UUID FK payments.id ON DELETE RESTRICT  -- the v1.4 ledger sale row to refund
  client_id               UUID FK clients.id ON DELETE RESTRICT
  yookassa_refund_id      TEXT NOT NULL                            -- ЮKassa /v3/refunds response id
  idempotency_key         TEXT NOT NULL                            -- caller-owned (Phase 48 D-48-11)
  amount_kopecks          INTEGER NOT NULL CHECK (amount_kopecks > 0) -- stored positive; refund row in payments is negated
  status                  TEXT NOT NULL CHECK (status IN ('pending','succeeded','canceled'))
  requested_by_user_id    UUID FK users.id ON DELETE RESTRICT
  reason                  TEXT NULL                                -- operator-supplied
  audit_correlation_id    UUID NULL                                -- chains to online_refund_initiated audit row
  requested_at            TIMESTAMPTZ NOT NULL DEFAULT now()
  succeeded_at            TIMESTAMPTZ NULL
  canceled_at             TIMESTAMPTZ NULL
  created_at / updated_at TIMESTAMPTZ NOT NULL DEFAULT now()       -- composition: Base + UUIDPkMixin (no TimestampMixin per Phase 49 D-49-04)
  ```
  UNIQUE `(yookassa_refund_id)` — ЮKassa cannot reissue the same refund id.
  UNIQUE `(idempotency_key)` — caller-side replay protection (mirror `online_payments.idempotency_key`).
  Partial UNIQUE `(online_payment_id) WHERE status IN ('pending','succeeded')` — at most one in-flight or successful refund per original online payment; reconciliation cron uses this to short-circuit duplicate requests.

- **D-51-05:** **The `payments` partial UNIQUE `uq_payments_refund_of_alive` on `refund_of` is the second-layer defense** (REFUND-03). Webhook handler INSERTs the signed `payments` row inside a `try` block; on `IntegrityError` (existing refund row found via the partial UNIQUE), `_is_refund_of_uniqueness_conflict(exc)` (already shipped by Phase 32 in `app/modules/payments/repository.py`) returns True → return 200 OK to ЮKassa silently (idempotent replay) + WARNING log. **Do NOT raise 500.**

- **D-51-06:** Alembic 0036 creates `online_refunds` table. `down_revision = "0035_fiscal_receipts"`. Naming convention via `op.f()` (Phase 49 / 50 precedent). Downgrade lossless reverse.

- **D-51-07:** New `app/modules/online_refunds/` module mirroring `app/modules/online_payments/` shape:
  ```
  app/modules/online_refunds/
  ├── __init__.py
  ├── constants.py        # ONLINE_REFUND_STATUS_TRANSITIONS (pending → succeeded | canceled)
  ├── models.py           # OnlineRefund ORM
  ├── repository.py       # insert, get_by_yookassa_refund_id, get_pending_older_than, mark_succeeded, mark_canceled
  ├── service.py          # initiate_online_refund(...) — orchestrates the POST endpoint flow
  └── schemas.py          # OPTIONAL — may live in app/api/v1/online_payments/schemas.py per D-51-01
  ```
  Service is the txn owner for the **request** path; webhook handler is the txn owner for the **completion** path. Each owns its `async with session.begin()` block (caller-owns-txn discipline, D-49-13 / SVC001 gate).

### Online-refund request flow (REFUND-01)

- **D-51-08:** `POST /api/v1/online-payments/memberships/{id}/refund` endpoint sequence (single-transaction, idempotent):
  1. **RBAC**: `Depends(require_permission(action='refund', resource='membership'))` — reception + owner can both initiate (mirror Phase 32 `refund_membership` permission shape).
  2. **CSRF**: `Depends(verify_csrf)` — standard mutating endpoint (this is user-facing, not `_internal`).
  3. **Pydantic body**: `OnlineRefundRequest { reason: str | None, idempotency_key: UUID }` — caller-owned idempotency key per Phase 48 D-48-11. Required.
  4. Load original `Membership` row + `_assert_can_transition(target='cancelled')` (Phase 32 precedent — refund is a special-case cancellation). Apply Phase 32 guards verbatim: `MustUnfreezeFirstError` (B-08), `CannotRefundRenewedSourceError` (B-09). 409 on guard failure.
  5. Locate the original sale-side `OnlinePayment` row by `client_id` + `membership_plan_id` (XOR-guaranteed non-null per D-49-04). 404 `online_payment_not_found` if missing.
  6. Locate the original `payments` ledger row (the sale row written by Phase 50 `payment_recorder.record_payment(method='online')`). 404 `original_payment_not_found` if missing — this should be IMPOSSIBLE post-Phase-50 atomic UoW, but defend.
  7. Inside `async with session.begin()`:
     - INSERT `online_refunds(status='pending', online_payment_id=..., original_payment_id=..., yookassa_refund_id="", amount_kopecks=ABS(original.amount_kopecks), idempotency_key=caller_key, requested_by_user_id=actor.id, reason=...)`. **Note**: `yookassa_refund_id` is filled AFTER the ЮKassa call but BEFORE commit (see step 9). Schema default-empty + UPDATE-before-commit is acceptable; alternative is to delay INSERT until after the ЮKassa call (preferred — see D-51-09).
     - Emit `online_refund_initiated` audit (CHILD of nothing — fresh chain root for this user-initiated action; `audit_correlation_id=fresh_uuid4()`).
  8. **OUTSIDE the txn block** (after `session.begin()` exits → commit settled), call `await yookassa_client.create_refund(payment_id=<original.yookassa_payment_id>, amount_kopecks=ABS(original.amount_kopecks), idempotency_key=caller_key, ...)`.
  9. Re-open transaction with `async with session.begin()`: UPDATE the `online_refunds` row's `yookassa_refund_id = result.refund_id`. Commit.
  10. Return 202 + `OnlineRefundResponse { online_refund_id, status='pending', yookassa_refund_id }`.

- **D-51-09:** **Variant on D-51-08 step 7/8 — call ЮKassa BEFORE the INSERT** (preferred; planner verifies):
  1. Run guards (steps 1–6).
  2. Call `yookassa_client.create_refund(...)` BEFORE any DB write. If transient-error → 502 (caller retries with the SAME idempotency_key — ЮKassa dedupes); if permanent → 422.
  3. On success, single `async with session.begin()` INSERTs the `online_refunds` row with the real `yookassa_refund_id` already in hand + emits the audit row.
  4. Return 202.
  Trade-off: this leaks a successful ЮKassa refund creation if the DB INSERT fails afterward (the reconciliation cron D-51-15 backfills). vs D-51-08's two-phase commit which can leave an `online_refunds` row with empty `yookassa_refund_id` if the ЮKassa call fails (then the reconciliation cron would need to delete or retry — messier).
  **Recommended: D-51-09 (call-then-INSERT). The reconciliation cron + DB UNIQUE on `(yookassa_refund_id)` covers the leak case cleanly.**

- **D-51-10:** RBAC pair: `('refund', 'membership')` + `('refund', 'pt_package')` already registered in the permission catalog (Phase 32 / 33 shipped these for offline refunds). **No new permissions needed.** Verify with `grep -n "('refund'" apps/backend/app/core/permissions.py` before planner finalizes.

### `refund.succeeded` webhook completion flow (REFUND-02 / REFUND-03)

- **D-51-11:** `handle_refund_succeeded(session, yookassa_client, *, body: dict) -> None` lives in `_internal/yookassa/handlers.py`. Sequence (mirrors Phase 50 `handle_payment_succeeded`):
  1. `object_id = body["object"]["id"]` — this is the **refund** id (not the payment id).
  2. Re-fetch via `result = await yookassa_client.get_refund(object_id)` (existing client method, `apps/backend/app/integrations/yookassa/client.py:445`). If `classification != 'ok'` or `result.status != 'succeeded'`, return 200 + structlog WARNING `event="yookassa_refund_refetch_failed"`. No DB write.
  3. `webhook_intake_corr = uuid4()`.
  4. `async with session.begin()`:
     - SELECT `OnlineRefund` row by `yookassa_refund_id = object_id` with `with_for_update()`. If `row is None`, return 200 + structlog WARNING `event="yookassa_refund_webhook_orphan"`. (DEFER-51-XX: orphan-refund reconciliation cron in Phase 53; for now the 30-min poll D-51-15 catches lost-context cases on the operator side, while this branch handles the inverse — ЮKassa fires `refund.succeeded` for a refund our DB doesn't know about, which shouldn't happen unless someone refunded directly via ЮKassa dashboard.)
     - `_assert_can_transition_refund(row, target='succeeded')` (helper in `_internal/yookassa/handlers.py`, mirrors Phase 50 D-50-16 byte-for-byte against `ONLINE_REFUND_STATUS_TRANSITIONS`).
     - UPDATE `online_refunds.status='succeeded'`, `succeeded_at=now(UTC)`.
     - **Atomic ledger write** — call the existing `PaymentRefunder` Protocol slot (`apps/backend/app/core/dependencies.py:1184` ish, registered by Phase 32 plan 32-02). The refunder INSERTs the negative-amount refund row in `payments` (with `refund_of=row.original_payment_id`, `subject_kind='refund'`), or raises `AlreadyRefundedError` on `uq_payments_refund_of_alive` race. Catch `AlreadyRefundedError` → return 200 + structlog WARNING `event="yookassa_refund_idempotent_replay"` (REFUND-03 idempotent semantics).
     - **Activator-style** subject-transition: dispatch on `online_payment.membership_plan_id` vs `pt_package_plan_id`. For the membership branch: call `repository.update_membership_status(target='cancelled', cancellation_reason=CANCELLATION_REASON_REFUNDED, cancelled_at=now(UTC))` (Phase 32 D-32-08 reuse — exact precedent in `refund_membership`). For PT-package: mirror against `repository.update_pt_package_status(...)` + Phase 33 D-33-XX sentinel. **The Membership/PtPackage Activator Protocol slots are NOT used here** — the activator semantics ("activate from webhook") only fit forward transitions. The repository call is direct (handler is under `app.api.*`, unrestricted by importlinter contracts per Phase 50 D-50-20).
     - INSERT `fiscal_receipts(payment_id=refund_payment_id, kind='refund', status='sent', customer_email=client.email, sent_at=now(UTC), audit_correlation_id=webhook_intake_corr)`. The UNIQUE `(payment_id, kind)` on `fiscal_receipts` permits one `'payment'` + one `'refund'` row per ledger payment id, by design (Phase 50 D-50-30).
     - Emit `online_payment_refunded` audit (CHILD; `audit_correlation_id=webhook_intake_corr`).
     - Emit `membership_refunded` (or `pt_package_refunded`) audit (CHILD; reuse Phase 32 / 33 LOCKED events verbatim — `('membership_refunded', 'membership')` and `('pt_package_refunded', 'pt_package')` are pre-locked).
     - Emit `yookassa_webhook_received` audit (chain ROOT; `idempotency_outcome='processed'`).
  5. POST-COMMIT: enqueue notification via the Phase 50 `_post_commit_enqueue` stub (DEFER-50-04). Phase 51 leaves the stub as no-op (Phase 52 fills NOT-02 refund DMs).

- **D-51-12:** **Redis dedup applies to `refund.succeeded`** — Phase 50 D-50-07 dedup key formula `sz:yookassa:webhook:{event_type}:{object_id}` already covers refund events (event_type = `"refund.succeeded"`, object_id = refund id). No router edits needed; only the `handle_refund_succeeded` branch in the dispatch.

### `dispatch_fiscal_receipt` ARQ task (FISCAL-05)

- **D-51-13:** ARQ task lives at `apps/backend/app/modules/fiscal_receipts/tasks.py` (new file in the Phase 50 module). Signature:
  ```python
  async def dispatch_fiscal_receipt(ctx: dict[str, Any], fiscal_receipt_id: str) -> None: ...
  ```
  Registration: appended to `WorkerSettings.functions` list in `apps/backend/app/workers/__init__.py` (D-51-16 enumerates the worker-config delta).

  Execution:
  1. Load `FiscalReceipt` row by id; if `status != 'sent'`, return immediately (already terminal or never queued — defensive).
  2. **Check circuit breaker** `sz:yookassa:circuit:receipts` via `await is_circuit_open(redis, 'receipts')` — if open, raise `Retry(defer=300)` (ARQ defers without consuming a `try` count). Mirror pattern: `apps/backend/app/integrations/email/circuit_breaker.py`.
  3. Build the 54-ФЗ receipt body: customer email from `fiscal_receipts.customer_email`, items composed via `build_receipt_item()` (Phase 48 ADAPTER-04 helper; uses `PaymentSubject.SERVICE` + `PaymentMode.FULL_PAYMENT` for refunds — verify per ЮKassa /v3/receipts spec lines: `payment_subject="service"` + for refunds `type="refund"` at the envelope level, not item level), `tax_system_code` + `vat_code` from `YooKassaSettings`.
  4. Call `await yookassa_client.create_receipt(...)` — **new client method** (not in Phase 48; add to `app/integrations/yookassa/client.py` mirroring `create_payment` shape: idempotency key = `fiscal_receipt_id` hex; transient/permanent/ok classification on the response).
  5. On `classification == 'ok'`:
     - UPDATE `fiscal_receipts.status='succeeded'` is **NOT** done by the task — the inbound `receipt.succeeded` webhook authoritatively transitions. Task only records the dispatched `yookassa_receipt_id` and emits `fiscal_receipt_dispatched` audit.
     - Wait — re-check FSM: `FISCAL_RECEIPT_STATUS_TRANSITIONS` (Phase 50 D-50-32) has `sent → succeeded | failed`. The webhook does the `sent → succeeded` flip; the dispatcher writes `yookassa_receipt_id` (a TEXT column already nullable per Phase 50 D-50-29) into the row WITHOUT changing status.
  6. On `classification == 'transient_error'`: `record_failure(redis, 'receipts')` + raise `arq.Retry(defer=_backoff_with_jitter(ctx['job_try']))` — ARQ schedules the next try. `max_tries=3` set on the function registration.
  7. On `classification == 'permanent_error'` OR after `max_tries` exhausted: UPDATE `fiscal_receipts.status='failed'`, `failed_at=now(UTC)`, `failure_reason=<classification + status_code>`. Emit `fiscal_receipt_failed` audit. Enqueue NOT-04 owner alert via post-commit stub (Phase 52 fills).

- **D-51-14:** **Circuit breaker scoped to YooKassa receipts.** Recommended layout: `apps/backend/app/integrations/yookassa/circuit_breaker.py` — **copy-and-adapt from `apps/backend/app/integrations/email/circuit_breaker.py`** rather than generalize. Rationale: cross-integration coupling between email + yookassa modules would violate the `integrations-isolated` import-linter contract (verify before planning); separate modules keep the threshold + TTL knobs independent and the audit-event names domain-specific.
  - Key: `sz:yookassa:circuit:receipts`
  - Threshold: 5 failures in 60s → open
  - Open TTL: 5 minutes (300s)
  - Atomic pipeline (per Pitfall 11): `MULTI / INCR counter / EXPIRE counter 60 / EXEC` for `record_failure`; `EXISTS sz:yookassa:circuit:receipts:open` for `is_open`.
  - Backoff schedule (D-51-13 step 6): try 1 → 30s, try 2 → 120s, try 3 → 600s. Jitter ±10% to prevent thundering herd (Pitfall 11 step 4).

- **D-51-15:** `dispatch_fiscal_receipt` ARQ task is **enqueued by the Phase 50 `_post_commit_enqueue` seam** — i.e., Phase 51 fills part of the Phase 50 stub specifically for fiscal-receipt dispatch (separate from Phase 52 NOT-02 / NOT-04 notification enqueues which the same seam handles). **Critical**: D-51-13 expects the row to already have `status='sent'` (Phase 50 inserts directly as 'sent' inside the webhook UoW), so the dispatch is a Redis enqueue from the post-commit hook calling `arq_pool.enqueue_job('dispatch_fiscal_receipt', str(fiscal_receipt_id))`. The fill is additive to the Phase 50 stub: the stub currently no-ops; Phase 51 adds the fiscal-dispatch branch; Phase 52 will add the notification branches in the same function. **The AST gate `test_post_commit_enqueue_body_is_only_log_info` (Phase 50 DEFER-50-04) MUST be updated by Phase 51 in lockstep** — the body grows from single `_log.info()` to a multi-call sequence including `arq_pool.enqueue_job()`. The Phase 51 plan must add this gate update as a discrete task.

### `monitor_stale_fiscal_receipts` ARQ cron (FISCAL-06)

- **D-51-16:** Cron job runs **every 15 min Europe/Moscow** (REQUIREMENTS line for FISCAL-06 — "runs every 15 min"; ROADMAP success criterion 3 says "older than 90 seconds" for the trigger, so the cron cadence is 15min but the staleness window is 90s).
  - Registered in `WorkerSettings.cron_jobs` (`apps/backend/app/workers/__init__.py:141`) using `cron(monitor_stale_fiscal_receipts, minute={0, 15, 30, 45}, hour=set(range(24)), unique=True, run_at_startup=False)`. Phase 18 ARQ-03 pattern; `cron_resolves_to_registered_function` test (Phase 18) auto-validates the function is in `WorkerSettings.functions`.
  - Function body: SELECT all `fiscal_receipts WHERE status='pending' AND created_at < now() - interval '90 seconds'`. (Note: Phase 50 inserts as `status='sent'` directly, NOT `'pending'`. The `'pending'` state is the upstream-error case where the dispatch task itself fails to even start — but the FSM allows `pending → sent` per Phase 50 D-50-32. So `'pending'` rows are an anomaly indicating dispatch never ran. The monitor cron is the safety net.) For each row: UPDATE `status='failed'`, `failed_at=now(UTC)`, `failure_reason='stale_pending_no_dispatch'`. Emit `fiscal_receipt_failed` audit. Enqueue NOT-04 owner alert via post-commit stub.
  - **Implementation note:** Use a single SELECT-FOR-UPDATE-SKIP-LOCKED to avoid lock contention with the dispatch task (which may be writing `yookassa_receipt_id` to the same row). `SKIP LOCKED` is Postgres-specific and standard for queue-style scans.

### `poll_pending_refunds` ARQ cron (REFUND-04)

- **D-51-17:** Cron job runs **every 30 min Europe/Moscow** — registered alongside D-51-16. Body:
  1. SELECT all `online_refunds WHERE status='pending' AND requested_at < now() - interval '30 minutes'`.
  2. For each row: `result = await yookassa_client.get_refund(row.yookassa_refund_id)`.
  3. If `result.status == 'succeeded'` and we never received the webhook, **synthesize the same UoW as `handle_refund_succeeded`** (D-51-11 steps 4) — UPDATE the refund row + INSERT signed `payments` row + transition membership/pt-package + INSERT `fiscal_receipts(kind='refund')` + emit audits. The `webhook_intake_corr` is freshly allocated; the audit chain root is a `yookassa_refund_polled` (new event? See D-51-19) instead of `yookassa_webhook_received`.
  4. If `result.status == 'canceled'`: UPDATE `online_refunds.status='canceled'`, `canceled_at=now(UTC)`. Emit `online_refund_canceled` audit (new event — see D-51-19).
  5. If `result.classification != 'ok'`: structlog WARNING + leave row pending for next cron tick.
  6. **Loop budget**: process at most 50 rows per tick (defensive cap to avoid blocking the worker on a backlog; mirror Phase 27 expiring-notifications batch pattern).

- **D-51-18:** Refactor opportunity: the body of D-51-11 (`handle_refund_succeeded`) and D-51-17 step 3 (poll cron synthesizing the same flow) should share a helper: `async def _settle_online_refund(session, *, online_refund_id: UUID, chain_root_corr: UUID, chain_root_event: str) -> None` — single function called by both the webhook and the cron with different chain-root semantics. Planner refines the exact split.

### New LOCKED audit events Phase 51 needs to add

- **D-51-19:** Phase 47 INFRA-35 pre-registered most v1.7 audit events. Phase 51 needs to add the following new pairs to `LOCKED_AUDIT_EVENTS` in `app/core/audit.py` + corresponding payload classes in `audit_payloads.py`:
  - `("online_refund_initiated", "online_refund")` — emitted by the POST endpoint (D-51-09). Payload: `{audit_correlation_id, online_refund_id, online_payment_id, original_payment_id, amount_kopecks, requested_by_user_id, reason}`.
  - `("online_refund_polled_settled", "online_refund")` — emitted by the cron (D-51-17 step 3) as chain root when synthesizing the settle UoW after a missed webhook. Payload: `{online_refund_id, yookassa_refund_id, settled_at}`.
  - `("online_refund_canceled", "online_refund")` — emitted by the cron (D-51-17 step 4) when ЮKassa reports the refund as canceled. Payload: `{online_refund_id, yookassa_refund_id, cancellation_reason}`.
  - Resource type `'online_refund'` is **new** (not in the existing Phase 47 catalog of `online_payment` / `fiscal_receipt` / `yookassa_webhook` / `membership` / `pt_package`). Add to the resource-type catalog docstring.
  - **Effective new LOCKED events count: 14** (Phase 47 shipped 11; Phase 50 added 2 — `membership_activated_online` + `pt_package_activated_online`, bringing to 13; Phase 51 adds 3, reaching 14). Verify the running count in `LOCKED_AUDIT_EVENTS` after planning.
  - All three guarded by Phase 47 INFRA-35 AST gate.

### YooKassa client extension — `create_receipt` method

- **D-51-20:** Add `async def create_receipt(self, *, payment_id: str, customer_email: str, items: list[ReceiptItem], tax_system_code: int, idempotency_key: str) -> YooKassaReceiptResult` to `app/integrations/yookassa/client.py`. Shape mirrors `create_refund` (already shipped, line 350) byte-for-byte:
  - HTTP: `POST /v3/receipts` with Basic auth + Idempotence-Key header.
  - Result type: `YooKassaReceiptResult { receipt_id: str, status: str, classification: Literal['ok','transient_error','permanent_error'] }` — new dataclass in `app/integrations/yookassa/types.py`.
  - structlog event names: `yookassa_create_receipt_ok` / `yookassa_create_receipt_{classification}` (mirror line 382, 399).
  - Add respx fixtures: `yookassa_create_receipt_ok`, `yookassa_create_receipt_429`, `yookassa_create_receipt_500` in `apps/backend/tests/integrations/yookassa/conftest.py`.

### `receipt.succeeded` / `receipt.canceled` webhook handlers (FISCAL-04)

- **D-51-21:** `handle_receipt_succeeded(session, *, body: dict) -> None`:
  1. `yookassa_receipt_id = body["object"]["id"]`.
  2. `async with session.begin()`:
     - SELECT `FiscalReceipt` row WHERE `yookassa_receipt_id = body["object"]["id"]` with `with_for_update()`. (Phase 50 ARQ dispatch task writes this id to the row before this webhook arrives. If `row is None`, structlog WARNING `event="yookassa_receipt_webhook_orphan"` — defensive; should not happen if dispatch task always commits.)
     - `_assert_can_transition_receipt(row, target='succeeded')` (helper mirroring D-50-16 against `FISCAL_RECEIPT_STATUS_TRANSITIONS`).
     - UPDATE `fiscal_receipts.status='succeeded'`, `succeeded_at=now(UTC)`.
     - Emit `fiscal_receipt_succeeded` audit (CHILD; `audit_correlation_id=row.audit_correlation_id`).
     - Emit `yookassa_webhook_received` audit (chain root for this delivery).
  - **No re-fetch** — receipt status is informational; ЮKassa is the source of truth and the webhook body is sufficient (D-51-03).

- **D-51-22:** `handle_receipt_canceled` mirror: target='failed', emit `fiscal_receipt_failed` with `failure_reason=body["object"].get("cancellation_details", {}).get("reason", "yookassa_receipt_canceled")`.

### FISCAL-07 — already shipped

- **D-51-23:** `YOOKASSA_TAX_SYSTEM_CODE` + `YOOKASSA_VAT_CODE` are shipped by Phase 47 `YooKassaSettings.tax_system_code: int` (line 50) + `.default_vat_code: int` (line 51). Phase 51 dispatch task (D-51-13 step 3) CONSUMES these from `settings.yookassa.tax_system_code` + `settings.yookassa.default_vat_code` when building the receipt body. **No new env vars; no new settings code.** The deployment runbook entry documenting the per-deployment values is Phase 53 VER-01 territory. Phase 51 only consumes.

### Permissions / RBAC

- **D-51-24:** Refund endpoints use `Depends(require_permission(action='refund', resource='membership'))` (or `'pt_package'`). Both pairs are registered in `app/core/permissions.py` since Phase 32 (verify with grep before planning).
- **D-51-25:** Webhook handler entry point inherits Phase 50 `_internal` discipline — IP-gated, anonymous (D-50-39). `EXCLUDED_PATHS` in `test_route_introspection.py` already covers `/api/v1/_internal/yookassa/webhook`; **no edits needed** because Phase 51 adds event-type branches to the same URL, not new URLs.
- **D-51-26:** The new `POST /api/v1/online-payments/memberships/{id}/refund` + `.../pt-packages/{id}/refund` are user-facing routes — they MUST be picked up by the route-introspection test as **gated** (not excluded). Both have `Depends(require_permission(...))` + `Depends(verify_csrf)` → no `EXCLUDED_PATHS` entry needed.

### Test strategy

- **D-51-27:** Test placement:
  - `apps/backend/tests/integration/online_refunds/` — new directory. Tests for the POST endpoint + the refund webhook + the poll cron.
  - `apps/backend/tests/integration/webhook_yookassa/test_handle_refund_succeeded.py` — webhook completion path (reuses Phase 50 webhook test fixtures).
  - `apps/backend/tests/integration/webhook_yookassa/test_handle_receipt_succeeded.py` + `test_handle_receipt_canceled.py`.
  - `apps/backend/tests/integration/fiscal_receipts/test_dispatch_fiscal_receipt.py` — ARQ task tests using `tests/integration/conftest.py` `worker_runner` fixture (Phase 39 ARQ test scaffolding).
  - `apps/backend/tests/integration/fiscal_receipts/test_monitor_stale_cron.py` + `test_poll_pending_refunds_cron.py`.
  - `apps/backend/tests/unit/test_yookassa_circuit_breaker.py` — Redis pipeline atomicity, threshold/TTL math (reuse `fakeredis` or live `RedisClient` test fixture).
  - `apps/backend/tests/integrations/yookassa/test_create_receipt.py` — respx-based, covers ok/transient/permanent classifications.
- **D-51-28:** Coverage targets (high-level per success criterion):
  - SC #1 (receipt.succeeded transitions sent→succeeded; receipt.canceled → failed): `test_receipt_webhook_succeeded_transitions_fsm`, `test_receipt_webhook_canceled_transitions_fsm`.
  - SC #2 (ARQ retry + circuit breaker): `test_dispatch_fiscal_receipt_retries_with_backoff_on_transient_error`, `test_dispatch_fiscal_receipt_short_circuits_when_breaker_open`, `test_circuit_breaker_opens_after_5_failures_within_60s`.
  - SC #3 (monitor cron emits failed audit for stale pending): `test_monitor_stale_fiscal_receipts_emits_failed_audit_on_90s_stale_pending`.
  - SC #4 (POST endpoint returns 202 + creates online_refunds row): `test_post_refund_membership_returns_202_and_creates_online_refund_row`, `test_post_refund_pt_package_returns_202_and_creates_online_refund_row`, `test_post_refund_replay_with_same_idempotency_key_returns_202_idempotent`.
  - SC #5 (refund.succeeded atomic UoW writes 4 things): `test_refund_succeeded_webhook_writes_signed_payment_row_transitions_subject_inserts_fiscal_receipt_emits_audit_chain`.
  - SC #6 (poll cron reconciles 30-min stale refunds): `test_poll_pending_refunds_settles_missing_webhook_after_30min`, `test_poll_pending_refunds_marks_canceled_when_yookassa_reports_canceled`.

### Wave / plan shape preview for planner

- **D-51-29:** Suggested plan ordering (researcher + planner refine):
  - **Wave 1 (sequential — bedrock):**
    - 51-01: Alembic 0036 `online_refunds` table + UNIQUEs (D-51-04, D-51-06). Schema only.
    - 51-02: `app/modules/online_refunds/` skeleton (constants + models + repository + ONLINE_REFUND_STATUS_TRANSITIONS, D-51-07). New LOCKED audit events + payload classes (D-51-19) added to `app/core/audit.py` + `audit_payloads.py`.
    - 51-03: `app/integrations/yookassa/client.create_receipt` + `YooKassaReceiptResult` + respx fixtures (D-51-20).
    - 51-04: `app/integrations/yookassa/circuit_breaker.py` (D-51-14, copy-and-adapt from email).
  - **Wave 2 (parallelizable after Wave 1):**
    - 51-05: `dispatch_fiscal_receipt` ARQ task + tests (D-51-13, depends on 51-02, 51-03, 51-04).
    - 51-06: `_post_commit_enqueue` seam fill — add fiscal-receipt dispatch branch + update AST gate test_post_commit_enqueue_body_is_only_log_info → test_post_commit_enqueue_dispatches_fiscal_receipt (D-51-15). Depends on 51-05.
    - 51-07: `handle_refund_succeeded` + `handle_receipt_succeeded` + `handle_receipt_canceled` webhook handlers (D-51-11, D-51-21, D-51-22) + event-type dispatch extension in router.py (D-51-03). Depends on 51-02.
    - 51-08: POST refund endpoint + service (`app/api/v1/online_payments/router.py` + `app/modules/online_refunds/service.py`, D-51-08/09). Depends on 51-02.
  - **Wave 3 (sequential — depends on Wave 2):**
    - 51-09: ARQ crons — `monitor_stale_fiscal_receipts` (D-51-16) + `poll_pending_refunds` (D-51-17) registered in `WorkerSettings.cron_jobs`. Tests cover the loop budget + reconciliation paths.
  - **Wave 4 (sequential — depends on Wave 3):**
    - 51-10: End-to-end integration tests (refund full-cycle, fiscal-receipt full-cycle including failure paths; route-introspection assertions).
  - **Estimated plan count: 10** (range 9–11; 51-06 may merge into 51-05 if the AST-gate update is trivial).

### Claude's Discretion

Downstream agents may settle the following without re-asking:

- **`receipt.succeeded` re-fetch policy:** No re-fetch (D-51-03). The webhook body is authoritative for receipt informational state.
- **`refund.succeeded` re-fetch policy:** YES re-fetch via `client.get_refund` (D-51-11 step 2). Financial state change requires authoritative re-read (Phase 50 D-50-12 doctrine).
- **Refund body shape:** ЮKassa accepts full refund via just `amount` + `payment_id` (no receipt body needed for full refunds — ЮKassa reuses original payment's receipt data per Pitfall 10 step 4). Phase 51 ships full-refund only; receipt body omitted from `create_refund` payload.
- **`OnlineRefund.amount_kopecks` storage convention:** Stored POSITIVE in `online_refunds`; the `payments` ledger row is signed negative (Phase 32 precedent). The Pydantic response surfaces positive minor units to clients.
- **Fiscal-receipt retry exhaustion notification:** Phase 51 emits `fiscal_receipt_failed` audit but does NOT send the Telegram DM. The DM enqueue is Phase 52 NOT-04 (FISCAL_RECEIPT_FAILED_DM template); Phase 51's post-commit stub leaves the branch as no-op for the NOT-04 path while filling the fiscal-dispatch branch.
- **Logger names:** `_log = structlog.get_logger("modules.fiscal_receipts.tasks")` / `_log = structlog.get_logger("modules.online_refunds.service")` / `_log = structlog.get_logger("integrations.yookassa.circuit_breaker")` — mirror existing module-namespace convention.
- **Cron timezone:** Europe/Moscow — `WorkerSettings.timezone` is already pinned (Phase 18 ARQ-03 precedent; verify in `app/workers/__init__.py`).
- **Receipt `payment_subject` for refund items:** `"service"` (same as sale, per Phase 50 FISCAL-03 AST gate); receipt-level `type` field discriminator is `"refund"` at the envelope level. ЮKassa `/v3/receipts` doc lines 226–250 confirm; planner verifies during research.
- **Idempotency-Key on /v3/refunds:** caller-owned UUID4, stored in `online_refunds.idempotency_key`. Replay by the same caller returns 202 + the existing refund row's id (REFUND-03 idempotent semantics).
- **`_post_commit_enqueue` signature evolution:** Phase 50 shipped `(arq_pool, *, online_payment_id, subject_kind, subject_id)`. Phase 51 extends with `fiscal_receipt_id: UUID | None = None`. Default None so Phase 50 callsites (the `payment.succeeded` UoW) keep working without edits — but the Phase 51 `payment.succeeded` UoW will be amended to pass the just-INSERTed `fiscal_receipt_id` so dispatch enqueues automatically. The `_post_commit_enqueue` body branches: if `fiscal_receipt_id` present → enqueue dispatch_fiscal_receipt; if `(subject_kind, subject_id)` present → no-op (Phase 52 will fill notifications).
- **ARQ task `max_tries=3`** explicit in `WorkerSettings.functions` declaration (override per-function via `arq` 0.28's `func(max_tries=3, timeout=20)` wrapper). Pitfall 11 step 1: 5 failures in 60s → open for 300s; Pitfall 11 step 2: max_tries=3 with exponential backoff.
- **`SELECT FOR UPDATE SKIP LOCKED`** in both cron functions — Postgres-specific but project already targets PG 16 (PROJECT.md Tech stack — Backend).
- **Test fixture for `arq_pool`:** existing `tests/integration/conftest.py:arq_pool_test` (Phase 18 ARQ-03 + Phase 39 cron tests) is reused. The post-commit enqueue path in tests asserts `arq_pool.enqueue_job.assert_called_once_with('dispatch_fiscal_receipt', <fr_id>)`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project / milestone scope
- `.planning/PROJECT.md` — milestone v1.7 framing, RF regional constraints
- `.planning/REQUIREMENTS.md` lines 51–58 — FISCAL-04..07 full text
- `.planning/REQUIREMENTS.md` lines 60–67 — REFUND-01..04 full text
- `.planning/REQUIREMENTS.md` traceability table — FISCAL-04..07 + REFUND-01..04 → Phase 51 mapping
- `.planning/ROADMAP.md` Phase 51 entry — goal + 6 success criteria
- `.planning/STATE.md` — milestone v1.7 status; deferred items table

### Prior phase context (Phase 47 / 48 / 49 / 50)
- `.planning/phases/47-bedrock/47-CONTEXT.md` — D-47-01..09: Protocol slot pattern, INFRA-35 LOCKED_AUDIT_EVENTS pre-registration of all 11 v1.7 events
- `.planning/phases/48-kassa-integration-adapter/48-CONTEXT.md` — D-48-19/20/22: webhook verifier; D-48-11 caller-owned Idempotence-Key discipline
- `.planning/phases/49-online-sales-orchestrator/49-CONTEXT.md` — D-49-04 OnlinePayment XOR CHECK; D-49-13 narrow-read pattern; D-49-19/20/29 audit chain + payments.models flip; D-49-21/22 v1.7 Protocol slot stubs filled by Phase 50
- `.planning/phases/50-webhook-fsm-fiscal-foundation/50-CONTEXT.md` — D-50-01..44 entire phase 50 doctrine (event dispatch, dedup, atomic UoW, fiscal_receipts table, AST gates, Claude-discretion notes); Phase 51 extends D-50-03 / D-50-19 / D-50-32
- `.planning/phases/50-webhook-fsm-fiscal-foundation/50-VERIFICATION.md` — Phase 50 outcome state at end-of-phase
- `.planning/phases/50-webhook-fsm-fiscal-foundation/deferred-items.md` — DEFER-50-01..05 carry-forward register (Phase 51 directly consumes DEFER-50-04 `_post_commit_enqueue` stub)
- `.planning/phases/49-online-sales-orchestrator/deferred-items.md` — D-49-29 (closed Phase 50), D-49-30 (Phase 53), Phase 50 yookassa_call_failed deferral (re-examined here)

### Research (v1.7 milestone)
- `.planning/research/PITFALLS.md` **Pitfall 10** — refund webhook dedup + v1.4 partial UNIQUE preservation (REFUND-03 directly traces)
- `.planning/research/PITFALLS.md` **Pitfall 11** — ARQ retry storm + circuit breaker (FISCAL-05 directly traces)
- `.planning/research/PITFALLS.md` **Pitfall 12** — atomic UoW for multi-step online payment flow (REFUND-02 atomic-UoW directly traces)
- `.planning/research/PITFALLS.md` Pitfall 8 — wrong 54-ФЗ subject/method tags (FISCAL-05 receipt body composition must respect)
- `.planning/research/PITFALLS.md` lines 357–390 — audit-event chain ordering for multi-step UoW (refund chain shape)
- `.planning/research/PITFALLS.md` lines 476–500 — LOCKED_AUDIT_EVENTS pre-registration discipline (D-51-19 adds 3 new events)
- `.planning/research/STACK.md` §1 lines 1–100 — Idempotence-Key, Basic Auth
- `.planning/research/STACK.md` §2 lines 100–170 — 54-ФЗ receipt structure (`/v3/receipts` endpoint)
- `.planning/research/STACK.md` §6 lines 252–261 — integration touchpoints
- `.planning/research/FEATURES.md` lines 195–215 — fiscal-receipt model + retry boundaries
- `.planning/research/FEATURES.md` lines 95–112 — `online_payments` FSM + UNIQUE discipline (mirror shape for `online_refunds`)

### Phase 32 / 33 offline-refund precedent
- `apps/backend/app/modules/memberships/service.py:882` — `refund_membership` (Phase 32 REF-01) full pattern: guards → PaymentRefunder Protocol call → status transition with `CANCELLATION_REASON_REFUNDED` sentinel → membership_refunded audit emit. Phase 51 refund-webhook handler RE-USES the Protocol slot + sentinel + audit event.
- `apps/backend/app/modules/pt_packages/service.py:1038` — `refund_pt_package` (Phase 33) mirror.
- `apps/backend/app/modules/memberships/constants.py:53` — `CANCELLATION_REASON_REFUNDED` sentinel (D-32-08).
- `apps/backend/app/modules/pt_packages/constants.py:46` — same sentinel.
- `apps/backend/app/modules/payments/service.py:184-225` — `issue_refund` body; D-51-11 step "atomic ledger write" calls the same PaymentRefunder Protocol slot consumer.
- `apps/backend/app/modules/payments/repository.py:_is_refund_of_uniqueness_conflict` — IntegrityError discriminator for REFUND-03 idempotency.

### Codebase contracts to preserve
- `apps/backend/app/integrations/yookassa/client.py:350` `create_refund` — Phase 48 ADAPTER-02 entry point used by D-51-09
- `apps/backend/app/integrations/yookassa/client.py:445` `get_refund` — Phase 48; used by D-51-17 reconciliation cron
- `apps/backend/app/integrations/yookassa/settings.py:50-51` — `tax_system_code` + `default_vat_code` consumed by D-51-13 dispatch task body
- `apps/backend/app/integrations/email/circuit_breaker.py` — copy-and-adapt source for D-51-14
- `apps/backend/app/core/audit.py:343-360` — `LOCKED_AUDIT_EVENTS` frozenset; Phase 51 appends 3 new pairs (D-51-19)
- `apps/backend/app/core/audit.py:124-198` — catalog docstring; extend for the 3 new pairs
- `apps/backend/app/core/audit_payloads.py` — add `OnlineRefundInitiatedPayload`, `OnlineRefundPolledSettledPayload`, `OnlineRefundCanceledPayload` + register in `AUDIT_PAYLOAD_SCHEMAS`
- `apps/backend/app/core/dependencies.py:1019-1066` — `FiscalReceiptDispatcher` Protocol slot; **Phase 51 ships real implementation** via `register_fiscal_receipt_dispatcher(real_impl)` in `app/main.py:create_app()`
- `apps/backend/app/core/dependencies.py` `PaymentRefunder` Protocol slot (Phase 32 D-32-14) — Phase 51 webhook handler consumes via `get_payment_refunder()`
- `apps/backend/app/api/v1/_internal/yookassa/router.py` — Phase 50 router; Phase 51 extends event-type dispatch chain (D-51-03)
- `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — Phase 50 handlers; Phase 51 ADDS three handlers (D-51-11, D-51-21, D-51-22)
- `apps/backend/app/api/v1/router.py` — mount new `online_payments_router` at `prefix="/online-payments"` (D-51-01)
- `apps/backend/app/modules/online_payments/models.py:OnlinePayment` — Phase 49 ORM read by D-51-08 step 5
- `apps/backend/app/modules/online_payments/constants.py` — Phase 50 D-50-15 ONLINE_PAYMENT_STATUS_TRANSITIONS unchanged
- `apps/backend/app/modules/fiscal_receipts/constants.py` — Phase 50 D-50-32 FISCAL_RECEIPT_STATUS_TRANSITIONS unchanged; Phase 51 ARQ task + webhook handler USE
- `apps/backend/app/modules/fiscal_receipts/models.py` — Phase 50 ORM; ARQ task UPDATEs `yookassa_receipt_id` + state; webhook UPDATEs status
- `apps/backend/app/modules/payments/models.py:81-117` — `Payment.refund_of` + `uq_payments_refund_of_alive` partial UNIQUE (REFUND-03 backstop)
- `apps/backend/app/workers/__init__.py:112` `WorkerSettings` — Phase 51 appends `dispatch_fiscal_receipt`, `monitor_stale_fiscal_receipts`, `poll_pending_refunds` to `functions` + `cron_jobs`; `_validate_cron_function_names` will auto-detect typos
- `apps/backend/app/main.py:create_app()` — composition root; register the real `FiscalReceiptDispatcher` impl
- `apps/backend/alembic/versions/0035_fiscal_receipts.py` — naming convention precedent for 0036
- `apps/backend/tests/unit/test_locked_yookassa_constants_ast.py` — Phase 50 D-50-33 AST gates; Phase 51 may extend with `payment_subject` literal check on the new `create_receipt` callsite
- `apps/backend/tests/integration/webhook_yookassa/test_post_commit_seam.py` — Phase 50 DEFER-50-04 AST gate `test_post_commit_enqueue_body_is_only_log_info` — **MUST be updated by Phase 51 plan 51-06 in lockstep with the body fill**
- `apps/backend/tests/integrations/yookassa/conftest.py` — Phase 48/49/50 respx fixtures; Phase 51 adds `yookassa_create_receipt_*`, `yookassa_get_refund_succeeded`, `yookassa_get_refund_canceled`
- `apps/backend/.importlinter` — verify the new `integrations/yookassa/circuit_breaker.py` does not cross-import `integrations/email` (D-51-14)

### External specs (ЮKassa / 54-ФЗ)
- https://yookassa.ru/developers/api?codeLang=python#create_refund — `POST /v3/refunds` schema (D-51-09)
- https://yookassa.ru/developers/api?codeLang=python#get_refund — `GET /v3/refunds/{id}` schema (D-51-17 reconciliation)
- https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values — receipt enums (D-51-13 receipt body composition)
- https://yookassa.ru/developers/api?codeLang=python#create_receipt — `POST /v3/receipts` schema (D-51-20 client extension)
- https://yookassa.ru/developers/using-api/webhooks — event catalog confirming `receipt.succeeded` / `receipt.canceled` / `refund.succeeded` event names (D-51-03)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`app/integrations/yookassa/client.py:create_refund`** (line 350) — already shipped; D-51-09 calls directly.
- **`app/integrations/yookassa/client.py:get_refund`** (line 445) — already shipped; D-51-17 reconciliation cron calls directly.
- **`app/integrations/yookassa/settings.py`** `tax_system_code` (line 50) + `default_vat_code` (line 51) — Phase 47 shipped; FISCAL-07 satisfied by direct consumption (D-51-23).
- **`app/integrations/email/circuit_breaker.py`** — pattern source for D-51-14 (copy-and-adapt to `app/integrations/yookassa/circuit_breaker.py`).
- **`app/core/audit.py:LOCKED_AUDIT_EVENTS`** — Phase 47 pre-registered the bulk of v1.7 events; Phase 51 only adds 3 (D-51-19).
- **`app/core/dependencies.py:FiscalReceiptDispatcher`** Protocol slot (line 1019) — Phase 47 declared; Phase 49 wired stub; **Phase 51 ships real implementation**.
- **`app/core/dependencies.py:PaymentRefunder`** Protocol slot (Phase 32 D-32-14) — Phase 51 webhook handler consumes; no edits.
- **`app/modules/memberships/service.py:refund_membership`** (line 882) + **`app/modules/pt_packages/service.py:refund_pt_package`** (line 1038) — Phase 32/33 patterns. Phase 51 REFUND-02 reuses the Protocol slot call + sentinel + audit event names verbatim.
- **`app/modules/memberships/constants.py:CANCELLATION_REASON_REFUNDED`** (line 53) + same for PT packages — Phase 51 refund-webhook handler sets this on the cancelled row.
- **`app/modules/payments/service.py:issue_refund`** + `_is_refund_of_uniqueness_conflict` — the partial UNIQUE backstop for REFUND-03 idempotency.
- **`app/api/v1/_internal/yookassa/router.py`** + **`handlers.py`** — Phase 50 home; Phase 51 extends both with the 3 new event branches + handlers.
- **`app/modules/fiscal_receipts/`** — Phase 50 module skeleton; Phase 51 ADDS `tasks.py` (dispatch + crons) + repository methods.
- **`app/workers/__init__.py`** `WorkerSettings.functions` + `.cron_jobs` — Phase 51 appends 3 entries (1 function + 2 cron jobs).
- **`tests/integration/conftest.py:arq_pool_test`** + worker fixtures (Phase 18 ARQ-03 + Phase 39) — reused by D-51-27 task/cron tests.
- **`tests/integration/webhook_yookassa/conftest.py`** (Phase 50 plan 50-06) — webhook test fixtures reused for the 3 new event types.
- **`tests/integrations/yookassa/conftest.py`** — Phase 48/49/50 respx fixtures; D-51-20 adds `yookassa_create_receipt_*` family.

### Established Patterns
- **`_internal` namespace anonymity + IP gate** (Phase 42 D-42-17 / Phase 50 D-50-39) — Phase 51's 3 new event branches inherit verbatim; no auth/CSRF.
- **AST-gated locked constants + AST-gated structural invariants** (Phase 47/48/50) — Phase 51's `_post_commit_enqueue` body update MUST update the matching AST gate in lockstep (D-51-15).
- **Caller-owns-txn UoW** (D-49-13 / SVC001) — Phase 51 refund endpoint service owns its txn; webhook handler owns its txn; ARQ task does its own atomic update.
- **Declarative FSM** (Phase 16 + 24 + 50) — `ONLINE_REFUND_STATUS_TRANSITIONS` constant mirrors `ONLINE_PAYMENT_STATUS_TRANSITIONS` byte-for-byte (D-51-07).
- **Protocol slot Phase-N stub → Phase-N+1 body** (D-47-01 lineage) — Phase 47 declared `FiscalReceiptDispatcher` stub; Phase 49 wired raising-NotImplementedError stub; Phase 51 fills with real ARQ-enqueue implementation.
- **Two-event audit chain with `audit_correlation_id`** (D-49-19 / D-50-18 step 7-8) — Phase 51 refund webhook emits 4 CHILD audits within the UoW (+ root `yookassa_webhook_received`).
- **Result-classification at integration boundary** (D-48-10) — Phase 51 dispatch task + reconciliation cron branch on `YooKassaRefundResult.classification` / `YooKassaReceiptResult.classification`.
- **ARQ task + cron registration pattern** (Phase 18 ARQ-03 + Phase 27 expiring-notifications + Phase 39 booking-reminders) — Phase 51 appends 3 entries; `_validate_cron_function_names` defensive class-init check (line 226) auto-catches typos.
- **Caller-owned Idempotence-Key on YooKassa mutations** (D-48-11) — Phase 51 refund endpoint requires `idempotency_key` from the caller, passes through to `create_refund`.
- **Partial UNIQUE as DB-level idempotency backstop** (Phase 32 `uq_payments_refund_of_alive` + Phase 50 D-50-08 Redis dedup + Phase 50 0034 `uq_online_payments_yookassa_payment_id`) — REFUND-03 traces both layers.

### Integration Points
- `apps/backend/alembic/versions/0036_online_refunds.py` (new) — table + UNIQUEs; `down_revision = "0035_fiscal_receipts"`.
- `apps/backend/app/modules/online_refunds/__init__.py` + `constants.py` + `models.py` + `repository.py` + `service.py` (new module).
- `apps/backend/app/modules/fiscal_receipts/tasks.py` (new) — `dispatch_fiscal_receipt` ARQ task + `monitor_stale_fiscal_receipts` cron body.
- `apps/backend/app/modules/online_refunds/tasks.py` (new — or co-located with fiscal_receipts/tasks.py per planner discretion) — `poll_pending_refunds` cron body.
- `apps/backend/app/api/v1/online_payments/__init__.py` + `router.py` + `schemas.py` (new package).
- `apps/backend/app/api/v1/router.py` — mount `online_payments_router` at `prefix="/online-payments"`, `tags=["online-payments"]`.
- `apps/backend/app/api/v1/_internal/yookassa/router.py` — extend event-type dispatch chain with 3 new branches (D-51-03).
- `apps/backend/app/api/v1/_internal/yookassa/handlers.py` — add `handle_refund_succeeded` / `handle_receipt_succeeded` / `handle_receipt_canceled` + `_assert_can_transition_refund` + `_assert_can_transition_receipt` helpers.
- `apps/backend/app/api/v1/_internal/yookassa/_post_commit_enqueue.py` (or wherever the Phase 50 stub lives) — extend body with fiscal-receipt dispatch branch (D-51-15); update lockstep AST gate.
- `apps/backend/app/integrations/yookassa/client.py` — add `create_receipt` method (D-51-20).
- `apps/backend/app/integrations/yookassa/types.py` — add `YooKassaReceiptResult` dataclass.
- `apps/backend/app/integrations/yookassa/circuit_breaker.py` (new) — copy-and-adapt from `integrations/email/circuit_breaker.py` (D-51-14).
- `apps/backend/app/core/audit.py` — append 3 new entries to `LOCKED_AUDIT_EVENTS` + extend docstring catalog (D-51-19).
- `apps/backend/app/core/audit_payloads.py` — add 3 new payload classes + register in `AUDIT_PAYLOAD_SCHEMAS`.
- `apps/backend/app/main.py:create_app()` — `register_fiscal_receipt_dispatcher(real_impl)` (replaces Phase 49 raising stub).
- `apps/backend/app/workers/__init__.py:WorkerSettings.functions` — append `dispatch_fiscal_receipt`; `.cron_jobs` — append 2 cron entries (D-51-16, D-51-17).
- `apps/backend/tests/integration/online_refunds/` (new directory).
- `apps/backend/tests/integration/webhook_yookassa/test_handle_refund_succeeded.py` + `test_handle_receipt_*.py` (new files).
- `apps/backend/tests/integration/fiscal_receipts/` (new directory) — task + cron tests.
- `apps/backend/tests/integrations/yookassa/conftest.py` — extend with `yookassa_create_receipt_*`, `yookassa_get_refund_*` respx fixtures.
- `apps/backend/tests/unit/test_yookassa_circuit_breaker.py` (new) — circuit breaker unit tests.
- `apps/backend/tests/integration/test_route_introspection.py` — no `EXCLUDED_PATHS` edits (the new `/online-payments/*/refund` routes are gated, not excluded).
- `apps/backend/.importlinter` — verify the new `integrations/yookassa/circuit_breaker.py` does not cross-import `integrations/email.*`.

</code_context>

<specifics>
## Specific Ideas

- **`online_refunds` table sketch (D-51-04 / D-51-06):**
  ```python
  # alembic/versions/0036_online_refunds.py upgrade()
  op.create_table(
      "online_refunds",
      sa.Column("id", PgUUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
      sa.Column("online_payment_id", PgUUID(as_uuid=True), nullable=False),
      sa.Column("original_payment_id", PgUUID(as_uuid=True), nullable=False),
      sa.Column("client_id", PgUUID(as_uuid=True), nullable=False),
      sa.Column("yookassa_refund_id", sa.Text(), nullable=False),
      sa.Column("idempotency_key", sa.Text(), nullable=False),
      sa.Column("amount_kopecks", sa.Integer(), nullable=False),
      sa.Column("status", sa.Text(), nullable=False),
      sa.Column("requested_by_user_id", PgUUID(as_uuid=True), nullable=False),
      sa.Column("reason", sa.Text(), nullable=True),
      sa.Column("audit_correlation_id", PgUUID(as_uuid=True), nullable=True),
      sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
      sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
      sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
      sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
      sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
      sa.PrimaryKeyConstraint("id", name=op.f("pk_online_refunds")),
      sa.ForeignKeyConstraint(["online_payment_id"], ["online_payments.id"], name=op.f("fk_online_refunds_online_payment_id_online_payments"), ondelete="RESTRICT"),
      sa.ForeignKeyConstraint(["original_payment_id"], ["payments.id"], name=op.f("fk_online_refunds_original_payment_id_payments"), ondelete="RESTRICT"),
      sa.ForeignKeyConstraint(["client_id"], ["clients.id"], name=op.f("fk_online_refunds_client_id_clients"), ondelete="RESTRICT"),
      sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], name=op.f("fk_online_refunds_requested_by_user_id_users"), ondelete="RESTRICT"),
      sa.CheckConstraint("amount_kopecks > 0", name=op.f("ck_online_refunds_amount_kopecks_positive")),
      sa.CheckConstraint("status IN ('pending','succeeded','canceled')", name=op.f("ck_online_refunds_status")),
      sa.UniqueConstraint("yookassa_refund_id", name=op.f("uq_online_refunds_yookassa_refund_id")),
      sa.UniqueConstraint("idempotency_key", name=op.f("uq_online_refunds_idempotency_key")),
  )
  op.create_index(
      "uq_online_refunds_online_payment_id_alive",
      "online_refunds", ["online_payment_id"],
      unique=True,
      postgresql_where=sa.text("status IN ('pending','succeeded')"),
  )
  ```

- **`ONLINE_REFUND_STATUS_TRANSITIONS` (D-51-07):**
  ```python
  ONLINE_REFUND_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType({
      "pending":   frozenset({"succeeded", "canceled"}),
      "succeeded": frozenset(),  # terminal
      "canceled":  frozenset(),  # terminal
  })
  ```

- **Refund endpoint skeleton (D-51-08 / D-51-09):**
  ```python
  @router.post(
      "/memberships/{membership_id}/refund",
      status_code=202,
      response_model=OnlineRefundResponse,
      dependencies=[Depends(verify_csrf)],
  )
  async def initiate_membership_refund(
      membership_id: UUID,
      body: OnlineRefundRequest,
      actor: Annotated[CurrentUser, Depends(require_permission('refund', 'membership'))],
      session: Annotated[AsyncSession, Depends(get_db)],
      yookassa_client: Annotated[YooKassaClient, Depends(get_yookassa_client_provider)],
  ) -> OnlineRefundResponse:
      return await initiate_online_refund(
          session, yookassa_client,
          subject_kind='membership', subject_id=membership_id,
          actor=actor, idempotency_key=body.idempotency_key, reason=body.reason,
      )
  ```

- **`dispatch_fiscal_receipt` ARQ task skeleton (D-51-13):**
  ```python
  async def dispatch_fiscal_receipt(ctx: dict[str, Any], fiscal_receipt_id: str) -> None:
      session_factory = ctx["session_factory"]
      redis = ctx["redis"]
      yookassa = ctx["yookassa_client"]
      breaker_key = "receipts"
      if await is_circuit_open(redis, breaker_key):
          raise Retry(defer=timedelta(seconds=300))
      async with session_factory() as session:
          row = await session.scalar(select(FiscalReceipt).where(FiscalReceipt.id == fiscal_receipt_id))
          if row is None or row.status != "sent":
              return
          # build receipt body from row + settings.yookassa
          try:
              result = await yookassa.create_receipt(
                  payment_id=..., customer_email=row.customer_email, items=[...],
                  tax_system_code=settings.yookassa.tax_system_code,
                  idempotency_key=fiscal_receipt_id,
              )
          except YooKassaTransientError:
              await record_failure(redis, breaker_key, threshold=5, window=60, open_ttl=300)
              raise Retry(defer=_backoff_with_jitter(ctx["job_try"]))
          if result.classification == "permanent_error":
              row.status = "failed"
              row.failed_at = datetime.now(UTC)
              row.failure_reason = f"yookassa_{result.classification}"
              await audit.emit(session, event="fiscal_receipt_failed", resource_type="fiscal_receipt",
                              payload=FiscalReceiptFailedPayload(fiscal_receipt_id=row.id, failure_reason=row.failure_reason))
              await session.commit()
              return
          # classification == 'ok' → only stash yookassa_receipt_id; webhook will flip status
          row.yookassa_receipt_id = result.receipt_id
          await audit.emit(session, event="fiscal_receipt_dispatched", resource_type="fiscal_receipt",
                          payload=FiscalReceiptDispatchedPayload(
                              fiscal_receipt_id=row.id, payment_id=row.payment_id,
                              kind=row.kind, customer_email=row.customer_email))
          await session.commit()
  ```

- **`handle_refund_succeeded` skeleton (D-51-11):**
  ```python
  async def handle_refund_succeeded(session, yookassa_client, *, body):
      refund_id = body["object"]["id"]
      result = await yookassa_client.get_refund(refund_id)
      if result.classification != "ok" or result.status != "succeeded":
          _log.warning("yookassa_refund_refetch_failed", classification=result.classification)
          return
      webhook_intake_corr = uuid4()
      async with session.begin():
          refund_row = (await session.execute(
              select(OnlineRefund).where(OnlineRefund.yookassa_refund_id == refund_id).with_for_update()
          )).scalar_one_or_none()
          if refund_row is None:
              _log.warning("yookassa_refund_webhook_orphan", refund_id=refund_id)
              return
          _assert_can_transition_refund(refund_row, target="succeeded")
          refund_row.status = "succeeded"
          refund_row.succeeded_at = datetime.now(UTC)
          try:
              refund_payment = await get_payment_refunder()(
                  session, subject_kind=..., subject_id=..., refund_user_id=refund_row.requested_by_user_id,
                  reason=refund_row.reason or "", audit_actor=None,
              )
          except AlreadyRefundedError:
              _log.warning("yookassa_refund_idempotent_replay", refund_id=refund_id)
              return  # txn auto-rollback; ЮKassa gets 200 (REFUND-03)
          # transition subject (membership/pt_package) to cancelled w/ refunded sentinel
          if refund_row.online_payment.membership_plan_id is not None:
              await update_membership_status(session, membership_id=...,
                  target="cancelled", cancellation_reason=CANCELLATION_REASON_REFUNDED,
                  cancelled_at=datetime.now(UTC))
              await audit.emit(session, event="membership_refunded", resource_type="membership",
                              payload=...)
          else:
              # mirror for pt_package
              ...
          session.add(FiscalReceipt(
              payment_id=refund_payment.id, kind="refund", status="sent",
              customer_email=refund_row.client.email, sent_at=datetime.now(UTC),
              audit_correlation_id=webhook_intake_corr,
          ))
          await audit.emit(session, event="online_payment_refunded", resource_type="online_payment",
                          payload=OnlinePaymentRefundedPayload(
                              online_payment_id=refund_row.online_payment_id,
                              refund_payment_id=refund_payment.id,
                              amount_kopecks=refund_row.amount_kopecks))
          await audit.emit(session, event="yookassa_webhook_received", resource_type="yookassa_webhook",
                          payload=YookassaWebhookReceivedPayload(
                              event_type="refund.succeeded", object_id=refund_id,
                              idempotency_outcome="processed"))
      # POST-COMMIT: Phase 52 NOT-02 will fill this branch; Phase 51 no-op
      await _post_commit_enqueue(arq_pool, online_payment_id=refund_row.online_payment_id,
                                  subject_kind=..., subject_id=...,
                                  fiscal_receipt_id=<the_just_inserted_id>)
  ```

- **Circuit breaker skeleton (D-51-14):**
  ```python
  # app/integrations/yookassa/circuit_breaker.py
  CIRCUIT_KEY_PREFIX: Final[str] = "sz:yookassa:circuit:"
  FAILURE_THRESHOLD: Final[int] = 5
  FAILURE_WINDOW_SECONDS: Final[int] = 60
  OPEN_TTL_SECONDS: Final[int] = 300

  async def is_circuit_open(redis: Redis, scope: str) -> bool:
      return bool(await redis.exists(f"{CIRCUIT_KEY_PREFIX}{scope}:open"))

  async def record_failure(redis: Redis, scope: str) -> None:
      counter_key = f"{CIRCUIT_KEY_PREFIX}{scope}:failures"
      open_key = f"{CIRCUIT_KEY_PREFIX}{scope}:open"
      async with redis.pipeline(transaction=True) as pipe:
          pipe.incr(counter_key)
          pipe.expire(counter_key, FAILURE_WINDOW_SECONDS)
          count, _ = await pipe.execute()
      if count >= FAILURE_THRESHOLD:
          await redis.set(open_key, "1", ex=OPEN_TTL_SECONDS)
  ```

- **`monitor_stale_fiscal_receipts` cron skeleton (D-51-16):**
  ```python
  async def monitor_stale_fiscal_receipts(ctx) -> None:
      async with ctx["session_factory"]() as session:
          rows = (await session.execute(
              select(FiscalReceipt).where(
                  FiscalReceipt.status == "pending",
                  FiscalReceipt.created_at < func.now() - text("interval '90 seconds'"),
              ).with_for_update(skip_locked=True).limit(50)
          )).scalars().all()
          for row in rows:
              row.status = "failed"
              row.failed_at = datetime.now(UTC)
              row.failure_reason = "stale_pending_no_dispatch"
              await audit.emit(session, event="fiscal_receipt_failed", resource_type="fiscal_receipt",
                              payload=FiscalReceiptFailedPayload(...))
          await session.commit()
  ```

- **`poll_pending_refunds` cron skeleton (D-51-17):**
  ```python
  async def poll_pending_refunds(ctx) -> None:
      async with ctx["session_factory"]() as session:
          rows = (await session.execute(
              select(OnlineRefund).where(
                  OnlineRefund.status == "pending",
                  OnlineRefund.requested_at < func.now() - text("interval '30 minutes'"),
              ).with_for_update(skip_locked=True).limit(50)
          )).scalars().all()
          for row in rows:
              result = await ctx["yookassa_client"].get_refund(row.yookassa_refund_id)
              if result.classification != "ok":
                  continue
              if result.status == "succeeded":
                  await _settle_online_refund(session, online_refund_id=row.id,
                                              chain_root_corr=uuid4(),
                                              chain_root_event="online_refund_polled_settled")
              elif result.status == "canceled":
                  row.status = "canceled"
                  row.canceled_at = datetime.now(UTC)
                  await audit.emit(session, event="online_refund_canceled", resource_type="online_refund",
                                  payload=OnlineRefundCanceledPayload(...))
          await session.commit()
  ```

</specifics>

<deferred>
## Deferred Ideas

- **`payment.waiting_for_capture` handler** — DEFER-50-01 carried from Phase 50; Phase 53 deployment runbook.
- **Orphan recovery cron** for ЮKassa-side state without matching DB row — DEFER-50-02; Phase 53 `reconcile_orphan_yookassa_payments`. Phase 51 inherits the same handling pattern for orphan refund webhooks (D-51-11 step "row is None" branch).
- **`v1.4 partial-refund` (B-02)** — still deferred to v1.8+; Phase 51 ships full-refund only (REQUIREMENTS REFUND-01 explicit).
- **NOT-02 refund DM + NOT-04 fiscal-failure DM** — Phase 52 fills the `_post_commit_enqueue` notification branches. Phase 51 leaves them as no-op (only the fiscal-dispatch branch is filled in 51-06).
- **DEFER-50-03 operator runbook** for `cancellation_reason` / `cancellation_party` enum values — Phase 53; refund cancellation reasons from `poll_pending_refunds` (D-51-17 step 4) will similarly need translation.
- **`yookassa_call_failed` audit event** — re-deferred from Phase 50 carry-forward. Phase 51 dispatch task + cron may emit this on transient-classification re-fetch failures; current decision is to keep structlog WARNING only and defer the audit-DB row to Phase 53 cleanup unless verification flags as gap.
- **`tests/integration/test_alembic_clean.py::test_alembic_check_clean`** — DEFER-50-05, pre-existing failure, still deferred to Phase 53.
- **3 pre-existing route-introspection failures** (auth password-reset × 2 + users invitations accept) — Phase 50 carry-forward; still deferred to v1.8 hardening (`auth` + `users` module owners).
- **Generalize circuit breaker** to a shared `app/core/circuit_breaker.py` consumed by both `email/` and `yookassa/` — explicitly rejected for Phase 51 (D-51-14 preserves integrations isolation); revisit when a 3rd integration needs it.
- **Receipt body for partial refunds** — out of scope; v1.7 ships full-refund where ЮKassa auto-derives the receipt body from the original payment per Pitfall 10 step 4.

### Reviewed Todos (not folded)
*No todos matched Phase 51 in `gsd-sdk query todo.match-phase 51` (`todo_count: 0`) — section omitted.*

</deferred>

---

*Phase: 51-Fiscal-FSM-Refunds*
*Context gathered: 2026-05-23*
*Mode: --auto (recommended defaults applied; deviations from prior phases documented inline)*
