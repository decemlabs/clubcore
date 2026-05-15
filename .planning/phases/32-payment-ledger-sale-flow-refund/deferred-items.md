# Phase 32 — Deferred Items

Out-of-scope discoveries during Phase 32 plan execution.

---

## Plan 32-01

### Pre-existing failure: `tests/integration/test_rbac_parity.py::test_owner_only_count_is_fifteen`

Status: failing before Plan 32-01 changes. Asserts `len(OWNER_ONLY) == 15`, but the
constant grew to 26 in Phase 30 INFRA-19 (verified by re-reading the source: 9 v1.1
entries + 6 v1.2 + 11 v1.4 = 26).

The assertion is stale; the comment in `app/core/permissions.py:55` correctly reads
"26 entries after Phase 30 INFRA-19". The test fixture was not updated in Phase 30.

Fix scope: ~1 line in `tests/integration/test_rbac_parity.py` (`assert len(OWNER_ONLY) == 26`).
Logged for a future Phase 30 retrospective fix or a follow-up tech-debt sweep — NOT
in scope for Plan 32-01.
