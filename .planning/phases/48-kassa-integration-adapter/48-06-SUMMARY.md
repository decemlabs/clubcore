---
phase: 48-kassa-integration-adapter
plan: 06
subsystem: integrations/yookassa
tags: [integrations, yookassa, respx, test-fixtures, json-fixtures]
requirements: [ADAPTER-06]
dependency_graph:
  requires:
    - Phase 48 Plan 48-02 will install respx>=0.21 to make these fixtures runtime-importable
  provides:
    - 6 canonical pytest fixtures (5 respx routers + 1 dict) for ЮKassa adapter + module tests
    - 6 JSON response-body files matching the actual ЮKassa wire format
  affects:
    - Plan 48-02 (test_client.py can opportunistically migrate off inline JSON to these fixtures)
    - Phase 49 (orchestrator tests reuse fixtures #1/#3/#4 for create→poll flow)
    - Phase 50 (webhook FSM tests reuse fixture #6 — the dict — for inbound body parsing)
    - Phase 51 (fiscal dispatch tests reuse fixture #4 — receipt_registration:succeeded trigger)
tech_stack:
  added: []
  patterns:
    - "JSON-as-data: response bodies live in _responses/*.json; conftest._load() reads them at fixture-resolve time. D-48-23 — wire-format drift edits do not churn Python."
    - "respx.MockRouter context-manager fixture pattern with yield (generator fixture) — first respx precedent in repo."
    - "Dict-returning fixture pattern for inbound webhook bodies (no transport mocking; tests POST the dict as JSON via httpx ASGITransport in Phase 50)."
key_files:
  created:
    - apps/backend/tests/integrations/__init__.py
    - apps/backend/tests/integrations/yookassa/__init__.py
    - apps/backend/tests/integrations/yookassa/conftest.py
    - apps/backend/tests/integrations/yookassa/_responses/__init__.py
    - apps/backend/tests/integrations/yookassa/_responses/create_payment_success.json
    - apps/backend/tests/integrations/yookassa/_responses/create_payment_422.json
    - apps/backend/tests/integrations/yookassa/_responses/get_payment_pending.json
    - apps/backend/tests/integrations/yookassa/_responses/get_payment_succeeded.json
    - apps/backend/tests/integrations/yookassa/_responses/create_refund_success.json
    - apps/backend/tests/integrations/yookassa/_responses/webhook_payment_succeeded.json
  modified: []
decisions:
  - "D-48-22 honoured exactly: 6 fixtures, 5 respx + 1 dict; names match plan spec"
  - "D-48-23 honoured: bodies live as JSON sidecars under _responses/, loaded by conftest._load()"
  - "Did NOT add respx>=0.21 to pyproject.toml — Plan 48-02 owns that edit; this plan explicitly states it does not re-add"
  - "Added tests/integrations/__init__.py + tests/integrations/yookassa/__init__.py as Rule 3 fix so pytest discovers the new conftest"
  - "Scrubbed the literal token 'secret_key' from create_payment_422.json description (T-48-06-01 acceptance criterion uses a grep deny-list; the original ЮKassa error wording quoted both 'shop_id' and 'secret_key' as informative copy)"
metrics:
  duration_min: 4
  completed_date: 2026-05-21
---

# Phase 48 Plan 48-06: Shared respx fixtures + JSON response bodies for ЮKassa adapter tests

Ship 6 canonical pytest fixtures backed by 6 JSON response-body files so the
Phase 48 adapter tests and all downstream Phase 49/50/51 tests reuse the same
ЮKassa wire-format mocks (SC5).

## What Shipped

### Task 1 (commit `f0458ba`) — JSON response bodies

`apps/backend/tests/integrations/yookassa/_responses/` (new directory):

| File | Endpoint mocked | HTTP | Key fields |
| --- | --- | --- | --- |
| `create_payment_success.json` | POST /v3/payments | 200 | status=pending, confirmation.confirmation_url, amount.value="1990.00" |
| `create_payment_422.json` | POST /v3/payments | 422 | type=error, code=invalid_credentials, description |
| `get_payment_pending.json` | GET /v3/payments/{id} | 200 | status=pending |
| `get_payment_succeeded.json` | GET /v3/payments/{id} | 200 | status=succeeded, receipt_registration=succeeded, paid=true, captured_at |
| `create_refund_success.json` | POST /v3/refunds | 200 | id, payment_id, status=succeeded, amount, receipt_registration=pending |
| `webhook_payment_succeeded.json` | (inbound webhook body) | n/a | type=notification, event=payment.succeeded, object.{id,status,amount,receipt_registration,metadata} |

Plus `_responses/__init__.py` marker.

Every JSON parses cleanly; every `amount.value` is a string per ЮKassa wire
contract; every UUID is a synthetic v4-shaped string (no production-looking
ids); no `secret_key`/`access_token`/`bearer`/`password` literal anywhere.

### Task 2 (commit `6f520df`) — conftest.py + package markers

`apps/backend/tests/integrations/yookassa/conftest.py` — six fixtures, all
named per D-48-22:

| # | Fixture name | Shape | Mocks |
| - | --- | --- | --- |
| 1 | `yookassa_create_payment_success` | `respx.MockRouter` generator | POST /v3/payments → 200 pending |
| 2 | `yookassa_create_payment_422` | `respx.MockRouter` generator | POST /v3/payments → 422 error |
| 3 | `yookassa_get_payment_pending` | `respx.MockRouter` generator | GET /v3/payments/{id} → 200 pending (UUID-permissive regex) |
| 4 | `yookassa_get_payment_succeeded` | `respx.MockRouter` generator | GET /v3/payments/{id} → 200 succeeded (UUID-permissive regex) |
| 5 | `yookassa_create_refund_success` | `respx.MockRouter` generator | POST /v3/refunds → 200 |
| 6 | `yookassa_webhook_payload` | `dict[str, Any]` | NOT a respx route — plain webhook body |

Module-level constants `_RESPONSES_DIR` (`Path(__file__).parent / "_responses"`)
and `_YOOKASSA_BASE_URL` (`"https://api.yookassa.ru/v3/"`). Helper `_load(name)`
parses the matching JSON file at fixture-resolve time.

All 5 `respx.mock(...)` calls mount the production base URL with
`assert_all_called=False` so consumer tests can opt into a subset of routes
without pytest failing on un-called mocks.

Empty `__init__.py` files added at `tests/integrations/` and
`tests/integrations/yookassa/` so pytest discovers the new `conftest.py` in
fresh test runs (Rule 3 — blocking issue for `--fixtures` collection).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Lint] E501 line-too-long on two docstrings**

- **Found during:** Task 2 verification (ruff)
- **Issue:** Module docstring line 15 (101 chars) + `yookassa_get_payment_succeeded` one-line docstring (106 chars) exceeded the 100-char limit pinned in `apps/backend/pyproject.toml` ruff config.
- **Fix:** Tightened both lines to ≤100 chars without losing meaning.
- **Files modified:** `apps/backend/tests/integrations/yookassa/conftest.py`
- **Commit:** `6f520df`

**2. [Rule 3 — Blocking issue] Missing `__init__.py` markers in new test sub-package**

- **Found during:** Task 2 (before commit)
- **Issue:** The plan only listed `_responses/__init__.py` in `files_modified`. Without `__init__.py` at `tests/integrations/` and `tests/integrations/yookassa/`, pytest in this project would not discover the new conftest as a sub-package collector (existing pattern across `tests/unit/integrations/...` always carries `__init__.py`).
- **Fix:** Added two empty `__init__.py` files following the project convention.
- **Files modified:** `apps/backend/tests/integrations/__init__.py`, `apps/backend/tests/integrations/yookassa/__init__.py`
- **Commit:** `6f520df`

**3. [Rule 2 — Mitigation of T-48-06-01] Removed literal `secret_key` token from 422 fixture description**

- **Found during:** Task 1 verification (defensive credential scan from plan threat model)
- **Issue:** The original ЮKassa-style 422 description copy from the plan body was `"Authentication failed: the shop_id or secret_key is incorrect."`. The plan's T-48-06-01 mitigation criterion is `! grep -E '(secret_key|access_token|bearer)' apps/backend/tests/integrations/yookassa/_responses/*.json`. The literal substring `secret_key` (informative copy, not a real secret) tripped that scan.
- **Fix:** Replaced the description with `"Authentication failed: invalid shop credentials."` — semantically equivalent, no banned tokens, still a realistic ЮKassa error body.
- **Files modified:** `apps/backend/tests/integrations/yookassa/_responses/create_payment_422.json`
- **Commit:** `f0458ba` (rewritten before commit)

### Architectural / Out-of-Scope Notes

**Deferred — respx not installed at the end of this plan.** The plan's
`<verification>` block runs `uv run mypy --strict` and `pytest --fixtures`
on the new conftest, but `respx` is not yet a project dependency: Plan
48-02 owns the `respx>=0.21` addition to `[dependency-groups] dev` and is
in wave 2. This plan (48-06) is wave 1 and the plan body explicitly states
"Plan 48-02 prerequisite: respx>=0.21 added to pyproject.toml ... This
plan does NOT re-add it."

Consequence: until Plan 48-02 lands, `uv run mypy --strict
tests/integrations/yookassa/conftest.py` reports one error
(`Cannot find implementation or library stub for module named "respx"
[import-not-found]`) and `uv run pytest tests/integrations/yookassa/
--fixtures` fails to import the conftest. After Plan 48-02 lands and adds
respx, both checks pass clean.

All structural acceptance criteria that do NOT depend on respx being
importable were verified:

- File exists; 6 `def yookassa_*` fixtures defined.
- All 6 fixture names present (exact match against D-48-22 list).
- `respx.mock` referenced 6 times (5 calls + 1 docstring); 5 calls use
  `assert_all_called=False`; the 6th fixture has no `respx` reference.
- `_load` helper and `_YOOKASSA_BASE_URL` constant present at module scope.
- ruff clean.

The plan's threat model says T-48-06-02 (fixture drift) is accepted risk
and T-48-06-03 (production-URL mount) is intentional — respx patches the
httpx transport, no real network call ever leaves the test runner.

## Downstream Consumers

| Phase | Plan | Reuses |
| --- | --- | --- |
| 48 | 48-02 | `test_client.py` may migrate inline ЮKassa response JSON to fixtures #1, #2, #3, #4, #5 (opportunistic; not required by 48-02's scope) |
| 49 | (Online Sales Orchestrator) | Create→poll flow tests use #1 + #3 + #4 |
| 50 | (Webhook FSM) | Fixture #6 (`yookassa_webhook_payload`) is the canonical inbound body for FSM transition tests |
| 51 | (Fiscal Dispatch) | Fixture #4 (`get_payment_succeeded` with `receipt_registration:"succeeded"`) is the 54-ФЗ fiscalisation trigger |

## Self-Check: PASSED

Verified the artefacts and commits exist:

```
apps/backend/tests/integrations/__init__.py                              — FOUND
apps/backend/tests/integrations/yookassa/__init__.py                     — FOUND
apps/backend/tests/integrations/yookassa/conftest.py                     — FOUND
apps/backend/tests/integrations/yookassa/_responses/__init__.py          — FOUND
apps/backend/tests/integrations/yookassa/_responses/create_payment_success.json — FOUND
apps/backend/tests/integrations/yookassa/_responses/create_payment_422.json     — FOUND
apps/backend/tests/integrations/yookassa/_responses/get_payment_pending.json    — FOUND
apps/backend/tests/integrations/yookassa/_responses/get_payment_succeeded.json  — FOUND
apps/backend/tests/integrations/yookassa/_responses/create_refund_success.json  — FOUND
apps/backend/tests/integrations/yookassa/_responses/webhook_payment_succeeded.json — FOUND

f0458ba: test(48-06): add canonical ЮKassa response fixtures under _responses/  — FOUND
6f520df: test(48-06): add conftest with 6 ЮKassa fixtures + package markers     — FOUND
```
