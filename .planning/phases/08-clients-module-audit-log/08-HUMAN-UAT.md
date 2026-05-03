---
status: partial
phase: 08-clients-module-audit-log
source: [08-VERIFICATION.md]
started: "2026-05-03T13:00:00Z"
updated: "2026-05-03T13:00:00Z"
---

## Current Test

[awaiting human testing]

## Tests

### 1. ILIKE wildcard escape (CR-01)
expected: Submitting `?q=%25` (URL-encoded `%`) returns only rows with literal `%` in the search columns, not the full table. Confirm pg_trgm GIN indexes are still used (EXPLAIN should show Bitmap Index Scan on ix_clients_*_trgm for prefix-bounded queries).
why_human: Goal text says "ILIKE on ФИО + phone (pg_trgm GIN)". Implementation passes literal user input into the LIKE pattern without escaping `%`/`_`/`\`. This is a real security warning (CR-01 in 08-REVIEW.md): a caller with VIEW,CLIENTS can craft `?q=%` to walk the client base. The behaviour observably matches goal text (the `test_list_q_filter_matches_last_name_or_phone` integration test passes), so the goal is technically achieved — but the deviation from secure ILIKE practice must be explicitly accepted or scheduled.
result: [pending]

### 2. `session.rollback()` inside service (CR-02)
expected: Either keep the explicit `await session.rollback()` inside `create_client`/`update_client` (current code) — and accept that under SAVEPOINT-shared sessions this rolls the OUTER transaction — or remove it and rely on `get_db` teardown. The 239-test suite passes today because the conflict path leaves no other pending mutations to lose; goal is met. A future caller staging multiple operations could lose work.
why_human: Goal is mutation + audit landed in one transaction; on the IntegrityError path no audit row is staged anyway, so the rollback does not erase any audit context that was already there. Whether the eager rollback is acceptable for future call patterns is an architectural decision that human review must resolve.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
