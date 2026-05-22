# Phase 49: Online Sales Orchestrator - Context

**Gathered:** 2026-05-22
**Status:** Ready for planning
**Mode:** `--auto` (recommended defaults applied; decisions logged inline)

<domain>
## Phase Boundary

Ship the **`app.modules.online_payments`** domain module — the first consumer of the Phase 48 ЮKassa adapter. Concretely:

- Alembic 0034 creates the `online_payments` table (FSM row, double-tap guard, deterministic idempotency key).
- Service layer composes `clients.email` gate + receipt-item assembly + `YooKassaClient.create_payment(...)` + DB insert + audit emit.
- Router exposes four sell endpoints (memberships + pt-packages × redirect + QR) and one `GET /online-payments/return` anti-oracle pending screen.
- Composition-root wiring switches the Phase 47 stub for `MembershipActivator` + `PtPackageActivator` to **real, but inert** implementations whose `__call__` is exercised only by Phase 50 webhook tests (parity-test asserts both slots non-None at startup).
- Import-linter `modules =` line is appended with `app.modules.online_payments` (Phase 47 INFRA-40 Option A deferral).

Requirements covered: **PAY-01..PAY-08** (8 reqs). 6 success criteria locked by ROADMAP.md.

**Out of phase (explicit):**
- Webhook handler, FSM transition logic, fiscal-receipt DB row, ledger `record_payment(method='online')` — Phase 50.
- Refund endpoint, ARQ retry, circuit breaker, fiscal receipt FSM — Phase 51.
- Telegram + email DMs, `email_templates.py` body, NOT-01/02 wiring — Phase 52.

Phase 47 / Phase 48 carry forward:
- `YOOKASSA_TRUSTED_IPS`, `verify_yookassa_ip` (body live), `YooKassaSettings`, `_money.py` converters, 9 v1.7 audit events in `LOCKED_AUDIT_EVENTS`, all 9 v1.7 Pydantic payloads in `audit_payloads.py`, four Protocol slots in `app/core/dependencies.py`.
- Phase 48 shipped `YooKassaClient.create_payment(...)` + typed `YooKassaPaymentResult` with closed `Literal` classification (`'ok' | 'validation_error' | 'transient_error' | 'permanent_error'`) and 6 respx test fixtures.
- `YooKassaClientProvider` slot is **already wired to the real client** (Phase 48 plan 48-07). Phase 49 consumes via `Depends(get_yookassa_client_provider)`.

</domain>

<decisions>
## Implementation Decisions

### Module layout — mirror v1.4 `payments/` sibling

- **D-49-01:** `app/modules/online_payments/` ships with the canonical v1.5+ module skeleton — file-for-file mirror of `app/modules/memberships/` minus the templates body:
  ```
  app/modules/online_payments/
  ├── __init__.py
  ├── constants.py        # status literals, error codes, header names
  ├── models.py           # OnlinePayment ORM (Phase 49)
  ├── repository.py       # insert + by-id + idempotency-key lookup
  ├── schemas.py          # SellRequest / SellResponse / ReturnScreenResponse
  ├── service.py          # orchestrator — calls YooKassaClient + DB insert + audit
  ├── router.py           # 5 routes (sell × 4 + return × 1)
  ├── permissions.py      # local can-checks if needed (none expected — PAY uses MEMBERSHIPS / PT_PACKAGES)
  └── email_templates.py  # empty placeholder file with module docstring; Phase 52 fills body
  ```
  - `notifications.py` is NOT shipped in Phase 49 — Phase 52 owns Telegram + email DM wiring. The empty `email_templates.py` file is created **now** so the Phase 47 `app.integrations.email.dispatcher → app.modules.online_payments.email_templates` import-linter ignore stops being "unmatched" (kills the `warn`). The file contains only a module docstring stating Phase 52 ownership.
  - `permissions.py` is created empty (module docstring only) — PAY endpoints reuse `Resource.MEMBERSHIPS` / `Resource.PT_PACKAGES` permission checks (see D-49-09).
- **D-49-02:** **`app.modules.online_payments` is appended to `[importlinter:contract:modules-independent] modules =` in commit 1 of Phase 49** (per Phase 47 INFRA-40 Option A deferral). This MUST happen in the same commit that creates `app/modules/online_payments/__init__.py` so import-linter resolves the package on its first run. After this commit:
  - 3 preemptive `ignore_imports` edges (D-49-29..31) become matched.
  - `unmatched_ignore_imports_alerting = warn` stays at `warn` (Phase 52 `online_payments.email_templates` body still unmatched until Phase 52 ships templates).
- **D-49-03:** Service-layer crosses **are exactly the two Phase 47 preemptively-ignored edges**: `online_payments.service → app.modules.payments.models` (PaymentReceipt-row return type — but **only used by Phase 50** wiring; Phase 49 imports the type defensively so the ignore is matched) and `online_payments.service → app.modules.users.display` (operator display name in audit context). No other cross-module imports are added in Phase 49.

### `online_payments` ORM + Alembic 0034 (PAY-01, PAY-02)

- **D-49-04:** `OnlinePayment` ORM model fields — match REQUIREMENTS.md PAY-01 literally:
  ```
  id                      UUID PK (UUIDv4, app-side default)
  client_id               UUID FK clients.id ON DELETE RESTRICT
  membership_plan_id      UUID FK membership_plans.id ON DELETE RESTRICT, NULL
  pt_package_plan_id      UUID FK pt_packages_plans.id ON DELETE RESTRICT, NULL
  yookassa_payment_id     TEXT NOT NULL
  idempotency_key         TEXT NOT NULL
  amount_kopecks          INTEGER NOT NULL CHECK (amount_kopecks > 0)
  status                  TEXT NOT NULL CHECK (status IN ('pending','succeeded','canceled'))
  confirmation_url        TEXT NULL                  -- NULL for QR confirmation flow
  confirmation_type       TEXT NOT NULL CHECK (confirmation_type IN ('redirect','qr'))
  initiated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
  succeeded_at            TIMESTAMPTZ NULL           -- written by Phase 50 webhook
  canceled_at             TIMESTAMPTZ NULL           -- written by Phase 50 webhook
  created_by_user_id      UUID FK users.id ON DELETE SET NULL, NULL
  audit_correlation_id    UUID NOT NULL              -- chain ROOT — see D-49-19
  ```
  - `audit_correlation_id` is a **new column** not explicitly listed in PAY-01 but required by D-49-19 (chain-root for downstream FSM events). Audit payload schema already names it as `audit_correlation_id` chain root (`OnlinePaymentInitiatedPayload.audit_correlation_id: UUID | None` — caller passes `None`; the column stores the row's own UUID as the chain root for Phase 50 consumers).
  - XOR FK guard via DB CHECK: `CHECK ((membership_plan_id IS NOT NULL) <> (pt_package_plan_id IS NOT NULL))` — exactly one populated.
  - `qr_payload` is NOT a separate column. For QR sales the **service computes the QR payload on-the-fly from the ЮKassa `confirmation.confirmation_data` field** and returns it in the response; the row stores `confirmation_url = NULL` and `confirmation_type = 'qr'`. Rationale: QR payloads are short-lived (tied to the pending payment) and stale data is worse than re-computing. Phase 50 webhook never needs the QR payload.
- **D-49-05:** Alembic 0034 ships **three UNIQUE / partial-UNIQUE indexes** in a single migration (atomic per success-criterion #5):
  1. `uq_online_payments_yookassa_payment_id` — `UNIQUE (yookassa_payment_id)` — full btree.
  2. `uq_online_payments_idempotency_key` — `UNIQUE (idempotency_key)` — full btree.
  3. `uq_online_payments_membership_double_tap` — `UNIQUE (client_id, membership_plan_id, DATE(initiated_at)) WHERE status != 'canceled' AND membership_plan_id IS NOT NULL`.
  4. `uq_online_payments_pt_package_double_tap` — `UNIQUE (client_id, pt_package_plan_id, DATE(initiated_at)) WHERE status != 'canceled' AND pt_package_plan_id IS NOT NULL`.
  - **Two partial unique indexes**, one per subject kind — mirror Phase 16/30 pattern where each plan type gets its own constraint instead of one polymorphic index. Predicate `WHERE status != 'canceled'` allows retry after explicit cancellation (PITFALLS Pitfall 3 wording).
  - `DATE(initiated_at)` is **immutable in PostgreSQL** (`DATE` cast of `TIMESTAMPTZ` honours `TIMEZONE` GUC); `alembic/env.py:_include_object` does NOT need to suppress these — they are full literals from `op.create_index`. If autogenerate misclassifies the partial predicate, suppress in env.py per the Phase 4/16 precedent (Wave 1 plan to verify and document either way).
- **D-49-06:** Migration 0034 file naming: `0034_online_payments.py`; `down_revision = "0033_clients_email_partial_unique"`. Downgrade is lossless reverse — `drop_index × 4` then `drop_table`.
- **D-49-07:** Repository methods (single file `repository.py`):
  - `insert_online_payment(session, *, fields) -> OnlinePayment` — pure INSERT, no SELECT-then-INSERT (CHECK constraint enforces XOR; DB raises `IntegrityError` on double-tap).
  - `get_online_payment_by_id(session, id) -> OnlinePayment | None`
  - `get_online_payment_by_idempotency_key(session, key) -> OnlinePayment | None` — used by D-49-08 retry path.
  - No update methods in Phase 49 (`status` transitions are Phase 50 territory).

### Idempotency-Key strategy (PAY-03 / PAY-04)

- **D-49-08:** **Deterministic key** — `idempotency_key = sha256(f"sell-{subject_kind}:{plan_id}:{client_id}:{today_iso}").hexdigest()` (256 hex chars) computed in the service layer **before** any DB or ЮKassa call. Stored verbatim in `online_payments.idempotency_key` (UNIQUE). Sent verbatim in `Idempotence-Key` header to ЮKassa.
  - Rationale: PAY-03 spec text locks the formula `sha256(f"sell-membership:{plan_id}:{client_id}:{today_iso}")`. The deterministic form means:
    - A double-click within the same UTC day → same key → ЮKassa returns the previously-created payment object verbatim (per ЮKassa Idempotence-Key spec). Service re-fetches by `idempotency_key` and returns the existing `online_payments` row (200, not 201; same `{ confirmation_url, online_payment_id }` payload).
    - A retry after server crash mid-flow → same key → guaranteed no double payment.
  - `today_iso` = `datetime.now(tz=UTC).date().isoformat()` (Europe/Moscow user-facing date convention from CLAUDE.md does NOT apply here — this is a wire-protocol key, not a user-facing date; UTC keeps the key stable across DST transitions).
  - Subject discriminator written as `membership` / `pt_package` (matches `OnlinePaymentInitiatedPayload.subject_kind` Literal).
- **D-49-09:** **Service-layer dedup precedence** when service computes a key that already exists in the table:
  1. Service computes key.
  2. Service does `repository.get_online_payment_by_idempotency_key(key)` — if hit and row's `subject_id` matches the requested `plan_id` and `status != 'canceled'`, return the existing row as 200 (replay).
  3. Otherwise insert the new row, then call ЮKassa. If ЮKassa returns `validation_error` (classification), the inserted row stays as `status='pending'` with `yookassa_payment_id=''` (placeholder column-NOT-NULL deferred-fill — see D-49-10) and the service returns 422 to the operator. **CORRECTION:** simpler shape — see D-49-10.
- **D-49-10:** **Insert AFTER ЮKassa success, not before.** Order of operations in `service.sell_membership(...)`:
  1. Validate `clients.email IS NOT NULL` (D-49-12).
  2. Compute deterministic `idempotency_key` (D-49-08).
  3. Replay check: `get_online_payment_by_idempotency_key(key)` → if hit, return existing row.
  4. Build receipt items via `app.integrations.yookassa.receipt.build_receipt_item(...)`.
  5. Call `YooKassaClient.create_payment(amount_kopecks, idempotency_key=key, receipt={...}, return_url=..., confirmation_type=...)`.
  6. **Switch on `result.classification`:**
     - `'ok'` → INSERT `online_payments` row with `yookassa_payment_id = result.payment_id`, `confirmation_url = result.confirmation_url` (or `None` if QR), `status = 'pending'`, `audit_correlation_id = new_uuid()`. Emit `online_payment_initiated` audit (chain root, `audit_correlation_id=None`) THEN `yookassa_payment_created` (chain child, `audit_correlation_id=row.audit_correlation_id`). Return 201 with `{ confirmation_url, online_payment_id }`.
     - `'validation_error'` → raise `ValidationAppError(code='yookassa_validation_error', message=result.error_code or 'yookassa_rejected_payment')`. **No DB row written.** The operator can fix input and retry (key changes only if `today_iso` rolls over).
     - `'transient_error'` → raise `ServiceUnavailableAppError(code='yookassa_unavailable')` → 503. **No DB row written.** Operator retries; ЮKassa Idempotence-Key dedupes server-side.
     - `'permanent_error'` → raise `BadGatewayAppError(code='yookassa_permanent_error')` → 502. **No DB row written.** Operator escalates.
  - Rationale: storing a half-baked row before the ЮKassa call confuses Phase 50 webhook FSM and leaves dangling rows under transient failure. Phase 48 result-classification semantics (D-48-10) make "ЮKassa-first, DB-second" safe — `httpx.AsyncClient` cannot leak exceptions past the integration boundary, and the deterministic key dedupes server-side. The replay check in step 3 catches the rare case where step 6 succeeded but the DB INSERT failed mid-commit (next operator click finds the ЮKassa payment via its idempotency key — see D-49-11).
- **D-49-11:** **Recovery path for "ЮKassa created, DB failed" rare case:** the replay check in D-49-10 step 3 catches the *next* operator click within the same day. For a true belt-and-suspenders we add an ARQ cron in Phase 53 (`reconcile_orphan_yookassa_payments`) that walks ЮKassa's payment list and creates missing `online_payments` rows. **Phase 49 ships nothing for this** — documented as `# TODO Phase 53:` in `service.py` and added to `deferred-items.md`.

### FIS-05 client email gate (PAY-06)

- **D-49-12:** Gate is checked **in the service layer**, NOT the router. The router calls `service.sell_membership(...)`; the service does `client = await client_repo.get_by_id(client_id)` → `if client.email is None: raise ValidationAppError(code='client_email_required_for_online_payment', message='...')`. FastAPI exception handler returns 422.
  - Rationale: schema validation can't see DB state; the gate must run after `client_id` resolution. Service layer keeps the rule single-source.
  - **Error code is locked literal:** `client_email_required_for_online_payment` (REQUIREMENTS.md PAY-06 + ROADMAP.md success-criterion #3 exact spelling). Add to `app/core/exceptions.py` as a class constant on `ValidationAppError` subclass `ClientEmailRequiredForOnlinePaymentError` for callsite clarity — single canonical raise site.
- **D-49-13:** Cross-module read of `clients` table: `online_payments.service → app.modules.clients.repository` is **not in the preemptive ignore list** from Phase 47 INFRA-40, and **must not be added**. Solution: service reads `clients.email` via a **scalar SELECT** through the shared `AsyncSession` — `await session.execute(select(Client.email).where(Client.id == client_id))` — but `Client` is an `app.modules.clients.models` import which would still trigger the modules-independent contract.
  - **Resolved:** add `online_payments.service → app.modules.clients.models` to `[importlinter:contract:modules-independent] ignore_imports` in commit 1 (alongside D-49-02 module append). Narrow ignore scope — `service.py` only — mirrors Phase 45 NOTIFY-11/12/13 precedent for `memberships.service → payments.models`. Document inline: "Phase 49 PAY-06 — `clients.email` gate read; service-layer scoped; no widening to repository.".
  - Alternative considered (and rejected): introduce a `ClientEmailReader` Protocol slot in `app.core.dependencies`. **Rejected** — over-engineering for a read-only single-field gate; Protocol slots are reserved for cross-process / cross-transaction wiring (D-47-01 lineage). The narrow ignore_imports entry is the established pattern.

### Sell endpoint surface (PAY-03, PAY-04, PAY-05)

- **D-49-14:** Four sell endpoints + one return-screen endpoint, all under `/api/v1/online-payments/*`:
  | Method | Path | Spec | Permission | CSRF |
  |---|---|---|---|---|
  | POST | `/online-payments/memberships/{plan_id}/sell` | PAY-03 redirect | `require_permission(CREATE, MEMBERSHIPS)` | yes |
  | POST | `/online-payments/memberships/{plan_id}/sell-qr` | PAY-05 QR | `require_permission(CREATE, MEMBERSHIPS)` | yes |
  | POST | `/online-payments/pt-packages/{plan_id}/sell` | PAY-04 redirect | `require_permission(CREATE, PT_PACKAGES)` | yes |
  | POST | `/online-payments/pt-packages/{plan_id}/sell-qr` | PAY-05 QR | `require_permission(CREATE, PT_PACKAGES)` | yes |
  | GET | `/online-payments/return` | PAY-07 anti-oracle | **no auth, no CSRF** (browser redirect target) | no |
  - All POST routes accept `SellRequest { client_id: UUID }` body (camelCase via `BackendSchemaBase.alias_generator` — Phase 4 convention).
  - All POST routes return 201 `ResponseEnvelope[SellResponse]` where `SellResponse = { confirmation_url: str | None, online_payment_id: UUID, qr_payload: str | None }`. Exactly one of `confirmation_url` / `qr_payload` is non-null (Pydantic root validator).
  - Both redirect and QR endpoints share the **same internal `service.sell_membership(... confirmation_type)`** — `confirmation_type` is the only branching argument.
- **D-49-15:** **Single shared webhook path** (success-criterion #2) is a Phase 50 concern — Phase 49 ships nothing under `/_internal/yookassa/webhook`. The single-path guarantee comes from D-49-14 (both sell variants use the same `online_payments` table + audit chain + Phase 50 reads one row regardless of how it was created).
- **D-49-16:** **Idempotency-Key (HTTP header) handling on the router:** every `POST /sell*` endpoint also accepts the standard FastAPI `Idempotency-Key` header (Sportzal-internal idempotency layer at `app/core/idempotency.py`). Two-layer model:
  - Outer layer (Sportzal `IDEMPOTENCY_REDIS_PREFIX`) → dedupes operator double-click at the HTTP level (5-second window). Replay returns the cached 201 response verbatim.
  - Inner layer (D-49-08 deterministic key → ЮKassa Idempotence-Key) → dedupes within-day at the ЮKassa side.
  - Both layers are belt-and-suspenders. The HTTP `Idempotency-Key` is **operator-supplied** (admin-web sends a UUID per click); the ЮKassa key is **server-derived** (D-49-08 formula).

### `return_url` anti-oracle screen (PAY-07)

- **D-49-17:** `GET /api/v1/online-payments/return` handler:
  - Accepts no query params (or accepts and IGNORES them — see below). Returns `text/html; charset=utf-8` with a **static Russian-text body**:
    ```
    <html><body>
      <h1>Оплата получена</h1>
      <p>Ожидаем подтверждение от платёжной системы. Эту страницу можно закрыть.</p>
    </body></html>
    ```
  - **No DB lookup.** No `payment_id` resolution. No `clients` query. No audit emission. The handler is a pure-static HTML responder.
  - ЮKassa **will append** `?payment_id={internal_id}` to the URL on redirect — the handler accepts the query param via `request.query_params` (untyped) and discards it. We do NOT bind it as a route param because doing so creates a path that varies by user, leaking which payment is being returned to (referrer/log oracle).
  - Response header `Cache-Control: no-store, max-age=0` to prevent browser caching of the static page (defense against "user bookmarks return URL, opens it later, screen still says success" — which we already guarantee by removing all status info, but no-store is the standard discipline).
- **D-49-18:** **Constant-time floor** on response duration:
  - `_constant_time_floor` is implemented as: `start = time.perf_counter()` at the top of the handler → `... static response build ...` → `elapsed = time.perf_counter() - start` → `await asyncio.sleep(max(0, FLOOR_SECONDS - elapsed))` → return response.
  - `FLOOR_SECONDS: Final[float] = 0.050` (50 ms) — long enough that any plausible static-build variance is masked; short enough that a real client doesn't notice.
  - The handler **does not branch** on query params, so there's no per-query timing variance to mask in Phase 49. The floor exists for **forward compatibility**: if Phase 50 or beyond ever adds per-payment lookup logic, the floor is already in place. Tests assert `min_response_time ≥ FLOOR_SECONDS - 5ms` (allow scheduler jitter).
  - PITFALLS Pitfall 4 (line 112+) explicitly calls out the timing oracle; this implementation is the recommended mitigation.

### Audit emission chain (PAY-03, PAY-08)

- **D-49-19:** **Two events per successful sell**, emitted **synchronously in the service** before the request returns 201:
  1. `("online_payment_initiated", "online_payment")` — chain ROOT. Caller passes `audit_correlation_id=None`. The audit row's own `id` becomes the chain UUID; service captures this and writes it to `online_payments.audit_correlation_id` (D-49-04 column). Payload: `OnlinePaymentInitiatedPayload { audit_correlation_id: None, online_payment_id, client_id, amount_kopecks, subject_kind, subject_id }`.
  2. `("yookassa_payment_created", "online_payment")` — chain CHILD. Caller passes `audit_correlation_id=row.audit_correlation_id`. Payload: `YookassaPaymentCreatedPayload { audit_correlation_id, online_payment_id, yookassa_payment_id, idempotency_key, confirmation_type }`.
  - Both payloads already exist in `app/core/audit_payloads.py` (Phase 47 INFRA-35); Phase 49 only emits, never declares.
  - Emission order matters for Phase 50 webhook handler which walks the chain by `audit_correlation_id` to correlate `online_payment_succeeded` back to the initiating click.
  - Both `audit.emit` calls live inside the **same `AsyncSession`** that holds the `online_payments` INSERT — Sportzal `caller-owns-txn` discipline. The service does NOT commit; the FastAPI dependency commits on response.
- **D-49-20:** **Failure modes that emit audits:**
  - `client_email_required_for_online_payment` → NO audit emission (validation error, no business event happened).
  - ЮKassa `validation_error` / `transient_error` / `permanent_error` → NO audit emission in Phase 49 (the row was not written; no `online_payment_initiated` to chain from). Phase 50 may add a `yookassa_call_failed` event to `LOCKED_AUDIT_EVENTS` if operational visibility demands it — DEFERRED.
  - Note: this means a transient ЮKassa outage produces **no audit trace** in Phase 49. Operator-facing visibility comes from `structlog` (the Phase 48 client logs structured warnings). Acceptable for v1.7 first cut.

### Composition root wiring (PAY-08)

- **D-49-21:** Phase 49 wires **two** of the four Phase 47 Protocol slots from no-op stubs to real implementations:
  - `register_membership_activator(impl=...)` — implementation lives in `app/modules/memberships/service.py` as `async def activate_membership_from_webhook(session, *, membership_id, audit_correlation_id) -> Membership`. **Phase 49 ships the wiring + the function signature + a stub body that raises `NotImplementedError("Phase 50 wires activation logic")`.** The slot is **non-None** (success-criterion #6 satisfied) but the implementation is inert — Phase 50 fills the body.
  - `register_pt_package_activator(impl=...)` — analogous mirror in `app/modules/pt_packages/service.py`.
  - Rationale: success-criterion #6 requires both slots non-None at startup. Wiring them to a stub-body satisfies the parity test; Phase 50 owns the body. The Protocol slot pattern (D-47-01) explicitly allows this two-step landing.
- **D-49-22:** **`FiscalReceiptDispatcher` slot stays no-op through Phase 49.** Phase 50 FISCAL-01 wires the real implementation. Success-criterion #6 mentions `FiscalReceiptDispatcher` AND `YooKassaClientProvider` — the test asserts those two **non-None**, NOT `FiscalReceiptDispatcher` (the latter is Phase 50). **Re-read of success-criterion #6:** "Startup integration test asserts `YooKassaClientProvider` and `FiscalReceiptDispatcher` slots are non-None (AST parity test)." → so the test DOES include `FiscalReceiptDispatcher`. Resolution:
  - **D-49-22 (corrected):** Phase 49 also wires `FiscalReceiptDispatcher` to a **stub callable** (`async def _fiscal_receipt_dispatcher_stub(...): raise NotImplementedError("Phase 50 wires real dispatch")`) so the parity test passes in Phase 49. Phase 50 replaces the stub with the real ARQ-enqueue body. The stub is registered from `app/main.py:create_app()` AND `app/workers/__init__.py:WorkerSettings.on_startup` (REG-29-03 double-wire). Document inline that the stub is a **Phase-49-only bridge** and gets replaced verbatim in Phase 50.
  - All four v1.7 Protocol slots therefore become non-None by end of Phase 49: `YooKassaClientProvider` (Phase 48 real), `MembershipActivator` (Phase 49 stub body), `PtPackageActivator` (Phase 49 stub body), `FiscalReceiptDispatcher` (Phase 49 stub callable).
- **D-49-23:** Parity test file: `apps/backend/tests/integration/test_v17_protocol_slot_parity.py` — runs after `create_app()` + ARQ `WorkerSettings.on_startup`, asserts all four `get_*` accessors return non-None objects without raising. Mirrors the v1.6 `PaymentRecorder` / `EmailDispatcher` parity tests.

### Permission mapping (PAY endpoints)

- **D-49-24:** No new `OWNER_ONLY` entries. PAY endpoints **reuse** the existing `(CREATE, MEMBERSHIPS)` and `(CREATE, PT_PACKAGES)` pairs — both are reception+owner (NOT in OWNER_ONLY per Phase 15 INFRA-08 / Phase 30 INFRA-18). Online sales follow the same role model as in-person sales — no separate "online sale" resource needed.
- **D-49-25:** `RBAC-04 ordering`: every POST route declares `Depends(require_permission(...))` BEFORE `Depends(verify_csrf)` in the function signature (mirrors `memberships/router.py:47-52` precedent). The 401-before-403 invariant is enforced statically by `tests/integration/test_route_introspection.py` (existing test — auto-covers new routes).
- **D-49-26:** `GET /online-payments/return` has **no permission gate** and **no CSRF gate** — it is a browser-target URL hit by users who may not have a Sportzal session. The endpoint reveals no data per D-49-17, so no auth is required. Documented as an explicit `# Phase 49 PAY-07: anonymous by design — no auth, no CSRF, no DB` block comment.

### Test strategy — leverage Phase 48 respx fixtures

- **D-49-27:** Phase 49 tests **reuse** the 6 respx fixtures from `apps/backend/tests/integrations/yookassa/conftest.py` (Phase 48 ADAPTER-06). Most importantly:
  - `yookassa_create_payment_success` → covers the happy-path sell endpoints.
  - `yookassa_create_payment_422` → covers the `validation_error` raise path in D-49-10.
  - For `transient_error` (5xx, network) and `permanent_error` (non-422 4xx) coverage, **new** respx fixtures land in `apps/backend/tests/modules/online_payments/conftest.py`: `yookassa_create_payment_500` and `yookassa_create_payment_404`. These are scoped to Phase 49 (no other module needs them) — not added to Phase 48's shared conftest.
- **D-49-28:** Service-layer tests use the `caller_provides_session` pattern with an in-memory SQLite-fake? **No.** Sportzal backend tests use **real Postgres via testcontainers** (Phase 4 testing convention from CLAUDE.md). Phase 49 follows suit — every sell-flow integration test runs against a per-test Postgres schema. Repository unit tests can run against the same fixture; no SQLite divergence.
- **D-49-29..31:** Three import-linter ignore edges become matched after commit 1 (D-49-02, D-49-03):
  - 29. `app.modules.online_payments.service → app.modules.payments.models` — written but **not exercised** in Phase 49 (Phase 50 webhook handler uses it via `record_payment`). Phase 49 adds a defensive type-only import: `if TYPE_CHECKING: from app.modules.payments.models import Payment`. **This satisfies grimp** (grimp follows TYPE_CHECKING imports) and keeps the runtime clean. Document inline that Phase 50 makes the import runtime.
  - 30. `app.modules.online_payments.service → app.modules.users.display` — used in Phase 49 for `format_actor_display(created_by_user_id)` inside audit-payload assembly (operator-display in `OnlinePaymentInitiatedPayload` IF the payload schema accepts it — re-check schema). Current `OnlinePaymentInitiatedPayload` does NOT include an operator display field (no `subject_kind`-adjacent operator field). **Revised:** Phase 49 does NOT import `users.display`; the ignore stays `warn`-unmatched (Phase 50 may add operator display to `OnlinePaymentSucceededPayload`). **Add `# TODO Phase 50:` note in `service.py`.**
  - 31. `app.modules.online_payments.service → app.modules.clients.models` — NEW ignore added by D-49-13 (`clients.email` gate read). Live & matched from commit 1.

### Wave / plan shape preview for planner

- **D-49-32:** Suggested plan ordering — researcher and planner should refine:
  - **Wave 1 (sequential — bedrock):**
    - 49-01: Alembic 0034 `online_payments` table + 4 indexes (PAY-01, PAY-02) — schema only, no models import yet.
    - 49-02: `app/modules/online_payments/` skeleton + ORM model + repository + import-linter `modules =` append + ignore_imports edits (D-49-02, D-49-13, D-49-29..31). **This commit unlocks every downstream plan.**
  - **Wave 2 (parallelizable after Wave 1):**
    - 49-03: Service-layer + schemas + FIS-05 gate + idempotency-key derivation (PAY-03, PAY-04, PAY-06).
    - 49-04: Router + sell endpoints × 4 + permission mapping (PAY-03, PAY-04, PAY-05).
    - 49-05: `GET /online-payments/return` anti-oracle handler + constant-time floor + tests (PAY-07).
    - 49-06: Composition-root wiring: `MembershipActivator` + `PtPackageActivator` + `FiscalReceiptDispatcher` stubs + parity test (PAY-08).
  - **Wave 3 (sequential — depends on Wave 2):**
    - 49-07: End-to-end integration tests (happy + 4 failure modes × 2 subject kinds × 2 confirmation types) + ROADMAP success-criteria checklist.
  - **Estimated plan count: 7** (range 6–8 depending on whether 49-03 splits service from schemas).

### Claude's Discretion

Downstream agents may settle the following without re-asking:

- **Schema file shape:** `SellRequest`/`SellResponse`/`ReturnScreenResponse` follow `BackendSchemaBase` (camelCase alias generator); `SellResponse.confirmation_url` and `SellResponse.qr_payload` are `str | None` with a Pydantic root validator asserting XOR.
- **Response wrap:** all POST routes use `envelope(SellResponse(...))` per D-14.
- **Error code constants:** add `code='yookassa_validation_error'`, `'yookassa_unavailable'`, `'yookassa_permanent_error'` to a single `app/modules/online_payments/constants.py` `ErrorCode` StrEnum — single canonical source for tests and exception class constants.
- **Logging:** every sell flow emits one structlog INFO line at success (`event="online_payment_sell"`, `outcome="ok"`, `online_payment_id=...`, `subject_kind=...`, `confirmation_type=...`, `client_id=...`). Failure path emits WARNING with `outcome="yookassa_<classification>"` + `error_code`.
- **`User-Agent` header for outbound:** already set in Phase 48 client to `Sportzal/1.7 ЮKassa-Adapter`. Phase 49 does not modify.
- **`return_url` value:** comes from `YooKassaSettings.return_url` (Phase 47 shipped). Service does NOT override.
- **QR payload extraction:** `result.qr_payload` field on `YooKassaPaymentResult` (Phase 48 already returns it when `confirmation_type='qr'`). If the field is missing in Phase 48's typed result, Wave-1 must add it — Phase 49 service code reads `result.qr_payload`, not raw response JSON. **Verifier:** Wave-1 first task = read Phase 48 `apps/backend/app/integrations/yookassa/types.py` `YooKassaPaymentResult` definition; if `qr_payload` is absent, file an inline plan-fix request that extends the dataclass (the field is `str | None`, default `None`, populated when `confirmation.type == 'qr'`).
- **`OWNER_ONLY` audit:** unchanged. Run `pytest tests/unit/test_owner_only_parity.py` to confirm frontend/backend stay in sync.
- **Deferred items file:** create `deferred-items.md` at end of Wave 3 for D-49-11 reconcile cron, D-49-20 `yookassa_call_failed` audit event, D-49-30 `users.display` import (Phase 50 owns).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project / milestone scope
- `.planning/PROJECT.md` — milestone v1.7 framing, RF regional constraints (ЮKassa only, no Stripe), webhook-security correction (IP allowlist, no HMAC)
- `.planning/REQUIREMENTS.md` lines 33–41 — PAY-01..PAY-08 full text
- `.planning/REQUIREMENTS.md` lines 134–141 — PAY req → Phase 49 mapping table
- `.planning/ROADMAP.md` lines 179–190 — Phase 49 goal + 6 success criteria
- `.planning/STATE.md` — milestone v1.7 status

### Prior phase context (Phase 47 Bedrock + Phase 48 Adapter)
- `.planning/phases/47-bedrock/47-CONTEXT.md` — D-47-01..09: Protocol slot wiring approach, INFRA-40 Option A deferral rationale
- `.planning/phases/47-bedrock/47-VERIFICATION.md` — Phase 47 outcome: settings, IP frozenset, AST gates, audit events, payloads, 4 Protocol slots
- `.planning/phases/47-bedrock/47-07-SUMMARY.md` — INFRA-40 deferral mechanics (the import-linter `modules =` append that lands in Phase 49)
- `.planning/phases/47-bedrock/deferred-items.md` — pre-existing E501 + mypy drift NOT in Phase 49 scope
- `.planning/phases/48-kassa-integration-adapter/48-CONTEXT.md` — D-48-01..26: adapter shape, result classification, idempotency-key discipline, respx fixtures
- `.planning/phases/48-kassa-integration-adapter/48-VERIFICATION.md` — Phase 48 outcome: live `YooKassaClient`, 6 respx fixtures, `YooKassaClientProvider` wired
- `.planning/phases/48-kassa-integration-adapter/48-PATTERNS.md` — pattern map (email-integration mirror, ledger-row return type discipline)

### Research (v1.7 milestone)
- `.planning/research/SUMMARY.md` lines 14–104 — Phase 49 placement in milestone, ledger-isolation rule (sibling module, not extension), `record_payment(method='online')` via Protocol slot
- `.planning/research/SUMMARY.md` lines 139–161 — BLOCKER list (return-URL oracle, timing oracle) + Phase 49 row
- `.planning/research/FEATURES.md` lines 15–66 — PAY-01..05 feature catalog (server-side payment creation, embedded widget deferred, QR/SBP, Telegram WebApp deferred, mobile deep-link deferred)
- `.planning/research/FEATURES.md` lines 95–112 — `online_payments` table FSM + UNIQUE discipline
- `.planning/research/FEATURES.md` lines 397–446 — phase ordering & deferred features
- `.planning/research/STACK.md` §1 (lines 1–100) — `Idempotence-Key` header (single `t`); Basic Auth; webhook IP security
- `.planning/research/STACK.md` §2 (lines 100–170) — 54-ФЗ receipt structure (consumed via `build_receipt_item` from Phase 48)
- `.planning/research/STACK.md` §6 lines 252–261 — integration touch points (receipt-dict shape)
- `.planning/research/PITFALLS.md` Pitfall 1 — IP allowlist + re-fetch-before-write (Phase 50 owns; Phase 49 inherits)
- `.planning/research/PITFALLS.md` Pitfall 2 — idempotency dedup discipline (caller-owned key per D-49-08)
- `.planning/research/PITFALLS.md` Pitfall 3 — activation-on-redirect anti-pattern (PAY-07 mitigation)
- `.planning/research/PITFALLS.md` Pitfall 4 — `return_url` payment-status oracle (D-49-17/18 mitigation)
- `.planning/research/PITFALLS.md` line 184–190 — partial UNIQUE double-tap guard (D-49-05 mirror)
- `.planning/research/PITFALLS.md` line 374–529 — webhook activation discipline + reference table for Phase 50 hand-off
- `.planning/research/ARCHITECTURE.md` — module-boundary contract for `online_payments` sibling
- `.planning/research/PITFALLS.md` line 529 — return-URL anti-oracle decision row

### Codebase contracts to preserve
- `apps/backend/.importlinter` — lines 16–98 (modules-independent contract); Phase 49 commit 1 MUST append `app.modules.online_payments` to `modules =` (per Phase 47 INFRA-40 / D-49-02). Also add `online_payments.service → clients.models` ignore (D-49-13).
- `apps/backend/.importlinter` lines 100–128 — integrations-not-depend-on-modules; existing `email.dispatcher → online_payments.email_templates` ignore becomes matched once Phase 49 ships the placeholder `email_templates.py` (D-49-01).
- `apps/backend/app/core/dependencies.py` lines 925–1195 — four v1.7 Protocol slots (`YooKassaClientProvider`, `FiscalReceiptDispatcher`, `MembershipActivator`, `PtPackageActivator`); composition-root setter + defensive-raise accessor pattern
- `apps/backend/app/core/audit.py` `LOCKED_AUDIT_EVENTS` — Phase 49 emits `("online_payment_initiated", "online_payment")` + `("yookassa_payment_created", "online_payment")` (lines 327–328); existing frozenset, no extension
- `apps/backend/app/core/audit_payloads.py` `OnlinePaymentInitiatedPayload` (line 738) + `YookassaPaymentCreatedPayload` (line 760) — already shipped Phase 47; Phase 49 only emits
- `apps/backend/app/core/permissions.py` — `Resource.MEMBERSHIPS`, `Resource.PT_PACKAGES`, `Action.CREATE`; OWNER_ONLY untouched (D-49-24)
- `apps/backend/app/core/exceptions.py` — `ValidationAppError` (line 48); Phase 49 adds `ClientEmailRequiredForOnlinePaymentError` subclass with locked code constant (D-49-12)
- `apps/backend/app/core/idempotency.py` — `IDEMPOTENCY_REDIS_PREFIX` + middleware; reused for outer HTTP Idempotency-Key layer (D-49-16)
- `apps/backend/app/core/schemas.py` — `BackendSchemaBase` + `envelope()` + `ResponseEnvelope` (Phase 4)
- `apps/backend/app/integrations/yookassa/client.py` — `YooKassaClient.create_payment(...)` Phase 48 entry point
- `apps/backend/app/integrations/yookassa/types.py` — `YooKassaPaymentResult` classified result (D-48-04); verify `qr_payload` field exists (Claude's discretion item)
- `apps/backend/app/integrations/yookassa/receipt.py` — `build_receipt_item(...)` + `PaymentSubject`/`PaymentMode`/`VatCode` enums (Phase 48 D-48-16/17)
- `apps/backend/app/integrations/yookassa/settings.py` — `YooKassaSettings.return_url` consumed by service
- `apps/backend/app/modules/memberships/router.py` — RBAC-04 ordering precedent (lines 47–52); router skeleton for D-49-14 mirror
- `apps/backend/app/modules/memberships/service.py` — `register_membership_activator` host module (D-49-21)
- `apps/backend/app/modules/pt_packages/service.py` — `register_pt_package_activator` host module (D-49-21)
- `apps/backend/app/modules/payments/models.py` — `Payment` ORM (TYPE_CHECKING import only in Phase 49 per D-49-29)
- `apps/backend/app/main.py` `create_app()` — composition-root edits for D-49-21/22
- `apps/backend/app/workers/__init__.py` `WorkerSettings.on_startup` — REG-29-03 double-wire mirror
- `apps/backend/tests/integrations/yookassa/conftest.py` — 6 respx fixtures (Phase 48 ADAPTER-06); reused by Phase 49 (D-49-27)
- `apps/backend/tests/integration/test_route_introspection.py` — RBAC-04 + CSRF ordering invariant test (D-49-25)
- `apps/backend/tests/integration/test_v17_protocol_slot_parity.py` — NEW Phase 49 test file (D-49-23)
- `apps/backend/alembic/versions/0033_clients_email_partial_unique.py` — most-recent migration; `down_revision = "0033_..."` for 0034 (D-49-06)

### External specs (ЮKassa / 54-ФЗ)
- https://yookassa.ru/developers/payment-acceptance/getting-started/payment-process — payment FSM, redirect flow, return-URL semantics
- https://yookassa.ru/developers/using-api/interaction-format — `Idempotence-Key` header (one `t`), Basic Auth, base URL
- https://yookassa.ru/developers/api?codeLang=python#create_payment — `POST /v3/payments` request schema incl. `confirmation.type='redirect'|'qr'`
- https://yookassa.ru/developers/payment-acceptance/scenario-extensions/widget — embedded widget (DEFERRED v1.9+)
- https://yookassa.ru/developers/payment-acceptance/receipts/54fz/yoomoney/parameters-values — receipt enums consumed via Phase 48 `build_receipt_item`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`app/integrations/yookassa/client.py`** (Phase 48) — `YooKassaClient.create_payment(idempotency_key, receipt, amount_kopecks, return_url, confirmation_type) → YooKassaPaymentResult`. Phase 49 service calls it once per sell.
- **`app/integrations/yookassa/receipt.py:build_receipt_item`** (Phase 48) — returns the receipt dict shape ЮKassa expects; Phase 49 assembles `receipt={items: [build_receipt_item(...)], customer: {email: clients.email}, tax_system_code: settings.tax_system_code}`.
- **`app/core/audit_payloads.py:OnlinePaymentInitiatedPayload` + `YookassaPaymentCreatedPayload`** (Phase 47) — Pydantic v2 payloads; Phase 49 emits both per D-49-19.
- **`app/modules/memberships/service.py` activation patterns** — `_activate_membership` helper called from `sell_membership`. Phase 49 wires `register_membership_activator` to a new `activate_membership_from_webhook` async function that reuses the activation primitives but defers body to Phase 50.
- **`app/modules/memberships/router.py` lines 47–80** — full RBAC-04 ordering + CSRF + envelope pattern; direct template for `online_payments/router.py`.
- **`app/core/idempotency.py`** — `idempotency_middleware` + `IDEMPOTENCY_REDIS_PREFIX`; outer HTTP-layer dedupe for D-49-16.
- **`apps/backend/tests/integrations/yookassa/conftest.py`** 6 respx fixtures (Phase 48 ADAPTER-06) — direct reuse; one new fixture file scoped to Phase 49 for 500/404 paths.
- **`apps/backend/alembic/versions/0033_clients_email_partial_unique.py`** — partial-UNIQUE precedent for D-49-05 (`WHERE` clause + index naming convention).
- **`app/core/schemas.py:envelope, ResponseEnvelope, BackendSchemaBase`** — wire format primitives.
- **`app/core/exceptions.py:ValidationAppError`** — base for `ClientEmailRequiredForOnlinePaymentError` (D-49-12).

### Established Patterns
- **Sibling-module ledger isolation** (SUMMARY.md line 102): `online_payments` is NOT an extension of `payments`; it owns its own FSM and table. v1.4 ledger discipline preserved.
- **Caller-owns-txn** (Phase 4): service does not commit; FastAPI dependency commits on response. Phase 49 audit emits + INSERT all share the same `AsyncSession`.
- **Result classification at the integration boundary** (D-48-10 lineage): every adapter result is a `*Result(classification=...)`; service switches on the closed Literal — no exception catch.
- **Protocol slot at composition root** (D-47-01): four v1.7 slots; Phase 49 wires `MembershipActivator` + `PtPackageActivator` + `FiscalReceiptDispatcher` (stub bodies) so success-criterion #6 parity test passes.
- **Deterministic idempotency key** (Pitfall 2): `sha256("sell-{kind}:{plan_id}:{client_id}:{today_iso}")` — locked by REQUIREMENTS.md PAY-03 wording.
- **Anti-oracle return URL** (PITFALLS Pitfall 3 + 4): static HTML, no query-param branching, constant-time floor.
- **RBAC-04 ordering** (clients/router.py + memberships/router.py): `require_permission` BEFORE `verify_csrf` in signature. Statically enforced by `test_route_introspection.py`.
- **Locked-constant AST gates** (Phase 48 D-48-18): if Phase 49 introduces new locked literals (`confirmation_type`, status enum members), extend `test_locked_yookassa_constants_ast.py` — currently `confirmation_type` is checked only inside the integration layer (Phase 48). Phase 49 service-side callsite may need a new gate; planner to decide.
- **Narrow `ignore_imports` precedent** (Phase 45 NOTIFY-11/12/13): cross-module imports allowed only at `service.py` granularity; never widened.

### Integration Points
- `apps/backend/.importlinter` — append `app.modules.online_payments` to `modules =`; add `online_payments.service → clients.models` ignore (D-49-13).
- `app/modules/online_payments/__init__.py` — module marker; commit 1.
- `app/modules/online_payments/models.py` (new) — `OnlinePayment` ORM; consumed by `repository.py` + `tests/integration/...`.
- `app/modules/online_payments/repository.py` (new) — three methods (D-49-07); consumed by service.
- `app/modules/online_payments/service.py` (new) — orchestrator; consumes `clients.models` (gate), `yookassa.client`, `yookassa.receipt`, `audit_payloads`. NOT imported by router directly — router calls `service.sell_*` functions.
- `app/modules/online_payments/schemas.py` (new) — `SellRequest`/`SellResponse`/`ReturnScreenResponse`; `BackendSchemaBase` subclass.
- `app/modules/online_payments/router.py` (new) — 5 routes; mounted in `app/api/v1/router.py`.
- `app/modules/online_payments/email_templates.py` (new) — empty placeholder (docstring only); Phase 52 fills body; matches Phase 47 import-linter `dispatcher → online_payments.email_templates` ignore.
- `app/modules/online_payments/permissions.py` (new) — empty placeholder (docstring only); no local can-checks in Phase 49 (D-49-24).
- `app/modules/online_payments/constants.py` (new) — `ErrorCode` StrEnum + literal constants (status, confirmation_type).
- `app/api/v1/router.py` — mount `online_payments_router` at `/online-payments` prefix.
- `apps/backend/alembic/versions/0034_online_payments.py` (new) — table + 4 indexes (D-49-05). `down_revision = "0033_clients_email_partial_unique"`.
- `app/modules/memberships/service.py` — add `async def activate_membership_from_webhook(session, *, membership_id, audit_correlation_id) -> Membership` with `NotImplementedError("Phase 50 wires activation logic")` body; register via `register_membership_activator(activate_membership_from_webhook)`.
- `app/modules/pt_packages/service.py` — mirror for PT-packages.
- `app/main.py` `create_app()` — three `register_*` calls (D-49-21, D-49-22).
- `app/workers/__init__.py` `WorkerSettings.on_startup` — mirror `register_*` calls for ARQ (REG-29-03 double-wire). `MembershipActivator` + `PtPackageActivator` are HTTP-only single-wire (per Phase 47 `MembershipActivator` docstring) — ONLY `register_fiscal_receipt_dispatcher` is double-wired in Phase 49.
- `apps/backend/tests/modules/online_payments/conftest.py` (new) — Phase-49-scoped respx fixtures (500/404 paths).
- `apps/backend/tests/modules/online_payments/test_service_sell_membership.py` (new) — service-layer integration tests.
- `apps/backend/tests/modules/online_payments/test_router_sell_endpoints.py` (new) — HTTP-level tests (ASGITransport).
- `apps/backend/tests/modules/online_payments/test_return_screen.py` (new) — PAY-07 anti-oracle + constant-time floor.
- `apps/backend/tests/integration/test_v17_protocol_slot_parity.py` (new) — success-criterion #6 parity test.
- `apps/backend/tests/integration/test_alembic_0034_online_payments.py` (new) — schema-shape + constraint-shape assertion.

</code_context>

<specifics>
## Specific Ideas

- **`SellResponse` Pydantic XOR validator (D-49-14):**
  ```python
  class SellResponse(BackendSchemaBase):
      confirmation_url: str | None
      qr_payload: str | None
      online_payment_id: UUID

      @model_validator(mode="after")
      def _exactly_one(self) -> "SellResponse":
          if (self.confirmation_url is None) == (self.qr_payload is None):
              raise ValueError("exactly one of confirmation_url / qr_payload must be set")
          return self
  ```

- **`return` handler skeleton (D-49-17 + D-49-18):**
  ```python
  _RETURN_HTML: Final[str] = (
      "<!doctype html><html lang=\"ru\"><head>"
      "<meta charset=\"utf-8\"><title>Оплата</title>"
      "</head><body>"
      "<h1>Оплата получена</h1>"
      "<p>Ожидаем подтверждение от платёжной системы. "
      "Эту страницу можно закрыть.</p>"
      "</body></html>"
  )
  _RETURN_FLOOR_SECONDS: Final[float] = 0.050

  @router.get("/return", include_in_schema=False)
  async def online_payment_return() -> Response:
      start = time.perf_counter()
      response = Response(
          content=_RETURN_HTML,
          media_type="text/html; charset=utf-8",
          headers={"Cache-Control": "no-store, max-age=0"},
      )
      elapsed = time.perf_counter() - start
      await asyncio.sleep(max(0.0, _RETURN_FLOOR_SECONDS - elapsed))
      return response
  ```

- **Deterministic idempotency-key formula (D-49-08):**
  ```python
  from datetime import UTC, datetime
  from hashlib import sha256

  today_iso = datetime.now(tz=UTC).date().isoformat()
  raw = f"sell-{subject_kind}:{plan_id}:{client_id}:{today_iso}"
  idempotency_key = sha256(raw.encode("utf-8")).hexdigest()
  ```

- **Order-of-operations in `service.sell_membership` (D-49-10):** validate email → compute key → replay-check → build receipt → `YooKassaClient.create_payment` → switch on classification → INSERT row (only on ok) → emit `online_payment_initiated` (chain root) → emit `yookassa_payment_created` (chain child) → return `SellResponse`.

- **Partial-UNIQUE migration shape (D-49-05):**
  ```python
  op.create_index(
      "uq_online_payments_membership_double_tap",
      "online_payments",
      ["client_id", "membership_plan_id", sa.text("DATE(initiated_at)")],
      unique=True,
      postgresql_where=sa.text(
          "status != 'canceled' AND membership_plan_id IS NOT NULL"
      ),
  )
  ```

- **Composition-root wiring snippet (D-49-21 / D-49-22):**
  ```python
  # app/main.py create_app():
  from app.modules.memberships.service import activate_membership_from_webhook
  from app.modules.pt_packages.service import activate_pt_package_from_webhook
  from app.modules.online_payments.service import phase49_fiscal_dispatcher_stub
  register_membership_activator(activate_membership_from_webhook)
  register_pt_package_activator(activate_pt_package_from_webhook)
  register_fiscal_receipt_dispatcher(phase49_fiscal_dispatcher_stub)
  ```

- **Audit chain construction (D-49-19):**
  ```python
  # 1. INSERT row first, capturing the row's audit_correlation_id
  row = await repo.insert_online_payment(
      session,
      audit_correlation_id=uuid4(),  # chain ROOT — stored on the row
      ... other fields ...
  )
  # 2. Emit initiated (chain root — audit_correlation_id=None per payload semantics)
  await audit.emit(
      session,
      event="online_payment_initiated",
      resource_type="online_payment",
      payload=OnlinePaymentInitiatedPayload(
          audit_correlation_id=None,
          online_payment_id=row.id,
          client_id=row.client_id,
          amount_kopecks=row.amount_kopecks,
          subject_kind=subject_kind,
          subject_id=row.membership_plan_id or row.pt_package_plan_id,
      ),
  )
  # 3. Emit yookassa_payment_created (chain child)
  await audit.emit(
      session,
      event="yookassa_payment_created",
      resource_type="online_payment",
      payload=YookassaPaymentCreatedPayload(
          audit_correlation_id=row.audit_correlation_id,
          online_payment_id=row.id,
          yookassa_payment_id=row.yookassa_payment_id,
          idempotency_key=row.idempotency_key,
          confirmation_type=row.confirmation_type,
      ),
  )
  ```

- **`ErrorCode` StrEnum (Claude's discretion):**
  ```python
  class ErrorCode(StrEnum):
      CLIENT_EMAIL_REQUIRED = "client_email_required_for_online_payment"
      YOOKASSA_VALIDATION_ERROR = "yookassa_validation_error"
      YOOKASSA_UNAVAILABLE = "yookassa_unavailable"
      YOOKASSA_PERMANENT_ERROR = "yookassa_permanent_error"
  ```

- **Parity-test shape (D-49-23):**
  ```python
  async def test_v17_protocol_slots_non_none_after_app_startup(app):
      assert get_yookassa_client_provider() is not None
      assert get_fiscal_receipt_dispatcher() is not None
      assert get_membership_activator() is not None
      assert get_pt_package_activator() is not None
  ```

</specifics>

<deferred>
## Deferred Ideas

- **Embedded ЮKassa widget (PAY-02 from research):** requires admin-web work. Deferred to **v1.9 / v2.0** per FEATURES.md line 446.
- **Telegram WebApp native invoice (PAY-04 from research):** different ЮKassa product surface; v2.0+.
- **Mobile deep-link confirmation (PAY-05 from research):** v2.0+.
- **Reconcile cron for "ЮKassa created, DB failed" orphans (D-49-11):** Phase 53 ARQ `reconcile_orphan_yookassa_payments`. Document as `# TODO Phase 53:` in `service.py`.
- **`yookassa_call_failed` audit event (D-49-20):** Phase 49 emits NO audit on ЮKassa-side failures. Phase 50 may add the event if operational visibility demands.
- **`OnlinePaymentSucceededPayload` operator-display extension (D-49-30):** Phase 49 does NOT touch payload schema. Phase 50 may add `created_by_display_name`; Phase 49 leaves `app.modules.online_payments.service → app.modules.users.display` ignore unmatched (warn).
- **`yookassa_call_failed` audit + `TYPE_CHECKING → runtime` import flip for `payments.models` (D-49-29):** Phase 49 ships `payments.models` as TYPE_CHECKING only; Phase 50 needs runtime for `record_payment(method='online')`.
- **Saved-card / recurring autopayment columns (`payment_method_id`):** out of scope for v1.7; SUMMARY.md flags v2.0 as the right phase to retro-add a column. Phase 49 does NOT preemptively add it (changes the migration shape and complicates the FSM).
- **Frontend admin-web online-sale UI:** out of scope; v1.7 backend ships API only. Frontend work tracked in v1.9 milestone.
- **`X-Forwarded-For` trust toggle on `verify_yookassa_ip`:** Phase 50 concern (deferred from Phase 48 D-48-deferred).
- **Webhook handler, FSM transitions, fiscal-receipt DB row:** Phase 50 (WH-01..WH-06, FISCAL-01..03).
- **Refund endpoint, ARQ retry, circuit breaker:** Phase 51 (REFUND-01..04).
- **Outer HTTP-layer Idempotency-Key admin-web alignment:** Phase 49 backend accepts it; admin-web must be taught to send a UUID per click. Frontend task tracked in v1.9.

### Reviewed Todos (not folded)
*No todos matched Phase 49 in `gsd-sdk query todo.match-phase 49` (`todo_count: 0`) — section omitted.*

</deferred>

---

*Phase: 49-Online-Sales-Orchestrator*
*Context gathered: 2026-05-22*
*Mode: --auto (recommended defaults applied; deviations from prior phases documented inline)*
