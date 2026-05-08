# Deferred Items — Phase 23

## Pre-existing test failure (out of scope for Phase 23)

**File:** `tests/integration/visits/test_visits_self_checkin.py::test_self_checkin_happy_path`
**Error:** `AttributeError: 'tuple' object has no attribute 'channel'` at line 67
**Status:** Pre-existing before Phase 23 started (confirmed via git stash)
**Impact:** 1 test failure when running full suite; does not affect Phase 23 features
**Owner:** Whoever owns the visits/self-checkin module; likely a Phase 22 or earlier regression

## Pre-existing mypy errors (out of scope for Phase 23)

130 mypy errors exist across 15 files, all pre-dating Phase 23:
- `tests/unit/test_config.py` — 65 errors
- `tests/integration/auth/test_sessions_endpoints.py` — 45 errors (our file, pre-existing pattern)
- Others: various test files with minor type annotation issues

These errors were present before Phase 23 execution began and are not caused by Phase 23 changes.
