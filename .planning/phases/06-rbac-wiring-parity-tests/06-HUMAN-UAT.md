---
status: partial
phase: 06-rbac-wiring-parity-tests
source: [06-VERIFICATION.md]
started: 2026-05-02T00:00:00Z
updated: 2026-05-02T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Run integration tests that require Postgres + Redis on CI
expected: |
  `cd apps/backend && uv run pytest tests/integration/auth/test_logout.py tests/integration/rbac/test_owner_only.py -v`
  passes all tests. Specifically:
    - test_logout_authenticated_without_csrf_header_returns_403 → 403 csrf_mismatch
    - test_logout_authenticated_with_wrong_csrf_header_returns_403 → 403 csrf_mismatch
    - test_logout_unauthenticated_returns_401 → 401 invalid_token (RBAC-04 canary, /logout)
    - test_logout_unauthenticated_returns_401_even_without_csrf → 401 invalid_token (RBAC-04 canary, dep-ordering)
    - test_owner_allowed_on_every_owner_only_pair[*] → 200 (9 parametrized)
    - test_reception_forbidden_on_every_owner_only_pair[*] → 403 forbidden (9 parametrized)
    - test_unauthenticated_returns_401_before_403[*] → 401 invalid_token (9 parametrized — RBAC-04 canary at OWNER_ONLY-matrix level)
    - test_reception_denial_emits_rbac_forbidden_event → audit emit verified end-to-end
result: [pending]

### 2. Spot-check that test_owner_only.py emits ≥28 parametrized runs
expected: |
  `cd apps/backend && uv run pytest tests/integration/rbac/test_owner_only.py --collect-only`
  reports ≥28 collected items (9 × 3 parametrized + 1 audit-emit smoke = 28).
  Already confirmed via collection: 28 items collected.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
