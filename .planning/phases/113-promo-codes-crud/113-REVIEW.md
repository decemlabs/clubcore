---
phase: 113-promo-codes-crud
reviewed: 2026-06-15T00:00:00Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - apps/admin-app/src/components/modals/PromoCodeModal.tsx
  - apps/admin-app/src/features/promoCodes/api.ts
  - apps/admin-app/src/features/promoCodes/schemas.ts
  - apps/admin-app/src/pages/plans/PlansPage.tsx
  - apps/admin-app/src/pages/plans/components/PromoCard.tsx
  - apps/admin-app/src/shared/session/can.test.ts
  - apps/admin-app/src/shared/session/can.ts
  - apps/admin-app/src/shared/session/registry.ts
  - apps/backend/alembic/versions/0072_promo_codes_description.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/core/permissions.py
  - apps/backend/app/modules/promo_codes/models.py
  - apps/backend/app/modules/promo_codes/repository.py
  - apps/backend/app/modules/promo_codes/router.py
  - apps/backend/app/modules/promo_codes/schemas.py
  - apps/backend/app/modules/promo_codes/service.py
  - apps/backend/tests/integration/promo_codes/__init__.py
  - apps/backend/tests/integration/promo_codes/conftest.py
  - apps/backend/tests/integration/promo_codes/test_promo_codes_crud.py
  - apps/backend/tests/integration/promo_codes/test_promo_codes_rbac.py
  - apps/backend/tests/integration/test_rbac_parity.py
  - apps/backend/tests/unit/test_permissions.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 113: Code Review Report

**Reviewed:** 2026-06-15
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

Adversarial review of the promo-codes admin CRUD phase: new `PROMO_CODES` RBAC
resource, four write/read endpoints with CSRF + owner-only gating, an additive
Alembic migration, and a frontend management UI wired into PlansPage.

The RBAC substrate is sound and internally consistent: `permissions.py`,
`can.ts`, `registry.ts`, `test_rbac_parity.py`, `test_permissions.py`, and
`can.test.ts` all agree at **45** OWNER_ONLY entries, with `(CREATE|EDIT|DELETE,
PROMO_CODES)` owner-only and `(LIST, PROMO_CODES)` retained for reception. CSRF
ordering (RBAC-04: `require_permission` before `verify_csrf`) is correct in all
three mutation endpoints. The migration is additive, nullable, with a correct
`down_revision` (0071 → 0072, confirmed head; table created in 0046). The
percentage→kopecks discount conversion is mathematically correct in both
directions, and `model_post_init` ValueError on the create schema correctly
surfaces as 422 (verified against Pydantic 2.13 runtime).

However, there is **one BLOCKER**: the frontend reuses the list-shaped
`PromoCodeSchema` (which requires `usedCount`) to parse the create/update
responses, but the backend `PromoCodeResponse` deliberately omits `usedCount`.
Every successful create/edit will throw a ZodError on the client, surfacing as a
generic failure toast while the row is actually persisted — the exact mock↔real
wire-shape drift the phase brief flagged. The integration test suite never
exercises the FE parse path, so it does not catch this.

## Critical Issues

### CR-01: FE create/update parse the response with the list schema, which requires `usedCount` the backend never returns — every successful write throws a ZodError

**File:** `apps/admin-app/src/features/promoCodes/api.ts:90` and `:113`
**Issue:**
`useCreatePromoCode` and `useUpdatePromoCode` both validate the mutation
response with `PromoCodeSchema.parse((raw).data)`. `PromoCodeSchema`
(`schemas.ts:22-36`) declares `usedCount: z.number()` and `createdAt:
z.string()` as **required**.

The backend create/edit response is `PromoCodeResponse`
(`apps/backend/app/modules/promo_codes/schemas.py:127-141`), which has **no
`used_count`/`usedCount` field** — that aggregate is list-only
(`PromoCodeListItemResponse`). The CRUD integration test even asserts this on
purpose: `assert "usedCount" not in data` (`test_promo_codes_crud.py:71`).

Result: on a successful 201/200, `PromoCodeSchema.parse` throws a `ZodError`
(missing `usedCount`). In `PromoCodeModal.handleSubmit`, that ZodError lands in
`onError → handlePromoError`, which (since it is not an `ApiError`) shows the
generic toast «Не удалось сохранить промокод. Попробуйте ещё раз.». The success
toast never fires and the modal never closes — even though the promo code was
created/updated server-side. This is the v3.0/v3.1 mock↔real drift failure mode
verbatim, and the test suite misses it because it never drives the FE parse path.

**Fix:** Parse mutation responses with a schema that matches `PromoCodeResponse`
(no `usedCount`). Either add a dedicated response schema or make `usedCount`
optional only for the write path:
```ts
// schemas.ts — response shape for POST/PATCH (no usedCount aggregate)
export const PromoCodeWriteResponseSchema = PromoCodeSchema.omit({ usedCount: true })
export type PromoCodeWriteData = z.infer<typeof PromoCodeWriteResponseSchema>

// api.ts — useCreatePromoCode / useUpdatePromoCode
return PromoCodeWriteResponseSchema.parse((raw as { data: unknown }).data)
```
Then ensure `handleEditPromo` (which feeds `promo` back into the modal) and any
optimistic cache update tolerate the missing `usedCount`. Add a FE-level test (or
extend the integration drift test) that round-trips the create response through
the actual Zod schema the hook uses.

## Warnings

### WR-01: Update schema skips the percentage ≤ 100% cap that the create schema enforces

**File:** `apps/backend/app/modules/promo_codes/schemas.py:66-96`
**Issue:** `PromoCodeCreateRequest` has `model_post_init` rejecting
`discount_type == "percentage" and discount_value > 10000` (>100%). The partial
`PromoCodeUpdateRequest` has **no** such check. An owner can `PATCH` a percentage
promo to `discountValue: 50000` (500%). It is mitigated downstream only because
`validate_promo_code` clamps `new_amount_kopecks` to ≥ 0 and then raises
`PromoNotApplicableError` when the result is ≤ 0 — but invalid data is persisted
and the FE inline guard (`isPercentTooHigh`) is client-side only, so an API
caller bypasses it entirely.
**Fix:** Add a cross-field validator on the update schema that enforces the same
cap when `discount_type == 'percentage'` (or when type is unchanged but a new
value is supplied), e.g. a `model_validator(mode="after")` that reads the
effective type. Because PATCH may omit `discount_type`, validate against the
existing row's type in the service layer if the request does not set it.

### WR-02: No backend validation that `valid_until >= valid_from`

**File:** `apps/backend/app/modules/promo_codes/schemas.py:37-38, 77-78`
**Issue:** Neither create nor update validates the validity window. The FE has an
inline guard (`PromoCodeModal.tsx:142-143`, `isDateRangeInvalid`), but it is
client-side only and disables the button — a direct API call (or the
not-yet-regenerated OpenAPI client) can persist `valid_from > valid_until`,
yielding a promo that `validate_promo_code` treats as both not-yet-active and
expired depending on `now`, effectively a silently-dead code with no operator
feedback.
**Fix:** Add a `model_validator(mode="after")` on `PromoCodeCreateRequest` (and an
effective-window check in `update_promo_code` after merging the patch onto the
loaded row) rejecting `valid_until < valid_from` with a stable error code.

### WR-03: `discount_type` can be changed on update without re-validating the existing `discount_value` semantics

**File:** `apps/backend/app/modules/promo_codes/service.py:502-547`,
`apps/backend/app/modules/promo_codes/schemas.py:73`
**Issue:** `update_promo_code` applies `model_dump(exclude_unset=True)` field by
field. If a caller sends only `{"discountType": "percentage"}` on a promo whose
stored `discount_value` is `50000` (originally 500 ₽ in kopecks for a fixed
code), the row becomes "500%" with no cap check (compounds WR-01). The two fields
are semantically coupled but validated independently.
**Fix:** When `discount_type` changes, require `discount_value` to be supplied in
the same request, or re-run the percentage cap / fixed-kopecks validation against
the merged (existing + patch) values in the service before commit.

### WR-04: Generic `IntegrityError` re-raise can surface as an opaque 500 on non-uniqueness DB violations

**File:** `apps/backend/app/modules/promo_codes/service.py:492-499, 541-547`
**Issue:** Both create and update catch `IntegrityError`, map the
`uq_promo_codes_code_alive` case to a 409, and `raise` everything else. Other DB
CHECK violations reachable from the update path — e.g.
`ck_promo_codes_discount_type` (if `discount_type` is somehow bypassed) or
`ck_promo_codes_discount_value_positive` — would bubble as a raw `IntegrityError`
→ unhandled 500, leaking a DB error to the client rather than a domain-coded 422.
The create path is mostly shielded by field validators, but the update path's
looser validation (WR-01/WR-03) makes a CHECK-constraint 500 reachable.
**Fix:** After the uniqueness branch, map known CHECK-constraint names to
`PromoCodeValidationError` (422), and only re-raise truly unexpected integrity
errors. Alternatively close WR-01/WR-03 so the DB CHECK is never the first line of
defense.

### WR-05: `usePromoCodes` query is `enabled` purely on client-side `can()`, so reception sees a perpetual loading state instead of data if `can()` and backend ever drift

**File:** `apps/admin-app/src/features/promoCodes/api.ts:66`
**Issue:** `enabled: can(role, 'list', 'promo-codes')`. Today reception is
allowed `list`, so this is fine. But the page treats `isPending` (the state when a
query is `enabled:false`) as a loading spinner (`PlansPage.tsx:446`). If a future
RBAC change moves `(list, promo-codes)` into OWNER_ONLY without updating this
page, reception would render an infinite `<PageLoading />` rather than the
intended `Lock` EmptyState (which only renders on a real 403 error). The pattern
matches sibling features but is a latent UX trap.
**Fix:** When `can(role,'list','promo-codes')` is false, render the `Lock`
EmptyState directly (mirror `promoCodesForbidden`) rather than relying on a
never-resolving pending query; or key the spinner on `isFetching && enabled`.

## Info

### IN-01: PromoCard renders the promo code twice (plain text + `<code>` chip)

**File:** `apps/admin-app/src/pages/plans/components/PromoCard.tsx:80-85`
**Issue:** The header renders `{p.code}` as bold text and then immediately again
inside a `<code>` chip, so the code appears duplicated (e.g. "SUMMER25 `SUMMER25`").
Looks like a copy/paste artifact from the design template — likely the bold span
was meant to be a human label, not the code.
**Fix:** Render the code once (keep the `<code>` chip, drop the leading `{p.code}`),
or replace the leading text with a real title/description field.

### IN-02: Dead/no-op `hint` expression in the valid-until Field

**File:** `apps/admin-app/src/components/modals/PromoCodeModal.tsx:363`
**Issue:** `hint={isDateRangeInvalid ? undefined : undefined}` always evaluates to
`undefined` regardless of the condition — dead code. The actual error message is
rendered separately below (lines 371-375), so the ternary serves no purpose.
**Fix:** Remove the `hint` prop entirely from this `Field`.

### IN-03: `parseIntField` can inject `NaN` into the submit payload

**File:** `apps/admin-app/src/components/modals/PromoCodeModal.tsx:64-68, 160-161`
**Issue:** For a non-integer string `parseIntField` returns `NaN`, which is placed
into `raw.maxUses` / `raw.perClientLimit`. `safeParse` then fails on
`z.number().int()` and the user gets the generic «Проверьте правильность...»
toast with no field-level hint. The number `<input step={1}>` makes this hard to
hit, but it is reachable via paste. Minor robustness gap.
**Fix:** Return `undefined` (or surface a targeted field error) instead of `NaN`
for non-integer input, or strip `NaN` values before `safeParse`.

### IN-04: `_read_plan_price` interpolates a table name into raw SQL (safe today, fragile pattern)

**File:** `apps/backend/app/modules/promo_codes/service.py:297-307`
**Issue:** The `table` variable is f-string-interpolated into the SQL text
(`# noqa: S608`). It is currently safe because `table` is derived from an internal
`kind` mapping, not user input, and the ternary only ever yields two literal
constants. Flagged for awareness: if `kind` ever becomes more directly
caller-influenced, this becomes an injection vector. No change required now.
**Fix:** None required. If extended, validate `kind` against an allowlist before
selecting the table (the current ternary effectively does this — keep it that way).

---

_Reviewed: 2026-06-15_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
