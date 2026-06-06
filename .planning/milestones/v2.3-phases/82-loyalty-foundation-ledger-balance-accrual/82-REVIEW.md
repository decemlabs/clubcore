---
phase: 82-loyalty-foundation-ledger-balance-accrual
reviewed: 2026-06-05T12:00:00Z
depth: deep
files_reviewed: 33
files_reviewed_list:
  - apps/backend/.importlinter
  - apps/backend/alembic/env.py
  - apps/backend/alembic/versions/0054_loyalty_ledger.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/core/audit.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/modules/clients/models.py
  - apps/backend/app/modules/clients/router.py
  - apps/backend/app/modules/clients/service.py
  - apps/backend/app/modules/loyalty/__init__.py
  - apps/backend/app/modules/loyalty/models.py
  - apps/backend/app/modules/loyalty/permissions.py
  - apps/backend/app/modules/loyalty/router.py
  - apps/backend/app/modules/loyalty/schemas.py
  - apps/backend/app/modules/loyalty/service.py
  - apps/backend/openapi.json
  - apps/backend/tests/integration/test_loyalty_accrual.py
  - apps/backend/tests/integration/test_loyalty_grant.py
  - apps/backend/tests/integration/test_loyalty_read.py
  - apps/backend/tests/integration/test_phase51_audit_chain_invariants.py
  - apps/backend/tests/integration/test_route_introspection.py
  - apps/backend/tests/unit/test_audit_taxonomy.py
  - apps/backend/tests/unit/test_loyalty_audit_events.py
  - apps/client-pwa/src/data/index.js
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/screens/ProfileScreen.identity.test.jsx
  - apps/client-pwa/src/screens/ProfileScreen.jsx
  - apps/client-pwa/src/screens/ProfileScreen.membership.test.jsx
  - apps/client-pwa/src/screens/sheets/CardSheet.wiring.test.jsx
  - apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx
  - apps/client-pwa/src/screens/sheets/LoyaltySheet.test.jsx
  - packages/api-client/src/schema.d.ts
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: findings
---

# Phase 82: Code Review Report

**Reviewed:** 2026-06-05T12:00:00Z
**Depth:** deep
**Files Reviewed:** 33
**Status:** findings

## Summary

Phase 82 delivers the loyalty ledger (append-only, BigInteger signed kopecks), welcome-bonus accrual (idempotent via partial UNIQUE index + `ON CONFLICT DO NOTHING`), owner-grant endpoint, client-facing read endpoints, and a PWA `LoyaltySheet`. The architecture is sound on the security-critical axes: IDOR is correctly prevented (client_id always from `require_client()` principal), the owner-guard (`require_owner_for_loyalty_grant`) is correctly wired before `verify_csrf` in the dependency chain, the partial UNIQUE predicate in `on_conflict_do_nothing` exactly mirrors the migration index definition, and the audit payload schema is properly registered in `AUDIT_PAYLOAD_SCHEMAS` before any callsite ships. No UPDATE/DELETE paths exist on `loyalty_ledger`.

One critical-severity defect exists: the `reason` field in `LoyaltyGrantRequest` has no Pydantic-level length constraint, while the DB column is `VARCHAR(255)`. A request with `reason` longer than 255 characters bypasses Pydantic validation and hits the database, which raises a `DataError` that surfaces as an unhandled 500 instead of a user-friendly 422. Two quality warnings are also present.

## Structural Findings (fallow)

No structural pre-pass (structural_findings block) was provided for this review.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: `reason` field has no max-length guard — oversized input yields 500 instead of 422

**File:** `apps/backend/app/modules/loyalty/schemas.py:59`

**Issue:** `LoyaltyGrantRequest.reason` is declared as a bare `str` with no `Field(max_length=255)` constraint. The corresponding DB column is `String(255)` (VARCHAR(255) in PostgreSQL), which enforces the limit server-side. A caller supplying a `reason` string longer than 255 characters passes Pydantic validation, reaches `pg_insert(LoyaltyLedger).values(reason=payload.reason, ...)` in `owner_grant_loyalty`, and receives an unhandled `sqlalchemy.exc.DataError` ("value too long for type character varying(255)"). Because no `try/except` wraps the insert in the service, and `DataError` is not a subclass of `AppError`, the exception handler cannot map it to a 422 — the request returns 500. This violates the API contract (owner sees an internal error for their own input mistake) and leaks a stack trace in non-production error modes.

**Fix:**
```python
# apps/backend/app/modules/loyalty/schemas.py
from pydantic import Field

class LoyaltyGrantRequest(BackendSchemaBase):
    amount_kopecks: int
    reason: str = Field(max_length=255)
    category: Literal["promo", "referral", "manual"]
```

Note: no change is needed for `category` (it is a `Literal` with a closed set, so overlong values already produce a 422) or `amount_kopecks` (integer, no length concept). The `reason` fix is sufficient to close the 500 path.

---

## Warnings

### WR-01: `amount_kopecks` positive-guard lives only in service, not in schema — inconsistent validation layer

**File:** `apps/backend/app/modules/loyalty/schemas.py:58`

**Issue:** The docstring on `LoyaltyGrantRequest` says "must be > 0 (validated in service)" and the service raises `LoyaltyGrantNegativeError` on `<= 0`. This is correct behaviour, but the validation lives in `service.py` rather than in the schema via `Field(gt=0)`. The established codebase convention (Pydantic-first validation) is that schema-layer constraints are the first line of defence: they produce automatic 422 responses with `fields` populated by the `_request_validation_handler`, whereas service-layer guards produce bespoke `ValidationAppError` subclasses. Having the guard only in the service means the error response shape for `amount_kopecks=0` differs from what a Pydantic constraint would produce: the service raises `grant_amount_must_be_positive` (422, custom code) while a `Field(gt=0)` would raise `validation_error` (422, standard fields response). Both are 422, but the inconsistency means API consumers must handle two distinct shapes for the same input mistake. Promoting the constraint to the schema would make the service check redundant but not wrong.

**Fix:**
```python
# apps/backend/app/modules/loyalty/schemas.py
from pydantic import Field

class LoyaltyGrantRequest(BackendSchemaBase):
    amount_kopecks: int = Field(gt=0)   # schema-layer guard; service check becomes belt-and-suspenders
    reason: str = Field(max_length=255) # see CR-01
    category: Literal["promo", "referral", "manual"]
```

Keeping the service-level check as belt-and-suspenders is fine. The schema constraint fires first and produces the standard `validation_error` shape.

---

### WR-02: `BonusHistorySheet.handleRefresh` calls `historyQuery.refetch()` on the stale page key when user is past page 1

**File:** `apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx:157-162`

**Issue:** `handleRefresh` is an `async` function that calls `setPage(1)` (a queued React state update), `setAllItems([])`, then immediately `await historyQuery.refetch()`. When the user has scrolled to page 2 or beyond, `historyQuery` is still keyed on the old page (`clientPortalKeys.loyaltyHistory(2)` etc.) at the time `refetch()` is invoked, because the `setPage(1)` state update has not yet been applied — React batches state updates and they take effect only after the current render cycle completes. The `refetch()` therefore re-fetches the old page, not page 1. The component recovers on the next render (because `page` becomes 1 and `historyQuery` switches to the page-1 key), but the `refetch()` call is a wasted network round-trip to the wrong page. More subtly, `setAllItems([])` clears the list before the old-page data arrives; if the old-page refetch resolves before the re-render with `page=1`, the `useEffect([historyData, page])` fires with `page` still at the old value and the `else` branch appends items into an empty array — flashing old-page content until the page-1 query returns.

**Fix:** Reset `allItems` and page together and invalidate rather than calling `refetch()` on a stale query handle:

```jsx
// apps/client-pwa/src/screens/sheets/LoyaltySheet.jsx
const handleRefresh = async () => {
  setAllItems([])
  setPage(1)
  // Invalidate both queries; React Query will re-fetch automatically
  // with the current (page=1 after re-render) key. No stale refetch.
  await balanceQuery.refetch()
  // historyQuery will re-mount with page=1 key after state update —
  // invalidate instead of refetch so the right key is targeted.
  await queryClient.invalidateQueries({ queryKey: clientPortalKeys.loyaltyHistory(1) })
}
```

If a `queryClient` reference is not already in scope, add `const queryClient = useQueryClient()` inside `BonusHistorySheet`. Alternatively, keep `await historyQuery.refetch()` but guard it with a check that page is already 1, so the pattern is harmless for the first-page case (the common case).

---

## Info

### IN-01: `ClientLoyaltyHistoryItem` omits `category` and `reason` — intentional but undocumented

**File:** `apps/backend/app/modules/loyalty/schemas.py:26-36`

**Issue:** The `ClientLoyaltyHistoryItem` response exposes only `id`, `type`, `amount_kopecks`, and `created_at`. The `category` and `reason` fields stored on `owner_grant` rows are not surfaced. The history SQL query (`service.py:256`) does not SELECT those columns. This is a reasonable product decision (keep admin-only context off the client-facing history view), but it is not documented anywhere in the schema or service docstring. A future developer adding a "bonus details" sheet will not know why those fields are absent.

**Fix:** Add a brief docstring note:

```python
class ClientLoyaltyHistoryItem(ResponseData):
    """Single ledger row for the paginated history endpoint (LOYL-02).

    Wire: { id, type, amountKopecks, createdAt }
    amountKopecks is signed: positive = accrual, negative = redemption (Phase 83).

    NOTE: category and reason from owner_grant rows are intentionally omitted
    from the client-facing response (admin-only context per 82-UI-SPEC.md §3.2).
    A future "bonus detail" endpoint may expose them under a separate admin path.
    """
    id: UUID
    type: str
    amount_kopecks: int
    created_at: datetime
```

---

_Reviewed: 2026-06-05T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
