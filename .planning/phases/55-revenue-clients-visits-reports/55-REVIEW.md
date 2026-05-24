---
phase: 55-revenue-clients-visits-reports
reviewed: 2026-05-24T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - apps/backend/app/modules/reports/constants.py
  - apps/backend/app/modules/reports/schemas.py
  - apps/backend/app/modules/reports/service.py
  - apps/backend/app/modules/reports/repository.py
  - apps/backend/app/modules/reports/router.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/tests/integration/reports/conftest.py
  - apps/backend/tests/integration/reports/test_reports_revenue.py
  - apps/backend/tests/integration/reports/test_reports_clients.py
  - apps/backend/tests/integration/reports/test_reports_visits.py
  - apps/backend/tests/unit/test_permissions.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 55: Code Review Report

**Reviewed:** 2026-05-24T00:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the Phase 55 reports module (revenue, clients, visits) across all production source files and integration tests. The implementation satisfies the primary security and correctness invariants: no SQL injection (f-string interpolation limited to an internal literal selected on a validated `Literal["day","month"]` enum; all user-supplied date values flow through `:from_date`/`:to_date` bind params), full read-only discipline (zero INSERT/UPDATE/DELETE, no `session.commit`/`flush`, no cross-module ORM imports), RBAC enforced on all three routes via `Depends(require_permission(Action.VIEW, Resource.REPORTS))`, and the 366-day cap plus `within` 1..30 guard applied consistently across all three service functions.

Two warnings were found. The first concerns a real behavioral inconsistency in `_pivot_revenue_buckets`: `by_method` accumulates refund rows (net behavior) while `by_subject_kind` excludes refund rows (gross behavior); the schema docstrings, the service docstring, the test file header comment, and the test function name are mutually inconsistent about which is correct, and no test assertion actually verifies `byMethod` values in a refund scenario. The second concerns `RevenueBucketBySubjectKind`'s class docstring, which opens with "Net kopecks split by subject kind" but then correctly states refunds are excluded — the "Net" label is factually wrong for that class. Two informational findings cover a missing exact-boundary test for the 366/367-day cap edge and silent data loss when an unrecognised payment method value is encountered in the pivot.

No critical/blocker-level issues were found.

---

## Warnings

### WR-01: `byMethod` refund-inclusion contradicts test description and creates asymmetric breakdown

**File:** `apps/backend/app/modules/reports/service.py:70` and `apps/backend/tests/integration/reports/test_reports_revenue.py:8`

**Issue:** `_pivot_revenue_buckets` accumulates **all** rows (including `subject_kind='refund'`) into `by_method`, so a cash sale of 100,000 kopecks followed by a cash refund of -100,000 kopecks produces `byMethod.cash = 0`. This is the net-payment-method model. At the same time, `by_subject_kind` excludes refund rows entirely, so `bySubjectKind.membership` stays at 100,000 (gross). These two fields inside the same `RevenueBucket` now carry semantically different things: one is net, the other is gross.

The test file docstring (line 8) asserts the _opposite_ contract: `"byMethod carries only positive sale amounts"`. The function `test_by_method_positive_sale_amounts_refund_excluded_from_subject_kind` (line 94) does not contain any assertion on `byMethod` values in the refund scenario, so the contradiction is untested and cannot be caught by the suite. If downstream consumers (frontend) rely on the gross interpretation (positive sale amounts by method), they will show incorrect cash/online breakdowns whenever refunds are present.

The service docstring on line 70 (`"by_method accumulates by method ('cash' / 'online') for ALL rows"`) and the `RevenueBucketByMethod` class docstring (`"Net kopecks split by payment method"`) are internally consistent with the net model. The discrepancy is therefore: **either the test description (and presumably the D-01 intent of "refunds fold into netKopecks only") is correct, and the code is wrong; or the code is correct, and the test description plus schema class docstring are wrong.**

**Fix — Option A (refunds excluded from byMethod, matching test description and D-01 "fold into netKopecks"):**
```python
# service.py, inside the for row loop, replace the method block:
method = str(row["method"])
# Only accumulate non-refund rows into by_method (gross sale amounts by method)
if subject_kind != "refund":
    if method == "cash":
        by_method = RevenueBucketByMethod(
            cash=by_method.cash + total,
            online=by_method.online,
        )
    elif method == "online":
        by_method = RevenueBucketByMethod(
            cash=by_method.cash,
            online=by_method.online + total,
        )
```
Then add an explicit assertion in the test:
```python
# test_by_method_positive_sale_amounts_refund_excluded_from_subject_kind
assert bucket["byMethod"]["cash"] == 100000  # gross sale, refund excluded
assert bucket["byMethod"]["online"] == 0
```

**Fix — Option B (keep net model, fix the documentation):**
```python
# schemas.py, RevenueBucketByMethod:
"""Net kopecks split by payment method (includes refunds with negative sign)."""

# test_reports_revenue.py, line 8:
#   "byMethod carries net amounts per method (sale + refund signed sum); refund does not appear in bySubjectKind (D-01)."

# test function: rename to test_by_method_net_includes_refunds_subject_kind_is_gross
# add assertion:
assert bucket["byMethod"]["cash"] == 0  # net: 100000 + (-100000) = 0
```

One of these two options must be chosen and applied consistently to resolve the semantic ambiguity.

---

### WR-02: `RevenueBucketBySubjectKind` docstring opens with "Net kopecks" but describes gross (refund-excluded) amounts

**File:** `apps/backend/app/modules/reports/schemas.py:66`

**Issue:** The class docstring reads: `"Net kopecks split by subject kind for a single period bucket. Only positive sale kinds appear here. Refunds are folded into netKopecks on the parent RevenueBucket but not broken out here (D-01)."` The word "Net" in the opening sentence is factually incorrect: a field that explicitly excludes refund rows carries **gross** sale amounts, not net. This will mislead any consumer reading the schema.

**Fix:**
```python
class RevenueBucketBySubjectKind(ResponseData):
    """Gross sale kopecks split by subject kind for a single period bucket.

    Only positive sale kinds appear here. Refunds are folded into
    netKopecks on the parent RevenueBucket but not broken out here (D-01).
    """
```

---

## Info

### IN-01: No exact-boundary test for the 366 / 367-day range cap

**File:** `apps/backend/tests/integration/reports/test_reports_revenue.py:191` and `apps/backend/tests/integration/reports/test_reports_visits.py:237`

**Issue:** Both `test_range_over_366_days_returns_422_with_code` tests use `fromDate=2024-01-01&toDate=2026-01-01` (731-day difference), which is far above the cap. The exact boundary — `(to_date - from_date).days == 366` (allowed) and `.days == 367` (blocked) — is never exercised. This leaves the `> 366` vs `>= 366` boundary unverified by the test suite.

**Fix:** Add a parametrised boundary test:
```python
@pytest.mark.parametrize("to_date_str,expect_422", [
    ("2025-01-01", False),  # diff=365, allowed
    ("2025-01-02", False),  # diff=366, at cap — allowed
    ("2025-01-03", True),   # diff=367, over cap — blocked
])
async def test_revenue_range_cap_boundary(authed_client_owner, to_date_str, expect_422):
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2024-01-01", "toDate": to_date_str},
    )
    assert r.status_code == (422 if expect_422 else 200)
```

---

### IN-02: Unknown payment method values silently drop from `byMethod` while still contributing to `net_kopecks`

**File:** `apps/backend/app/modules/reports/service.py:97-106`

**Issue:** The `if method == "cash": / elif method == "online":` chain has no `else` branch. If a future payment row carries an unrecognised method value, `total` is added to `net_kopecks` (line 94, before the method check) but silently omitted from `by_method`. The resulting `RevenueBucket` will have `netKopecks != byMethod.cash + byMethod.online`, a silent inconsistency with no log or error to surface it.

The same pattern exists for `subject_kind`, but there the `else` (refund) behaviour is explicitly documented and intentional. The method chain has no such documented intent for unknown values.

**Fix:** Add an `else` branch with structured logging to surface unknown values at runtime without blocking the response:
```python
else:
    import structlog
    structlog.get_logger().warning(
        "reports.unknown_payment_method",
        method=method,
        period=period_str,
        total_kopecks=total,
    )
```

---

_Reviewed: 2026-05-24T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
