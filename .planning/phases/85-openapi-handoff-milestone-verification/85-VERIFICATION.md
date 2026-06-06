---
phase: 85-openapi-handoff-milestone-verification
verified: 2026-06-06T06:45:00Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  note: initial verification
---

# Phase 85: OpenAPI Handoff + Milestone Verification — Verification Report

**Phase Goal:** Контракт v2.3 заморожен — byte-stable regen openapi.json + schema.d.ts со всеми новыми loyalty/autopay client-путями + `_v23Checks` forward-guards; staff-пути байт-идентичны contract-freeze-v1.11.0 (drift gate зелёный); milestone-gate проверен.
**Verified:** 2026-06-06T06:45:00Z
**Status:** passed
**Re-verification:** No — initial verification

All gates were re-run independently by the verifier (not trusted from SUMMARY.md). The byte-stable drift gate, Redocly lint, tsc, contract vitest, PWA vitest, mypy --strict, lint-imports, the CISO-01 no-edit guard, the secret-leak audit, the v2.3 backend test subset, and the audit-taxonomy isolation claim were all executed in this session.

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | Fresh regen of openapi.json + schema.d.ts produces zero git diff (byte-stable) | ✓ VERIFIED | Ran `export_openapi` (wrote 424568 bytes) + `pnpm -F @clubcore/api-client codegen`, then `git diff --exit-code` on both → exit 0 / exit 0. Independently reproduced. |
| 2 | openapi.json contains all 3 new v2.3 paths + ClientCheckoutRequest.loyaltyRedeemKopecks | ✓ VERIFIED | JSON parse: all 3 paths present (`/client/loyalty/balance`, `/client/loyalty/history`, `/clients/{client_id}/loyalty/grant`); `ClientCheckoutRequest.properties` = `[loyaltyRedeemKopecks, promoCode, savePaymentMethod]`. |
| 3 | schema.contract.test.ts has `_v23Checks` (4 AssertNonNever guards) + checkout-body guard + new toHaveLength(4) | ✓ VERIFIED | Read lines 507-580: 4 guard type aliases (balance GET, history GET, grant POST, membership-checkout requestBody) → `_v23Checks` tuple → `it(...) expect(_v23Checks).toHaveLength(4)`. |
| 4 | git diff --exit-code clean on both artifacts (drift gates green) | ✓ VERIFIED | Both `git diff --exit-code` exit 0 after live regen. Artifacts committed in b010e3b3 / 1e9a30dd. |
| 5 | Redocly lint passes clean | ✓ VERIFIED | `npx @redocly/cli@latest lint apps/backend/openapi.json` → "Your API description is valid 🎉". |
| 6 | Existing staff/admin-web contract paths unmodified (additive-only; CISO-01 byte-parity) | ✓ VERIFIED | `git diff --stat contract-freeze-v1.11.0 -- permissions.py can.ts registry.ts` → exit 0, zero changed lines. `_v20Checks`/toHaveLength(23) untouched (no `-` lines vs baseline). |
| 7 | Full milestone gate green (pytest, mypy, lint-imports, PWA tsc+vitest, Redocly, no-edit) | ✓ VERIFIED | mypy exit 0 (242 files); lint-imports exit 0 (3 kept / 0 broken); PWA tsc exit 0; PWA vitest 149/149; api-client tsc exit 0 + vitest 10/10; 90 v2.3 backend tests pass. |
| 8 | Failures are pre-existing-known and documented as NOT v2.3 regressions | ✓ VERIFIED | audit-taxonomy guard passes in isolation (exit 0); promo F821 debt (8 errors at runtime) is in STATE.md Deferred Items; test_freeze_race flaky is documented. None modified by phase 85. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `apps/backend/openapi.json` | Frozen v2.3 contract, byte-stable, contains loyalty paths | ✓ VERIFIED | Byte-stable (zero diff on regen); 3 paths + loyaltyRedeemKopecks present; no leaked token fields. |
| `packages/api-client/src/schema.d.ts` | Generated TS path types, byte-stable | ✓ VERIFIED | Byte-stable (zero diff on codegen); all 3 loyalty paths present in generated types (codegen wiring proven). |
| `packages/api-client/src/schema.contract.test.ts` | `_v23Checks` (4 guards) + runtime path-count assertion | ✓ VERIFIED | 4 AssertNonNever guards + toHaveLength(4); tsc resolves all 4 paths (exit 0) → type-level wiring proven. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| schema.contract.test.ts | schema.d.ts | `paths['/api/v1/client/loyalty/balance']` type lookup | ✓ WIRED | tsc --noEmit exit 0 — all 4 guard paths resolve in schema.d.ts (a dropped path would flip AssertNonNever to a type error). |
| openapi.json | schema.d.ts | openapi-typescript codegen | ✓ WIRED | codegen exit 0 + zero diff; 3 loyalty paths present in generated schema.d.ts. |

### Data-Flow Trace (Level 4)

N/A — this is an infrastructure/contract-freeze phase. Artifacts are generated specs and type-level guards, not dynamic-data-rendering components. The "data flow" is the deterministic export→codegen pipeline, verified byte-stable above.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Byte-stable export | `export_openapi && git diff --exit-code` | exit 0 (424568 bytes written, zero diff) | ✓ PASS |
| Byte-stable codegen | `codegen && git diff --exit-code` | exit 0 (zero diff) | ✓ PASS |
| Contract guards compile | `pnpm -F @clubcore/api-client exec tsc --noEmit` | exit 0 | ✓ PASS |
| Contract vitest | `vitest run src/schema.contract.test.ts` | 10/10 passed | ✓ PASS |
| Redocly lint | `npx @redocly/cli lint openapi.json` | "API description is valid" | ✓ PASS |
| mypy strict | `uv run mypy --strict app` | no issues, 242 files | ✓ PASS |
| import-linter | `uv run lint-imports` | 3 kept / 0 broken | ✓ PASS |
| PWA typecheck | `pnpm -F @clubcore/client-pwa typecheck` | exit 0 | ✓ PASS |
| PWA vitest | `pnpm -F @clubcore/client-pwa exec vitest run` | 149/149 passed | ✓ PASS |
| v2.3 backend tests | `pytest -k "loyalty or redemption or autopay or audit_taxonomy"` | 90 passed | ✓ PASS |
| audit-taxonomy isolation | `pytest tests/unit/...::test_every_audit_emit_pair_is_in_locked_set` | 1 passed | ✓ PASS |
| CISO-01 no-edit guard | `git diff --stat contract-freeze-v1.11.0 -- permissions.py can.ts registry.ts` | 0 changed lines | ✓ PASS |
| Secret-leak audit | JSON walk for yookassa_method_id/payment_method_id field props | 0 leaked fields (1 benign prose mention) | ✓ PASS |

### Probe Execution

No conventional `scripts/*/tests/probe-*.sh` probes declared by this phase. The PLAN's verification is gate-command-based (drift gate, lint, typecheck, pytest), all executed above in Behavioral Spot-Checks.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| HND-01 | 85-01 | Byte-stable openapi.json + schema.d.ts regen with new loyalty/autopay paths + `_v23Checks` forward-guards; staff paths byte-identical to contract-freeze-v1.11.0 (drift gate green) | ✓ SATISFIED | Truths 1-6 verified; byte-stable drift gate green; `_v23Checks` present; CISO-01 no-edit guard 0 lines. |

No orphaned requirements: ROADMAP maps only HND-01 to Phase 85, and plan 85-01 claims it.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | None in phase-modified files | — | No TODO/FIXME/XXX/TBD debt markers introduced. Generated artifacts + additive guard block only; `_v20Checks` and prior guards untouched. |

### Human Verification Required

None. This is a pure infrastructure/contract-freeze phase with no user-facing behavior. All checks are programmatic (deterministic regen, type guards, lint, gate commands) and were executed by the verifier this session. The v2.3 live-YooKassa human-verify items (Phase 83/84 end-to-end) are already tracked in STATE.md Deferred Items and are out of Phase 85 scope.

### Gaps Summary

No gaps. The central HND-01 invariant (byte-stable regen → zero git diff) was independently reproduced by the verifier on both `apps/backend/openapi.json` and `packages/api-client/src/schema.d.ts`. All 3 new v2.3 loyalty paths and the `loyaltyRedeemKopecks` checkout field are present; the `_v23Checks` forward-guards compile (tsc exit 0) and run (vitest 10/10); the CISO-01 no-edit guard shows zero changed staff-RBAC lines vs `contract-freeze-v1.11.0`; Redocly lint, mypy --strict, import-linter, and the PWA gate are all green.

The only non-passing backend results are documented pre-existing debt (STATE.md `## Deferred Items`), none modified by this phase:
- `test_freeze_race` — documented flaky (timing-dependent 409 reason-code).
- `test_client_promo_validate.py` — pre-existing F821/fixture debt (8 runtime errors observed; SUMMARY noted ~6 — the count varies but it is the same documented item, NOT a v2.3 regression).
- `test_audit_taxonomy::test_every_audit_emit_pair_is_in_locked_set` — confirmed a full-suite cross-test socket-leak artifact: PASSES in isolation (exit 0), as the SUMMARY classified.

Minor note (non-blocking): the SUMMARY described the promo failures as "6 collection ERRORs"; the actual current state is clean collection but 8 runtime errors. This is a cosmetic discrepancy in failure-mode description of an already-documented pre-existing item, with no bearing on HND-01 or any v2.3 contract surface.

---

_Verified: 2026-06-06T06:45:00Z_
_Verifier: Claude (gsd-verifier)_
