---
phase: 53-milestone-verification
verified: 2026-05-23T20:00:00Z
status: human_needed
score: 4/5 must-haves verified (VER-01 SQL defect fixed post-verification — commit f5ce4ec; VER-03 operator-pending by design)
overrides_applied: 0
resolved_gaps:
  - truth: "The runbook drives sell → payment.succeeded webhook → membership activated → fiscal_receipts row confirmed → refund → idempotency-key replay returns idempotent 2xx"
    status: resolved
    resolution_commit: f5ce4ec
    original_reason: "scenario 09 step5 and cleanup used fiscal_receipts.online_payment_id which does not exist (the column is payment_id FK to payments.id). At runtime the psql query emitted 'column online_payment_id does not exist' and step5 exited 1."
    fix: "09 step5 now JOINs fiscal_receipts → payments on the activated MEMBERSHIP_ID4 (subject_kind='membership', subject_id=membership_id), filters kind='payment', orders by fr.created_at. 09/10 cleanup DELETEs rewritten to target fiscal_receipts via payment_id through membership + refund payments, FK-safe ordering. All fixed SQL validated against the live schema via the postgres container; bash -n + shellcheck clean."
human_verification:
  - test: "Run bash apps/backend/scripts/verify/v1_7_runbook.sh against the docker compose up stack with YOOKASSA_SANDBOX=true"
    expected: "All scenarios pass and runbook prints 'ALL SCENARIOS PASS'. (The fiscal_receipts column-reference defect is fixed in commit f5ce4ec; remaining requirement is a seeded live stack.)"
    why_human: "Live end-to-end runbook execution requires a seeded docker compose stack (backend + Postgres 16 + Redis 7 + ARQ worker + Telegram bot). Cannot execute without the live stack."
  - test: "ЮKassa sandbox walkthrough (VER-03) — operator records a live membership sale + refund through the ЮKassa dashboard and deposits evidence at .planning/handoff/v1.7-yookassa-sandbox-evidence/"
    expected: "All seven checklist items in the README checked off: sale initiated, payment.succeeded callback received + processed, fiscal_receipts row observed, refund initiated, refund.succeeded callback processed, refund fiscal_receipts row observed, at least one YAML evidence file saved with redacted values"
    why_human: "Requires real ЮKassa sandbox credentials and a live sandbox session — intentionally operator-pending per D-04 (mirrors Phase 52 CARRY-01/02 pattern)"
---

# Phase 53: v1.7 Milestone Verification — Verification Report

**Phase Goal:** The complete v1.7 online-payment + fiscal-receipt flow is verified end-to-end via operator runbook and race tests; no more than 5 inline regressions are accepted.
**Verified:** 2026-05-23T20:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator runs one command (`v1_7_runbook.sh`) and all v1.7 scenarios pass without manual intervention | PARTIAL | Scripts exist, parse cleanly (`bash -n` + shellcheck pass), architecture is correct — BUT scenario 09 step5 SQL uses `fiscal_receipts.online_payment_id` which does not exist; see gap detail below |
| 2 | The runbook drives sell → payment.succeeded webhook → membership activated → fiscal_receipts row confirmed → refund → idempotency-key replay returns idempotent 2xx | PARTIAL | Sell, webhook simulation, activation, refund (202), and idempotent replay steps are structurally correct; the `fiscal_receipts` row confirmation step uses a non-existent column and will fail at runtime |
| 3 | Concurrent payment.succeeded double-delivery is deduplicated by Redis SET NX AND backstopped by DB UNIQUE — both layers proven independently | VERIFIED | `test_payment_succeeded_double_delivery_race.py` — 1 test passed (14/14 overall wave-1); asyncio.gather N=5, exactly 1 fiscal_receipts row, both dedup layers confirmed |
| 4 | A webhook after Redis-restart gap is caught solely by the DB UNIQUE | VERIFIED | `test_webhook_after_redis_restart_race.py` — explicit dedup-key delete, second delivery does not double-insert; DB UNIQUE is sole catcher confirmed |
| 5 | Concurrent refund webhook + manual refund is arbitrated by partial UNIQUE uq_payments_refund_of_alive | VERIFIED | `test_concurrent_refund_arbitration_race.py` — exactly 1×200 + 4×409, exactly 1 payments refund row survives |
| 6 | Concurrent kopecks↔rubles edge-value conversions preserve Decimal precision with no rounding drift | VERIFIED | `test_kopecks_rubles_precision_race.py` — 11 tests; edges 0, 1, 99, 100, 9_999_999; zero drift; wire-format 2 decimal places; no float coercion |
| 7 | VER-03 ЮKassa sandbox walkthrough evidence shipped to operator | VERIFIED (scaffold) | Evidence directory `.planning/handoff/v1.7-yookassa-sandbox-evidence/README.md` exists with all nine sections; classified OPERATOR-PENDING per D-04 — live session is the operator's deliverable |
| 8 | Inline regressions ≤ 5 (hard cap); excess rolls to v1.8 DEFER | VERIFIED | `.planning/milestones/v1.7-VERIFICATION-LOG.md` — 0/5 regressions; cap not exceeded; no v1.7 product code changed (`git diff --name-only faacc41 HEAD -- apps/backend/app/` is empty) |
| 9 | DEFER-46-03 closed: FISCAL-05 circuit-breaker open-state short-circuit confirmed | VERIFIED | `test_circuit_breaker_open_state_parity.py` — 2/2 passed; `sz:yookassa:circuit:receipts` pre-opened via 5 `record_failure` calls; `dispatch_fiscal_receipt` raises `arq.Retry(defer=300)`; respx call count == 0; seeded row remains `pending` |

**Score:** 7/9 truths fully verified; 2/9 partial (VER-01 runbook runtime defect); 1 human-needed by design (VER-03)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/scripts/verify/v1_7_runbook.sh` | Top-level orchestrator: preflight gate + iterates 09+ scenarios; prints `ALL SCENARIOS PASS` | VERIFIED (static) | 83 lines; invokes `_preflight.sh`; loops `09_*.sh + 1[0-9]_*.sh`; prints `ALL SCENARIOS PASS` on exit 0; `bash -n` + shellcheck pass; commit `b2be08c` |
| `apps/backend/scripts/verify/09_online_sale_to_fiscal.sh` | Scenario: sell → webhook → activation → fiscal_receipts row confirmed | PARTIAL | 172 lines; correct structure for sell/webhook/activation/fiscal steps — but step5 SQL query uses `fiscal_receipts.online_payment_id` (column does not exist); would fail at runtime; commit `27487ae` |
| `apps/backend/scripts/verify/10_online_refund_and_idempotent_replay.sh` | Scenario: refund (202) + idempotency-key replay returns idempotent 2xx | PARTIAL (cleanup only) | 245 lines; refund and idempotent-replay logic correct; cleanup DELETEs use same `fiscal_receipts.online_payment_id` non-column (silent failure, leaves orphan rows between runs); commit `27487ae` |
| `apps/backend/scripts/verify/_preflight.sh` | Extended with Redis + ARQ-worker + YOOKASSA_SANDBOX checks (checks 9–11) | VERIFIED | Checks 9 (Redis reachable), 10 (ARQ worker registered), 11 (YOOKASSA_SANDBOX=true) added; existing `app:app` Postgres check untouched; `bash -n` + shellcheck pass; commit `b2be08c` |
| `apps/backend/scripts/verify/README.md` | v1.7 Runbook section: one-command entry point, sandbox requirement, evidence dir, ≤5 cap | VERIFIED | "v1.7 Runbook" section added at line ~28; `YOOKASSA_SANDBOX=true` documented; evidence dir documented; inline-regression hard cap 5 documented; commit `b2be08c` |
| `apps/backend/tests/integration/online_payments/test_payment_succeeded_double_delivery_race.py` | VER-02(a) Redis dedup + DB UNIQUE double-delivery race | VERIFIED | asyncio.gather N=5; both dedup layers proven; inline `create_async_engine` (no new dependency); commit `1fa721d` (ruff-cleaned `e7fd5ed`) |
| `apps/backend/tests/integration/online_payments/test_webhook_after_redis_restart_race.py` | VER-02(b) DB UNIQUE as sole catcher after dedup-key flush | VERIFIED | Explicit dedup-key delete; single delivery gap; DB UNIQUE sole catcher; commit `1fa721d` |
| `apps/backend/tests/integration/online_payments/test_concurrent_refund_arbitration_race.py` | VER-02(c) partial-UNIQUE-on-refund_of arbitration | VERIFIED | N=5 concurrent refunds; `uq_payments_refund_of_alive` is arbiter; exactly 1 surviving row; commit `9395b79` |
| `apps/backend/tests/integration/online_payments/test_kopecks_rubles_precision_race.py` | VER-02(d) Decimal-precision kopecks↔rubles edges | VERIFIED | Edge values [0, 1, 99, 100, 9_999_999]; zero drift; `decimal.Decimal` with `ROUND_HALF_EVEN`; no float; commit `9395b79` |
| `apps/backend/tests/integration/fiscal_receipts/test_circuit_breaker_open_state_parity.py` | VER-05 DEFER-46-03 closure: open-state breaker parity against FISCAL-05 | VERIFIED | 2/2 passed; `sz:yookassa:circuit:receipts`; `arq.Retry(defer=300)` raised; respx 0 calls; `pending` unchanged; commit `c8cdbf0` |
| `.planning/handoff/v1.7-yookassa-sandbox-evidence/README.md` | VER-03 operator capture procedure + evidence-dir scaffold | VERIFIED (scaffold) | All nine sections present; references VER-03, D-04, evidence path; security note T-53-09; acceptance checklist; operator-pending classification; commit `680ce4c` |
| `.planning/milestones/v1.7-VERIFICATION-LOG.md` | VER-04 inline-regression ledger (hard cap 5) with `overrides:` section | VERIFIED | Hard cap 5 documented; `regressions: []` (0/5); `overrides: []`; >5-blocks-and-defers guard present; DEFER-46-03 closure noted |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `v1_7_runbook.sh` | `_preflight.sh` + `09_*.sh` + `1[0-9]_*.sh` | bash invocation in for-loop, abort on non-zero | VERIFIED | `bash "$SCRIPT_DIR/_preflight.sh"` at line 46; for-loop at lines 57–80; `ALL SCENARIOS PASS` at line 83 |
| `09_online_sale_to_fiscal.sh` | `POST /api/v1/_internal/yookassa/webhook` | raw curl trusted-IP `payment.succeeded` payload | VERIFIED | Line ~109: `curl ... "$BASE_URL/api/v1/_internal/yookassa/webhook"` with `payment.succeeded` body |
| `09_online_sale_to_fiscal.sh` | `fiscal_receipts` row assertion | psql_exec SELECT | PARTIAL | Step5 SQL uses non-existent column `online_payment_id`; query would fail at runtime |
| Race tests | `db_session_real_commit` / inline `create_async_engine` | un-SAVEPOINTed real-Postgres commits | VERIFIED | All 4 race test files use inline `create_async_engine(str(settings.database_url), pool_pre_ping=True)` with TRUNCATE-CASCADE teardown; D-03 satisfied (no new dependency) |
| `test_circuit_breaker_open_state_parity.py` | `dispatch_fiscal_receipt` via `is_circuit_open` guard | pre-open breaker, invoke task, assert Retry + 0 calls | VERIFIED | 5 × `record_failure(redis, "receipts")` crosses threshold; task raises `arq.Retry(defer=300)`; respx call count == 0 |
| `v1.7-VERIFICATION-LOG.md` | regression tally ≤5 | `regressions: []` count | VERIFIED | 0 ≤ 5; `git diff --name-only faacc41 HEAD -- apps/backend/app/` empty (no product code changed) |

---

### Data-Flow Trace (Level 4)

Not applicable. Phase 53 is a milestone-verification phase that produces verification artifacts (runbook scripts, integration tests, planning documents). No dynamic data-rendering components. No `apps/backend/app/` files were changed.

---

### Behavioral Spot-Checks (Step 7b)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `v1_7_runbook.sh` parses cleanly | `bash -n apps/backend/scripts/verify/v1_7_runbook.sh` | exit 0 | PASS |
| `09_online_sale_to_fiscal.sh` parses cleanly | `bash -n apps/backend/scripts/verify/09_online_sale_to_fiscal.sh` | exit 0 | PASS |
| `10_online_refund_and_idempotent_replay.sh` parses cleanly | `bash -n apps/backend/scripts/verify/10_online_refund_and_idempotent_replay.sh` | exit 0 | PASS |
| `_preflight.sh` parses cleanly | `bash -n apps/backend/scripts/verify/_preflight.sh` | exit 0 | PASS |
| `v1_7_runbook.sh` contains `ALL SCENARIOS PASS` string | `grep -q "ALL SCENARIOS PASS" v1_7_runbook.sh` | found at line 83 | PASS |
| `_preflight.sh` contains YOOKASSA_SANDBOX check | `grep -q "YOOKASSA_SANDBOX" _preflight.sh` | found at line 87 | PASS |
| `_preflight.sh` contains Redis check | `grep -q "Redis reachable" _preflight.sh` | found at line 74 | PASS |
| `09_online_sale_to_fiscal.sh` fiscal_receipts SQL | runtime SQL correctness | `fiscal_receipts.online_payment_id` used at lines ~60, ~150 — column does not exist in DB schema | FAIL |
| Race tests import no `pytest_postgresql`/`testcontainers` | grep on imports | no `^import pytest_postgresql`, no `^import testcontainers` (only mentioned in docstrings/comments) | PASS |
| No `app/` files modified in phase | `git diff --name-only faacc41 HEAD -- apps/backend/app/` | empty output | PASS |

---

### Probe Execution

Step 7c: No `scripts/*/tests/probe-*.sh` probes declared in PLAN frontmatter or found via convention for this milestone-verification phase. The `v1_7_runbook.sh` is itself the operator probe — its live execution requires the docker compose stack and is classified as human_needed (VER-01 gap noted above). SKIPPED (no self-contained probes runnable without live stack).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| VER-01 | 53-01 | Operator runbook: sell → webhook → fiscal → refund → idempotent replay | PARTIAL | Scripts exist, parse, architecture correct; fiscal_receipts step fails at runtime (SQL column mismatch) |
| VER-02 | 53-02 | Race tests (real Postgres): double-delivery, Redis-restart, refund arbitration, Decimal precision | SATISFIED | 14/14 pytest tests passed against real Postgres + Redis |
| VER-03 | 53-04 | ЮKassa sandbox walkthrough evidence | OPERATOR-PENDING | Scaffold shipped (D-04 planned disposition); live session is operator deliverable |
| VER-04 | 53-04 | Inline-regression hard cap ≤5 | SATISFIED | 0/5 regressions; no `apps/backend/app/` files changed; VERIFICATION-LOG present |
| VER-05 | 53-03 | DEFER-46-03 closure: FISCAL-05 circuit-breaker parity | SATISFIED | 2/2 parity tests passed; DEFER-46-03 closed |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `09_online_sale_to_fiscal.sh` | ~60, ~150 | `fiscal_receipts.online_payment_id` — column does not exist in DB schema (fiscal_receipts has `payment_id` FK to `payments.id`, not to `online_payments.id`) | Blocker (runtime SQL error) | step5 assertion exits 1 — runbook fails at fiscal_receipts confirmation; cleanup DELETE silently skips leaving orphan rows |
| `10_online_refund_and_idempotent_replay.sh` | ~54, ~171 | Same `fiscal_receipts.online_payment_id` in cleanup DELETEs | Warning (silent at runtime) | Cleanup does not remove fiscal_receipt rows between runs; functional refund+idempotency logic unaffected |

No `TBD`, `FIXME`, or `XXX` markers found in any phase-53-created file.

---

### Human Verification Required

#### 1. VER-01 Runbook — Live Execution After Fix

**Test:** After fixing `fiscal_receipts.online_payment_id` references in `09_online_sale_to_fiscal.sh` (step5 + cleanup) and `10_online_refund_and_idempotent_replay.sh` (cleanup) to use the correct `payment_id`-based JOIN, run `bash apps/backend/scripts/verify/v1_7_runbook.sh` against the `docker compose up` stack with `YOOKASSA_SANDBOX=true`.

**Expected:** All scenarios pass; final output contains `ALL SCENARIOS PASS`. Scenario 09 confirms `fiscal_receipts` row with `kind='payment'` + `status='sent'` via the corrected `psql_exec` query.

**Why human:** Live end-to-end execution requires the full docker compose stack (backend + Postgres 16 + Redis 7 + ARQ worker + seeded test data). The SQL bug must be fixed first.

#### 2. VER-03 — ЮKassa Sandbox Walkthrough

**Test:** Using real ЮKassa sandbox credentials, follow the walkthrough in `.planning/handoff/v1.7-yookassa-sandbox-evidence/README.md`: initiate a membership sale → pay with sandbox test card → confirm `payment.succeeded` webhook callback processed → observe `fiscal_receipts` row → initiate refund → confirm `refund.succeeded` callback → observe refund fiscal row. Deposit at least one YAML evidence file (redacted) per completed step.

**Expected:** All seven acceptance checklist items in the README checked off; no real credentials or PII committed.

**Why human:** Requires real ЮKassa sandbox credentials and a live sandbox session. Operator-pending per D-04 (planned disposition, mirrors Phase 52 CARRY-01/02).

---

## Gaps Summary

**1 actionable gap (VER-01 runtime SQL defect):**

Scenarios `09_online_sale_to_fiscal.sh` and `10_online_refund_and_idempotent_replay.sh` reference `fiscal_receipts.online_payment_id` — a column that does not exist. The `fiscal_receipts` table has `payment_id` (FK to `payments.id`), not `online_payment_id`. This causes:
- Scenario 09 step5 assertion to fail at runtime with empty `FISCAL_ROW` → `exit 1 "FAIL — no fiscal_receipts row found"`
- Cleanup DELETEs in both scripts to silently fail (psql exits 0 without ON_ERROR_STOP), leaving orphan rows between runs

The correct query for step5 must JOIN through the ledger payment: `fiscal_receipts` → `payments.id` = `fiscal_receipts.payment_id`, then trace to the membership/client. Example:
```sql
SELECT fr.kind, fr.status
FROM fiscal_receipts fr
JOIN payments p ON p.id = fr.payment_id
JOIN memberships m ON m.id = p.subject_id
WHERE m.client_id = '${CLIENT_ID}'
ORDER BY fr.id DESC LIMIT 1;
```

**Root cause:** The online_payments service uses `online_payment_id` as a structlog field name in multiple places, which may have misled the script author into treating it as a DB column name.

**Scope note:** This is a defect in the VER-01 verification artifact (the runbook script), not in the product code. VER-02 independently proves the fiscal_receipts row IS correctly created when the webhook fires — the product behavior is verified. The fix required is in the bash script only.

**VER-03 operator-pending (not a gap):** The operator sandbox session is the planned disposition per D-04. It does not block technical criteria and is not counted as a gap.

---

## Technical Close Assessment

| Req | Technical Criteria | Result |
|-----|--------------------|--------|
| VER-01 | Runbook scripts parse + shellcheck clean; scenario content matches spec | PARTIAL — scripts parse; fiscal_receipts SQL column wrong |
| VER-02 | 14/14 race tests pass against real Postgres + Redis | PASS |
| VER-03 | Sandbox evidence scaffold shipped; live session operator-pending | OPERATOR-PENDING (by design) |
| VER-04 | Regression ledger present; 0 ≤ 5 regression cap | PASS |
| VER-05 | 2/2 circuit-breaker parity tests pass | PASS |

**Four of five requirements technically verified.** VER-01 has a runtime SQL defect in the fiscal_receipts step that must be fixed before the runbook can be successfully executed by the operator. VER-03 remains operator-pending per D-04.

---

_Verified: 2026-05-23T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
