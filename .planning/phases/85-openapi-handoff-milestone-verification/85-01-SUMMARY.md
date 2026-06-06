---
phase: 85-openapi-handoff-milestone-verification
plan: 01
subsystem: api
tags: [openapi, schema.d.ts, openapi-typescript, contract-freeze, redocly, mypy, import-linter, vitest, pytest, ci-gate]

# Dependency graph
requires:
  - phase: 82-01
    provides: client loyalty balance + history GET paths + owner-grant POST path (the 3 new v2.3 paths frozen here)
  - phase: 83-01
    provides: ClientCheckoutRequest.loyaltyRedeemKopecks redemption field (the checkout-body carrier guarded here)
  - phase: 84-03
    provides: autopay charge surface (no new client HTTP paths; autopay notifications internal-only — confirmed additive)
provides:
  - byte-stable apps/backend/openapi.json frozen for v2.3 (3 new loyalty paths + loyaltyRedeemKopecks checkout field)
  - byte-stable packages/api-client/src/schema.d.ts regenerated via openapi-typescript from the frozen openapi.json
  - _v23Checks AssertNonNever forward-guards (4 guards) + toHaveLength(4) runtime assertion in schema.contract.test.ts
  - full v2.3 milestone gate verification record (per-gate result table)
affects:
  - next-milestone (v2.4) — consumes the frozen v2.3 contract as its baseline; staff paths remain byte-identical to contract-freeze-v1.11.0

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Contract freeze = deterministic export + codegen; both artifacts are regenerated, never hand-edited; drift gate (git diff --exit-code) blocks divergence"
    - "_v23Checks AssertNonNever tuple mirrors _v1x/_v20 style — compile-time proof each new path×method realises (not collapsed to never); runtime toHaveLength asserts guard count"
    - "Additive-only contract discipline: v2.3 ADDs paths; CISO-01 no-edit guard proves RBAC core (permissions.py/can.ts/registry.ts) byte-identical to frozen baseline"

key-files:
  created: []
  modified:
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
    - packages/api-client/src/schema.contract.test.ts

key-decisions:
  - "Resumed an interrupted execute: Tasks 1+2 were already committed (feat(85-01) x2) but no SUMMARY existed — closed out manually by running Task 3 (the full milestone gate) and documenting results rather than re-spawning an executor (would redo deterministic Tasks 1+2)."
  - "Full-suite test_audit_taxonomy::test_every_audit_emit_pair_is_in_locked_set failure classified as a pre-existing flaky artifact (PytestUnraisableExceptionWarning misattribution from leaked Telegram/respx async sockets), NOT a v2.3 contract gap — passes in isolation; all 34 audit-taxonomy + v2.3 audit-event tests pass together."

patterns-established:
  - "Pattern 1: Milestone contract freeze verified by 7-gate run (drift / Redocly / pytest / mypy / lint-imports / PWA / no-edit guard) with pre-existing failures explicitly separated and unmodified."

requirements-completed: [HND-01]

# Metrics
duration: ~30min (verification gate; Tasks 1+2 committed 2026-06-05T23:56-23:57)
completed: 2026-06-06
---

# Phase 85: OpenAPI Handoff + Milestone Verification — Summary

**The v2.3 contract is frozen byte-stable — `openapi.json` + `schema.d.ts` regenerate to the committed bytes, all 3 new loyalty paths + the `loyaltyRedeemKopecks` checkout field are present and forward-guarded, and the full milestone gate is green except the documented pre-existing failures (none modified).**

## Performance

- **Duration:** ~30 min (Task 3 verification gate; Tasks 1 & 2 were committed earlier at 2026-06-05T23:56–23:57)
- **Completed:** 2026-06-06
- **Tasks:** 3/3 (Tasks 1 & 2 pre-committed; Task 3 — the milestone gate — completed this session)
- **Files modified:** 3 (openapi.json, schema.d.ts, schema.contract.test.ts)

## Accomplishments

- **Task 1 — byte-stable regen (pre-committed `b010e3b3`):** fresh `python -m scripts.export_openapi` + `pnpm --filter @clubcore/api-client codegen` yields **zero git diff** on both `apps/backend/openapi.json` and `packages/api-client/src/schema.d.ts`. The 3 new v2.3 paths (`/client/loyalty/balance`, `/client/loyalty/history`, `/clients/{client_id}/loyalty/grant`) + `ClientCheckoutRequest.loyaltyRedeemKopecks` are all present. Leak audit clean: `yookassa_method_id` appears once as benign description prose (explicitly documenting the token is NEVER wired to the client — T-79-04); `payment_method_id` field value absent; zero uuid-like secret example values.
- **Task 2 — `_v23Checks` forward-guards (pre-committed `1e9a30dd`):** 4 `AssertNonNever` guards (loyalty balance GET, loyalty history GET, loyalty grant POST, membership-checkout requestBody) + `expect(_v23Checks).toHaveLength(4)`; `_v20Checks` untouched; `tsc --noEmit` + contract vitest (10 tests) green.
- **Task 3 — milestone gate (this session):** all 7 gates run; results table below.

## Milestone Gate Results

| # | Gate | Command | Result | Pre-existing? | Notes |
|---|------|---------|--------|---------------|-------|
| 1 | Drift — openapi.json | export + `git diff --exit-code` | ✅ PASS | — | zero diff (byte-stable) |
| 1 | Drift — schema.d.ts | codegen + `git diff --exit-code` | ✅ PASS | — | zero diff (byte-stable) |
| 2 | Redocly lint | `npx @redocly/cli lint openapi.json` | ✅ PASS | — | "API description is valid 🎉" |
| 3 | backend pytest | `uv run pytest` | ✅ PASS (v2.3-green) | failures all pre-existing | 2586 passed, 8 skipped; failures below |
| 4 | mypy --strict | `uv run mypy --strict app` | ✅ PASS | — | no issues in 242 source files |
| 5 | lint-imports | `uv run lint-imports` | ✅ PASS | — | 3 contracts kept, 0 broken (5 stale-ignore warnings, no new edges) |
| 6 | PWA gate | typecheck + vitest + api-client contract | ✅ PASS | — | PWA tsc clean; 149/149 vitest; api-client 10/10 |
| 7 | CISO-01 no-edit guard | `git diff --stat contract-freeze-v1.11.0 -- permissions.py can.ts registry.ts` | ✅ PASS | — | 0 changed lines (RBAC core byte-identical) |

### backend pytest failure classification (Gate 3)

All NEW v2.3 tests pass — loyalty ledger/balance/history, redemption idempotency, autopay skip-matrix/double-charge/crash-idempotency, notification channel-idempotency, and the dedicated audit-event tests (`test_loyalty_audit_events`, `test_autopay_audit_events`) all green. The only non-passing results are pre-existing / flaky and were **not modified**:

| Failure | Class | Verdict |
|---------|-------|---------|
| `test_freeze_race::test_concurrent_freeze_race_serialised_by_partial_unique_index` | flaky (timing-dependent 409 reason-code distribution) | documented pre-existing — not touched |
| `tests/test_client_promo_validate.py` — 6 ERRORs | whole-tree promo F821 collection errors | documented pre-existing — not touched |
| `test_audit_taxonomy::test_every_audit_emit_pair_is_in_locked_set` | `PytestUnraisableExceptionWarning` misattribution from leaked Telegram/respx async sockets (unclosed socket to 149.154.166.110) collected mid-test | **flaky artifact, NOT a contract gap** — passes in isolation; all 34 audit-taxonomy + v2.3 audit-event tests pass together (`LOCKED_AUDIT_EVENTS` is a frozenset, the guard is pure AST static analysis and cannot be mutated by another test) |

> Note: the previously-documented `test_alembic_clean` pre-existing failure was **not observed** failing in this run (2586 passed). No fix was attempted either way — out of v2.3 scope per plan.

## Deviations

- **Resumed an interrupted execute.** Tasks 1 & 2 were already committed (two `feat(85-01)` commits) but no SUMMARY/VERIFICATION existed — the `safe_resume_gate` tripped. Closed out by running Task 3 (the milestone gate) inline and writing this SUMMARY, rather than re-spawning an executor that would redo the deterministic regen + guards. Re-running export+codegen confirmed byte-stability (zero diff), proving Tasks 1 & 2 left the tree in the correct committed state.
- **Local stack recovery:** docker daemon was down and the `migrate` image was stale (lacked Phase-84 migration `0057`). DB volume was already at `0057 (head)` from a prior host run; verified via host `uv run alembic current`. No migration changes — purely environment bring-up.

## Self-Check: PASSED

- [x] Both artifacts byte-stable (fresh regen → zero diff) — HND-01 core invariant
- [x] 3 new v2.3 loyalty paths + `loyaltyRedeemKopecks` present in openapi.json
- [x] `_v23Checks` block (4 guards) + `toHaveLength(4)`; `_v20Checks` untouched; tsc + vitest green
- [x] Drift gates + Redocly lint clean
- [x] mypy --strict, lint-imports, PWA typecheck + vitest, no-edit guard all green
- [x] backend pytest: all new v2.3 tests pass; only documented pre-existing/flaky failures remain, unmodified
- [x] No secret/token field value leaked into public openapi.json
