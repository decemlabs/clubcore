# Phase 53: Milestone Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-23
**Phase:** 53-milestone-verification
**Mode:** `--auto` (Claude auto-selected recommended option for every area)
**Areas discussed:** Runbook architecture, Webhook delivery strategy, Race-test harness, VER-03 evidence classification, Regression cap + DEFER-46-03

---

## Runbook architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `scripts/verify/` harness | `v1_7_runbook.sh` orchestrator reusing `_lib.sh`/`_preflight.sh` + new `NN_*.sh` scenarios | ✓ |
| Monolithic standalone script | Single self-contained bash script, no harness reuse | |

**Auto-selected:** Extend existing harness (recommended) — consistent with v1.4/v1.6 verification harness already in `scripts/verify/`.

---

## Webhook delivery strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Local trusted-IP webhook POST | Runbook POSTs `payment.succeeded` payload to own endpoint — deterministic, CI-friendly | ✓ |
| Drive real ЮKassa sandbox | Wait on real sandbox callbacks inside the runbook | |

**Auto-selected:** Local simulated POST (recommended). Real-sandbox drive is owned separately by VER-03.

---

## Race-test harness

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse `db_session_real_commit` pattern | Mirror existing integration race tests + ASGITransport; no new dep | ✓ |
| Add `pytest-postgresql`/`testcontainers` | New real-Postgres test dependency | |

**Auto-selected:** Reuse existing real-commit fixture pattern (recommended) — `test_payments_refund_race.py` precedent already proves the pattern.

---

## VER-03 evidence classification

| Option | Description | Selected |
|--------|-------------|----------|
| Operator-pending (CARRY pattern) | Ship scaffolding + README; owner records sandbox session with real creds | ✓ |
| Block phase on sandbox evidence | Require live sandbox session before phase completes | |

**Auto-selected:** Operator-pending (recommended) — mirrors Phase 52 CARRY-01/02 handling; technical criteria auto-verified.

---

## Regression cap + DEFER-46-03

| Option | Description | Selected |
|--------|-------------|----------|
| VERIFICATION-LOG protocol + fix-as-own-commit | D-36-15..17 lineage; block at >5, roll excess to v1.8; re-run scenario-08 vs FISCAL-05 breaker | ✓ |
| Inline-fix without separate tracking | Fix in place, no override log / hard-cap enforcement | |

**Auto-selected:** VERIFICATION-LOG protocol (recommended) — preserves the established hard-cap discipline and closes DEFER-46-03 via fixture re-run.

---

## Claude's Discretion

- Exact scenario numbering/splitting in `v1_7_runbook.sh`, VERIFICATION.md / VERIFICATION-LOG.md layout, per-race-test file naming — deferred to planner under existing conventions.

## Deferred Ideas

- v1.7 functionality defects beyond the ≤5 cap → v1.8 DEFER (VER-04).
- MailHog inbox assertions (DEFER-46-05) → v1.9-optional, not in this runbook.
- Pre-existing CI tech-debt (DEFER-46-04) → out of scope, does not count against the cap.
