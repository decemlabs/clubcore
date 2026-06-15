---
phase: 117-openapi-handoff-milestone-gate
plan: "02"
subsystem: contract-tests
tags: [drift-guard, capture-fixtures, zod-contract, backend-test, phase-117]
dependency_graph:
  requires: ["117-01"]
  provides: ["D-V32-DRIFT-LESSON", "HND-01-criterion-2"]
  affects: ["apps/admin-app/src/features/*/capture/", "apps/backend/tests/integration/*/test_*_capture.py"]
tech_stack:
  added: []
  patterns:
    - "Backend ASGITransport → JSON capture → FE Zod parse (end-to-end drift guard)"
    - "pytest per-file-ignores for F811 pytest re-export fixture pattern"
key_files:
  created:
    - apps/backend/tests/integration/payments/test_refund_capture.py
    - apps/backend/tests/integration/users/test_role_change_capture.py
    - apps/backend/tests/integration/promo_codes/test_promo_capture.py
    - apps/backend/tests/integration/reports/test_load_now_capture.py
    - apps/backend/tests/integration/reports/test_payments_csv.py
    - apps/backend/tests/messaging/test_threads_capture.py
    - apps/admin-app/src/features/payments/capture/refund-response.json
    - apps/admin-app/src/features/users/capture/role-change-response.json
    - apps/admin-app/src/features/promoCodes/capture/promo-codes-list-response.json
    - apps/admin-app/src/features/reports/capture/load-now-response.json
    - apps/admin-app/src/features/messages/capture/threads-list-response.json
    - apps/admin-app/src/features/payments/refund.contract.test.ts
    - apps/admin-app/src/features/users/role-change.contract.test.ts
    - apps/admin-app/src/features/promoCodes/promo.contract.test.ts
    - apps/admin-app/src/features/reports/load-now.contract.test.ts
    - apps/admin-app/src/features/messages/messages.contract.test.ts
  modified:
    - apps/admin-app/src/features/messages/api.ts
    - apps/backend/ruff.toml
decisions:
  - "Capture fixture path: parents[5] from integration tests, parents[4] from tests/messaging"
  - "Role-change capture uses GET /users list (PATCH returns 204); FE contract test parses UsersListResponseSchema"
  - "Refund contract test parses captured.data with PaymentSchema (mirrors hook extraction pattern)"
  - "F811 per-file-ignores added to ruff.toml for pytest re-export pattern in test_threads_capture.py"
  - "StaffThreadSchema also exported (completeness) alongside StaffInboxSchema"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-15"
  tasks_completed: 3
  files_created: 17
  files_modified: 2
---

# Phase 117 Plan 02: Real Backend Response Contract Tests Summary

Structurally closed D-V32-DRIFT-LESSON: for each of the five new v3.2 domains, a
backend ASGITransport test hits the REAL endpoint and serializes the actual JSON
response into a shared `capture/` fixtures directory; an FE vitest contract test
loads that JSON and parses it with the domain's REAL FE Zod schema.

## What Was Built

### Shared fixtures directory + path convention

```
apps/admin-app/src/features/<domain>/capture/<endpoint>.json
```

Populated by backend pytest, consumed by FE vitest contract tests. No hand-authoring.

### Fixture paths (resolved from `pathlib.Path(__file__).resolve().parents[N]`)

| Backend test file | parents[N] = repo root | Output fixture |
|---|---|---|
| `tests/integration/payments/test_refund_capture.py` | `parents[5]` | `payments/capture/refund-response.json` |
| `tests/integration/users/test_role_change_capture.py` | `parents[5]` | `users/capture/role-change-response.json` |
| `tests/integration/promo_codes/test_promo_capture.py` | `parents[5]` | `promoCodes/capture/promo-codes-list-response.json` |
| `tests/integration/reports/test_load_now_capture.py` | `parents[5]` | `reports/capture/load-now-response.json` |
| `tests/messaging/test_threads_capture.py` | `parents[4]` | `messages/capture/threads-list-response.json` |

### FE schemas used per domain

| Domain | Captured endpoint | FE Zod schema | Schema export source |
|---|---|---|---|
| payments | `POST /payments/{id}/refund` | `PaymentSchema` (parse `.data`) | `features/payments/schemas.ts` |
| users | `GET /users` (after PATCH 204) | `UsersListResponseSchema` | `features/users/schemas.ts` |
| promoCodes | `GET /promo-codes` | `PromoCodesListResponseSchema` | `features/promoCodes/schemas.ts` |
| reports | `GET /reports/load/now` | `LoadNowSchema` | `features/reports/schemas.ts` |
| messages | `GET /messages/threads` | `StaffInboxSchema` | `features/messages/api.ts` (Task 2) |

### Seed helpers reused per capture test

| Domain | Seed helper |
|---|---|
| payments | `_seed_sale_payment` (inline, mirrors `test_payments_arbitrary_refund.py`) |
| users | Direct ORM `User(role=Role.RECEPTION, ...)` insert via `db_session` |
| promo codes | `make_promo_code` conftest fixture |
| reports | No seed needed — `load/now` returns `count=0` when window is empty (valid shape) |
| messages | Raw SQL `INSERT INTO message_threads/messages` via `db_session.execute(text(...))` |

### payments.csv backend assertion

`test_payments_csv.py` asserts `GET /api/v1/reports/payments.csv`:
- HTTP status 200
- `Content-Type` starts with `text/csv`
- `r.text[0] == BOM` and `ord(r.text[0]) == 0xFEFF`
- Header row matches `CSV_PAYMENTS_HEADERS` constant

No JSON capture for CSV (not a Zod-parsed body — correct).

## Captured Shape Summary (snapshot)

### refund-response.json
```json
{
  "data": {
    "id": "<uuid>",
    "subjectKind": "refund",
    "amountKopecks": -250000,
    "method": "cash",
    "receivedAt": "<iso>",
    "receivedByUserId": "<uuid>",
    "refundOf": "<uuid>",
    "auditLogId": null
  }
}
```
No drift detected — `PaymentSchema` parsed clean.

### role-change-response.json
```json
{
  "data": {
    "items": [{ "id": "<uuid>", "email": "...", "fullName": "...", "role": "owner", "status": "active", ... }],
    "total": N, "page": 1, "pageSize": 50
  }
}
```
**Extra fields** observed in real backend response: `isActive`, `createdAt`, `deactivatedAt`,
`deactivatedByUserId`, `isDeactivated` — these are stripped by Zod (default `.strip()` mode).
No required fields missing; `UsersListResponseSchema` parsed clean.

### promo-codes-list-response.json
No drift — all `PromoCodeSchema` fields present in camelCase. `usedCount` present in list (correct — list-only field).

### load-now-response.json
```json
{ "data": { "count": 0, "asOf": "<iso>", "windowMinutes": 120 } }
```
`LoadNowSchema` parsed clean.

### threads-list-response.json
```json
{
  "data": {
    "items": [{ "id": "<uuid>", "clientId": "<uuid>", "clientName": "Иван Захватов",
                "clientInitials": "ИЗ", "lastMessageAt": "<iso>", "lastMessageBody": "...",
                "lastMessageRole": "client", "staffUnreadCount": 1 }],
    "total": 1
  }
}
```
`StaffInboxSchema` parsed clean. No drift on `staffUnreadCount` (was a drift risk).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Unused imports in capture test files**
- **Found during:** Task 1 ruff check
- **Fix:** Removed unused `_csrf_headers` import from `test_promo_capture.py`, `hash_password` and `OWNER_EMAIL` from `test_role_change_capture.py`, `AsyncIterator` from `test_threads_capture.py`
- **Files modified:** 3 test files

**2. [Rule 1 - Bug] Import ordering in test_payments_csv.py**
- **Found during:** Task 1 ruff check (I001)
- **Fix:** Moved `import pytest` to standard import position (before third-party imports)

**3. [Rule 2 - Missing] F811 per-file-ignores for pytest re-export pattern**
- **Found during:** Task 1 ruff check on `test_threads_capture.py`
- **Issue:** Ruff F811 "redefinition of unused name" false positive: fixture names imported at module level AND appearing as function parameters (canonical pytest fixture pattern)
- **Fix:** Added per-file-ignores for `test_threads_capture.py` (and pre-existing `test_staff_messaging.py`) in `apps/backend/ruff.toml`
- **Files modified:** `apps/backend/ruff.toml`

**4. [Rule 1 - Bug] `make_user` fixture not found in test_threads_capture.py**
- **Found during:** First test run of Task 1
- **Issue:** `make_client` fixture transitively requires `make_user` (memberships conftest dependency)
- **Fix:** Added `make_user` to the re-export block in `test_threads_capture.py`

## Schema Drift Discoveries

**None** — all 5 domains parsed their captured JSON cleanly on first run.
The payload shapes (camelCase field names, nullability, types) matched the FE Zod schemas exactly.

This is the intended outcome: these domains were wired in v3.2 (phases 112/113/115/116) with
the drift lesson already in mind. The contract tests now provide a regression guard
for future changes.

## Known Stubs

None — all contract tests load REAL generated fixtures and parse against REAL Zod schemas.

## Threat Surface

T-117-04 (captured fixtures contain synthetic test data only — SAVEPOINT session, no PII):
confirmed. All captured UUIDs and names are seeded test data, not real user data.

T-117-05 (fixtures generated by backend, not hand-authored): confirmed. The write path
is exclusively `json.dumps(r.json(), ...) + "\n"` in the backend pytest; FE tests are
read-only consumers.

## Self-Check: PASSED

All files exist, all commits present.
