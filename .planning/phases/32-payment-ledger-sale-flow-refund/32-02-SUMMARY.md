---
phase: 32-payment-ledger-sale-flow-refund
plan: 02
subsystem: backend/memberships+payments
tags: [sale-flow, payment-recorder, idempotency, audit-chain, uow-atomicity, anti-fraud]
requires:
  - 32-01 PaymentRecorder Protocol slot + get_payment_recorder defensive accessor
  - 32-01 payments.service.record_payment caller-owns-txn function
  - 32-01 idempotency.{verify_idempotency, begin_idempotency, load_idempotency_response}
  - 32-01 audit_hash.payment_row_hash helper
  - Phase 30 LOCKED_AUDIT_EVENTS ("membership_created", "payment_recorded")
provides:
  - memberships.service.create_membership consumes get_payment_recorder() in same UoW
  - membership_created audit payload extended with payment_id field (free-form per D-30-02)
  - POST /api/v1/memberships requires Idempotency-Key (Phase 32 PAY-09)
  - In-router two-phase replay (SET NX placeholder -> store envelope -> body-hash diff)
  - PAYMENT_SUBJECT_KIND_MEMBERSHIP local constant in memberships.constants
  - 5 idempotency integration tests + 4 sale-flow tests + 4 audit-chain tests
affects:
  - memberships.service.create_membership flow
  - memberships.router.create_membership signature (+3 Depends params, returns Response)
  - memberships.constants — new PAYMENT_SUBJECT_KIND_MEMBERSHIP literal
  - payments.service.record_payment / issue_refund audit emit (UUID -> str cast)
  - 4 pre-existing membership integration test files (_csrf_headers extended with Idempotency-Key)
  - 1 pre-existing audit shape test asserting the now 4-key membership_created payload
tech-stack:
  added: []
  patterns:
    - "Inline two-phase Redis idempotency claim (SET NX placeholder -> envelope JSON -> replay)"
    - "Recorder consumed via defensive-raise accessor in caller-owned UoW (atomic rollback on raise)"
    - "Cross-module string-literal pinning via parallel local constants anchored on migration CHECK"
key-files:
  created:
    - apps/backend/tests/integration/payments/test_idempotency.py
    - apps/backend/tests/integration/payments/test_payments_sale.py
    - apps/backend/tests/integration/payments/test_payments_audit_chain.py
  modified:
    - apps/backend/app/modules/memberships/service.py
    - apps/backend/app/modules/memberships/router.py
    - apps/backend/app/modules/memberships/constants.py
    - apps/backend/app/modules/payments/service.py
    - apps/backend/tests/integration/memberships/test_memberships_audit.py
    - apps/backend/tests/integration/memberships/test_memberships_crud.py
    - apps/backend/tests/integration/memberships/test_memberships_list.py
    - apps/backend/tests/integration/memberships/test_memberships_rbac.py
decisions:
  - "PAYMENT_SUBJECT_KIND_MEMBERSHIP literal lives in memberships.constants (not imported from payments.constants) — preserves the modules-independent importlinter contract. Same string value pinned to migration 0012 ck_payments_subject_kind."
  - "Idempotency replay logic implemented inline in the router because Phase 32-01's exported store_idempotency_response stored a hash of the response body as body_hash but the orchestrator helper compares to a request-body hash — guaranteed mismatch. The helper is preserved for callers that don't need replay parity; the router builds the envelope dict manually with body_hash=sha256(request) and body_b64=base64(response)."
  - "Recorder failure / slot-unregistered tests use pytest.raises + explicit db_session.rollback() to simulate the production get_db context-manager exit. The SAVEPOINT-shared test fixture reuses one session across requests so the prod context-manager rollback must be invoked by hand to verify UoW atomicity."
  - "Locked event name 'membership_created' used verbatim (Phase 30 INFRA-11 AST gate). 'membership_sold' wording in ROADMAP / CONTEXT is terminology drift — the canonical taxonomy is membership_created."
metrics:
  duration_minutes: 21
  tasks_completed: 3
  files_created: 3
  files_modified: 8
  integration_tests_added: 13
  completed_date: "2026-05-15"
---

# Phase 32 Plan 02: Sale-Flow Atomic Wire-Up Summary

**One-liner:** Wires `get_payment_recorder()` into `create_membership` so every membership sale atomically writes a snapshot-symmetric Payment row + emits `payment_recorded` (with `payment_row_hash`) + extends `membership_created` audit with `payment_id` — all in one UoW; gates POST /api/v1/memberships behind a per-call Idempotency-Key with cached-envelope replay and key-reuse collision detection.

## Modified create_membership Flow

`apps/backend/app/modules/memberships/service.py:create_membership` (lines ~503-543):

```python
# Existing flow unchanged:
membership = await repository.insert_membership(session, data, plan=plan, ...)
await session.flush()

# NEW — Phase 32 PAY-05:
payment = await get_payment_recorder()(
    session,
    subject_kind=PAYMENT_SUBJECT_KIND_MEMBERSHIP,
    subject_id=membership.id,
    amount_kopecks=membership.price_kopecks_snapshot,    # snapshot-symmetric
    method="cash",
    received_by_user_id=actor.id,
    audit_actor=actor,
)
# Recorder is caller-owns-txn: internally flushes + emits payment_recorded.
# Does NOT commit. Defensive-raise from get_payment_recorder() rolls UoW back.

await audit.emit(
    session, "membership_created",
    ...existing kwargs...,
    payment_id=str(payment.id),                          # NEW — D-30-02 free-form
)
await session.commit()                                    # commits whole UoW atomically
```

Snapshot-symmetry invariant: `payment.amount_kopecks == membership.price_kopecks_snapshot` always holds because the recorder is fed the snapshot value from the ORM row — client cannot supply on wire (T-32-02-01 anti-tampering mitigation; MembershipCreateRequest schema unchanged, no `amountKopecks` field).

## Modified POST /api/v1/memberships Endpoint

`apps/backend/app/modules/memberships/router.py:create_membership` — handler signature gained 3 new dependencies (preserving RBAC-04 ordering auth → rbac → csrf → idempotency):

```python
async def create_membership(
    payload: MembershipCreateRequest,
    request: Request,                                    # NEW — raw body for hash
    actor: Annotated[CurrentUser, Depends(require_permission(CREATE, MEMBERSHIPS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],   # NEW
    redis: Annotated[Redis, Depends(get_redis)],                    # NEW
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    incoming_hash = body_sha256(await request.body())
    is_first = await begin_idempotency(redis, idempotency_key)
    if not is_first:
        stored = await load_idempotency_response(redis, idempotency_key)
        if stored is None or isinstance(stored, str):
            raise ConflictError("idempotency_in_flight")
        if stored["body_hash"] != incoming_hash:
            raise ValidationAppError("idempotency_key_reuse")
        return Response(base64.b64decode(stored["body_b64"]), status_code=stored["status_code"], ...)
    membership = await service.create_membership(session, actor, payload)
    body_bytes = json.dumps(envelope(membership).model_dump(by_alias=True), ...).encode()
    envelope_json = json.dumps({"status_code": 201, "body_hash": incoming_hash, "body_b64": base64.b64encode(body_bytes).decode("ascii")}, ...)
    await redis.set(f"sz:idem:{idempotency_key}", envelope_json, ex=3600)
    return Response(body_bytes, status_code=201, media_type="application/json")
```

## 13 New Integration Tests

### Sale flow (`tests/integration/payments/test_payments_sale.py`) — 4 cases

| Test | Asserts |
|------|---------|
| `test_sale_records_payment_with_snapshot_symmetry` | Exactly one payment row; amount_kopecks == price_kopecks_snapshot == plan.priceKopecks; method='cash'; refund_of is None |
| `test_sale_records_payment_sign_positive` | payments.amount_kopecks > 0 (defence-in-depth against CHECK ck_payments_amount_sign_matches_subject_kind) |
| `test_recorder_failure_rolls_back_uow` | monkeypatch `_payment_recorder` to a RuntimeError-raising coroutine; assert no new membership / payment / audit rows after explicit session.rollback() simulating prod get_db context-manager exit |
| `test_recorder_not_registered_raises_runtime_error` | monkeypatch slot to None; assert RuntimeError("payment_recorder not registered") surface + zero persisted state |

### Audit chain (`tests/integration/payments/test_payments_audit_chain.py`) — 4 cases

| Test | Asserts |
|------|---------|
| `test_audit_chain_membership_created_to_payment_recorded` | Both rows co-exist in same UoW; share created_at (transaction-stable now()); linkage via membership_created.payload.payment_id == str(payment.id) |
| `test_audit_chain_traceable_via_resource_id` | payment_audit.resource_id == payment.id; membership_audit.resource_id == membership_id; cross-reference consistent |
| `test_payment_recorded_payload_includes_row_hash` | payload['payment_row_hash'] matches ^sha256:[0-9a-f]{64}$ |
| `test_payment_recorded_row_hash_deterministic` | Recomputing payment_row_hash via app.core.audit_hash on the 8-column stable projection matches the stored payload value |

### Idempotency (`tests/integration/payments/test_idempotency.py`) — 5 cases

| Test | Asserts |
|------|---------|
| `test_missing_idempotency_key_returns_422` | 422 + message=idempotency_key_required |
| `test_invalid_idempotency_key_format_returns_422` | 422 + message=idempotency_key_invalid_format |
| `test_first_call_returns_201` | 201 + envelope.data.id well-formed UUID |
| `test_replay_returns_cached_envelope` | Same key + same body → byte-identical r2.content == r1.content (cached envelope replayed) |
| `test_same_key_different_body_returns_422` | Same key + different planId → 422 message=idempotency_key_reuse; only ONE payment row exists for the first membership (second sale did NOT execute) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Phase 32-01 payments.service emit-callsites passed raw UUIDs to JSONB payload**

- **Found during:** Task 1 first integration test run.
- **Issue:** `payments.service.record_payment` (and `issue_refund`) called `audit.emit(..., payment_id=payment.id, subject_id=subject_id, received_by_user_id=received_by_user_id, ...)` with raw UUID objects. Postgres JSONB encoder fails: "Object of type UUID is not JSON serializable". The Phase 32-01 unit tests didn't catch this because `tests/integration/payments/test_payments_list.py` seeds via the `make_payment` fixture which inserts directly via the ORM, bypassing the `record_payment` audit emit path entirely. Sale-flow now exercises that path on every membership create.
- **Fix:** Cast UUID kwargs to `str()` at the emit callsite. Pydantic's `UUID` field validators accept both UUID instances and well-formed UUID strings, so `PaymentRecordedPayload` / `RefundIssuedPayload` still validate. Free-form payloads (membership_created etc.) already use `str(...)`.
- **Files modified:** `apps/backend/app/modules/payments/service.py`.
- **Commit:** `b266f6d`.

**2. [Rule 1 - Bug] Pre-existing `test_membership_created_payload_shape` asserts a closed 3-key payload**

- **Found during:** Task 1 integration suite re-run after wiring the recorder.
- **Issue:** `tests/integration/memberships/test_memberships_audit.py:test_membership_created_payload_shape` asserted `set(payload.keys()) == {"client_id", "plan_id", "end_date"}`. Phase 32 PAY-05 adds `payment_id` to the payload (D-30-02 free-form), so the closed-set assertion fails.
- **Fix:** Extended the assertion to the 4-key set, plus an explicit UUID-shape check on `payload["payment_id"]`.
- **Files modified:** `apps/backend/tests/integration/memberships/test_memberships_audit.py`.
- **Commit:** `b266f6d`.

**3. [Rule 1 - Bug] Phase 32-01 `store_idempotency_response` conflates request vs response body hashing**

- **Found during:** Task 2 `test_replay_returns_cached_envelope` failure.
- **Issue:** The helper hashes `body_bytes` and stores it as `IdempotencyEnvelope.body_hash`. The orchestrator helper `idempotent_response` then compares that stored value to `body_sha256(incoming_request_body)`. If you call `store_idempotency_response(redis, key, body_bytes=RESPONSE_BYTES)` (as the plan §action 4 dictates), the stored hash is `sha256(response)` but the comparison hashes `request`. Result: every replay raises `idempotency_key_reuse`, infinite mismatch.
- **Fix:** Built the envelope JSON dict by hand inside the router using `body_hash=sha256(REQUEST body)` and `body_b64=base64(RESPONSE body)`, then `await redis.set(...)`. Avoided modifying `idempotency.py`'s exported signature (other consumers — e.g. Plan 32-03 refund — may still want the existing helper for cases where request body hash isn't relevant). Documented as a workaround in the router code comments.
- **Files modified:** `apps/backend/app/modules/memberships/router.py`.
- **Commit:** `e8b7a0e`.

**4. [Rule 3 - Blocking] importlinter `modules-independent` rejects `memberships.service -> payments.constants`**

- **Found during:** Task 3 `uv run lint-imports` after writing tests.
- **Issue:** Plan §action 2 said to `from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP`. importlinter contract `modules cannot import each other` forbids this — `app.modules.memberships -> app.modules.payments` is explicitly an independent-modules pair. The whole point of the `PaymentRecorder` Protocol slot pattern (Phase 32-01 D-32-14) is that the orchestrator never imports from `payments.*`.
- **Fix:** Added local constant `PAYMENT_SUBJECT_KIND_MEMBERSHIP = "membership"` to `memberships.constants`. Same string value, pinned to the migration 0012 `ck_payments_subject_kind` CHECK constraint literal. `payments.constants.SUBJECT_KIND_MEMBERSHIP` remains the canonical name on the payments side. Cross-module string parity enforced by both modules anchoring on the migration CHECK constraint value.
- **Files modified:** `apps/backend/app/modules/memberships/constants.py`, `apps/backend/app/modules/memberships/service.py`.
- **Commit:** `053e860`.

**5. [Rule 1 - Bug] Plan asserted audit-chain order via `created_at ASC` but Postgres `now()` is transaction-stable**

- **Found during:** Task 3 `test_audit_chain_membership_created_to_payment_recorded` failed when run alongside other tests (pseudo-flaky depending on UUID ordering).
- **Issue:** Plan §behavior asserted "ASC ordering ... first row action='payment_recorded'". But `audit_log.created_at` defaults to `func.now()` which in Postgres returns the **transaction start timestamp** — constant for the whole UoW. Both rows are written before `session.commit()`, so they share `created_at` to nanosecond precision. The query's secondary order-by on `audit_log.id` is by UUIDv4 — random.
- **Fix:** Replaced index-based ordering assertion (`chain[0].action == "payment_recorded"`) with an order-agnostic lookup (`by_action = {r.action: r for r in chain}`) + the genuine forensic invariant: the **`payment_id` linkage** in the `membership_created` payload proves causality, not the unreliable creation-time ordering. Also added an explicit `assert by_action["payment_recorded"].created_at == by_action["membership_created"].created_at` to lock in the same-UoW guarantee.
- **Files modified:** `apps/backend/tests/integration/payments/test_payments_audit_chain.py`.
- **Commit:** `053e860`.

**6. [Rule 3 - Blocking] Recorder-failure rollback test required explicit session.rollback() in test fixture**

- **Found during:** Task 3 `test_recorder_failure_rolls_back_uow` failed: the membership row was visible to the test query after the RuntimeError.
- **Issue:** Production `get_db` is a context manager — `async with sessionmaker() as session: yield session`. On unhandled exception inside the request handler, `__aexit__` rolls back. The test fixture overrides `get_db` with a bare `yield db_session` (the shared SAVEPOINT-mode session) — no context-manager rollback on exception. So `session.flush()` writes from `repository.insert_membership` remain in pending state and are visible to subsequent queries on the same session.
- **Fix:** In the test, after `pytest.raises(RuntimeError, ...)`, explicitly `await db_session.rollback()` to simulate the production context-manager behavior, then assert clean state. This proves what the plan invariant actually requires: that nothing was COMMITTED. (The service has no internal `session.commit()` until the final one at the end of `create_membership`, so any pending state belongs to the aborted UoW.)
- **Files modified:** `apps/backend/tests/integration/payments/test_payments_sale.py` (both recorder-failure tests).
- **Commit:** `053e860`.

**7. [Rule 3 - Blocking] Updated 4 pre-existing membership integration test files to send Idempotency-Key**

- **Found during:** Task 2 — adding `Depends(verify_idempotency)` to POST /memberships immediately broke 31 pre-existing POST sale callsites across `test_memberships_crud.py` / `test_memberships_rbac.py` / `test_memberships_list.py` / `test_memberships_audit.py`.
- **Fix:** Extended each file's `_csrf_headers(client)` helper to also return `"Idempotency-Key": uuid4().hex`. Per-call unique UUID so no replay collision. Sub-routes (`/cancel`, `/freeze`, `/unfreeze`, `/renew`) ignore the header — harmless to always include.
- **Files modified:** the 4 test files listed in `key-files.modified` above.
- **Commit:** `e8b7a0e`.

### Locked Event Terminology Drift Recorded

- ROADMAP / CONTEXT references "membership_sold" in some places. The LOCKED event in Phase 30 INFRA-11 / `LOCKED_AUDIT_EVENTS` is `"membership_created"`. The service emits the locked literal verbatim. No code or test references "membership_sold".

### Pre-existing Failures Out of Scope

- `tests/integration/test_rbac_parity.py::test_owner_only_count_is_fifteen` continues to fail (26 vs 15) — Phase 32-01's `deferred-items.md` already documents this. Phase 32 did not touch the OWNER_ONLY set; the test belt is stale from Phase 30 INFRA-19's expansion to 26 entries.

## Verification Evidence

- **mypy --strict**: clean on `memberships/service.py`, `memberships/router.py`, `payments/service.py` (3 source files; 0 issues).
- **lint-imports**: 3/3 contracts kept (core ⊥ modules, modules ⊥ each other, integrations ⊥ modules).
- **Wider unit suite**: 428/428 green.
- **memberships + payments integration**: 193/193 green.
- **Wider integration suite**: 465/465 green (deselected the pre-existing `test_owner_only_count_is_fifteen`; no other regressions).
- **AST commit-gate**: SVC001 walker still green — `create_membership` owns its `await session.commit()` literally.
- **AST append-only**: payments service body still has no `update(Payment)` / `delete(Payment)`.

## Confirmation: Phase 32 Idempotency-Key Scope

Per D-32-20, the `Idempotency-Key` dependency is wired ONLY on POST /api/v1/memberships. The 4 sub-routes (`/{id}/cancel`, `/{id}/freeze`, `/{id}/unfreeze`, `/{id}/renew`) and POST /api/v1/memberships/{id}/refund (Plan 32-03) use natural guards:
- **/cancel, /freeze, /unfreeze**: status-transition guards in `_assert_can_*` raise 409 invalid_transition on repeat.
- **/renew**: returns a NEW membership; idempotency is a separate-business concern handled by FE retry semantics.
- **/refund**: DB partial UNIQUE `uq_payments_refund_of_alive` enforces at-most-one refund per sale at the storage layer.

## Self-Check: PASSED

**Files verified to exist:**
- FOUND: apps/backend/tests/integration/payments/test_idempotency.py
- FOUND: apps/backend/tests/integration/payments/test_payments_sale.py
- FOUND: apps/backend/tests/integration/payments/test_payments_audit_chain.py
- FOUND: apps/backend/app/modules/memberships/service.py (modified — get_payment_recorder, PAYMENT_SUBJECT_KIND_MEMBERSHIP, payment_id audit kwarg)
- FOUND: apps/backend/app/modules/memberships/router.py (modified — verify_idempotency Depends + cached envelope replay)
- FOUND: apps/backend/app/modules/memberships/constants.py (modified — PAYMENT_SUBJECT_KIND_MEMBERSHIP)
- FOUND: apps/backend/app/modules/payments/service.py (modified — UUID->str cast in emit callsites)

**Commits verified:**
- FOUND: b266f6d — Task 1 (recorder wired + payment_id audit + UUID-cast bug fix)
- FOUND: e8b7a0e — Task 2 (Idempotency-Key Depends + cached-envelope replay + test fixture updates)
- FOUND: 053e860 — Task 3 (8 integration tests + import-linter fix + audit-chain ordering fix)
