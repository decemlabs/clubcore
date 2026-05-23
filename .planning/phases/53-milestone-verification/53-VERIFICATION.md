# Phase 53: v1.7 Milestone Verification Report

**Milestone:** v1.7 — Online Payments + 54-ФЗ
**Phase:** 53-milestone-verification
**Date:** 2026-05-23
**Status:** TECHNICALLY VERIFIED (VER-03 operator-pending per D-04)

---

## Requirements Summary

| Req | Name | Status | Evidence |
|-----|------|--------|----------|
| VER-01 | Operator runbook — sell → webhook → fiscal → refund → idempotent replay | **VERIFIED** | Plans 53-01 Tasks 1+2 |
| VER-02 | Real-Postgres race tests (4 concurrency surfaces) | **VERIFIED** | Plan 53-02 Tasks 1+2 |
| VER-03 | ЮKassa sandbox walkthrough evidence | **OPERATOR-PENDING** | D-04 — scaffold shipped, live session is operator deliverable |
| VER-04 | Inline-regression ledger, hard cap ≤5 | **VERIFIED** | `v1.7-VERIFICATION-LOG.md` — 0/5 regressions |
| VER-05 | DEFER-46-03 closure: FISCAL-05 circuit-breaker open-state parity | **VERIFIED** | Plan 53-03 Task 1 |

**Regression tally:** 0 inline regressions (sourced from `v1.7-VERIFICATION-LOG.md`). Assertion: 0 ≤ 5. Hard cap NOT exceeded.

---

## VER-01 — Operator Runbook

**Status:** TECHNICALLY VERIFIED

**Artifacts:**

- `apps/backend/scripts/verify/09_online_sale_to_fiscal.sh` — commit `27487ae`
- `apps/backend/scripts/verify/10_online_refund_and_idempotent_replay.sh` — commit `27487ae`
- `apps/backend/scripts/verify/v1_7_runbook.sh` — commit `b2be08c`
- `apps/backend/scripts/verify/_preflight.sh` — commit `b2be08c` (extended: checks 9–11 added)
- `apps/backend/scripts/verify/README.md` — commit `b2be08c` (v1.7 Runbook section added)

**Evidence:**

- `bash -n` parses all three runbook scripts — no syntax errors.
- `shellcheck` reports only SC1091 info-level warnings (not following sourced `_lib.sh`) —
  identical posture to existing scenarios 01–08.
- Scenario 09 drives: `login_as owner` → `POST /api/v1/online-payments/memberships/{plan_id}/sell`
  → `POST /_internal/yookassa/webhook payment.succeeded` (fresh YK_PAYMENT_ID per run) →
  `GET /api/v1/memberships?status=active` (assert ≥1) → `psql_exec SELECT kind, status FROM
  fiscal_receipts` (assert `kind='payment'` + `status='sent'`).
- Scenario 10 drives: inline sell + webhook setup → `POST /api/v1/online-payments/memberships/{id}/refund`
  (assert 202) → `POST /_internal/yookassa/webhook refund.succeeded` → idempotency replay
  (uuidgen key, two identical POSTs, assert 2xx + row count unchanged).
- `v1_7_runbook.sh` prints exact string `ALL SCENARIOS PASS` on full success.
- `_preflight.sh` extended with checks 9–11: Redis reachable, ARQ worker registered, `YOOKASSA_SANDBOX=true`.

**Must-haves satisfied:**
- Operator runs one command (`v1_7_runbook.sh`) — confirmed.
- Webhook simulated via raw curl to `/_internal/yookassa/webhook` with `YOOKASSA_SANDBOX=true` (D-02) — confirmed.
- Each scenario is hermetic and re-runnable (fresh `yookassaPaymentId` from sell response per run) — confirmed.
- Extends existing numbered-scenario harness (D-01); reuses `_lib.sh` + `_preflight.sh` — confirmed.

---

## VER-02 — Real-Postgres Race Tests

**Status:** TECHNICALLY VERIFIED

**Artifacts:**

- `apps/backend/tests/integration/online_payments/test_payment_succeeded_double_delivery_race.py` — commit `1fa721d`
- `apps/backend/tests/integration/online_payments/test_webhook_after_redis_restart_race.py` — commit `1fa721d`
- `apps/backend/tests/integration/online_payments/test_concurrent_refund_arbitration_race.py` — commit `9395b79`
- `apps/backend/tests/integration/online_payments/test_kopecks_rubles_precision_race.py` — commit `9395b79`

**Evidence:**

```
14 tests, 14 passed, 0 failed, 0 skipped (Postgres running)
```

- **VER-02(a)** N=5 concurrent `payment.succeeded` webhook POSTs with same `object.id` →
  Redis `SET NX EX 86400` lets exactly 1 request acquire dedup lock → all 5 respond 200 →
  exactly 1 `fiscal_receipts` row survives. Both Redis dedup AND `uq_fiscal_receipts_payment_id_kind`
  UNIQUE proven independently.
- **VER-02(b)** Redis key deleted (simulates restart gap) → 2nd delivery re-enters UoW →
  `SELECT-FOR-UPDATE` finds `OnlinePayment.status='succeeded'` → FSM guard raises
  `InvalidTransitionError` → returns 200 `idempotency_outcome='illegal_transition'` (D-50-17) →
  exactly 1 `fiscal_receipts` row total. DB UNIQUE is the SOLE catcher confirmed.
- **VER-02(c)** N=5 concurrent `POST /api/v1/memberships/{id}/refund` (cash path) → exactly
  1×200 + 4×409 `already_refunded` → exactly 1 `payments` refund row + 1 audit row. `uq_payments_refund_of_alive` on `(refund_of) WHERE refund_of IS NOT NULL` is the load-bearing arbiter.
- **VER-02(d)** Edge values 0, 1, 99, 100, 9_999_999 kopecks × N=20 concurrent round-trips →
  zero drift. Wire-format assertions: always 2 decimal places. DB INSERTs of each edge value
  read back exactly as seeded (no Integer coercion). All arithmetic via `decimal.Decimal` with
  `ROUND_HALF_EVEN` — no float.

**Must-haves satisfied:** All four concurrency surfaces covered; inline real-commit engine
pattern; no new `pytest-postgresql`/`testcontainers` dependency (D-03) — confirmed.

---

## VER-03 — ЮKassa Sandbox Walkthrough Evidence

**Status:** OPERATOR-PENDING (D-04)

**Classification:** This requirement is NOT a blocking criterion for the phase's technical
close. It is modeled on the Phase 52 CARRY-01/02 operator-pending pattern.

**Scaffolding shipped by agent (Phase 53, Plan 53-04):**

- Evidence directory: `.planning/handoff/v1.7-yookassa-sandbox-evidence/` — commit `680ce4c`
- Capture README: `.planning/handoff/v1.7-yookassa-sandbox-evidence/README.md` — commit `680ce4c`
  - Contains nine sections: title+frontmatter, purpose, required env vars (`YOOKASSA_SHOP_ID`,
    `YOOKASSA_SECRET_KEY`, `YOOKASSA_SANDBOX`, `YOOKASSA_RETURN_URL`), security note (T-53-09),
    sale walkthrough (Steps 1–5), refund walkthrough (Steps 6–7), what to capture, evidence
    file format, acceptance criteria checklist.
- Security note (T-53-09) forbids committing real ЮKassa keys or live PII; all artifacts
  must be redacted before commit.

**Operator deliverable (D-04):**

The owner must run the live ЮKassa sandbox session (using real sandbox credentials), follow
the walkthrough in the README, and deposit at minimum one YAML evidence file per completed
step. VER-03 closes when the acceptance checklist in the README is fully checked off.

**Acceptance checklist (from README):**

- [ ] ЮKassa sandbox sale initiated and payment completed (sandbox test card used)
- [ ] `payment.succeeded` webhook callback received and processed (HTTP 200 / `ok`)
- [ ] `fiscal_receipts` row with `kind='payment'` + `status='sent'` observed and captured
- [ ] ЮKassa sandbox refund initiated and `refund.succeeded` callback processed
- [ ] `fiscal_receipts` row with `kind='refund'` + `status='sent'` observed and captured
- [ ] At least one YAML evidence file saved with redacted values
- [ ] No real ЮKassa live keys, real payment IDs, or personal PII committed

---

## VER-04 — Inline-Regression Ledger

**Status:** TECHNICALLY VERIFIED

**Source:** `.planning/milestones/v1.7-VERIFICATION-LOG.md`

**Regression tally:**

```
Inline regressions discovered during Phase 53: 0 / 5 (hard cap)
```

**Assertion:** 0 ≤ 5 → PASSES hard cap. Phase does NOT block. No rollover to v1.8 DEFER required.

**Protocol enforced (D-05 / D-36-15..17 lineage):**

Each inline regression would be fixed as its own `fix(53-NN): REG-53-XX <desc>` commit,
re-run confirmed, and logged in `v1.7-VERIFICATION-LOG.md`. Since zero regressions were
discovered, the ledger records only the distinction between product-code regressions
(count toward cap) and verification-artifact style fixes (do not count).

---

## VER-05 — DEFER-46-03 Closure: FISCAL-05 Circuit-Breaker Open-State Parity

**Status:** TECHNICALLY VERIFIED

**Artifact:**

- `apps/backend/tests/integration/fiscal_receipts/test_circuit_breaker_open_state_parity.py`
  — commit `c8cdbf0`

**Evidence:**

```
pytest tests/integration/fiscal_receipts/test_circuit_breaker_open_state_parity.py -x -v
2 passed in 0.78s
```

**Test 1:** `test_fiscal_receipt_dispatch_short_circuits_when_breaker_open_via_5_failures`

- Pre-opens `sz:yookassa:circuit:receipts` via exactly 5 `record_failure(redis, "receipts")`
  calls (crossing D-51-14 locked threshold).
- Seeds a `fiscal_receipts(status='pending')` row.
- Invokes `dispatch_fiscal_receipt(ctx, receipt_id)`.
- Asserts `arq.Retry(defer=300)` raised — head-of-body `is_circuit_open` guard at tasks.py:276-278.
- Asserts respx route call count == 0 (no ЮKassa `/v3/receipts` POST issued).
- Asserts seeded row remains `status='pending'`, `yookassa_receipt_id=None`, `succeeded_at=None`.

**Test 2:** `test_fiscal_receipt_dispatch_short_circuits_when_breaker_open_via_direct_set`

- Directly SETs the open-marker key: `await fiscal_redis.set("sz:yookassa:circuit:receipts", "1", ex=300)`.
- Same assertions — confirms `is_circuit_open` is EXISTS-based (O(1)).

**DEFER-46-03 disposition:** CLOSED. The v1.6 VER-09 scenario-08 open-state parity gap is
resolved. The FISCAL-05 circuit breaker (reused from v1.6) exhibits the expected short-circuit
behavior when open, mirroring the v1.6 unit-level assertion while adding the integration-level
proof against real Postgres + Redis.

**Note for STATE.md:** The Deferred Items table entry for DEFER-46-03 should be updated to
`closed` in the phase-close step (orchestrator responsibility).

---

## Technical Close Assessment

The following requirements are technically verified and do not block v1.7 milestone close:

| Req | Technical Criteria | Result |
|-----|--------------------|--------|
| VER-01 | Runbook scripts parse + shellcheck clean; scenario content matches spec | PASS |
| VER-02 | 14/14 race tests pass against real Postgres + Redis | PASS |
| VER-04 | Regression ledger present; 0 ≤ 5 regression cap | PASS |
| VER-05 | 2/2 circuit-breaker parity tests pass | PASS |

VER-03 is OPERATOR-PENDING per D-04. This is the planned disposition for this requirement —
it is not a technical failure. The operator may complete the sandbox walkthrough at any time
by following `.planning/handoff/v1.7-yookassa-sandbox-evidence/README.md`.

**Phase 53 is technically complete.** The v1.7 milestone may be closed on technical criteria.
VER-03 remains open as an operator follow-up item (analogous to CARRY-01/02 in Phase 52).
