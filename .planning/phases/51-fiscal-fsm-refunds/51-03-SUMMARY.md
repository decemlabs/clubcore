---
phase: 51
plan: 51-03
subsystem: integrations/yookassa
tags:
  - 54-fz
  - fiscal
  - yookassa
  - integration-adapter
requirements:
  - FISCAL-05
dependency_graph:
  requires:
    - 48-02  # YooKassaClient base (create_payment/get_payment/create_refund/get_refund)
    - 47-INFRA-36  # YooKassaSettings
  provides:
    - YooKassaClient.create_receipt method
    - YooKassaReceiptResult dataclass (promoted from placeholder)
    - 3 respx fixtures (create_receipt_ok / _429 / _500)
  affects:
    - 51-05  # dispatch_fiscal_receipt ARQ task — primary consumer
tech_stack:
  added: []
  patterns:
    - Mirror existing create_refund classification taxonomy byte-for-byte
    - Caller-owned idempotency key (string-typed, D-48-11 + D-51-20)
    - Never re-raise transport errors (SC1)
    - PII discipline: customer_email NEVER in structlog kwargs (T-51-03-01)
key_files:
  created:
    - apps/backend/tests/integrations/yookassa/test_create_receipt.py
    - apps/backend/tests/integrations/yookassa/_responses/create_receipt_success.json
    - apps/backend/tests/integrations/yookassa/_responses/create_receipt_429.json
    - apps/backend/tests/integrations/yookassa/_responses/create_receipt_500.json
    - .planning/phases/51-fiscal-fsm-refunds/deferred-items.md
  modified:
    - apps/backend/app/integrations/yookassa/client.py
    - apps/backend/app/integrations/yookassa/types.py
    - apps/backend/tests/integrations/yookassa/conftest.py
decisions:
  - 429 maps to permanent_error per Phase 48 _classify_http_status_error (rate-limit is operator concern, not ARQ retry)
  - kind discriminator chooses payment_id vs refund_id body field per ЮKassa /v3/receipts spec
metrics:
  duration_seconds: 374
  duration_minutes: 6
  tasks_completed: 2
  files_created: 5
  files_modified: 3
  tests_added: 11
  completed_date: "2026-05-23"
---

# Phase 51 Plan 51-03: YooKassaClient.create_receipt for 54-ФЗ Fiscalization Summary

One-liner: extended the Phase 48 ЮKassa adapter with `create_receipt` (POST /v3/receipts) mirroring `create_refund`'s classification taxonomy byte-for-byte, plus respx fixtures and 11 unit tests covering classification + idempotency + PII safety.

## Objective

Ship the integration-layer `create_receipt` method that the Phase 51 `dispatch_fiscal_receipt` ARQ task (plan 51-05) will call to issue 54-ФЗ refund receipts. Phase 48 shipped `create_payment` / `get_payment` / `create_refund` / `get_refund` but NOT `create_receipt` — for `kind='refund'` fiscal receipts there is no inline-embed possible, so a dedicated POST /v3/receipts call is required.

## Tasks Completed

| Task | Name | Status | Commit |
| ---- | ---- | ------ | ------ |
| 1 | Add `create_receipt` method to `YooKassaClient` + confirm `YooKassaReceiptResult` dataclass shape | done | 20ca1f4 |
| 2 | Add respx fixtures + unit tests for `create_receipt` | done | 756a73b |

## Exact Signature Shipped

```python
async def create_receipt(
    self,
    *,
    payment_id: str,
    customer_email: str,
    items: list[dict[str, Any]],
    tax_system_code: int,
    idempotency_key: str,
    kind: Literal["payment", "refund"] = "payment",
) -> YooKassaReceiptResult:
```

`YooKassaReceiptResult` (frozen dataclass):

```python
@dataclass(frozen=True)
class YooKassaReceiptResult:
    ok: bool
    classification: Literal["ok", "validation_error", "transient_error", "permanent_error"]
    receipt_id: str | None = None
    http_status: int | None = None
    error_code: str | None = None
    error: str | None = None
```

The existing placeholder shape (Phase 48 types.py line 119) already matched the contract — only the docstring was promoted from "placeholder for Phase 51 FISCAL-04" to "active implementation for FISCAL-05".

## Classification Taxonomy Verified

Drives off the shared `_classify_http_status_error` helper (client.py line 103), unchanged:

| Upstream                                  | Result classification |
| ----------------------------------------- | --------------------- |
| 200 OK                                    | `ok`                  |
| 422                                       | `validation_error`    |
| ≥500                                      | `transient_error`     |
| Other 4xx (incl. 403, 429)                | `permanent_error`     |
| `httpx.TimeoutException`                  | `transient_error`     |
| `httpx.RequestError` (network)            | `transient_error`     |
| `json.JSONDecodeError`                    | `permanent_error`     |
| Bare `Exception`                          | `transient_error`     |

Decision: **429 → permanent_error** per the Phase 48 convention. The plan suggested 429 might be transient; the helper proves otherwise. Documented in test + conftest docstring. ЮKassa rate-limit retry is operator concern, not ARQ backoff.

## ЮKassa API Doc Clarifications

- **Body field for refund-receipts**: `kind="refund"` branch routes the `payment_id` parameter into the `refund_id` body field (per ЮKassa /v3/receipts spec — `type="payment"` uses `payment_id`, `type="refund"` uses `refund_id`). Unit test `test_create_receipt_kind_refund_uses_refund_id_field_name` asserts the exact body shape.
- **`send: True`** is hard-coded in the request body — caller does NOT control whether ЮKassa emails the receipt to the customer. Matches the 54-ФЗ guarantee that the customer receives the fiscal receipt.

## Fixtures Registered

In `apps/backend/tests/integrations/yookassa/conftest.py`:

| Fixture                          | Route             | Status | Body fixture                                 |
| -------------------------------- | ----------------- | ------ | -------------------------------------------- |
| `yookassa_create_receipt_ok`     | POST /v3/receipts | 200    | `_responses/create_receipt_success.json`     |
| `yookassa_create_receipt_429`    | POST /v3/receipts | 429    | `_responses/create_receipt_429.json`         |
| `yookassa_create_receipt_500`    | POST /v3/receipts | 500    | `_responses/create_receipt_500.json`         |

## Tests Added (11 in `test_create_receipt.py`)

1. `test_create_receipt_returns_ok_classification_with_receipt_id`
2. `test_create_receipt_classifies_429_as_permanent_error` (decision-bearing — see Decisions above)
3. `test_create_receipt_classifies_500_as_transient_error`
4. `test_create_receipt_classifies_422_as_validation_error`
5. `test_create_receipt_classifies_403_as_permanent_error`
6. `test_create_receipt_timeout_returns_transient_error`
7. `test_create_receipt_passes_idempotency_key_in_header`
8. `test_create_receipt_kind_refund_uses_refund_id_field_name`
9. `test_create_receipt_kind_payment_uses_payment_id_field_name`
10. `test_create_receipt_does_not_leak_customer_email_to_structlog` (T-51-03-01 mitigation)
11. `test_create_receipt_failure_path_does_not_leak_customer_email` (T-51-03-01 mitigation)

All 11 pass; full yookassa suite is 66 tests green.

## Verification Results

- `cd apps/backend && uv run pytest tests/integrations/yookassa/ -x -q` → 66 passed
- `cd apps/backend && uv run mypy --strict app/integrations/yookassa/` → Success: no issues found in 9 source files
- `cd apps/backend && uv run lint-imports` → Contracts: 3 kept, 0 broken (`integrations-isolated` contract still holds — no email/ cross-imports introduced)
- `cd apps/backend && uv run ruff check app/integrations/yookassa/client.py app/integrations/yookassa/types.py` → clean
- `cd apps/backend && uv run ruff check tests/integrations/yookassa/test_create_receipt.py` → clean

## Threat Model Compliance

All STRIDE entries in the plan's threat register are accounted for:

| Threat ID    | Disposition | Verification                                                                                                                                             |
| ------------ | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T-51-03-01   | mitigate    | Two tests (success path + failure path) assert customer_email never appears in any structlog event kwarg                                                 |
| T-51-03-02   | mitigate    | Idempotency-Key header passed verbatim per caller; consumer (51-05) uses unique `fiscal_receipt_id.hex`                                                  |
| T-51-03-03   | mitigate    | Classification taxonomy correctly emitted so plan 51-05's circuit breaker can read it (verified by 3 classification-path tests)                          |
| T-51-03-04   | accept      | httpx TLS endpoint identity trust unchanged                                                                                                              |
| T-51-03-05   | mitigate    | SecretStr handling unchanged from Phase 48 — client.py never logs settings directly                                                                      |
| T-51-03-06   | mitigate    | Caller (51-05) responsibility; this plan provides the audit-friendly classification                                                                      |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's predicted 429 classification was incorrect**
- **Found during:** Task 2 (running tests)
- **Issue:** Plan suggested `429 → transient_error`; the existing `_classify_http_status_error` (client.py line 130) classifies 4xx ≠ 422 as `permanent_error`
- **Fix:** Updated test assertion + test name + conftest docstring + plan summary to document that 429 maps to `permanent_error`, matching the Phase 48 byte-for-byte mirror requirement
- **Files modified:** `apps/backend/tests/integrations/yookassa/test_create_receipt.py`, `apps/backend/tests/integrations/yookassa/conftest.py`
- **Commit:** 756a73b

### Out-of-Scope Findings (Deferred)

Pre-existing ruff S110 + RUF100 errors in `apps/backend/tests/integrations/yookassa/conftest.py` line 57 (existing `_reset_structlog_for_capture` fixture). Documented in `.planning/phases/51-fiscal-fsm-refunds/deferred-items.md`. These exist at the wave-base commit (a4392fcd) and are unrelated to the create_receipt work. Sweep target: DEFER-46-04 (v1.9 ruff tree-wide cleanup).

### Pre-Test Environment Workaround

The conftest.py at `apps/backend/tests/conftest.py` loads `.env.example` defaults via `os.environ.setdefault` AFTER importing `app.main` (which transitively instantiates `YooKassaSettings()` at module-load time in `webhook_verifier.py`). On a fresh checkout without `.env`, this race causes Settings validation errors. Workaround: copied `.env.example` → `.env`. The `.env` is gitignored (apps/backend/.gitignore line 25) and was NOT committed. This is a pre-existing environment bug, not introduced by this plan.

## Auth Gates

None. Plan fully autonomous; no human-action checkpoints.

## Self-Check: PASSED

Files exist:
- FOUND: apps/backend/app/integrations/yookassa/client.py (modified, includes `create_receipt`)
- FOUND: apps/backend/app/integrations/yookassa/types.py (modified, `YooKassaReceiptResult` docstring promoted)
- FOUND: apps/backend/tests/integrations/yookassa/conftest.py (modified, 3 new fixtures)
- FOUND: apps/backend/tests/integrations/yookassa/test_create_receipt.py (created, 11 tests)
- FOUND: apps/backend/tests/integrations/yookassa/_responses/create_receipt_success.json
- FOUND: apps/backend/tests/integrations/yookassa/_responses/create_receipt_429.json
- FOUND: apps/backend/tests/integrations/yookassa/_responses/create_receipt_500.json

Commits:
- FOUND: 20ca1f4 (feat: create_receipt method + YooKassaReceiptResult docstring)
- FOUND: 756a73b (test: respx fixtures + 11 unit tests)
