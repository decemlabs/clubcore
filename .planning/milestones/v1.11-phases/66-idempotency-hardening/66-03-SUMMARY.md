---
phase: 66-idempotency-hardening
plan: "03"
subsystem: backend/idempotency
tags: [idempotency, security, wiring, memberships, webhook]
dependency_graph:
  requires:
    - 66-01 (audit classification — C-set = 4 membership transitions)
    - 66-02 (idempotent_execute orchestrator + verify_idempotency user-scoping)
  provides:
    - apps/backend/app/modules/memberships/router.py (4 transitions wired)
    - apps/backend/app/api/v1/_internal/yookassa/router.py (webhook exclusion comment)
    - apps/backend/app/modules/online_payments/router.py (B-classification comments)
  affects:
    - 66-04 (IDM-04 $ref injection — CATEGORY_A_OPERATION_IDS now complete 22-entry set)
    - 66-05 (IDM-03 tests — regression baseline expanded; 4 new wired endpoints to cover)
tech_stack:
  added: []
  patterns:
    - "IDM-07 wiring: C-class → A via idempotent_execute + verify_idempotency in RBAC-04 order"
    - "B-classification comment pattern: IDM-07 absence is intentional and reviewable"
    - "D-66-WEBHOOK-EXCLUDE: webhook exclusion from user-scoped verify_idempotency documented in code"
key_files:
  created: []
  modified:
    - apps/backend/app/modules/memberships/router.py
    - apps/backend/app/api/v1/_internal/yookassa/router.py
    - apps/backend/app/modules/online_payments/router.py
    - apps/backend/tests/integration/memberships/test_renewal_endpoint.py
    - apps/backend/tests/integration/memberships/test_renewal_active.py
    - apps/backend/tests/integration/memberships/test_renewal_archived_plan.py
    - apps/backend/tests/integration/memberships/test_renewal_expired_source.py
    - apps/backend/tests/integration/memberships/test_renewal_from_frozen.py
    - apps/backend/tests/integration/memberships/test_renewal_price_change.py
    - apps/backend/tests/integration/memberships/test_freeze_endpoints.py
    - apps/backend/tests/integration/memberships/test_freeze_cycle.py
    - apps/backend/tests/integration/memberships/test_freeze_limit.py
    - apps/backend/tests/integration/memberships/test_freeze_race.py
    - apps/backend/tests/integration/memberships/test_freeze_resolver.py
    - apps/backend/tests/integration/memberships/test_cancel_during_freeze.py
    - apps/backend/tests/integration/memberships/test_resolver.py
decisions:
  - "cancel/freeze/unfreeze/renew membership wired to idempotent_execute + verify_idempotency in RBAC-04 order (require_permission → verify_csrf → verify_idempotency)"
  - "freeze/unfreeze/renew have no request body; incoming_body=b'' passed through — key scoped by user+method+path+header (D-66-USER-SCOPE) so empty-body collision is correctly bounded"
  - "refund_membership_online and refund_pt_package_online: B-classification comment added; NO wiring (binding from 66-01 audit)"
  - "ЮKassa webhook: exclusion comment added (D-66-WEBHOOK-EXCLUDE / D-11-IDM-WEBHOOK); no functional change"
  - "Race test (test_freeze_race.py): each of 5 parallel requests now uses a unique Idempotency-Key so all 5 pass the idempotency guard and race to the DB UNIQUE index — preserving MEM-FRZ-TEST-03 semantics"
metrics:
  duration: "~30min"
  completed_date: "2026-05-29"
  tasks_completed: 2
  files_modified: 16
---

# Phase 66 Plan 03: IDM-07 Wiring — Membership Transitions + Webhook Exclusion Comment

**One-liner:** 4 C-class membership transitions (cancel/freeze/unfreeze/renew) wired to idempotent_execute + verify_idempotency in RBAC-04 order; webhook exclusion and B-class online refund comments added; 13 test files updated.

## What Was Done

### Task 1: Wire verify_idempotency + orchestrator into 4 membership C-class endpoints

Wired `cancel_membership`, `freeze_membership`, `unfreeze_membership`, `renew_membership` each onto the shared `idempotent_execute` orchestrator from 66-02. Pattern mirrors the already-refactored `create_membership` callsite.

**Changes per endpoint:**

| Endpoint | Status Code | Body | Notes |
|----------|-------------|------|-------|
| `cancel_membership` | 200 | `MembershipCancelRequest` payload | Has request body; incoming_body from request |
| `freeze_membership` | 200 | None (b"") | No body; empty bytes passed through |
| `unfreeze_membership` | 200 | None (b"") | No body; empty bytes passed through |
| `renew_membership` | 201 | None (b"") | No body; value-creating (new membership row) |

RBAC-04 ordering preserved: `require_permission → verify_csrf → verify_idempotency → get_redis → get_db`.

Return types changed from `ResponseEnvelope[MembershipResponse]` to `Response`. `response_model` decorator annotation removed (returns verbatim-replay `Response`).

**Test updates (Rule 2 — missing critical correctness in tests):**

13 integration test files updated — `_csrf_headers` helpers that previously returned only `X-CSRF-Token` now also include `"Idempotency-Key": uuid4().hex`. Files without `uuid4` import had it added.

Race test (`test_freeze_race.py`) updated: each of 5 concurrent POST `/freeze` requests now gets a unique `Idempotency-Key` so all 5 pass the idempotency gate and race to the DB partial UNIQUE index, preserving the original test semantics (exactly 1x200 + 4x409 `already_frozen`).

### Task 2: Refund endpoints (B-classification) + webhook exclusion comment

**Online refunds (B — not wired):**

`refund_membership_online` and `refund_pt_package_online` classified B per 66-01 audit. No wiring. Added IDM-07 B-classification comment to each docstring explaining:
- Body-level `payload.idempotency_key` forwarded to ЮKassa `Idempotence-Key`
- DB partial UNIQUE `uq_online_refunds_alive_per_online_payment` is the load-bearing race defence
- 202 async return makes verbatim-replay awkward
- Decision is binding per v1.11-idempotency-audit.md

**ЮKassa webhook exclusion comment:**

Added IDM-07 / D-66-WEBHOOK-EXCLUDE / D-11-IDM-WEBHOOK inline comment block to `yookassa_webhook` docstring:
- States endpoint is NOT wired to `verify_idempotency`
- Describes separate `cc:yookassa:webhook:` dedup path (SET NX EX 86400)
- Notes no `current_user` (IP-authenticated via `verify_yookassa_ip`)
- Explains why adding user-scoped idempotency would break (no current_user) and is architecturally wrong

No functional changes to the webhook.

## Final CATEGORY_A_OPERATION_IDS (Complete 22-Entry Set for 66-04)

All A-class operationIds now carrying `Depends(verify_idempotency)`:

```
cancel_booking
cancel_membership       ← newly wired (IDM-07)
cancel_pt_package
cancel_pt_session
cancel_slot
create_booking
create_membership
create_pt_package
create_recurring_template
create_time_off
deactivate_recurring_template
delete_time_off
freeze_membership       ← newly wired (IDM-07)
publish_slot
record_pt_session
refund_pt_package
renew_membership        ← newly wired (IDM-07)
sell_membership_qr
sell_membership_redirect
sell_pt_package_qr
sell_pt_package_redirect
unfreeze_membership     ← newly wired (IDM-07)
```

Total: **22 operationIds** (18 already-wired from 66-02 + 4 IDM-07 additions from this plan).

This list is the authoritative input for 66-04 IDM-04 `$ref` injection into `CATEGORY_A_OPERATION_IDS`.

## Deviations from Plan

### Rule 2: Updated 13 integration test files to include Idempotency-Key header

**Found during:** Task 1 — running memberships integration tests after wiring
**Issue:** Test `_csrf_headers` helpers returned only `X-CSRF-Token`. After wiring, the 4 new endpoints require `Idempotency-Key`; tests without it got 422 `idempotency_key_required`.
**Fix:** Updated `_csrf_headers` in 13 test files to include `"Idempotency-Key": uuid4().hex`. Added `uuid4` import to files that only imported `UUID`. Race test updated to use per-request unique keys.
**Files modified:** 13 test files under `tests/integration/memberships/`
**Commit:** a4fb9948

## Verification Results

- `uv run pytest tests/integration/memberships tests/integration/test_route_introspection.py tests/integration/online_payments tests/integration/online_refunds -q` — **232 passed, 4 skipped**
- `uv run ruff check` — passed
- `uv run ruff format --check` — 637 files already formatted
- `uv run mypy --strict app` — 0 errors, 210 source files
- `uv run lint-imports` — 3 contracts kept, 0 broken
- `grep -c "Depends(verify_idempotency)" apps/backend/app/modules/memberships/router.py` — **5** (create + 4 C-class)
- `grep -q "D-11-IDM-WEBHOOK" apps/backend/app/api/v1/_internal/yookassa/router.py` — matched
- `grep -q "verify_idempotency" apps/backend/app/api/v1/_internal/yookassa/router.py` — matched (in comment text)

## Known Stubs

None — this plan is a pure implementation/wiring plan with no UI or data stubs.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. Existing endpoints hardened.

## Self-Check: PASSED
- `apps/backend/app/modules/memberships/router.py` exists: FOUND
- `apps/backend/app/api/v1/_internal/yookassa/router.py` exists: FOUND
- `apps/backend/app/modules/online_payments/router.py` exists: FOUND
- Commit `a4fb9948` exists: FOUND (Task 1)
- Commit `f4c21a20` exists: FOUND (Task 2)
