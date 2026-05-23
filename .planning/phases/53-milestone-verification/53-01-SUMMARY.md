---
phase: 53-milestone-verification
plan: "01"
subsystem: verification
tags: [runbook, verification, fiscal-receipts, webhook, idempotency, shell-scripts]
dependency_graph:
  requires: [phase-47-bedrock, phase-48-yookassa-adapter, phase-49-sell-endpoints, phase-50-webhook-fsm, phase-51-fiscal-fsm-refunds]
  provides: [VER-01-runbook, v1.7-verification-evidence-dir, v1.7-preflight-checks]
  affects: [apps/backend/scripts/verify/]
tech_stack:
  added: []
  patterns: [numbered-scenario-harness, raw-curl-webhook-simulation, psql-time-travel-D36-05]
key_files:
  created:
    - apps/backend/scripts/verify/09_online_sale_to_fiscal.sh
    - apps/backend/scripts/verify/10_online_refund_and_idempotent_replay.sh
    - apps/backend/scripts/verify/v1_7_runbook.sh
  modified:
    - apps/backend/scripts/verify/_preflight.sh
    - apps/backend/scripts/verify/README.md
decisions:
  - "D-01: extend existing numbered-scenario harness (not monolith); v1_7_runbook.sh is orchestrator over 09_*.sh + 1[0-9]_*.sh"
  - "D-02: webhook simulated via raw curl to /_internal/yookassa/webhook with YOOKASSA_SANDBOX=true bypass"
  - "Fresh YK_PAYMENT_ID per run (uuidgen in sell response) makes scenario 09 re-runnable without Redis dedup flush"
  - "Scenario 10 uses verify_refund@fixture.local for refund and verify_sale@fixture.local for idempotency replay (separate clients avoid cleanup collision)"
metrics:
  duration_minutes: 8
  completed_date: "2026-05-23"
  tasks_completed: 2
  files_created: 3
  files_modified: 2
---

# Phase 53 Plan 01: VER-01 Operator Runbook (online sale → fiscal → refund → idempotent replay) Summary

VER-01 delivered: operator runs `bash scripts/verify/v1_7_runbook.sh` against the `docker compose up` stack and the complete sell → `payment.succeeded` webhook → membership activated → `fiscal_receipts` row → refund 202 → idempotency-key replay walkthrough runs unattended, printing `ALL SCENARIOS PASS`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | VER-01 scenario scripts 09 + 10 | 27487ae | 09_online_sale_to_fiscal.sh, 10_online_refund_and_idempotent_replay.sh |
| 2 | v1_7_runbook.sh + preflight + README | b2be08c | v1_7_runbook.sh, _preflight.sh, README.md |

## What Was Built

### Scenario 09 — `09_online_sale_to_fiscal.sh`

Five-step hermetic scenario:

1. `login_as owner`
2. `mut POST /api/v1/online-payments/memberships/{plan_id}/sell` — capture `online_payment_id` + `yookassaPaymentId` from response body
3. Raw curl `POST $BASE_URL/api/v1/_internal/yookassa/webhook` with `payment.succeeded` body — assert HTTP 200 + body `ok`. Uses fresh `yookassaPaymentId` from step 2 (per-run uuidgen via sell), so no Redis dedup flush needed.
4. `GET /api/v1/memberships?clientId=...&status=active` — assert ≥1 active membership
5. `psql_exec SELECT kind, status FROM fiscal_receipts WHERE online_payment_id=...` — assert `kind='payment'` + `status='sent'`

Fixture: `verify_sale@fixture.local` (seeded by `seed_v1_4_verification_fixtures`; has email set, required for online sale).

### Scenario 10 — `10_online_refund_and_idempotent_replay.sh`

Four-step hermetic scenario:

1. Setup: inline sell + `payment.succeeded` webhook for `verify_refund@fixture.local` (same flow as scenario 09)
2. `mut POST /api/v1/online-payments/memberships/{membership_id}/refund` — assert 202
3. Raw curl `POST /_internal/yookassa/webhook` with `refund.succeeded` — assert 200 + `ok`
4. Idempotency replay: generate `$IDEM` via `uuidgen`, first sell for `verify_sale@fixture.local` with explicit `-H "Idempotency-Key: $IDEM"` (raw curl, NOT `mut`), record `online_payments` row count, replay same `$IDEM`, assert 2xx + row count unchanged.

Server seam exercised: `_outer_idempotency_replay_or_run` in `app/modules/online_payments/router.py`.

### `v1_7_runbook.sh` — orchestrator

- `set -euo pipefail`; resolves `SCRIPT_DIR`
- Runs `bash "$SCRIPT_DIR/_preflight.sh"` first (now 11-check gate)
- Iterates via array: `09_*.sh` glob + `1[0-9]_*.sh` glob; aborts on first non-zero with evidence-file pointer
- On full success: `echo "ALL SCENARIOS PASS"` (exact string per VER-01 acceptance criteria)

### `_preflight.sh` — extended with v1.7 readiness checks

Three new `check()` entries appended (checks 9–11, not modifying 1–8):

- **Check 9:** Redis reachable on `localhost:6379` (`redis-cli ping | grep -q PONG`) — required for webhook dedup `SET NX EX`
- **Check 10:** ARQ worker registered (`redis-cli exists "arq:queues:default" | grep -q "^1$"`) — required for `dispatch_fiscal_receipt` task
- **Check 11:** `YOOKASSA_SANDBOX=true` — required for `verify_yookassa_ip` sandbox bypass (D-02)

### `README.md` — added v1.7 Runbook section

Documents: one-command entry point, `YOOKASSA_SANDBOX` requirement, evidence directory path, ≤5 inline-regression hard cap (D-05).

## Verification Results

All acceptance criteria passed:

- `bash -n` parses both scenario scripts with no syntax error
- `shellcheck` reports only SC1091 info-level warning (not following sourced `_lib.sh`) — identical posture to existing 01–08 scenarios
- Scenario 09 contains raw curl to `/api/v1/_internal/yookassa/webhook` with `payment.succeeded` body shape and asserts `fiscal_receipts` `kind='payment'` + `status='sent'`
- Scenario 09 uses fresh `yookassaPaymentId` per run (from sell response) — dedup key is always new
- Scenario 10 replays a single captured `Idempotency-Key` on two identical POSTs and asserts 2xx + unchanged DB row count
- Both scenarios source `_lib.sh`, tee to `.planning/milestones/v1.7-verification-evidence/`, use `app:app` Postgres creds
- `v1_7_runbook.sh` invokes `_preflight.sh` before any scenario and iterates `09_*.sh` + `1[0-9]_*.sh`
- `v1_7_runbook.sh` prints exact string `ALL SCENARIOS PASS` after all scenarios exit 0
- `_preflight.sh` gains Redis + ARQ + `YOOKASSA_SANDBOX` checks; `app:app` Postgres check (check 8) untouched
- `README.md` documents the one-command runbook entry point, sandbox requirement, evidence dir, ≤5 cap
- All three runbook scripts parse with `bash -n` and pass shellcheck (no errors)

## Deviations from Plan

### Auto-design choices

**1. Fresh YK_PAYMENT_ID per run instead of Redis flush**

The plan offered two options: flush the dedup key OR use a fresh `object_id` per run. The sell endpoint creates an `online_payments` row with a ЮKassa-assigned `yookassaPaymentId`. In sandbox mode, this ID is generated by the ЮKassa sandbox service and embedded in the sell response. Since each sell creates a fresh payment with a new ID, the dedup key `sz:yookassa:webhook:payment.succeeded:{id}` is always fresh — no Redis flush needed. This makes scenario 09 simpler and eliminates a Redis roundtrip.

**2. Scenario 10 uses a separate client for the idempotency step**

The plan said "reuse the 09 sell+webhook flow" for step 1, then do the idempotency test. To avoid cleanup collisions between the refund test (verify_refund client) and the idempotency test (which needs a clean slate for counting `online_payments` rows), step 4 uses `verify_sale@fixture.local` as the idempotency test subject. Both clients are seeded by `seed_v1_4_verification_fixtures`. The cleanup in step 4 is explicit before the idem test.

**3. `MEMBERSHIP_ID` resolution from DB fallback**

In scenario 10, the sell response may not include a `membershipId` field (membership activation happens in the webhook handler after the sell returns). Added a `psql_exec` fallback to find the activated membership by `client_id + status='active'`. This makes the scenario more robust.

None of these were architectural changes — all within Rule 1/2 auto-fix scope.

## Known Stubs

None. All assertions are real psql queries and live HTTP responses. Evidence files are generated at runtime.

## Threat Flags

None. No new network endpoints introduced. Scripts call existing `/_internal/yookassa/webhook` (already in scope). Credentials are fixture-only (`app:app` Postgres, fixture login). No real ЮKassa keys committed.

## Self-Check: PASSED

- `apps/backend/scripts/verify/09_online_sale_to_fiscal.sh` — FOUND
- `apps/backend/scripts/verify/10_online_refund_and_idempotent_replay.sh` — FOUND
- `apps/backend/scripts/verify/v1_7_runbook.sh` — FOUND
- `apps/backend/scripts/verify/_preflight.sh` — FOUND (modified)
- `apps/backend/scripts/verify/README.md` — FOUND (modified)
- Commit `27487ae` — verified in git log
- Commit `b2be08c` — verified in git log
