# Phase 53: Milestone Verification - Context

**Gathered:** 2026-05-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Verify the complete v1.7 online-payment + fiscal-receipt flow end-to-end and prove its race-safety, then close the remaining v1.6 carry-over verification gap (DEFER-46-03) under a hard ≤5 inline-regression cap.

This phase delivers **verification artifacts, not new product behavior**:
1. An operator runbook (`apps/backend/scripts/verify/v1_7_runbook.sh`) walking sell → `payment.succeeded` webhook → membership activated → `fiscal_receipts` row confirmed → refund → idempotency-key replay (VER-01).
2. Real-Postgres race tests proving Redis dedup + DB UNIQUE on double-delivery, DB-UNIQUE catch after Redis restart, partial-UNIQUE arbitration of concurrent refund vs manual refund, and Decimal-precision kopecks↔rubles edges (VER-02).
3. ЮKassa sandbox walkthrough evidence captured to `.planning/handoff/v1.7-yookassa-sandbox-evidence/` (VER-03 — operator-pending, see D-04).
4. DEFER-46-03 closure: re-run v1.6 VER-09 scenario-08 cron-chain circuit-breaker fixture against the new FISCAL-05 circuit breaker, confirm parity (VER-05).
5. Inline-regression hard cap ≤5; excess rolls to v1.8 DEFER (VER-04).

**Not in scope:** new endpoints, schema changes, or fixing newly-discovered functionality bugs beyond the ≤5 inline-regression cap. Excess defects become v1.8 DEFER items, not phase work.
</domain>

<decisions>
## Implementation Decisions

### Runbook architecture
- **D-01:** Extend the **existing `scripts/verify/` numbered-scenario harness** rather than writing a monolithic standalone script. `v1_7_runbook.sh` is an orchestrator that reuses `_lib.sh` (hermetic per-scenario cookie jars) and `_preflight.sh` (readiness gate), and adds new numbered scenario scripts following the established `NN_*.sh` convention (current harness ends at `08_cross_phase_smoke.sh`). Each scenario stays hermetic and uses `curl` + `jq` + `uuidgen` + `psql`. Mid-scenario `psql` time-travel is allowed (D-36-05 lineage) when logged in the scenario comment + VERIFICATION-LOG.

### Webhook delivery strategy in the runbook
- **D-02:** The runbook **simulates `payment.succeeded` by POSTing a trusted-IP webhook payload to our own webhook endpoint locally** (deterministic, runnable against the `docker compose up` stack in CI/operator context without waiting on real ЮKassa callbacks). This is the source of truth for VER-01's automated walkthrough. Driving the **real ЮKassa sandbox dashboard** is a *separate* concern owned by VER-03 (owner-recorded evidence), not the runbook.

### Race-test harness
- **D-03:** Race tests **mirror the existing integration race-test pattern** — `db_session_real_commit` fixture + `httpx ASGITransport` (see `tests/integration/payments/test_payments_refund_race.py`, `tests/integration/memberships/test_freeze_race.py`). **No new `pytest-postgresql`/`testcontainers` dependency** — the real-commit fixture already provides the un-SAVEPOINTed real-Postgres semantics race serialization needs. VER-02 covers 4 scenarios: (a) concurrent `payment.succeeded` double-delivery (Redis dedup + DB UNIQUE both proven), (b) webhook after Redis restart (DB UNIQUE catches), (c) concurrent refund webhook + manual refund command (partial UNIQUE on `refund_of` arbitrates), (d) concurrent kopecks↔rubles edge values (Decimal precision proven).

### VER-03 sandbox evidence classification
- **D-04:** VER-03 is an **operator-pending deliverable** modeled on the Phase 52 CARRY-01/02 pattern: this phase ships the evidence-directory scaffolding + README (capture instructions, expected screenshots/session log) at `.planning/handoff/v1.7-yookassa-sandbox-evidence/`, but the actual owner-recorded sandbox session requires real ЮKassa sandbox credentials and is completed by the operator. The **technical criteria (VER-01, VER-02, VER-04, VER-05) are verified automatically** in-phase; VER-03 is marked operator-pending in VERIFICATION.md (mirrors how CARRY-01/02 were tracked in Phase 52).

### Regression hard-cap + DEFER-46-03
- **D-05:** Inline-regression protocol follows the **D-36-15..17 lineage**: reproduce → fix as its own commit `fix(53-NN): REG-53-XX <desc>` → re-run → log in VERIFICATION-LOG.md `overrides:`. **Hard cap = 5**; the phase blocks at >5 and rolls excess to the v1.8 DEFER list (VER-04). DEFER-46-03 (VER-05): re-run the v1.6 VER-09 scenario-08 cron-chain circuit-breaker open-state fixture, now exercising the **FISCAL-05 circuit breaker**, and assert parity with the v1.6 expectation that the v1.6 run recorded only as PARTIAL.

### Claude's Discretion
- Exact scenario numbering/splitting inside `v1_7_runbook.sh`, the precise VERIFICATION.md / VERIFICATION-LOG.md layout, and per-race-test file naming are left to the planner — follow existing harness + integration-test conventions.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements & roadmap
- `.planning/REQUIREMENTS.md` §VER-01..VER-05 — the five verification requirements this phase satisfies (lines ~84-88).
- `.planning/ROADMAP.md` → "Phase 53: Milestone Verification" detail block — goal + 5 success criteria.
- `.planning/STATE.md` → Outstanding-items table — DEFER-46-03 (this phase closes it) and the surrounding v1.7 DEFER ledger.

### Existing verification harness (reuse — D-01)
- `apps/backend/scripts/verify/_lib.sh` — hermetic per-scenario cookie-jar + helper conventions.
- `apps/backend/scripts/verify/_preflight.sh` — 10-check readiness gate.
- `apps/backend/scripts/verify/08_cross_phase_smoke.sh` — closest analog for a cross-feature scenario; new v1.7 scenarios extend the `NN_*.sh` series past 08.
- `apps/backend/scripts/verify/README.md` — sweep recipe + inline-regression fix protocol (hard cap 5) + env-var preflight.

### Race-test precedents (mirror — D-03)
- `apps/backend/tests/integration/payments/test_payments_refund_race.py` — partial-UNIQUE-on-`refund_of` race + `db_session_real_commit` rationale (TOCTOU note).
- `apps/backend/tests/integration/test_concurrent_expiring_cron_double_pings_race.py` — concurrent double-delivery / idempotency race pattern.
- `apps/backend/tests/integration/memberships/test_freeze_race.py` — original partial-UNIQUE race template referenced by the refund race.

### v1.7 modules under verification
- `apps/backend/app/modules/online_payments/` — sell orchestrator + webhook FSM + `tasks.py` (notification enqueue) under test.
- `apps/backend/app/modules/fiscal_receipts/` — fiscal FSM + FISCAL-05 circuit breaker (DEFER-46-03 parity target).
- `apps/backend/app/modules/payments/` — refund path + `refund_of` partial UNIQUE.

### Prior-phase context (carried decisions)
- `.planning/phases/52-cross-channel-notifications-v1-6-carry-out/52-CONTEXT.md` — CARRY-01/02 operator-pending pattern reused for VER-03 (D-04).
- `.planning/phases/51-fiscal-fsm-refunds/51-CONTEXT.md` — fiscal FSM + refund decisions feeding the race + runbook scenarios.

### Operator one-shot cron runners (DEFER-46-03 re-run — D-05)
- `apps/backend/scripts/run_expiring_cron_once.py` — pattern for one-shot operator cron runners reused to exercise the circuit-breaker fixture.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/verify/_lib.sh` + `_preflight.sh`: hermetic-scenario scaffolding — `v1_7_runbook.sh` orchestrator and new `NN_*.sh` scenarios bolt onto these (D-01).
- `db_session_real_commit` integration fixture: provides un-SAVEPOINTed real-Postgres commits required for race serialization — no new test dependency needed (D-03).
- Phase 52 CARRY-01/02 evidence-dir + README + STATE/VERIFICATION tracking convention: template for VER-03 operator-pending handling (D-04).
- `run_expiring_cron_once.py`: one-shot operator cron runner pattern reusable for the DEFER-46-03 circuit-breaker re-run (D-05).

### Established Patterns
- Numbered hermetic scenario scripts (`01_*.sh`..`08_*.sh`), each owning its cookie jar; new scenarios continue the series.
- Race tests assert the **DB constraint** (partial/full UNIQUE) is the race arbiter, NOT app-layer guards (TOCTOU is real); use real-commit fixture, count exactly `1×200 + (N-1)×409`.
- Inline-regression fix-as-own-commit protocol `fix(NN-MM): REG-NN-XX` + VERIFICATION-LOG `overrides:` (D-36-15..17 lineage), hard cap 5.

### Integration Points
- Runbook drives the live `docker compose up` stack (backend + Postgres 16 + Redis 7 + ARQ worker + Telegram bot + migrate) via `curl`/`psql`.
- Webhook simulation POSTs a trusted-IP `payment.succeeded`/`refund.succeeded` payload directly to the online_payments webhook endpoint.
- DEFER-46-03 re-run exercises the FISCAL-05 circuit breaker in `app/modules/fiscal_receipts/`.
</code_context>

<specifics>
## Specific Ideas

- VER-01 walkthrough order is fixed by the success criterion: sell → `payment.succeeded` webhook → membership activated → `fiscal_receipts` row confirmed → refund → idempotency-key replay returns idempotent 200.
- VER-02 must explicitly prove BOTH layers of dedup independently: Redis dedup AND the DB UNIQUE (by simulating a Redis-restart gap so the DB UNIQUE is the sole catcher).
- VER-03 evidence path is locked: `.planning/handoff/v1.7-yookassa-sandbox-evidence/`.
</specifics>

<deferred>
## Deferred Ideas

- Any v1.7 functionality defect beyond the ≤5 inline-regression cap → roll to **v1.8 DEFER** (VER-04). Do not expand phase scope to fix.
- MailHog inbox assertions (DEFER-46-05) remain v1.9-optional; not pulled into this runbook.
- Pre-existing tree-wide CI tech-debt (DEFER-46-04: ruff/format/mypy) stays out of scope — does not count against the regression cap.

*No scope creep surfaced — discussion stayed within verification-phase boundary.*
</deferred>

---

*Phase: 53-milestone-verification*
*Context gathered: 2026-05-23*
