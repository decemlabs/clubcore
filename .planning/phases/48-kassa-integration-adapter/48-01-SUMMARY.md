---
phase: 48-kassa-integration-adapter
plan: 01
subsystem: integrations/yookassa
tags: [integrations, yookassa, dto, frozen-dataclass, literal-classification, audit-payloads]
dependency_graph:
  requires:
    - apps/backend/app/integrations/yookassa/settings.py  # Phase 47
    - apps/backend/app/integrations/email/types.py  # pattern source (D-42-13)
    - apps/backend/app/core/audit_payloads.py  # YookassaWebhookReceivedPayload (Phase 47)
  provides:
    - apps/backend/app/integrations/yookassa/types.py  # 4 frozen-dataclass DTOs
    - YooKassaPaymentResult  # consumed by Plan 48-02 client.create_payment / get_payment
    - YooKassaRefundResult  # consumed by Plan 48-02 client.create_refund / get_refund
    - YooKassaReceiptResult  # placeholder for Phase 51 FISCAL-04
    - YooKassaWebhookEvent  # consumed by Phase 50 webhook handler
    - YookassaWebhookReceivedPayload.idempotency_outcome="rejected_ip"  # consumed by Phase 50 webhook route
  affects:
    - Plan 48-02 (httpx client) — frozen DTO return contract
    - Plan 48-03 (factory + boot probe) — uses YooKassaPaymentResult shape
    - Plan 48-05 (webhook IP verifier) — structlog event_type="yookassa_webhook_received"
    - Phase 49 (Online Sales Orchestrator) — switches on classification Literal
    - Phase 50 (Webhook FSM) — consumes YooKassaWebhookEvent + emits audit row with rejected_ip outcome
tech_stack:
  added: []
  patterns:
    - "frozen-dataclass DTO + closed Literal classification (D-48-04 / D-42-13 lineage)"
    - "cloudpickle-safe DTOs for ARQ enqueue forward-compat"
    - "no-SDK-types-cross-boundary discipline (D-48-05)"
    - "additive Literal widening for forward-compat with downstream phases"
key_files:
  created:
    - apps/backend/app/integrations/yookassa/types.py
    - apps/backend/tests/integrations/__init__.py
    - apps/backend/tests/integrations/yookassa/__init__.py
    - apps/backend/tests/integrations/yookassa/test_types.py
  modified:
    - apps/backend/app/integrations/yookassa/__init__.py  # barrel re-exports
    - apps/backend/app/core/audit_payloads.py  # Literal widening + docstring
decisions:
  - "D-48-03 — 4 frozen-dataclass DTOs (Payment/Refund/Receipt/WebhookEvent); receipt is a Phase 51 placeholder"
  - "D-48-04 — closed Literal classification taxonomy (ok / validation_error / transient_error / permanent_error); diverges from email's blocked variant"
  - "D-48-05 — no SDK types cross the boundary; module never imports from yookassa.* or aioyookassa.*"
  - "Literal widening of idempotency_outcome is additive only; no source_ip field (lives as a structlog kwarg in Phase 48 / Plan 48-05)"
metrics:
  duration_minutes: ~12
  completed_date: "2026-05-21"
  tasks_completed: 3
  files_created: 4
  files_modified: 2
  tests_added: 9
  commits: 3
---

# Phase 48 Plan 01: ЮKassa Transport DTOs Summary

## One-Liner

Wave 1 contract file: 4 frozen-dataclass DTOs (`YooKassaPaymentResult` / `YooKassaRefundResult` / `YooKassaReceiptResult` / `YooKassaWebhookEvent`) with closed `Literal` classification taxonomy, plus additive widening of `YookassaWebhookReceivedPayload.idempotency_outcome` to admit `"rejected_ip"`.

## Outcome

Phase 48's downstream Wave-2 plans (48-02 client, 48-03 factory, 48-05 webhook verifier) and downstream phases (49 orchestrator, 50 webhook FSM) now have a stable, frozen DTO surface they implement against. Transport errors are values, not exceptions; classification is a closed enum that mypy verifies at compile time. No SDK types appear in this module.

## Tasks Completed

| Task | Name                                                       | Commit    | Files                                                                              |
| ---- | ---------------------------------------------------------- | --------- | ---------------------------------------------------------------------------------- |
| 1    | Create types.py with 4 frozen dataclasses                  | `9557d22` | apps/backend/app/integrations/yookassa/types.py                                    |
| 2    | Widen YookassaWebhookReceivedPayload.idempotency_outcome   | `b0a752d` | apps/backend/app/core/audit_payloads.py                                            |
| 3    | Update package __init__.py + create test_types.py          | `dcfa34c` | apps/backend/app/integrations/yookassa/__init__.py, apps/backend/tests/integrations/__init__.py, apps/backend/tests/integrations/yookassa/__init__.py, apps/backend/tests/integrations/yookassa/test_types.py |

## Verification

| Check                                                                                                  | Result      |
| ------------------------------------------------------------------------------------------------------ | ----------- |
| `ruff check app/integrations/yookassa/ tests/integrations/yookassa/`                                   | PASSED      |
| `mypy --strict app/integrations/yookassa/types.py app/core/audit_payloads.py tests/integrations/yookassa/test_types.py` | PASSED (no issues found in 3 source files) |
| `pytest tests/integrations/yookassa/test_types.py tests/unit/test_audit_taxonomy.py -q`                | 16 passed (9 new + 7 audit_taxonomy regression-free) |
| barrel import smoke test                                                                               | PASSED      |
| `@dataclass(frozen=True)` appears exactly 4 times in types.py                                          | PASSED      |
| No SDK imports (`yookassa.*` / `aioyookassa.*`)                                                        | PASSED      |
| No `app.modules.*` imports (importlinter contract)                                                     | PASSED      |
| `source_ip` field NOT present in audit_payloads.py                                                     | PASSED      |
| `extra="forbid"` preserved on YookassaWebhookReceivedPayload                                           | PASSED      |

## Success Criteria

- [x] 4 frozen dataclasses exposed at `app.integrations.yookassa.types` and re-exported from the package barrel
- [x] Closed Literal classification taxonomy in place: ok / validation_error / transient_error / permanent_error
- [x] `YookassaWebhookReceivedPayload.idempotency_outcome` widened to include `"rejected_ip"` (additive Literal-only; no new fields; `extra="forbid"` preserved)
- [x] No SDK types cross the boundary (verified by grep + module docstring statement)
- [x] mypy strict + ruff clean across the touched files
- [x] Test coverage: instantiation + frozen-ness + classification-shape for all 4 DTOs

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Created `tests/integrations/__init__.py`**
- **Found during:** Task 3
- **Issue:** Plan listed only `tests/integrations/yookassa/__init__.py` but the parent `tests/integrations/` directory did not yet exist (the repo currently uses singular `tests/integration/`). Without a top-level package marker, pytest would still collect via `rootdir` but `mypy --strict` namespace resolution and intra-package imports would be brittle.
- **Fix:** Added `apps/backend/tests/integrations/__init__.py` (single-line comment marker) alongside the leaf package marker.
- **Files modified:** `apps/backend/tests/integrations/__init__.py`
- **Commit:** `dcfa34c`

**2. [Rule 1 - Bug-equivalent] Replaced `timezone.utc` with `UTC` alias**
- **Found during:** Task 3 ruff verification
- **Issue:** Initial `test_types.py` used `from datetime import datetime, timezone` + `timezone.utc`. Project ruff config enforces `UP017` (use the Python 3.11+ `datetime.UTC` alias).
- **Fix:** Switched to `from datetime import UTC, datetime` + `tz=UTC` (3 callsites).
- **Files modified:** `apps/backend/tests/integrations/yookassa/test_types.py`
- **Commit:** `dcfa34c` (same commit as Task 3)

No other deviations.

## Authentication Gates

None.

## Threat Flags

None — the threat surface of this plan is documented in the plan's `<threat_model>` block (T-48-01-01..03) and the verifier checks confirm `extra="forbid"` is preserved and no `source_ip` field leaked into the audit-payload class.

## Known Stubs

`YooKassaReceiptResult` is intentionally a placeholder for Phase 51 FISCAL-04 — it has no client method in Phase 48. This is documented in the class docstring and in plan D-48-03.

## Downstream Consumers

- **Plan 48-02 (httpx client):** imports `YooKassaPaymentResult` / `YooKassaRefundResult` from `app.integrations.yookassa.types` as return types for `create_payment` / `get_payment` / `create_refund` / `get_refund`.
- **Plan 48-03 (factory + boot probe):** consumes `YooKassaPaymentResult` shape indirectly through the client it constructs.
- **Plan 48-05 (webhook verifier):** emits structlog event `yookassa_webhook_received` with `outcome="rejected_ip"` — the audit DB row that consumes the widened Literal lives in Phase 50.
- **Phase 49 (Online Sales Orchestrator):** switches on `result.classification` to dispatch retry / alert / success branches.
- **Phase 50 (Webhook FSM):** parses inbound bodies into `YooKassaWebhookEvent` and emits the `YookassaWebhookReceivedPayload` audit row with `idempotency_outcome="rejected_ip"` after the upstream `verify_yookassa_ip` Depends() rejects an IP.

## Self-Check: PASSED

- `apps/backend/app/integrations/yookassa/types.py` — FOUND
- `apps/backend/app/integrations/yookassa/__init__.py` — FOUND (modified)
- `apps/backend/app/core/audit_payloads.py` — FOUND (modified)
- `apps/backend/tests/integrations/__init__.py` — FOUND
- `apps/backend/tests/integrations/yookassa/__init__.py` — FOUND
- `apps/backend/tests/integrations/yookassa/test_types.py` — FOUND
- Commit `9557d22` — FOUND in `git log`
- Commit `b0a752d` — FOUND in `git log`
- Commit `dcfa34c` — FOUND in `git log`
