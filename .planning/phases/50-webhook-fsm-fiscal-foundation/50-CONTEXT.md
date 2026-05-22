# Phase 50: Webhook FSM + Fiscal Foundation - Context

**Gathered:** 2026-05-22
**Status:** Ready for planning
**Mode:** `--auto` (recommended defaults applied; decisions logged inline)

<domain>
## Phase Boundary

Ship the **ЮKassa webhook intake + payment FSM + fiscal-receipts foundation** — the inbound counterpart to Phase 49's outbound sell flow. Concretely:

- **Webhook route** `POST /api/v1/_internal/yookassa/webhook` mounted under the existing `_internal` namespace (Phase 42 EMAIL-07 established it), with `Depends(verify_yookassa_ip)` enforcing IP allowlist BEFORE body parse (Phase 48 shipped the verifier body; Phase 50 mounts the consumer).
- **Re-fetch-before-write** discipline: handler calls `YooKassaClient.get_payment(object.id)` to refresh status before any DB write (never trust the webhook body as authoritative — PITFALLS Pitfall 1).
- **Redis dedup** via `SET NX EX 86400 sz:yookassa:webhook:{event_type}:{object_id}` (24h TTL covers ЮKassa's retry window).
- **Payment FSM** `pending → succeeded | canceled` with `ONLINE_PAYMENT_STATUS_TRANSITIONS` declarative constant + `_assert_can_transition` guard, mirroring `app/modules/memberships/constants.py:22` + `service.py:208`.
- **Atomic UoW on `payment.succeeded`**: status update + `payment_recorder.record_payment(method='online')` (v1.4 ledger row) + activator call via `MembershipActivator`/`PtPackageActivator` Protocol slots (Phase 49 shipped raises; Phase 50 fills bodies) + `fiscal_receipts(status='sent')` row INSERT — all in one `async with session.begin()`.
- **`payment.canceled`** path: status update + `online_payment_canceled` audit emit with `cancellation_party` and `cancellation_reason` from webhook body.
- **Alembic 0035** for `fiscal_receipts` table with UNIQUE `(payment_id, kind)`, FK to `payments.id`.
- **FISCAL-03 ratification**: AST gate on `payment_subject="service"` + `payment_mode` literal callsites (Phase 49's `service.sell_*` already passes these as Phase 48 `PaymentSubject.SERVICE` / `PaymentMode.FULL_PREPAYMENT` enums; Phase 50 hardens the gate so Phase 51 refund/recurring callsites stay compliant).

Requirements covered: **WH-01..WH-06, FISCAL-01, FISCAL-02, FISCAL-03** (9 reqs). 6 success criteria locked by ROADMAP.md.

**Out of phase (explicit):**
- `receipt.succeeded` / `receipt.canceled` webhook handler — Phase 51 FISCAL-04.
- ARQ `dispatch_fiscal_receipt` task + circuit breaker — Phase 51 FISCAL-05.
- Cron `monitor_stale_fiscal_receipts` — Phase 51 FISCAL-06.
- Refund endpoint + `refund.succeeded` webhook — Phase 51 REFUND-01..04.
- Telegram + email cancellation/success DMs — Phase 52 NOT-04 / NOT-05.

Phase 47/48/49 carry-forward:
- `verify_yookassa_ip` body (Phase 48), `YOOKASSA_TRUSTED_IPS` (Phase 47), `_internal` router namespace (Phase 42).
- `YooKassaClient.get_payment(payment_id) → YooKassaPaymentResult` (Phase 48 ADAPTER-02; Phase 49 Plan 49-01 extended with `qr_payload` extraction — same `get_payment` callable used here for re-fetch).
- All 4 v1.7 Protocol slots wired non-None at end of Phase 49 (`YooKassaClientProvider` real, `MembershipActivator`/`PtPackageActivator`/`FiscalReceiptDispatcher` stubs raising `NotImplementedError` — Phase 50 fills the activator bodies).
- All v1.7 audit payloads in `app/core/audit_payloads.py` (`OnlinePaymentSucceededPayload`, `OnlinePaymentCanceledPayload`, `FiscalReceiptDispatchedPayload`, `YookassaWebhookReceivedPayload` — Phase 47 INFRA-35).
- `online_payments` table from Phase 49's Alembic 0034; `_internal/email/router.py` is the structural template for `_internal/yookassa/router.py`.
- `PaymentRecorder` Protocol slot (`app/core/dependencies.py:339`) + `record_payment(method='online')` from `app/modules/payments/service.py:90`.

</domain>

<decisions>
## Implementation Decisions

### Module layout — webhook under `_internal/yookassa/`

- **D-50-01:** Webhook router lives at `apps/backend/app/api/v1/_internal/yookassa/router.py` (mirror `_internal/email/router.py` shape). Structurally:
  ```
  apps/backend/app/api/v1/_internal/yookassa/
  ├── __init__.py             # module marker + brief docstring on _internal discipline
  ├── router.py               # POST /webhook handler — IP gate → Redis dedup → re-fetch → dispatch
  └── handlers.py             # per-event-type business-logic handlers (succeeded / canceled)
  ```
  - `router.py` owns transport concerns (FastAPI route, IP gate Depends, structlog INFO line, audit-row emit for `yookassa_webhook_received`).
  - `handlers.py` owns business-logic dispatch (FSM transition, ledger write, activator call, fiscal-receipt INSERT, audit chain). The router calls `await handlers.handle_payment_succeeded(...)` etc., one function per event type.
  - Rationale: keeps router signature lean (matches `_internal/email/router.py:56` shape) and lets per-event tests target `handlers.py` directly without ASGI plumbing.
- **D-50-02:** **No new `app/modules/` directory** — the webhook is a transport-layer entry point, not a domain module (per Phase 42 D-42-17 `_internal` namespace doctrine). Business logic delegates back to existing domain modules via Protocol slots + the `payment_recorder` Protocol.
- **D-50-03:** Router mounted in `app/api/v1/router.py` as the **second** `_internal` inhabitant:
  ```python
  app.include_router(
      yookassa_webhook_router,
      prefix="/_internal/yookassa",
      tags=["_internal"],
  )
  ```
  Full path: `POST /api/v1/_internal/yookassa/webhook`.

### IP gate ordering (WH-01)

- **D-50-04:** Route declaration uses `dependencies=[Depends(verify_yookassa_ip)]` on the path-operation decorator (NOT in the function signature). FastAPI resolves route-level `dependencies=[...]` BEFORE any body parsing or signature-level dependencies. Mirror precedent: `_internal/email/router.py:101` (`dependencies=[Depends(_verify_email_webhook_signature)]`).
- **D-50-05:** **AST gate test** at `apps/backend/tests/unit/test_locked_yookassa_constants_ast.py` (existing file from Phase 47/48) — extend with `test_webhook_route_has_verify_ip_dependency_before_body_parse`: parse the router file's AST, find the `POST /webhook` route decorator, assert `dependencies=[Depends(verify_yookassa_ip)]` is present as a literal. Existing Phase 47 plan 47-03 + Phase 48 D-48-18 AST gates establish the pattern.
- **D-50-06:** `verify_yookassa_ip` already emits **structlog warning only** on rejected_ip (Phase 48 D-48-19 / SUMMARY); Phase 50 router additionally emits the **audit DB row** (`yookassa_webhook_received` with `idempotency_outcome='rejected_ip'`) — but this is only reachable when `verify_yookassa_ip` ACCEPTS the IP (false positive on the verifier wouldn't allow control to reach the router body). For genuine 403s the structlog warning is the only trace, by design.

### Redis dedup (WH-03)

- **D-50-07:** Dedup key formula: `sz:yookassa:webhook:{event_type}:{object_id}` — per PITFALLS line 64, `(event_type, object.id)` is the natural key (NOT just `object.id`, because `payment.canceled` + `payment.succeeded` are distinct events for the same payment row).
- **D-50-08:** Implementation: `await redis.set(key, "1", nx=True, ex=86400)`. If `set` returns `None` (key already exists), short-circuit with **HTTP 200** (ЮKassa won't retry on 200) + structlog INFO `event="yookassa_webhook_dedup_hit"`. Do NOT emit an audit DB row for dedup hits — the original delivery already emitted; the duplicate is operationally invisible.
- **D-50-09:** TTL = `86400` seconds (24h) — matches ЮKassa's retry window. Constant `WEBHOOK_DEDUP_TTL_SECONDS: Final[int] = 86400` in `app/api/v1/_internal/yookassa/router.py`. Constant `WEBHOOK_DEDUP_KEY_PREFIX: Final[str] = "sz:yookassa:webhook:"` — co-located with the `record_payment(method='online')` namespace conventions.
- **D-50-10:** **Atomic dedup BEFORE re-fetch.** Order is: IP gate → JSON parse → Redis SET NX → re-fetch → handler. Rationale: re-fetch is an outbound HTTP call; running it on every duplicate webhook delivery wastes ЮKassa rate-budget. The DB UNIQUE `(yookassa_payment_id)` on Phase 49's `online_payments` is the second-layer defense if Redis is down (per PITFALLS Pitfall 2's fail-safe discipline).

### Re-fetch-before-write (WH-02)

- **D-50-11:** Handler signature: `async def handle_payment_succeeded(session, redis, yookassa_client, *, webhook_body: dict) -> Response`. First action AFTER dedup is `result = await yookassa_client.get_payment(webhook_body["object"]["id"])`. If `result.classification != 'ok'`, return 200 + structlog WARNING `event="yookassa_webhook_refetch_failed"` (no DB write; ЮKassa will retry; on next retry the re-fetch may succeed).
- **D-50-12:** **Status-source-of-truth is `result.status` (from re-fetch), NOT `webhook_body["object"]["status"]`** — PITFALLS line 30 ("the cryptographic anchor that HMAC would otherwise provide"). The re-fetch result populates the audit payload's `yookassa_payment_id` field and drives the FSM transition decision.
- **D-50-13:** If `result.status == 'pending'` (race: webhook arrived before ЮKassa internal commit), return 200 + structlog INFO `event="yookassa_webhook_pending_skip"`. Do NOT delete the Redis dedup key (the next retry within 24h will find the same key and short-circuit — acceptable; eventual consistency wins). Phase 53 may add a stale-pending audit cron if operator feedback demands.
- **D-50-14:** AST gate test `test_payment_succeeded_handler_calls_get_payment_before_any_db_write`: parse `handlers.py` AST, find `handle_payment_succeeded`, assert the first `await session.execute|add|flush|commit` call appears AFTER an `await yookassa_client.get_payment` call. This is structural enforcement of WH-02 (mirror Phase 48 D-48-18 AST gate pattern).

### Payment FSM (WH-04)

- **D-50-15:** Declarative transitions constant lives in `apps/backend/app/modules/online_payments/constants.py` (Phase 49 placeholder file):
  ```python
  from collections.abc import Mapping
  from types import MappingProxyType
  
  ONLINE_PAYMENT_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType({
      "pending":   frozenset({"succeeded", "canceled"}),
      "succeeded": frozenset(),  # terminal
      "canceled":  frozenset(),  # terminal
  })
  ```
  Mirror byte-for-byte Phase 16 `MEMBERSHIP_STATUS_TRANSITIONS` shape. Add to `__all__`.
- **D-50-16:** `_assert_can_transition` helper lives in `apps/backend/app/api/v1/_internal/yookassa/handlers.py` (NOT in `app/modules/online_payments/service.py` — keeps Phase 49's service.py focused on outbound sell flow; Phase 50 webhook handlers own the inbound FSM):
  ```python
  def _assert_can_transition(row: OnlinePayment, *, target: str) -> None:
      allowed = ONLINE_PAYMENT_STATUS_TRANSITIONS.get(row.status, frozenset())
      if target not in allowed:
          raise IllegalTransitionError(
              code="online_payment_illegal_transition",
              message=f"Cannot transition online_payment {row.id} from {row.status} to {target}",
              fields={"current": row.status, "target": target},
          )
  ```
  Pattern: byte-for-byte mirror of `app/modules/memberships/service.py:208`.
- **D-50-17:** **Illegal transition** → return HTTP 200 + structlog WARNING `event="yookassa_webhook_illegal_transition"`. Do NOT 4xx (would trigger ЮKassa retry storm for a state the system can never recover from — e.g., a stale `payment.succeeded` arriving after manual cancellation). Audit DB row emitted with `idempotency_outcome='illegal_transition'` for forensics.

### Atomic UoW on `payment.succeeded` (WH-05)

- **D-50-18:** Single `async with session.begin()` block in `handle_payment_succeeded` executes in this order:
  1. SELECT `OnlinePayment` row `FOR UPDATE` (row-level lock to serialize concurrent webhook deliveries for the same payment).
  2. `_assert_can_transition(row, target="succeeded")`.
  3. UPDATE `online_payments` SET `status='succeeded'`, `succeeded_at=now()`.
  4. `payment_id = await payment_recorder.record_payment(session, *, client_id=row.client_id, amount_kopecks=row.amount_kopecks, method="online", **)` — returns ledger row UUID.
  5. INSERT `fiscal_receipts(payment_id=payment_id, kind="payment", status="sent", customer_email=clients.email, sent_at=now())` (single-statement; Phase 51 ARQ task will flip to `succeeded` later).
  6. `await activator(session, subject_id=row.membership_plan_id or row.pt_package_plan_id, audit_correlation_id=row.audit_correlation_id)` — Phase 50 ships real bodies (see D-50-22).
  7. Emit `online_payment_succeeded` audit (chain CHILD with `audit_correlation_id=webhook_intake_corr`).
  8. Emit `yookassa_webhook_received` audit (chain ROOT — `webhook_intake_corr` becomes its `id`). Done in REVERSE order from Phase 49: webhook intake is emitted LAST inside the UoW so its UUID is the chain root for all post-commit notifications (Phase 52 NOT-04 reads it).

  Implementation note: SQLAlchemy `session.execute(select(...).with_for_update())` is the locking primitive; `session.begin()` wraps the whole block; commit on `__aexit__`.
- **D-50-19:** **Post-commit hook for notifications** (Phase 52 will populate; Phase 50 lays the seam): after `session.commit()`, the handler enqueues `notify_membership_activated(...)` / `notify_pt_package_activated(...)` ARQ tasks. Phase 50 ships a `_post_commit_enqueue(arq_pool, payment_id, subject_kind, subject_id)` helper that currently no-ops (logs INFO `event="webhook_post_commit_enqueue_skip"`); Phase 52 fills it. Rationale: keep the wiring in place so Phase 52 is a body-fill, not a re-architecture.
- **D-50-20:** **Multi-step UoW reaches into 2 modules' ORMs.** Specifically:
  - `app/modules/payments/models.py:Payment` — already imported by `payment_recorder` Protocol consumer (D-49-29 marker said TYPE_CHECKING in Phase 49; flip to runtime in Phase 50). Add ignore: `app.api.v1._internal.yookassa.handlers → app.modules.payments.models` is NOT needed — handlers don't import the model directly; they call the Protocol.
  - `app/modules/online_payments/models.py:OnlinePayment` — Phase 50 webhook handler SELECTs + UPDATEs this. Need import-linter ignore? The handler lives under `app.api.v1._internal.yookassa.handlers`. The `core-not-depend-on-modules` contract scopes `app.core`, not `app.api`. The `modules-independent` contract scopes `app.modules.*`. `app.api.*` is unrestricted by both — no ignore needed. Verify with `lint-imports` after the import lands.
- **D-50-21:** **Membership-vs-PT-package dispatch** inside the handler: read `row.membership_plan_id` and `row.pt_package_plan_id`; whichever is non-NULL drives which activator to call. Single conditional branch (per D-49-04 XOR CHECK constraint guarantees exactly one is non-NULL).

### Activator bodies (Phase 50 fills Phase 49 stubs)

- **D-50-22:** `app/modules/memberships/service.py:activate_membership_from_webhook` body:
  1. SELECT `MembershipPlan` by `subject_id` (read-only — fetch `duration_days` to compute `end_date`).
  2. SELECT or INSERT `Membership` row for `client_id` + `plan_id` (idempotent — if a row already exists in `pending` state, transition to `active`; if it exists in `active`, no-op + WARNING; if it exists in `cancelled`, error).
  3. UPDATE `Membership.status='active'`, `start_date=today_msk`, `end_date=today_msk + duration_days`.
  4. Emit `membership_activated_online` audit (NEW LOCKED event — see D-50-23) with `audit_correlation_id=audit_correlation_id` (CHILD of webhook intake chain).
  5. Return the Membership row.
- **D-50-23:** **New audit event:** `("membership_activated_online", "membership")` — must be appended to `LOCKED_AUDIT_EVENTS` in `app/core/audit.py` + payload class `MembershipActivatedOnlinePayload { audit_correlation_id, membership_id, client_id, online_payment_id }` in `audit_payloads.py`. Mirror: `("pt_package_activated_online", "pt_package")` + `PtPackageActivatedOnlinePayload` for the PT-package path. Both events guarded by AST gate (Phase 47 INFRA-35 discipline). **Effective new LOCKED events count: 11 (was 9 in Phase 47; +2 here).**
- **D-50-24:** `app/modules/pt_packages/service.py:activate_pt_package_from_webhook` body: mirror of D-50-22 against `PtPackage` + `pt_packages_plans`. Returns the PtPackage row.

### Cancellation path (WH-06)

- **D-50-25:** `handle_payment_canceled` handler does NOT call the activator. Atomic UoW:
  1. SELECT-FOR-UPDATE the `OnlinePayment` row.
  2. `_assert_can_transition(row, target="canceled")`.
  3. UPDATE `status='canceled'`, `canceled_at=now()`.
  4. Emit `online_payment_canceled` audit (CHILD of webhook intake chain). Payload: `cancellation_party = webhook_body["object"]["cancellation_details"].get("party")`; `cancellation_reason = webhook_body["object"]["cancellation_details"].get("reason")`. Both fields are `str | None` (ЮKassa may omit `cancellation_details` entirely on operator-initiated cancellations; payload schema already accepts `None` per Phase 47 D-47-01).
  5. Emit `yookassa_webhook_received` audit (chain ROOT).
- **D-50-26:** No fiscal-receipt INSERT on cancellation (cancelled payment never produced a fiscal obligation).
- **D-50-27:** **NOTIFY-05 reasoning capture** (deferred to Phase 52): cancellation_reason is preserved in the audit row for Phase 52 NOT-05 DM body composition. Phase 50 does NOT enqueue any DMs (D-50-19 same no-op).

### `fiscal_receipts` ORM + Alembic 0035 (FISCAL-01, FISCAL-02)

- **D-50-28:** New module skeleton: `app/modules/fiscal_receipts/` — sibling of `online_payments`, matches the v1.5+ module shape:
  ```
  app/modules/fiscal_receipts/
  ├── __init__.py
  ├── constants.py        # FISCAL_RECEIPT_STATUS_TRANSITIONS (pending → sent → succeeded/failed)
  ├── models.py           # FiscalReceipt ORM
  ├── repository.py       # insert + by-id + by-payment_id_and_kind
  └── (no router/service/schemas — Phase 51 fills these for the dispatch task + receipt webhook)
  ```
- **D-50-29:** `FiscalReceipt` ORM fields (mirror FISCAL-01 spec):
  ```
  id                     UUID PK (UUIDv4, app-side default)
  payment_id             UUID FK payments.id ON DELETE RESTRICT
  kind                   TEXT NOT NULL CHECK (kind IN ('payment', 'refund'))
  status                 TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'succeeded', 'failed'))
  yookassa_receipt_id    TEXT NULL
  customer_email         TEXT NOT NULL
  failure_reason         TEXT NULL
  sent_at                TIMESTAMPTZ NULL
  succeeded_at           TIMESTAMPTZ NULL
  failed_at              TIMESTAMPTZ NULL
  audit_correlation_id   UUID NULL                # carries Phase 50 webhook chain UUID
  ```
  - FK `payment_id → payments.id` (NOT `online_payments.id`) — fiscal obligation attaches to the committed ledger row, per FEATURES.md SUMMARY line 104.
  - `audit_correlation_id` lets Phase 51 FISCAL-04/05 audit events thread back to the Phase 50 webhook intake.
- **D-50-30:** Alembic 0035 ships **one** UNIQUE index per FISCAL-02: `UNIQUE (payment_id, kind)` — full btree (no partial predicate). Phase 49's 0034 pattern (named via `op.f()`, IMMUTABLE-safe SQL) carried forward.
- **D-50-31:** Migration file: `apps/backend/alembic/versions/0035_fiscal_receipts.py`; `down_revision = "0034_online_payments"`. Downgrade is lossless reverse — `drop_constraint('uq_fiscal_receipts_payment_id_kind')` then `drop_table('fiscal_receipts')`.
- **D-50-32:** `FISCAL_RECEIPT_STATUS_TRANSITIONS` in `app/modules/fiscal_receipts/constants.py` — declarative-FSM constant matching `ONLINE_PAYMENT_STATUS_TRANSITIONS` shape:
  ```python
  FISCAL_RECEIPT_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType({
      "pending":   frozenset({"sent"}),       # Phase 50 inserts directly as 'sent' on payment.succeeded
      "sent":      frozenset({"succeeded", "failed"}),  # Phase 51 ARQ task transitions
      "succeeded": frozenset(),               # terminal
      "failed":    frozenset(),               # terminal
  })
  ```
  Phase 50 inserts `status='sent'` directly (D-50-18 step 5); the `'pending' → 'sent'` transition exists for Phase 51's ARQ retry flow (where the row may be re-INSERTed as `'pending'` after a failed dispatch and later flipped).

### FISCAL-03 ratification — AST gate on payment_subject / payment_mode literals

- **D-50-33:** Extend `apps/backend/tests/unit/test_locked_yookassa_constants_ast.py` (existing from Phase 47/48) with `test_payment_subject_callsites_use_locked_literal` + `test_payment_mode_callsites_use_locked_literal`. Walk the AST of every `.py` file under `apps/backend/app/`, find `build_receipt_item(...)` calls, assert `payment_subject=` and `payment_mode=` keyword args are either:
  - Enum reference: `PaymentSubject.SERVICE`, `PaymentMode.FULL_PREPAYMENT`, etc. (Phase 49 uses these).
  - String literal exactly equal to `"service"` / `"full_payment"` / `"full_prepayment"`.
  Reject any non-literal (variable name, f-string, function call).
- **D-50-34:** **Receipt-embedded-in-payment-create is already shipped** by Phase 49 plan 49-03 service.sell_* via `build_receipt_item()`. Phase 50 does NOT modify the sell flow; FISCAL-03 here is the AST-gate hardening only.

### YOOKASSA_TAX_SYSTEM_CODE / YOOKASSA_VAT_CODE configuration (FISCAL-07)

- **D-50-35:** **Already shipped by Phase 47 `YooKassaSettings`** (`tax_system_code: int`, `default_vat_code: int`). FISCAL-07 listed under Phase 51 in REQUIREMENTS.md (lines 50-57: `FISCAL-07` is between FISCAL-04 and the REFUND block, both Phase 51). Phase 50 does NOT touch FISCAL-07. **Re-read of REQUIREMENTS.md confirms FISCAL-07 is Phase 50/51 boundary-adjacent**; the ROADMAP Phase 50 line lists `FISCAL-01, FISCAL-02, FISCAL-03` only. Leaving FISCAL-07 to Phase 51 per ROADMAP.

### Composition root + worker wiring

- **D-50-36:** `app/main.py:create_app()` `register_membership_activator(activate_membership_from_webhook)` / `register_pt_package_activator(activate_pt_package_from_webhook)` calls are ALREADY wired by Phase 49 plan 49-06 (just the bodies were stubs). Phase 50 fills the bodies (D-50-22/24) — no composition-root edits needed for these two.
- **D-50-37:** `FiscalReceiptDispatcher` stays as the **`phase49_fiscal_dispatcher_stub`** (raising `NotImplementedError` from Phase 49). Phase 50 does NOT swap it — the dispatcher is the ARQ enqueue path for the receipt-webhook flow (Phase 51 FISCAL-05). Phase 50 writes `fiscal_receipts(status='sent')` rows directly inside the webhook UoW; no Protocol dispatch needed.
- **D-50-38:** Worker startup (`app/workers/__init__.py:WorkerSettings.on_startup`) needs no edits — `MembershipActivator` and `PtPackageActivator` are HTTP-only single-wire (per Phase 47 docstrings), only the FastAPI side has them. The webhook handler itself runs HTTP-side (FastAPI route), not in the ARQ worker.

### Permissions / RBAC

- **D-50-39:** `_internal` endpoints are **anonymous** by design (verified by IP allowlist, NOT by session cookie). No `Depends(require_permission(...))`, no `Depends(verify_csrf)`, no `Depends(current_user)`. The `verify_yookassa_ip` Depends is the only auth. Mirror precedent: `_internal/email/router.py:101`.
- **D-50-40:** Add `/api/v1/_internal/yookassa/webhook` to `EXCLUDED_PATHS` in `apps/backend/tests/integration/test_route_introspection.py` (the test that asserts every protected route declares a gate). Phase 49 plan 49-05 already added `/return` to EXCLUDED_PATHS; pattern is established.

### Test strategy

- **D-50-41:** **Reuse Phase 48 respx fixtures** for the `GET /v3/payments/{id}` re-fetch — `yookassa_get_payment_pending`, `yookassa_get_payment_succeeded` are already shipped. NEW fixtures land in `apps/backend/tests/integration/online_payments/conftest.py` (Phase 49 plan 49-07 home) OR a new `tests/integration/webhook_yookassa/conftest.py`:
  - `webhook_payment_succeeded_body` — canonical webhook body dict (Phase 48 already ships `yookassa_webhook_payload`; verify shape covers Phase 50's expected `cancellation_details` for the cancellation tests).
  - `webhook_payment_canceled_body` — new; includes `object.cancellation_details = {party, reason}`.
  - `webhook_payment_succeeded_qr_body` — new; covers PT-package + QR sale lineage.
- **D-50-42:** Test placement: `apps/backend/tests/integration/webhook_yookassa/` (new directory mirroring `tests/integration/online_payments/` shape). Tests use cookie-jar-less `AsyncClient` (the webhook endpoint is anonymous) — direct ASGI POST with `X-Real-IP` header set to a value inside `YOOKASSA_TRUSTED_IPS` (or sandbox bypass per Phase 48 D-48-19).
- **D-50-43:** Coverage targets:
  - `test_wh01_403_outside_trusted_ips` — IP gate rejects with 403.
  - `test_wh02_refetches_before_db_write` — assert `respx_mock.get(...).called` BEFORE any `online_payments` UPDATE (count SQL statements or use a session-state spy fixture).
  - `test_wh03_redis_dedup_blocks_second_delivery` — POST same body twice; second returns 200, no second DB write.
  - `test_wh04_illegal_transition_returns_200_with_audit_row` — pre-set `online_payments.status='canceled'`, POST `payment.succeeded`; assert 200 + audit row with `illegal_transition` outcome.
  - `test_wh05_succeeded_atomic_uow_writes_4_rows_in_one_commit` — POST `payment.succeeded`; assert `online_payments` updated + `payments` ledger row inserted + `memberships`/`pt_packages` row activated + `fiscal_receipts` row inserted, all within a single observable commit boundary.
  - `test_wh06_canceled_records_cancellation_details` — POST `payment.canceled` with `cancellation_details`; assert audit payload fields.
  - `test_alembic_0035_fiscal_receipts` — schema-shape assertion for the new table + UNIQUE constraint.
  - `test_fiscal_03_ast_gate_payment_subject_payment_mode_literals` — AST scan rejects non-literal callsites.
  - `test_membership_activated_online_audit_event_locked` — `("membership_activated_online", "membership")` in `LOCKED_AUDIT_EVENTS`.

### Wave / plan shape preview for planner

- **D-50-44:** Suggested plan ordering — researcher and planner should refine:
  - **Wave 1 (sequential — bedrock):**
    - 50-01: Alembic 0035 `fiscal_receipts` table + UNIQUE (FISCAL-01, FISCAL-02). Schema only.
    - 50-02: `app/modules/fiscal_receipts/` skeleton + ORM + repository + `FISCAL_RECEIPT_STATUS_TRANSITIONS` constant. `ONLINE_PAYMENT_STATUS_TRANSITIONS` constant added to `app/modules/online_payments/constants.py`. New LOCKED audit events `membership_activated_online` + `pt_package_activated_online` + their payload classes (D-50-23) added to `app/core/audit.py` + `audit_payloads.py`.
  - **Wave 2 (parallelizable after Wave 1):**
    - 50-03: Activator bodies — `activate_membership_from_webhook` + `activate_pt_package_from_webhook` (D-50-22 / D-50-24) in `memberships/service.py` + `pt_packages/service.py`. No composition-root edits (Phase 49 plan 49-06 already wired the registrations).
    - 50-04: Webhook router + handlers — `app/api/v1/_internal/yookassa/{router,handlers}.py` (D-50-01..27) + mount in `app/api/v1/router.py` + `_internal/__init__.py` updates.
    - 50-05: FISCAL-03 AST gate extension (D-50-33) — additive test functions in `tests/unit/test_locked_yookassa_constants_ast.py`.
  - **Wave 3 (sequential — depends on Wave 2):**
    - 50-06: End-to-end integration tests + audit-chain verification + route-introspection exclusion (D-50-40..43).
  - **Estimated plan count: 6** (range 5–7 depending on whether 50-02 splits ORM from FSM constants).

### Claude's Discretion

Downstream agents may settle the following without re-asking:

- **Logger naming:** `_log = structlog.get_logger("api.v1._internal.yookassa")` — mirror `_internal/email/router.py:54`.
- **Webhook body Pydantic shape:** parse via `WebhookEnvelope { event: str, object: dict[str, Any] }` minimal model with `extra='allow'` (NOT `extra='forbid'`) — ЮKassa adds fields between API versions; permissive parse + targeted lookups is more robust than re-shipping a v1.7 schema each time they extend.
- **Webhook payload size limit:** rely on FastAPI default (`MAX_CONTENT_LENGTH` not set in project); ЮKassa bodies are < 2 KB. No streaming.
- **`Idempotency-Key` HTTP header:** webhook deliveries do NOT carry one; Redis SET NX is the dedup primitive (D-50-08).
- **`payment.waiting_for_capture` event:** PITFALLS line 311 mentions this as a 4th event type in production. Phase 50 ignores it (returns 200 + structlog INFO `event="yookassa_webhook_unsupported_event_type"`); Phase 53 deployment runbook documents the subscription set. The handler dispatch is a simple `if event == "payment.succeeded": ...` chain; unknown events fall through to the no-op INFO log.
- **`refund.succeeded` event:** out of scope for Phase 50 (Phase 51 REFUND-01..04 wires it). Falls through to the unknown-event no-op log here.
- **Logging payload PII:** the structlog INFO line on success/failure logs `event_type`, `object_id`, `online_payment_id`, but NOT `customer_email` (PII discipline; email lives only in the fiscal_receipts row + the audit DB).
- **HTTP response shape:** always return `Response(status_code=200, content="ok", media_type="text/plain")`. ЮKassa accepts any 2xx body. Mirror precedent: `_internal/email/router.py` returns 204 No Content; we use 200 + body for symmetry with Stripe-style webhook conventions and to match D-50-08's plain-text-OK dedup short-circuit.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project / milestone scope
- `.planning/PROJECT.md` — milestone v1.7 framing, RF regional constraints, webhook IP-allowlist security model
- `.planning/REQUIREMENTS.md` lines 43–48 — WH-01..06 full text
- `.planning/REQUIREMENTS.md` lines 50–57 — FISCAL-01..07 full text (Phase 50 covers FISCAL-01..03 per ROADMAP)
- `.planning/REQUIREMENTS.md` traceability table — WH/FISCAL → Phase 50 / 51 mapping
- `.planning/ROADMAP.md` lines 207–218 — Phase 50 goal + 6 success criteria
- `.planning/STATE.md` — milestone v1.7 status

### Prior phase context (Phase 47 / 48 / 49)
- `.planning/phases/47-bedrock/47-CONTEXT.md` — D-47-01..09: Protocol slot pattern, LOCKED_AUDIT_EVENTS discipline
- `.planning/phases/48-kassa-integration-adapter/48-CONTEXT.md` — D-48-19/20/22: `verify_yookassa_ip` body + AST gate + respx fixtures
- `.planning/phases/48-kassa-integration-adapter/48-VERIFICATION.md` — Phase 48 outcome: live `YooKassaClient.get_payment` for re-fetch
- `.planning/phases/49-online-sales-orchestrator/49-CONTEXT.md` — D-49-19 audit chain shape; D-49-21/22 stubs to fill; D-49-04 OnlinePayment columns
- `.planning/phases/49-online-sales-orchestrator/49-07-SUMMARY.md` — full Phase 49 outcome, including 4 v1.7 Protocol slots non-None
- `.planning/phases/49-online-sales-orchestrator/49-VERIFICATION.md` — Phase 49 verification (14/14 must-haves)
- `.planning/phases/49-online-sales-orchestrator/deferred-items.md` — D-49-29 (payments.models flip from TYPE_CHECKING to runtime in Phase 50), D-49-30 (users.display), Phase 50 yookassa_call_failed event

### Research (v1.7 milestone)
- `.planning/research/SUMMARY.md` lines 16–104 — ledger isolation rule, `record_payment(method='online')` Protocol slot
- `.planning/research/PITFALLS.md` Pitfall 1 — IP allowlist + re-fetch-before-write (Phase 50 owns the implementation)
- `.planning/research/PITFALLS.md` Pitfall 2 — webhook dedup discipline (`(event_type, object.id)`); 24h ЮKassa retry window
- `.planning/research/PITFALLS.md` Pitfall 4 — return-URL oracle (informational; Phase 49 owns)
- `.planning/research/PITFALLS.md` Pitfall 12 — atomic UoW for multi-step online payment flow (D-50-18 directly traces this)
- `.planning/research/PITFALLS.md` Pitfall 10 — refund-webhook dedup (informational; Phase 51 owns)
- `.planning/research/PITFALLS.md` lines 357–390 — audit-event chain ordering for multi-step UoW
- `.planning/research/PITFALLS.md` lines 476–500 — LOCKED_AUDIT_EVENTS pre-registration discipline (D-50-23 adds 2 new events)
- `.planning/research/STACK.md` §1 lines 1–100 — Idempotence-Key, Basic Auth, webhook IP security
- `.planning/research/STACK.md` §2 lines 100–170 — 54-ФЗ receipt structure
- `.planning/research/STACK.md` §6 lines 252–261 — integration touchpoints
- `.planning/research/FEATURES.md` lines 95–112 — `online_payments` FSM + UNIQUE discipline
- `.planning/research/FEATURES.md` lines 195–215 — fiscal-receipt model + retry boundaries

### Codebase contracts to preserve
- `apps/backend/app/api/v1/_internal/__init__.py` + `apps/backend/app/api/v1/_internal/email/router.py` (lines 1–60, 99–115) — structural template for `_internal/yookassa/router.py`
- `apps/backend/app/api/v1/router.py` lines 75–88 — `_internal` mounting pattern (Phase 50 adds the second `_internal` inhabitant)
- `apps/backend/app/integrations/yookassa/webhook_verifier.py` — `verify_yookassa_ip` body (Phase 48 D-48-19); Phase 50 mounts it via `Depends`
- `apps/backend/app/integrations/yookassa/client.py` `get_payment` — re-fetch entry point (consumes `qr_payload` extraction from Phase 49 plan 49-01)
- `apps/backend/app/integrations/yookassa/types.py` `YooKassaPaymentResult` — typed result for re-fetch (`status`, `amount_kopecks`, `payment_id`, `confirmation_url`, `qr_payload`, `classification`)
- `apps/backend/app/core/redis.py` `get_redis` — Depends-injectable Redis client (used for dedup SET NX)
- `apps/backend/app/core/audit.py` `LOCKED_AUDIT_EVENTS` + `emit` — extend with `membership_activated_online` + `pt_package_activated_online`
- `apps/backend/app/core/audit_payloads.py` — add `MembershipActivatedOnlinePayload` + `PtPackageActivatedOnlinePayload`; existing `OnlinePaymentSucceededPayload` (line 780) + `OnlinePaymentCanceledPayload` (line 799) + `YookassaWebhookReceivedPayload` (line 894) reused by Phase 50
- `apps/backend/app/core/dependencies.py` lines 339–413 — `PaymentRecorder` Protocol slot + `get_payment_recorder` accessor (consumed by webhook handler D-50-18 step 4)
- `apps/backend/app/core/dependencies.py` lines 1059–1195 — `MembershipActivator` + `PtPackageActivator` slots (Phase 49 wired stubs; Phase 50 fills bodies in `memberships/service.py` + `pt_packages/service.py`)
- `apps/backend/app/modules/payments/service.py` `record_payment(method='online')` (line 90) — ledger row writer; consumed via Protocol
- `apps/backend/app/modules/online_payments/models.py` `OnlinePayment` — Phase 50 SELECT-FOR-UPDATE target
- `apps/backend/app/modules/online_payments/constants.py` (Phase 49 placeholder) — Phase 50 adds `ONLINE_PAYMENT_STATUS_TRANSITIONS`
- `apps/backend/app/modules/memberships/constants.py:22` + `service.py:208` — `_assert_can_transition` byte-for-byte mirror source
- `apps/backend/app/modules/memberships/service.py:activate_membership_from_webhook` — Phase 49 stub body to fill
- `apps/backend/app/modules/pt_packages/service.py:activate_pt_package_from_webhook` — Phase 49 stub body to fill
- `apps/backend/app/modules/memberships/models.py` `Membership` + `MembershipPlan` — activator UoW targets
- `apps/backend/app/modules/pt_packages/models.py` `PtPackage` + `PtPackagePlan` — activator UoW targets
- `apps/backend/app/main.py:create_app()` lines 317–329 — composition-root precedent (no edits needed; activators already registered Phase 49)
- `apps/backend/app/workers/__init__.py:WorkerSettings.on_startup` — HTTP-only single-wire pattern (no edits)
- `apps/backend/alembic/versions/0034_online_payments.py` — naming convention + IMMUTABLE-expression precedent for 0035
- `apps/backend/tests/unit/test_locked_yookassa_constants_ast.py` — existing AST gates (Phase 47 + 48); Phase 50 extends with WH-02 ordering + FISCAL-03 literal gates
- `apps/backend/tests/integration/test_route_introspection.py` — `EXCLUDED_PATHS` precedent (Phase 49 plan 49-05 added `/return`; Phase 50 adds `/webhook`)
- `apps/backend/tests/integrations/yookassa/conftest.py` — Phase 48/49 respx fixtures (reused for re-fetch tests)
- `apps/backend/tests/integration/online_payments/conftest.py` — Phase 49 plan 49-07 cookie-jar fixture (reused if Phase 50 tests land alongside; otherwise new `tests/integration/webhook_yookassa/conftest.py`)
- `apps/backend/.importlinter` — likely no edits in Phase 50 (handler under `app.api.*` which is unrestricted by `core-not-depend-on-modules` + `modules-independent` contracts); verify post-implementation

### External specs (ЮKassa / 54-ФЗ)
- https://yookassa.ru/developers/using-api/webhooks — IP allowlist + retry semantics + event-type catalog (`payment.succeeded`, `payment.canceled`, `payment.waiting_for_capture`, `refund.succeeded`)
- https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process — payment FSM `pending → succeeded | canceled`
- https://yookassa.ru/developers/api?codeLang=python#get_payment — `GET /v3/payments/{id}` schema for re-fetch
- https://yookassa.ru/developers/payment-acceptance/scenario-extensions/cancellation-details — `cancellation_details.party` + `cancellation_details.reason` enum values (D-50-25)
- https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values — receipt enums (FISCAL-03 AST gate target)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`app/api/v1/_internal/email/router.py`** — direct structural template for `_internal/yookassa/router.py`. Same route-level `dependencies=[...]` ordering, same structlog logger naming, same NO-CSRF / NO-auth model.
- **`app/integrations/yookassa/webhook_verifier.py:verify_yookassa_ip`** — body already filled in Phase 48; Phase 50 just mounts it as `Depends(verify_yookassa_ip)` on the route decorator.
- **`app/integrations/yookassa/client.py:get_payment`** — re-fetch entry point; Phase 49 plan 49-01 extended it to populate `qr_payload` on QR confirmations (re-fetch result returns `YooKassaPaymentResult` with classification).
- **`app/core/redis.py:get_redis`** + Redis `SET NX EX` — exact dedup primitive already used by `app/core/idempotency.py:IDEMPOTENCY_REDIS_PREFIX`.
- **`app/core/audit.py:emit` + `LOCKED_AUDIT_EVENTS`** — Phase 47 + 49 v1.7 events all locked; Phase 50 adds 2 (`membership_activated_online`, `pt_package_activated_online`).
- **`app/core/audit_payloads.py` `OnlinePaymentSucceededPayload`** (line 780) + `OnlinePaymentCanceledPayload` (line 799) + `YookassaWebhookReceivedPayload` (line 894) — all Phase 47 shipped; Phase 50 only emits, never declares.
- **`app/core/dependencies.py:get_payment_recorder`** (line 404) — Phase 32 Protocol slot; Phase 50 webhook UoW step 4.
- **`app/core/dependencies.py:get_membership_activator` / `get_pt_package_activator`** (lines 1112, 1181) — Phase 47 declared / Phase 49 wired (stubs); Phase 50 fills bodies and calls via accessor.
- **`app/modules/payments/service.py:record_payment(method='online')`** (line 90) — caller-owns-txn ledger writer; Phase 50 calls from inside webhook UoW.
- **`app/modules/memberships/constants.py:MEMBERSHIP_STATUS_TRANSITIONS`** (line 22) + `service.py:_assert_can_transition` (line 208) — byte-for-byte mirror source for `ONLINE_PAYMENT_STATUS_TRANSITIONS` + its guard.
- **`app/modules/online_payments/constants.py`** (Phase 49 placeholder, single-docstring file) — Phase 50 adds `ONLINE_PAYMENT_STATUS_TRANSITIONS`.
- **`tests/integrations/yookassa/conftest.py:yookassa_get_payment_succeeded` + `yookassa_get_payment_pending`** — Phase 48 ADAPTER-06 fixtures reused for re-fetch path tests.
- **`tests/integration/online_payments/conftest.py`** — Phase 49 plan 49-07 cookie-jar + structlog reset fixtures (precedent; Phase 50 may mirror under new `tests/integration/webhook_yookassa/conftest.py` if directory separation preferred).
- **`apps/backend/alembic/versions/0034_online_payments.py`** — naming convention (`op.f()` wrappers, IMMUTABLE-safe SQL) for 0035.

### Established Patterns
- **`_internal` namespace anonymity** (D-42-17 / Phase 42 EMAIL-07) — transport-layer endpoints get a dedicated `/api/v1/_internal/*` prefix; IP gate (for ЮKassa) or HMAC gate (for SES) are the only auth.
- **AST-gated locked constants** (Phase 47/48 INFRA-15) — every literal that must NEVER drift gets a parser-level guard. Phase 50 adds: WH-02 ordering gate (re-fetch BEFORE DB write), FISCAL-03 payment_subject/payment_mode literal gate.
- **Caller-owns-txn UoW** — Phase 50 webhook handler is the txn owner; `record_payment` + activator + fiscal-receipt INSERT all run inside the handler's `async with session.begin()`.
- **Two-event audit chain with `audit_correlation_id`** (D-49-19 lineage) — Phase 50 emits CHILD events with `audit_correlation_id=webhook_intake_corr` and the webhook-intake row's own UUID becomes the chain ROOT.
- **Declarative FSM** (Phase 16 + 24) — `_TRANSITIONS` mapping + `_assert_can_transition` guard; raise `IllegalTransitionError` not return-tuple.
- **Protocol slot Phase-N stub → Phase-N+1 body** (D-47-01 lineage) — Phase 49 shipped activator stubs; Phase 50 fills bodies. Composition-root edits stay zero.
- **Result-classification at integration boundary** (D-48-10) — `YooKassaPaymentResult.classification` drives the re-fetch error branch (D-50-11).

### Integration Points
- `apps/backend/app/api/v1/_internal/yookassa/__init__.py` (new) — module marker.
- `apps/backend/app/api/v1/_internal/yookassa/router.py` (new) — POST /webhook handler + `WEBHOOK_DEDUP_TTL_SECONDS` + `WEBHOOK_DEDUP_KEY_PREFIX` constants.
- `apps/backend/app/api/v1/_internal/yookassa/handlers.py` (new) — `handle_payment_succeeded`, `handle_payment_canceled`, `_assert_can_transition`, `_post_commit_enqueue` (no-op stub for Phase 52).
- `apps/backend/app/api/v1/router.py` — mount `yookassa_webhook_router` at `prefix="/_internal/yookassa"`, `tags=["_internal"]`.
- `apps/backend/alembic/versions/0035_fiscal_receipts.py` (new) — table + UNIQUE; `down_revision = "0034_online_payments"`.
- `apps/backend/app/modules/fiscal_receipts/__init__.py` + `constants.py` + `models.py` + `repository.py` (new module).
- `apps/backend/app/modules/online_payments/constants.py` — add `ONLINE_PAYMENT_STATUS_TRANSITIONS` + `__all__` entry.
- `apps/backend/app/modules/memberships/service.py:activate_membership_from_webhook` — replace `NotImplementedError` body with D-50-22 implementation.
- `apps/backend/app/modules/pt_packages/service.py:activate_pt_package_from_webhook` — replace body with D-50-24.
- `apps/backend/app/core/audit.py` — append 2 new entries to `LOCKED_AUDIT_EVENTS` and the docstring catalog.
- `apps/backend/app/core/audit_payloads.py` — add `MembershipActivatedOnlinePayload` + `PtPackageActivatedOnlinePayload`; register in `AUDIT_PAYLOAD_SCHEMAS`.
- `apps/backend/tests/unit/test_locked_yookassa_constants_ast.py` — add 3 test functions (WH-02 ordering + FISCAL-03 payment_subject + payment_mode gates).
- `apps/backend/tests/integration/webhook_yookassa/conftest.py` (new) + `test_webhook_*.py` files (9 test surface per D-50-43).
- `apps/backend/tests/integration/test_alembic_0035_fiscal_receipts.py` (new) — schema-shape assertion.
- `apps/backend/tests/integration/test_route_introspection.py` — append `/api/v1/_internal/yookassa/webhook` to `EXCLUDED_PATHS`.

</code_context>

<specifics>
## Specific Ideas

- **Webhook route shape (D-50-04 / D-50-08):**
  ```python
  WEBHOOK_DEDUP_KEY_PREFIX: Final[str] = "sz:yookassa:webhook:"
  WEBHOOK_DEDUP_TTL_SECONDS: Final[int] = 86400

  router = APIRouter()

  @router.post(
      "/webhook",
      include_in_schema=False,
      dependencies=[Depends(verify_yookassa_ip)],
  )
  async def yookassa_webhook(
      request: Request,
      session: Annotated[AsyncSession, Depends(get_db)],
      redis: Annotated[Redis, Depends(get_redis)],
      yookassa_client: Annotated[YooKassaClient, Depends(get_yookassa_client_provider)],
  ) -> Response:
      body = await request.json()
      event_type = body.get("event", "")
      object_id = body.get("object", {}).get("id", "")
      if not event_type or not object_id:
          return Response(status_code=200, content="ok", media_type="text/plain")
      dedup_key = f"{WEBHOOK_DEDUP_KEY_PREFIX}{event_type}:{object_id}"
      if not await redis.set(dedup_key, "1", nx=True, ex=WEBHOOK_DEDUP_TTL_SECONDS):
          _log.info("yookassa_webhook_dedup_hit", event_type=event_type, object_id=object_id)
          return Response(status_code=200, content="ok", media_type="text/plain")
      if event_type == "payment.succeeded":
          await handle_payment_succeeded(session, yookassa_client, body=body)
      elif event_type == "payment.canceled":
          await handle_payment_canceled(session, yookassa_client, body=body)
      else:
          _log.info("yookassa_webhook_unsupported_event_type", event_type=event_type)
      return Response(status_code=200, content="ok", media_type="text/plain")
  ```

- **Atomic UoW skeleton (D-50-18):**
  ```python
  async def handle_payment_succeeded(
      session: AsyncSession,
      yookassa_client: YooKassaClient,
      *,
      body: dict[str, Any],
  ) -> None:
      object_id = body["object"]["id"]
      result = await yookassa_client.get_payment(object_id)
      if result.classification != "ok":
          _log.warning("yookassa_webhook_refetch_failed", classification=result.classification)
          return
      if result.status != "succeeded":
          _log.info("yookassa_webhook_pending_skip", status=result.status)
          return
      webhook_intake_corr = uuid4()
      async with session.begin():
          row = (await session.execute(
              select(OnlinePayment).where(OnlinePayment.yookassa_payment_id == object_id).with_for_update()
          )).scalar_one_or_none()
          if row is None:
              _log.warning("yookassa_webhook_orphan_payment_succeeded", object_id=object_id)
              return  # Phase 53 reconcile cron handles orphan recovery
          _assert_can_transition(row, target="succeeded")
          row.status = "succeeded"
          row.succeeded_at = datetime.now(UTC)
          payment_recorder = get_payment_recorder()
          ledger_row_id = await payment_recorder(
              session,
              client_id=row.client_id,
              amount_kopecks=row.amount_kopecks,
              method="online",
              audit_correlation_id=webhook_intake_corr,
          )
          subject_kind = "membership" if row.membership_plan_id else "pt_package"
          subject_id = row.membership_plan_id or row.pt_package_plan_id
          activator = (
              get_membership_activator() if subject_kind == "membership"
              else get_pt_package_activator()
          )
          await activator(session, subject_id=subject_id, audit_correlation_id=row.audit_correlation_id)
          session.add(FiscalReceipt(
              payment_id=ledger_row_id,
              kind="payment",
              status="sent",
              customer_email=row.client.email,  # Or fetch via separate SELECT
              sent_at=datetime.now(UTC),
              audit_correlation_id=webhook_intake_corr,
          ))
          await audit.emit(session, event="online_payment_succeeded", resource_type="online_payment",
                           payload=OnlinePaymentSucceededPayload(
                               audit_correlation_id=webhook_intake_corr,
                               online_payment_id=row.id,
                               yookassa_payment_id=object_id,
                               amount_kopecks=row.amount_kopecks,
                               payment_id=ledger_row_id,
                           ))
          await audit.emit(session, event="yookassa_webhook_received", resource_type="yookassa_webhook",
                           payload=YookassaWebhookReceivedPayload(
                               event_type="payment.succeeded",
                               object_id=object_id,
                               idempotency_outcome="processed",
                           ))
      # POST-COMMIT (outside async with):
      await _post_commit_enqueue(...)
  ```

- **Cancellation handler skeleton (D-50-25):**
  ```python
  async def handle_payment_canceled(session, yookassa_client, *, body):
      object_id = body["object"]["id"]
      result = await yookassa_client.get_payment(object_id)
      if result.classification != "ok" or result.status != "canceled":
          return
      details = body["object"].get("cancellation_details", {})
      webhook_intake_corr = uuid4()
      async with session.begin():
          row = await _select_for_update(session, object_id)
          if row is None:
              return
          _assert_can_transition(row, target="canceled")
          row.status = "canceled"
          row.canceled_at = datetime.now(UTC)
          await audit.emit(session, event="online_payment_canceled", resource_type="online_payment",
                           payload=OnlinePaymentCanceledPayload(
                               audit_correlation_id=webhook_intake_corr,
                               online_payment_id=row.id,
                               yookassa_payment_id=object_id,
                               cancellation_party=details.get("party"),
                               cancellation_reason=details.get("reason"),
                           ))
          await audit.emit(session, event="yookassa_webhook_received", resource_type="yookassa_webhook",
                           payload=YookassaWebhookReceivedPayload(
                               event_type="payment.canceled",
                               object_id=object_id,
                               idempotency_outcome="processed",
                           ))
  ```

- **Alembic 0035 partial sketch (D-50-30):**
  ```python
  def upgrade():
      op.create_table(
          "fiscal_receipts",
          sa.Column("id", PgUUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
          sa.Column("payment_id", PgUUID(as_uuid=True), nullable=False),
          sa.Column("kind", sa.Text(), nullable=False),
          sa.Column("status", sa.Text(), nullable=False),
          sa.Column("yookassa_receipt_id", sa.Text(), nullable=True),
          sa.Column("customer_email", sa.Text(), nullable=False),
          sa.Column("failure_reason", sa.Text(), nullable=True),
          sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
          sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
          sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
          sa.Column("audit_correlation_id", PgUUID(as_uuid=True), nullable=True),
          sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
          sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
          sa.PrimaryKeyConstraint("id", name=op.f("pk_fiscal_receipts")),
          sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], name=op.f("fk_fiscal_receipts_payment_id_payments"), ondelete="RESTRICT"),
          sa.CheckConstraint("kind IN ('payment', 'refund')", name=op.f("ck_fiscal_receipts_kind")),
          sa.CheckConstraint("status IN ('pending', 'sent', 'succeeded', 'failed')", name=op.f("ck_fiscal_receipts_status")),
          sa.UniqueConstraint("payment_id", "kind", name=op.f("uq_fiscal_receipts_payment_id_kind")),
      )
  ```

- **AST gate test sketch (D-50-14, D-50-33):**
  ```python
  def test_payment_succeeded_handler_calls_get_payment_before_any_db_write():
      tree = ast.parse(Path("app/api/v1/_internal/yookassa/handlers.py").read_text())
      # Find handle_payment_succeeded
      fn = next(n for n in ast.walk(tree)
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "handle_payment_succeeded")
      # Walk body in order; assert any await get_payment appears before any session.execute|add|flush|commit
      get_payment_line = None
      first_db_write_line = None
      for node in ast.walk(fn):
          if isinstance(node, ast.Await) and "get_payment" in ast.unparse(node):
              get_payment_line = get_payment_line or node.lineno
          if isinstance(node, ast.Call) and any(
              ast.unparse(node).startswith(x) for x in ("session.execute", "session.add", "session.flush", "session.commit")
          ):
              first_db_write_line = first_db_write_line or node.lineno
      assert get_payment_line < first_db_write_line, "WH-02: re-fetch must precede DB write"
  ```

- **Custom exception for D-50-16:**
  ```python
  # in app/core/exceptions.py
  class IllegalTransitionError(AppError):
      """FSM transition guard rejection."""
      pass
  ```
  Mirror precedent: existing exception subclass naming pattern from Phase 8/16.

- **`OnlinePayment.client.email` JOIN consideration:** the D-50-18 step 5 references `row.client.email`. If `OnlinePayment.client` is a lazy-loaded relationship, accessing `.email` triggers a separate SELECT. Two options:
  - (a) Use `selectinload(OnlinePayment.client)` on the SELECT-FOR-UPDATE statement.
  - (b) Issue a separate `await session.scalar(select(Client.email).where(Client.id == row.client_id))` — mirrors D-49-13 narrow read pattern.
  Prefer (a) for clarity; (b) if the relationship isn't already defined on the ORM. Planner verifies.

</specifics>

<deferred>
## Deferred Ideas

- **`payment.waiting_for_capture` handling** — Phase 50 currently no-ops with structlog INFO; PITFALLS line 311 mentions it as a subscribed event. Phase 53 deployment runbook documents the subscription set; if production sees the event, Phase 53 may add a dedicated handler.
- **`refund.succeeded` handler** — Phase 51 REFUND-01..04. Phase 50 falls through to unknown-event no-op.
- **`receipt.succeeded` / `receipt.canceled` handlers** — Phase 51 FISCAL-04. Phase 50 inserts `fiscal_receipts(status='sent')` directly; Phase 51 ARQ dispatch flips status.
- **ARQ `dispatch_fiscal_receipt` task** — Phase 51 FISCAL-05. Phase 50's `fiscal_receipts(status='sent')` direct INSERT is the simpler v1.7 baseline.
- **Circuit breaker** for fiscal-receipt dispatch — Phase 51 FISCAL-05.
- **Cron `monitor_stale_fiscal_receipts`** — Phase 51 FISCAL-06.
- **Post-commit notification enqueue** — `_post_commit_enqueue` is a no-op stub in Phase 50 (D-50-19); Phase 52 NOT-04/05 fills the body with ARQ task enqueues.
- **Operator runbook for cancellation_reason / cancellation_party enum values** — Phase 53.
- **`yookassa_call_failed` audit event** — deferred from Phase 49 D-49-20. Phase 50 may add it now (re-fetch failures D-50-11 / D-50-12 are natural emission sites); deferred again to Phase 51 cleanup to keep Phase 50 scope tight unless verification flags it as a gap.
- **`tests/integration/test_alembic_clean.py::test_alembic_check_clean`** — pre-existing failure on master since before Phase 49. Phase 50 inherits; Phase 53 cleanup or final-verifier pass.
- **Orphan recovery cron** (D-50-18 step where `row is None` path returns 200 with WARNING) — Phase 53 `reconcile_orphan_yookassa_payments` ARQ cron (D-49-11 marker).

### Reviewed Todos (not folded)
*No todos matched Phase 50 in `gsd-sdk query todo.match-phase 50` (`todo_count: 0`) — section omitted.*

</deferred>

---

*Phase: 50-Webhook-FSM-Fiscal-Foundation*
*Context gathered: 2026-05-22*
*Mode: --auto (recommended defaults applied; deviations from prior phases documented inline)*
