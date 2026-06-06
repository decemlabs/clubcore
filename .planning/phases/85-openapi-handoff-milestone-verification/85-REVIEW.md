---
phase: 85-openapi-handoff-milestone-verification
reviewed: 2026-06-06T00:00:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - packages/api-client/src/schema.contract.test.ts
findings:
  critical: 0
  warning: 0
  info: 1
  total: 1
status: clean
---

# Phase 85: Code Review Report

**Reviewed:** 2026-06-06T00:00:00Z
**Depth:** standard
**Status:** clean
**Files Reviewed:** 1
**Iteration:** 2 (re-review after --auto fix loop)

## Summary

Re-reviewed `packages/api-client/src/schema.contract.test.ts` after the two prior
Warning findings (WR-01, WR-02) were addressed. Both fixes are confirmed sound and
the edit introduced no new Critical or Warning issues. The sole remaining finding
is the pre-existing Info-severity cosmetic comment nit (IN-01), which is acceptable.

**WR-01 (RESOLVED — checkout-body field guard) — verified sound.**
The guard was replaced with `_ClientCheckoutLoyaltyField` (lines 524-528), which now
drills into the actual field:

```ts
type _ClientCheckoutLoyaltyField = AssertNonNever<
  NonNullable<
    paths['/api/v1/client/checkout/memberships/{plan_id}']['post']['requestBody']
  >['content']['application/json']['loyaltyRedeemKopecks']
>
```

Verified against the regenerated schema:
- `requestBody` is non-optional (schema.d.ts:7262, no `?`), so `NonNullable<...>` is a
  safe no-op and the chain resolves cleanly.
- `['content']['application/json']` resolves to `ClientCheckoutRequest` (schema.d.ts:7264).
- `['loyaltyRedeemKopecks']` resolves to the field type `number | null` declared at
  schema.d.ts:3691 (`loyaltyRedeemKopecks?: number | null`).

Because the field is optional, the property index yields `number | null | undefined`,
which `AssertNonNever` correctly evaluates to `true`. The guard's real protection is
the **property-existence** compile check: if `loyaltyRedeemKopecks` were removed from
`ClientCheckoutRequest`, the `['loyaltyRedeemKopecks']` index would become a
"property does not exist" TS error under strict mode and fail the `tsc --noEmit` CI
step. This is exactly the right semantic for an optional contract field, and the
inline comment (lines 517-518, "proves the REDM-01 loyaltyRedeemKopecks field is
present on the checkout body") is now accurate — no overclaim. The previously-noted
gap (a guard that would pass even if the field were deleted) is closed.

**WR-02 (RESOLVED — runtime assertion strengthened) — verified sound.**
Line 581 now reads `expect(_v23Checks).toEqual([true, true, true, true])`, replacing
the near-vacuous `.toHaveLength(4)`. The runtime assertion now pairs the element-count
expectation with the boolean-value expectation, so a future edit that lets a guard
slot resolve to `false` fails both the `tsc` build and a standalone `vitest` run. The
fix matches the prior review's recommended remediation verbatim.

**New-issue scan — clean.**
- The `_v23Checks` tuple type annotation (lines 530-535) still constrains each slot to
  its `AssertNonNever<...>` result type; any `never`-collapse fails at `tsc`. No
  regression in the static layer.
- `_ClientCheckoutLoyaltyField` is consumed by the `_v23Checks` tuple (line 534),
  satisfying `noUnusedLocals` — no dead/unused local introduced.
- No new imports, no `any`, no eval/exec, no secrets, no dangerous patterns. This is a
  pure type-level contract test with no runtime surface or security exposure.

No correctness, security, or robustness defects remain. Status set to `clean`.

## Info

### IN-01: v2.3 static-check tuple omits the conventional one-line header comment

**File:** `packages/api-client/src/schema.contract.test.ts:530`
**Issue:** Minor consistency nit (carried over from iteration 1, acknowledged
acceptable). Every other static-check tuple in the file carries a leading
`// Static checks for vX.Y surface — each must resolve to true at compile time.`
comment (e.g. lines 377, 424, 476). The `_v23Checks` tuple (line 530) lacks this
header; the `// --- v2.3 surface ---` banner documents the paths but not the tuple's
compile-time-resolution contract. Purely cosmetic; does not affect behavior.

**Fix:** Add the conventional one-line header above line 530:

```ts
// Static checks for v2.3 surface — each must resolve to true at compile time.
const _v23Checks: [
```

---

_Reviewed: 2026-06-06T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
