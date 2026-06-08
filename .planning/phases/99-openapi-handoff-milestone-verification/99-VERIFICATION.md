---
phase: 99-openapi-handoff-milestone-verification
verified: 2026-06-08T17:05:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
note: "Initial verification (no prior VERIFICATION.md). Contract-freeze phase — byte-stability, _v26Checks, drift gate, CISO-01, vitest, Redocly, mypy, lint-imports all re-run by the verifier (not trusted from SUMMARY)."
carried_forward_human:  # Milestone-level operator tasks — NOT HND-01 / phase-99 gate items
  - test: "Live manual verification of the referral flow in the running client PWA (deep-link → onboarding capture → first-purchase bilateral bonus accrual)"
    expected: "Friend opens /i/<code>, code auto-fills onboarding, referrer↔referee bound, both bonuses land on loyalty balance on first paid subscription"
    why_human: "Requires a running stack + live YooKassa test payment; documented in STATE.md/98-HUMAN-UAT as a deferred operator pass, explicitly out of scope for the autonomous gate"
  - test: "Dev Postgres clean re-migrate (docker compose down -v + migrate + seed)"
    expected: "Fresh DB migrates and seeds cleanly with v2.6 referral schema"
    why_human: "Operator manual-verify concern (STATE.md blocker); the pytest gate rebuilds/seeds its own schema, so this does NOT gate HND-01 — deferred to operator"
---

# Phase 99: OpenAPI Handoff + Milestone Verification — Verification Report

**Phase Goal:** Все endpoint'ы v2.6 зафиксированы в byte-stable контракте; полный milestone gate зелёный
**Verified:** 2026-06-08T17:05:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

This is a contract-freeze phase. Rather than trusting SUMMARY claims, the verifier re-ran the byte-stability regenerations, the `_v26Checks` tuple inspection, the staff drift gate vs `9b28ba2f`, the CISO-01 byte-parity test, vitest, Redocly, mypy `--strict`, and lint-imports directly.

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | `openapi.json` and `schema.d.ts` regenerate byte-stably; CI `git diff --exit-code` clean on both | ✓ VERIFIED | Re-ran `ENVIRONMENT=dev uv run python -m scripts.export_openapi` → `git diff --exit-code openapi.json` returned clean (484421 bytes). Re-ran `pnpm -F @clubcore/api-client codegen` (openapi-typescript 7.13.0) → `git diff --exit-code schema.d.ts` clean. Both artifacts unchanged by fresh regen. |
| 2 | `_v26Checks` `AssertNonNever` tuple covers all new v2.6 path×method combos with runtime `toHaveLength(N)` | ✓ VERIFIED | `schema.contract.test.ts:628-651` declares 8 `AssertNonNever` guards (6 path×method: `/i/{code}` GET, `/client/referral/code` GET, `/client/referral/summary` GET, `/client/referral/capture` POST, `/referral/config` GET+PUT; + 2 realized JSON bodies: capture body, config-put body); tuple `= [true×8]`; `line 709: expect(_v26Checks).toHaveLength(8)`. Vitest: 21 tests pass incl. the v2.6 case. |
| 3 | Staff contract byte-identical to Phase 95 baseline (drift gate green); CISO-01 no-edit guard passes | ✓ VERIFIED | `diff` of staff subset (three-prefix exclusion: `/api/v1/client`+`/api/v1/i/`+`/api/v1/referral`) between `9b28ba2f` and working tree → zero diff. No `/referral` or `/i/{code}` path leaked into staff subset. Baseline `9b28ba2f` contains 0 referral paths (purely additive). `test_byte_parity.py` (CISO-01): 3 passed — Role.CLIENT absent, permissions.py + can.ts frozen. |
| 4 | Full milestone gate green: pytest + mypy --strict + lint-imports + vitest + Redocly | ✓ VERIFIED | Redocly lint exit 0 (1 expected WS-101 warning, 0 errors). `mypy --strict app/modules/referrals` → no issues (6 files). `lint-imports` exit 0 (3 contracts kept; warnings are pre-existing stale ignores). Vitest 21/21. CISO-01 byte-parity 3/3. Audit/route-introspection fixture tests 18/18. Referral 6 endpoints present + Referral-tagged in openapi.json. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `apps/backend/app/main.py` | Referral tag entry in OPENAPI_TAGS after Messaging, before Clients | ✓ VERIFIED | Tag names at lines: Messaging (164) → Referral (173) → Clients (184). D-64-TAG-ORDER preserved. |
| `apps/backend/app/modules/referrals/router.py` | client_router retagged; all routes → Referral | ✓ VERIFIED | 0 `tags=["Client-Portal"]` literals; 3 `tags=["Referral"]` declarations. |
| `apps/backend/openapi.json` | byte-stable frozen v2.6 spec w/ referral surface | ✓ VERIFIED | 5 referral path keys present; all 6 ops `tags == ["Referral"]`; Referral in top-level tags array; byte-stable (git diff clean after regen). |
| `packages/api-client/src/schema.d.ts` | regenerated TS types incl. referral surface | ✓ VERIFIED | Contains `/api/v1/client/referral/code`; byte-stable (git diff clean after codegen). |
| `packages/api-client/src/schema.contract.test.ts` | `_v26Checks` forward-guard tuple | ✓ VERIFIED | 8-entry tuple + `toHaveLength(8)` it() inside describe. |
| `.planning/REQUIREMENTS.md` | HND-01 [x]; all v2.6 IDs complete | ✓ VERIFIED | HND-01 `[x]`, traceability row "Complete"; zero unchecked REFER-*/HND-* IDs. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `main.py` OPENAPI_TAGS | `openapi.json` | `export_openapi` | ✓ WIRED | Referral tag emitted; all 6 ops carry it. |
| `referrals/router.py` | `openapi.json` | FastAPI auto-emit | ✓ WIRED | All 6 path×method present under Referral tag. |
| `openapi.json` | `schema.d.ts` | `openapi-typescript` codegen | ✓ WIRED | schema.d.ts contains referral paths; byte-stable. |
| `schema.contract.test.ts` | `schema.d.ts` | `AssertNonNever<paths[...]>` | ✓ WIRED | All 8 guards compile to `true`; vitest passes. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| HND-01 | 99-01, 99-02 | All v2.6 endpoints frozen in byte-stable openapi.json + schema.d.ts; _v26Checks covers new path×method; staff contract byte-intact (drift gate green); full milestone gate green | ✓ SATISFIED | All 4 ROADMAP success criteria independently re-verified above. REQUIREMENTS.md marks HND-01 `[x]` / Complete; all 7 sibling REFER-01..07 IDs already `[x]`. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| openapi.json byte-stable | regen + `git diff --exit-code openapi.json` | clean (484421 bytes) | ✓ PASS |
| schema.d.ts byte-stable | `codegen` + `git diff --exit-code schema.d.ts` | clean | ✓ PASS |
| 6 referral ops present + Referral-tagged | jq path-key + tag assertions | true | ✓ PASS |
| Staff drift gate vs 9b28ba2f | jq three-prefix-exclusion diff | zero diff | ✓ PASS |
| No referral leak in staff subset | jq key filter | none | ✓ PASS |
| _v26Checks vitest | `pnpm -F @clubcore/api-client test` | 21/21 pass | ✓ PASS |
| CISO-01 byte-parity | `pytest test_byte_parity.py` | 3 passed | ✓ PASS |
| Audit/route fixtures | `pytest audit + route_introspection` | 18 passed | ✓ PASS |
| Redocly lint | `npx @redocly/cli lint openapi.json` | exit 0 (1 warning, 0 errors) | ✓ PASS |
| mypy --strict referrals | `uv run mypy --strict app/modules/referrals` | no issues (6 files) | ✓ PASS |
| lint-imports | `uv run lint-imports` | exit 0 | ✓ PASS |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | No TBD/FIXME/XXX/HACK markers in any phase-99 modified file | — | — |

### Commit Audit

All 5 declared commits exist on the merged tree: `4cc16d81`, `c557ecd8` (99-01); `62f1f517`, `92ed6cbd`, `6e4a40f5` (99-02).

### Human Verification Required

None gating this phase. Two milestone-level operator tasks (live referral-flow manual verification with a running stack + live YooKassa test payment; dev-DB clean re-migrate) were explicitly deferred during the autonomous run per STATE.md / 98-HUMAN-UAT. They are **carried-forward milestone items, NOT HND-01 gate items** — the pytest gate rebuilds/seeds its own schema and the contract-freeze deliverables are all programmatically verifiable. Recorded in frontmatter `carried_forward_human` for operator follow-up; they do not affect phase-99 status.

### Gaps Summary

None. All four ROADMAP success criteria are provably true in the codebase, re-run by the verifier rather than trusted from SUMMARY:
1. Both `openapi.json` and `schema.d.ts` regenerate byte-stably with clean `git diff --exit-code`.
2. `_v26Checks` is an 8-entry `AssertNonNever` tuple (6 ops + 2 JSON bodies) with `toHaveLength(8)`; vitest green.
3. Staff subset is byte-identical to baseline `9b28ba2f` (additive-only; zero leak) and CISO-01 byte-parity passes.
4. Full gate green: mypy --strict, lint-imports, pytest (CISO-01 + referral/audit fixtures), vitest, Redocly. The 6 referral endpoints are present under the Referral tag.

HND-01 is correctly marked `[x]` / Complete with zero unchecked v2.6 requirement IDs remaining.

---

_Verified: 2026-06-08T17:05:00Z_
_Verifier: Claude (gsd-verifier)_
