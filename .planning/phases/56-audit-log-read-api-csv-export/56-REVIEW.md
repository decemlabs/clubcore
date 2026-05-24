---
phase: 56-audit-log-read-api-csv-export
reviewed: 2026-05-24T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - apps/backend/app/modules/reports/schemas.py
  - apps/backend/app/modules/reports/repository.py
  - apps/backend/app/modules/reports/service.py
  - apps/backend/app/modules/reports/router.py
  - apps/backend/app/modules/reports/constants.py
  - apps/backend/app/modules/reports/csv_export.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/tests/integration/reports/test_audit_log.py
  - apps/backend/tests/integration/reports/test_csv_export.py
  - apps/backend/tests/integration/reports/conftest.py
  - apps/backend/tests/integration/clients/test_audit_writes.py
findings:
  critical: 1
  warning: 2
  info: 2
  total: 5
status: issues_found
---

# Phase 56: Code Review Report

**Reviewed:** 2026-05-24
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 56 implements the audit-log read API (paginated JSON listing + CSV export) and CSV
export endpoints for the three existing report types. The core architecture is sound: RBAC
is correctly wired (`(LIST, AUDIT_LOG)` and `(VIEW, REPORTS)` are both in `OWNER_ONLY`),
filter predicates are fully parameterized via ORM column ops, the BOM is correctly written as
`"(U+FEFF)"` (Python escape, not a literal U+FEFF glyph), and the eager `validate_audit_filters`
call before `StreamingResponse` construction is a correct and well-documented pattern.

One security defect was found: free-text values written to the audit-log CSV
(`actor_email_snapshot`, and indirectly the JSON payload string) are not sanitized for leading
formula-injection characters (`= + - @ |`), which allows a malicious actor who controls what
gets audited to embed active content that executes when the CSV is opened in Excel or
LibreOffice Calc. Two warnings were identified: ILIKE wildcard characters in
`actor_email_snapshot` are not escaped, silently changing filter semantics; and the
`actor_email_snapshot` filter field has no length or character-set constraint. Two informational
gaps round out the findings.

---

## Critical Issues

### CR-01: CSV formula injection — `actor_email_snapshot` and `payload` cells are not sanitized

**File:** `apps/backend/app/modules/reports/csv_export.py:31-46` and
`apps/backend/app/modules/reports/service.py:433-440`

**Issue:** `csv.writer` with `QUOTE_MINIMAL` handles RFC-4180 structural escaping (commas,
double-quotes, newlines) but does **not** neutralize spreadsheet formula-injection payloads.
Any cell whose string value starts with `=`, `+`, `-`, `@`, or `|` is interpreted as a
formula by Excel and LibreOffice Calc when the file is opened. The `actor_email_snapshot`
field is written verbatim to the CSV without any prefix check:

```python
# service.py:436
row.actor_email_snapshot or "",
```

A malicious `actor_email_snapshot` value such as `=cmd|"/C calc"!A0` or
`+cmd|"/C calc"!A0` (stored by an attacker who triggers any audited endpoint that captures
`actor_email_snapshot`) would be preserved in `audit-log.csv` and execute as a formula when
an owner opens the export in a spreadsheet application. The `payload` JSON serialization is
less risky in practice (it always starts with `{` for normal dicts) but is not structurally
guaranteed to be safe if a `payload` value were ever a bare string or number at the top
level.

The audience is specifically the gym owner (the only role that can download the CSV), making
this a real privilege-escalation vector: an adversary who can log in as a reception-role
user (or who simply sends requests to any unauthenticated audited endpoint to inject a
crafted value into `actor_email_snapshot`) can then plant formula content that executes on
the owner's machine.

**Fix:** Apply a sanitizer to every string cell before writing it. The standard approach is
to prefix cells that start with a formula trigger character with a single-quote (which
Excel/LibreOffice interprets as "treat as text") or with a tab character. A reusable helper
in `csv_export.py`:

```python
_FORMULA_TRIGGERS = frozenset("=+-@|")

def _sanitize_cell(value: object) -> object:
    """Prefix formula-trigger cells with a tab to prevent spreadsheet injection.

    Only strings are affected; all other types are returned as-is.
    The tab prefix is invisible in most spreadsheet UIs and is the
    de-facto standard for CSV formula injection mitigation.
    """
    if isinstance(value, str) and value and value[0] in _FORMULA_TRIGGERS:
        return "\t" + value
    return value


def _row_to_csv_line(row: list[object]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, dialect="excel")
    writer.writerow([_sanitize_cell(v) for v in row])
    return buf.getvalue()
```

Applying `_sanitize_cell` inside `_row_to_csv_line` covers all four CSV endpoints without
any change to callers.

---

## Warnings

### WR-01: ILIKE wildcard injection — `%` and `_` in `actor_email_snapshot` filter are not escaped

**File:** `apps/backend/app/modules/reports/repository.py:263-266`

**Issue:** The `actor_email_snapshot` substring-search pattern is built with a bare f-string:

```python
like_pattern = f"%{query.actor_email_snapshot}%"
predicates.append(AuditLog.actor_email_snapshot.ilike(like_pattern))
```

SQLAlchemy's ORM `.ilike()` emits a parameterized bind (no SQL injection risk), but it
passes the pattern string, including any `%` or `_` meta-characters, **literally to
PostgreSQL**. This means:

- `?actorEmailSnapshot=%` produces pattern `%%%` and matches every row regardless of the
  actual email value.
- `?actorEmailSnapshot=_` produces pattern `%_%` and matches any row with at least one
  character.
- `?actorEmailSnapshot=a%b` matches any email containing `a`, then any characters, then
  `b` — broader than the intent of substring search.

For the audit-log use case this silently changes the filter semantics, returning rows the
owner did not intend to retrieve and undermining the integrity of audit investigations. It
is also potentially a performance concern: a pattern of `%` causes a full table scan on
`actor_email_snapshot` (no index benefit) even when the index `ix_audit_log_created_at`
would otherwise help narrow the result set.

**Fix:** Escape LIKE wildcards in the user-supplied substring before constructing the
pattern. PostgreSQL ILIKE supports `ESCAPE` clauses, and SQLAlchemy supports it directly:

```python
# Escape literal % and _ so they are treated as characters, not wildcards.
escaped = (
    query.actor_email_snapshot
    .replace("\\", "\\\\")   # must come first
    .replace("%", "\\%")
    .replace("_", "\\_")
)
like_pattern = f"%{escaped}%"
predicates.append(AuditLog.actor_email_snapshot.ilike(like_pattern, escape="\\"))
```

### WR-02: `actor_email_snapshot` filter has no length or character-set constraint

**File:** `apps/backend/app/modules/reports/schemas.py:193`

**Issue:** `actor_email_snapshot: str | None = None` in `AuditLogQuery` has no `max_length`
constraint. Any string of arbitrary length is accepted and forwarded to the database as a
LIKE pattern. A caller can send a kilobytes-long string, which the DB must evaluate against
every row in the result set (especially costly with the `%...%` pattern). With the wildcard
injection gap (WR-01) still open this compounds into trivially-triggered expensive queries.
Even after fixing WR-01, an unconstrained length allows resource exhaustion from a single
authenticated owner-role request.

**Fix:** Add a `max_length` bound matching the database column (`actor_email_snapshot` is
`Text` in `AuditLog`, but the search term does not need to be that long):

```python
from pydantic import Field

actor_email_snapshot: Annotated[str, Field(max_length=254)] | None = None
```

254 characters is the RFC 5321 maximum email address length and is a reasonable upper bound
for a substring filter on email values.

---

## Info

### IN-01: No unauthenticated (401) test coverage for CSV endpoints

**File:** `apps/backend/tests/integration/clients/test_audit_writes.py:178-195`

**Issue:** `test_audit_log_endpoint_requires_auth` verifies that an unauthenticated
`GET /api/v1/audit-log` returns 401, but the test does **not** cover the four CSV export
endpoints (`/reports/revenue.csv`, `/reports/clients.csv`, `/reports/visits.csv`,
`/audit-log.csv`). The reception→403 path is tested for all four, but there is no
corresponding unauthenticated→401 assertion for any of them. If a future routing or
middleware refactor accidentally strips authentication from a CSV path, the test suite would
not catch it.

**Fix:** Extend `test_audit_log_endpoint_requires_auth` (or add a parametrized test in
`test_csv_export.py`) to cover all four CSV paths with an unauthenticated client:

```python
@pytest.mark.parametrize("path", [
    "/api/v1/reports/revenue.csv",
    "/api/v1/reports/clients.csv",
    "/api/v1/reports/visits.csv",
    "/api/v1/audit-log.csv",
])
async def test_csv_endpoints_require_auth(
    async_client: AsyncClient,
    path: str,
) -> None:
    r = await async_client.get(path)
    assert r.status_code == 401, f"{path} unexpectedly returned {r.status_code}"
```

### IN-02: `test_literal_from_to_params_bind` asserts `status in (200, 422)` — vacuous assertion

**File:** `apps/backend/tests/integration/reports/test_audit_log.py:128`

**Issue:** The test verifies that `?fromDate=...&toDate=...` (wrong wire names) either
returns 200 or 422, and explicitly acknowledges that either outcome is acceptable:

```python
assert r2.status_code in (200, 422), r2.text
```

This assertion can never fail — any response code except 200 and 422 (e.g., 500) would
catch a real regression, but those codes are also not asserted against. More importantly,
the comment in the test body explains the ambiguity: `extra='forbid'` on `AuditLogQuery`
(inherited via `BackendSchemaBase`) *should* reject unknown fields with 422, so the
expected behavior is deterministic. The `in (200, 422)` form allows a broken state where
the filter silently accepts `fromDate` as a valid field name.

**Fix:** Assert the deterministic expected behavior. Since `BackendSchemaBase` has
`extra='forbid'`, `fromDate` is an unknown field and should yield 422:

```python
# extra='forbid' on AuditLogQuery means unknown query params → 422
assert r2.status_code == 422, (
    "Expected 422 for unknown 'fromDate' param (extra='forbid'); "
    f"got {r2.status_code}"
)
```

If the intended assertion is that `fromDate` is silently ignored (e.g., if FastAPI strips
unknown query params before Pydantic validation), then the test comment and assertion should
be aligned to that behavior rather than leaving both outcomes as acceptable.

---

_Reviewed: 2026-05-24_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
