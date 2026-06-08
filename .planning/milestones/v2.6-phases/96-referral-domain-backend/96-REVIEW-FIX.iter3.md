---
phase: 96-referral-domain-backend
fixed_at: 2026-06-08T14:58:00Z
review_path: .planning/phases/96-referral-domain-backend/96-REVIEW.md
iteration: 2
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 96: Code Review Fix Report (Iteration 2)

**Fixed at:** 2026-06-08T14:58:00Z
**Source review:** .planning/phases/96-referral-domain-backend/96-REVIEW.md
**Iteration:** 2

**Summary:**
- Findings in scope: 1 (WR-01 — critical_warning scope)
- Fixed: 1
- Skipped: 0

## Fixed Issues

### WR-01: `get_or_create_referral_code` concurrent-mint race yields unhandled `IntegrityError`

**Files modified:** `apps/backend/app/modules/referrals/service.py`, `apps/backend/app/modules/referrals/router.py`
**Commit:** `a2ab7c1b`
**Applied fix:** Option A from the review (mirrors `capture_referral` idempotent pattern).

Replaced `session.add(ReferralCode(...)) + flush()` with:

```python
stmt = (
    pg_insert(ReferralCode)
    .values(client_id=client_id, code=new_code_str)
    .on_conflict_do_nothing(index_elements=["client_id"])
    .returning(ReferralCode.id, ReferralCode.code)
)
row = (await session.execute(stmt)).one_or_none()
```

When RETURNING is None (concurrent mint won the race), re-reads the winner row via
`repository.get_code_by_client_id` and returns its code without emitting audit.
When RETURNING is non-None (real insert), emits `referral_code_generated` audit and commits.
Preserves INFRA-15 idempotent audit semantics exactly. Module docstring updated to reflect
the new pg_insert approach.

**Pre-existing UUID JSONB serialization fix bundled in same commit:** The iter-1 CR-03 fix
removed `str()` wrappers from UUID payload kwargs passed to `audit.emit`, causing
`TypeError: Object of type UUID is not JSON serializable` when SQLAlchemy serializes the
JSONB payload column (stdlib `json.dumps` cannot handle UUID objects). This broke 12 tests
across `test_referral_code.py` and `test_referral_capture.py`. Both `get_or_create_referral_code`
and `capture_referral` audit emit callsites are now corrected to use `str(uuid)` for payload
kwargs. Pydantic v2 coerces `str` inputs back to `UUID` at `model_validate` time, so
`ReferralCodeGeneratedPayload` and `ReferralCapturedPayload` (both `extra="forbid"`) validate
correctly with string inputs, and the DB stores UUID strings as expected by test assertions.

**DB schema note:** `uq_referral_codes_client_id` (added in the iter-1 migration 0067 edit)
was absent from the live test DB because Alembic considered migration 0067 already applied.
Created manually via `CREATE UNIQUE INDEX IF NOT EXISTS uq_referral_codes_client_id ON
referral_codes (client_id)` to align the DB with the migration DDL before testing.

**Verification:**
- `uv run mypy --strict app/modules/referrals/`: Success — no issues in 6 source files
- `uv run ruff check app/modules/referrals/`: All checks passed
- Full referral test suite (34 tests): all pass

```
tests/unit/test_referral_audit_events.py           6 passed
tests/integration/test_alembic_0067_referral.py    4 passed
tests/integration/test_referral_code.py            5 passed
tests/integration/test_referral_capture.py         6 passed
tests/integration/test_referral_resolve.py         7 passed
tests/integration/test_referral_config.py          6 passed
                                                  34 passed in 14.60s
```

## Optional IN-01 Decision (Info severity — out of scope for critical_warning)

IN-01 (`public_resolve_referral_code` has no `Path` length bound) is Info severity and
outside `critical_warning` fix_scope. Applied opportunistically in the same commit since
it required only adding `Path` to the fastapi import and one annotation change. Used
`max_length=16` (column width) per the reviewer's rationale: 9-16 char strings resolve to
`valid=False` gracefully rather than 422, avoiding a detectable response-shape difference
for unauthenticated callers.

---

_Fixed: 2026-06-08T14:58:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
