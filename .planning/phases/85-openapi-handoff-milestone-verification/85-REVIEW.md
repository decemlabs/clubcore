---
phase: 85-openapi-handoff-milestone-verification
reviewed: 2026-06-06T00:00:00Z
depth: standard
files_reviewed: 1
files_reviewed_list:
  - packages/api-client/src/schema.contract.test.ts
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 85: Code Review Report

**Reviewed:** 2026-06-06T00:00:00Z
**Depth:** standard
**Files Reviewed:** 1
**Status:** issues_found

## Summary

Reviewed the single hand-written change for Phase 85: the `_v23Checks` block
(lines 507-533) plus its runtime `it(...)` assertion (lines 578-580) added to
`packages/api-client/src/schema.contract.test.ts`. The two other changed files
(`openapi.json`, `schema.d.ts`) are machine-generated and out of scope per the
phase brief.

Verification performed against the regenerated `schema.d.ts`:

- All four asserted v2.3 paths exist and expose the asserted method:
  `/api/v1/client/loyalty/balance` GET (schema.d.ts:892-914),
  `/api/v1/client/loyalty/history` GET (schema.d.ts:916+),
  `/api/v1/clients/{client_id}/loyalty/grant` POST (schema.d.ts:1433-1451),
  `/api/v1/client/checkout/memberships/{plan_id}` POST requestBody
  (schema.d.ts:7253-7266).
- The guards have real teeth: CI (`.github/workflows/ci.yml:142`) runs
  `tsc --noEmit` across the api-client package, so a missing path key (direct
  property-access error) or a `never`-collapsed operation (`AssertNonNever`
  → `false` assigned to a `true`-typed tuple slot) fails the type build.

The addition is structurally consistent with the eight prior version blocks and
is substantively correct. No correctness or security defects. Findings below are
quality/robustness issues: one guard is weaker than its comment claims, and the
runtime assertion (matching pre-existing file convention) is near-vacuous.

## Warnings

### WR-01: `_ClientCheckoutMembershipBody` guard does not verify `loyaltyRedeemKopecks` — comment overclaims

**File:** `packages/api-client/src/schema.contract.test.ts:524-526`
**Issue:** The inline comment (lines 517-518) states this guard "proves
ClientCheckoutRequest (carrying loyaltyRedeemKopecks) is realised." It does not.
The guard only asserts that the `requestBody` member is non-`never`:

```ts
type _ClientCheckoutMembershipBody = AssertNonNever<
  paths['/api/v1/client/checkout/memberships/{plan_id}']['post']['requestBody']
>
```

In the generated schema (schema.d.ts:7262-7266) `requestBody` is an always-present
`{ content: { "application/json": ClientCheckoutRequest } }` object. This path was
already realised before v2.3 (the membership checkout POST shipped in Phase 71).
The `loyaltyRedeemKopecks` field (schema.d.ts:3691, `loyaltyRedeemKopecks?: number | null`)
is *optional*, so even if it were removed from `ClientCheckoutRequest` entirely the
`requestBody` type would remain non-`never` and this guard would still pass. The
REDM-01 contract surface this comment claims to lock is therefore not actually
guarded — the test would not catch its regression.

**Fix:** Assert the field itself, not just body presence:

```ts
// Proves the REDM-01 loyaltyRedeemKopecks field is present on the checkout body.
type _ClientCheckoutLoyaltyField = AssertNonNever<
  NonNullable<
    paths['/api/v1/client/checkout/memberships/{plan_id}']['post']['requestBody']
  >['content']['application/json']['loyaltyRedeemKopecks']
>
```

If pinning the exact field is judged out of scope, instead soften the comment to
state the guard only confirms the checkout body type is realised — do not claim it
proves the loyalty field exists.

### WR-02: v2.3 runtime `it(...)` asserts only tuple length, not guard values

**File:** `packages/api-client/src/schema.contract.test.ts:578-580`
**Issue:** The runtime block checks `expect(_v23Checks).toHaveLength(4)` only. It
never asserts the elements are `true`. The real enforcement lives entirely at the
`tsc` layer; if `vitest run` were ever executed without the separate typecheck
step (e.g. a local `pnpm -F @clubcore/api-client test` during development), a
broken contract would still report a green test. The length check is satisfied by
the literal `[true, true, true, true]` array regardless of type correctness, so
the runtime assertion provides essentially no signal — it is a tsc-counter only.
This mirrors the pre-existing convention in the file (acknowledged in the
lines 537-539 comment), so it is not a regression, but the v2.3 block inherits the
weakness.

**Fix:** Make the runtime assertion non-vacuous so a local `vitest` run carries
signal independent of `tsc`:

```ts
it('compiles against the regenerated v2.3 Loyalty surface (Phases 82-84)', () => {
  expect(_v23Checks).toEqual([true, true, true, true])
})
```

`toEqual([true, true, true, true])` still passes trivially today, but pairs the
count and the boolean expectation; if a future edit lets a guard tuple admit a
`false` slot, the runtime test fails too. (Applying this to all version blocks
would be the consistent fix, but is optional cleanup beyond this phase.)

## Info

### IN-01: v2.3 block omits the explanatory header comment style used by peer blocks for the runtime test

**File:** `packages/api-client/src/schema.contract.test.ts:528-533`
**Issue:** Minor consistency nit. Every other static-check tuple in the file
carries a leading `// Static checks for vX.Y surface — each must resolve to true
at compile time.` comment (e.g. lines 377, 424, 476). The `_v23Checks` tuple
(line 528) has no such header line; the surrounding `// --- v2.3 surface ---`
banner documents the paths but not the tuple's compile-time-resolution contract.
Purely cosmetic; does not affect behavior.

**Fix:** Add the conventional one-line header above line 528:

```ts
// Static checks for v2.3 surface — each must resolve to true at compile time.
const _v23Checks: [
```

---

_Reviewed: 2026-06-06T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
