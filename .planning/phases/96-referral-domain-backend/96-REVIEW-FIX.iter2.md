---
phase: 96-referral-domain-backend
fixed_at: 2026-06-08T00:00:00Z
review_path: .planning/phases/96-referral-domain-backend/96-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 96: Code Review Fix Report

**Fixed at:** 2026-06-08
**Source review:** .planning/phases/96-referral-domain-backend/96-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (3 Critical + 4 Warning; IN-01 out of scope for critical_warning fix_scope)
- Fixed: 7
- Skipped: 0

All fixes verified: `uv run mypy --strict app/modules/referrals/` clean,
`uv run ruff check app/modules/referrals/ alembic/versions/0067_referral_tables.py` clean,
34/34 tests pass.

## Fixed Issues

### CR-01 + WR-04: Missing commit — code mint and capture writes never persisted / inconsistent txn discipline

**Files modified:** `apps/backend/app/modules/referrals/service.py`
**Commit:** ff3873f2
**Applied fix:** Added `await session.commit()` at the end of the new-insert path in
`get_or_create_referral_code` and at the end of the real-insert path in `capture_referral`
(after the RETURNING-gated audit emit). Both now match the `update_referral_config` and
`gym.service.update_gym_info` pattern: service owns flush+commit (D-03). Module docstring
updated to reflect the unified discipline. The router handlers are untouched — they
correctly return `envelope(result)` with no commit call, matching the service-owns-commit
pattern.

Note: CR-01 and WR-04 are correlated (both concern transaction discipline in the same
module) and were fixed in a single atomic commit together with CR-03, WR-01, WR-02.

---

### CR-02: Missing UNIQUE constraint on `referral_codes.client_id`

**Files modified:** `apps/backend/alembic/versions/0067_referral_tables.py`
**Commit:** 9cd1725d
**Applied fix:** Replaced the plain non-unique `ix_referral_codes_client_id` index
(unique=False, using `op.f()`) with a UNIQUE index named `uq_referral_codes_client_id`
using a literal name (no `op.f()`) per 96-PATTERNS discipline — matching the
`uq_referral_captures_referee_client_id` naming convention. The migration docstring was
updated to document the new index. The `downgrade()` function was updated to drop
`uq_referral_codes_client_id` by its literal name before `op.drop_table("referral_codes")`.

---

### CR-03: Audit emit passes string UUIDs where payload schemas expect UUID objects

**Files modified:** `apps/backend/app/modules/referrals/service.py`
**Commit:** ff3873f2 (same commit as CR-01/WR-01/WR-02/WR-04)
**Applied fix:** In `get_or_create_referral_code`, changed `client_id=str(client_id)`
to `client_id=client_id` and `referral_code_id=str(code_row.id)` to
`referral_code_id=code_row.id`. In `capture_referral`, changed all four UUID kwargs
(`referee_client_id`, `referrer_client_id`, `referral_capture_id`, `referral_code_id`)
from `str(...)` to raw UUID objects. The structlog `_log.info()` calls retain `str(...)`
as structlog requires string values.

Note: The `capture_referral` function was rewritten for WR-01 (pg_insert pattern), so
`capture_id` (a UUID from RETURNING) is used directly as the raw UUID kwarg.

---

### WR-01: Concurrent captures raise unhandled 500 — TOCTOU on `get_capture_by_referee`

**Files modified:** `apps/backend/app/modules/referrals/service.py`
**Commit:** ff3873f2 (same commit as CR-01/CR-03/WR-02/WR-04)
**Applied fix:** Replaced the read-check-insert TOCTOU pattern with
`pg_insert(ReferralCapture).values(...).on_conflict_do_nothing(index_elements=["referee_client_id"]).returning(ReferralCapture.id)`.
When `session.scalar(stmt)` returns `None`, the conflict path returns silently (no-op,
no IntegrityError 500). Audit is only emitted when RETURNING returns a real `capture_id`
(RETURNING-gated per INFRA-15). The initial `get_capture_by_referee` call was removed
(the pg_insert handles idempotency atomically). Added `from sqlalchemy.dialects.postgresql import insert as pg_insert` to the imports.

---

### WR-02: `resolve_public_code` returns `valid=True` for a soft-deleted referrer

**Files modified:** `apps/backend/app/modules/referrals/service.py`
**Commit:** ff3873f2 (same commit as CR-01/CR-03/WR-01/WR-04)
**Applied fix (resolve_public_code):** After the raw-SQL `SELECT first_name FROM clients
WHERE id = :cid AND deleted_at IS NULL` lookup, added a `if row is None:` branch that
returns `ReferralResolveResponse(valid=False, referrer_first_name=None,
welcome_bonus_kopecks=0)` with a debug log. This prevents `valid=True` with a `None`
first name for soft-deleted referrers.

**Applied fix (capture_referral):** Added a raw-SQL alive check (`SELECT 1 FROM clients
WHERE id = :cid AND deleted_at IS NULL`) after resolving the code row. If the referrer
is soft-deleted, raises `ReferralCodeNotFoundError` (404) before the pg_insert, rejecting
the capture. The docstring was updated to document this additional 404 case.

---

### WR-03: `ReferralCaptureRequest.code` allows spaces and arbitrary non-Crockford characters

**Files modified:** `apps/backend/app/modules/referrals/schemas.py`
**Commit:** 070da4a2
**Applied fix:** Changed `Field(min_length=1, max_length=16)` to `Field(min_length=8,
max_length=8, pattern=r"^[0-9A-HJKMNPQRSTVWXYZa-hjkmnpqrstvwxyz]{8}$")`. The pattern
accepts both upper- and lower-case Crockford characters (excluding O/I/L/U per Crockford
spec) since `repository.get_code_by_value` normalises via `.upper()`. The class docstring
was updated to explain the constraint.

---

## Skipped Issues

None.

---

_Fixed: 2026-06-08_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
