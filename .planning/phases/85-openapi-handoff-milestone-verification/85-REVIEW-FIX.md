---
phase: 85-openapi-handoff-milestone-verification
fixed_at: 2026-06-06T06:48:00Z
review_path: .planning/phases/85-openapi-handoff-milestone-verification/85-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 85: Code Review Fix Report

**Fixed at:** 2026-06-06T06:48:00Z
**Source review:** .planning/phases/85-openapi-handoff-milestone-verification/85-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2 (WR-01, WR-02 — Warning tier)
- Fixed: 2
- Skipped: 0

In-scope was `critical_warning`. The review had 0 critical, 2 warning, 1 info.
The single info finding (IN-01, cosmetic comment header) is out of scope and was
not addressed. Only `packages/api-client/src/schema.contract.test.ts` was touched;
the byte-stable machine-generated artifacts (`apps/backend/openapi.json`,
`packages/api-client/src/schema.d.ts`) were left untouched per the contract-freeze
constraint.

Both fixes verified green from repo root equivalent:
- `tsc --noEmit` on the api-client package → exit 0, no errors.
- `vitest run src/schema.contract.test.ts` → 10/10 tests passed.

## Fixed Issues

### WR-01: `_ClientCheckoutMembershipBody` guard does not verify `loyaltyRedeemKopecks`

**Files modified:** `packages/api-client/src/schema.contract.test.ts`
**Commit:** 7fbc3a75
**Applied fix:** Replaced the `_ClientCheckoutMembershipBody` type alias (which only
asserted `requestBody` was non-`never`) with `_ClientCheckoutLoyaltyField`, which
resolves and asserts the actual field type
`NonNullable<...['requestBody']>['content']['application/json']['loyaltyRedeemKopecks']`.
The field path was verified against `schema.d.ts` first: the membership checkout
POST requestBody (`client_checkout_membership`, schema.d.ts:7262-7266) is an
always-present `{ content: { "application/json": ClientCheckoutRequest } }`, and
`ClientCheckoutRequest.loyaltyRedeemKopecks?: number | null` (schema.d.ts:3691)
is a real (non-`never`) type, so `AssertNonNever<...>` resolves to `true` at compile
time. Updated the `_v23Checks` tuple member to reference the renamed alias and
softened the inline comment to state the guard proves the loyalty field is present.
If the optional field were removed from the schema, the field-access type would
collapse to `never` and the type build would fail — the guard now has the teeth its
comment claims.

### WR-02: v2.3 runtime `it(...)` asserts only tuple length, not guard values

**Files modified:** `packages/api-client/src/schema.contract.test.ts`
**Commit:** 67ad9481
**Applied fix:** Changed the runtime assertion from `expect(_v23Checks).toHaveLength(4)`
to `expect(_v23Checks).toEqual([true, true, true, true])`. The new assertion pairs
the element count with the boolean expectation, so a local `vitest` run carries signal
independent of the separate `tsc` typecheck step: if a future edit lets a guard tuple
slot admit `false`, the runtime test fails too.

---

_Fixed: 2026-06-06T06:48:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
