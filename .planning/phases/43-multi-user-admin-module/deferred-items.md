# Phase 43 — Deferred Items

Items discovered during phase execution that are out of scope for the
current plan but tracked here for resolution in a follow-up.

## Stale Test DB Rows (43-08 execution)

**Discovered:** 43-08 test execution
**Category:** test_pollution

While running `tests/integration/users/test_users_crud.py::test_list_users_paginated_envelope_no_password_leak`, the
`GET /api/v1/users?active=true` endpoint failed during Pydantic response
serialization because two stale rows existed in the `users` table from
prior test runs with `*@test.local` emails (RFC-2606 reserved TLD; rejected by
Pydantic v2 `EmailStr` validation):

  - `cr04-74a071716af54d17b005b515c1cf8ee6@test.local`
  - `cr04-rt-8ff426e586704057b9e998482ad4c0e1@test.local`

These rows leaked from earlier tests (CR-04 lineage hash prefix) that
bypassed the SAVEPOINT-rolled `db_session` fixture by issuing direct
commits outside the per-test transaction envelope.

**Workaround applied:** `DELETE FROM users WHERE email LIKE '%@test.local';`
executed manually before re-running 43-08 tests. No code change.

**Defer to:** v1.9 doc-debt / test-debt sweep — root cause is a CR-04 era
test that does not enrol in the SAVEPOINT pattern; fixing it requires
auditing the offending test file and aligning it with the Phase 5 D-22
discipline. Until then, fresh dev environments may need to repeat the
manual DELETE if CR-04 tests are re-run.

**Scope guard:** This pollution is NOT caused by Phase 43 code; the only
impact on 43-08 was a transient test failure that cleared once the
stale rows were dropped.
