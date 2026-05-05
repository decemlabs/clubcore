---
phase: 04-auth-foundations-cookie-rbac-primitives
plan: "05"
subsystem: backend/core
tags: [pydantic, schemas, wire-format, camelcase, generics, api-contract]
requirements-completed: [API-03]
dependency_graph:
  requires: []
  provides:
    - "apps/backend/app/core/schemas.py: ContractModel, RequestContract, ResponseData, ResponseEnvelope[T], ProblemDetails, envelope()"
  affects:
    - "apps/backend/app/core/pagination.py (Plan 04-06 will rewrite to use RequestContract/ResponseData)"
    - "apps/backend/tests/unit/test_schemas.py (Plan 04-09 unit tests)"
    - "Phase 5+ endpoint response_model=ResponseEnvelope[X]"
tech_stack:
  added: []
  patterns:
    - "Pydantic 2.11+ validate_by_name + validate_by_alias replacing deprecated populate_by_name"
    - "PEP 695 generics (Python 3.12): class ResponseEnvelope[T] and def envelope[T]"
    - "ContractModel hierarchy: alias_generator=to_camel for camelCase wire format"
    - "RequestContract extra='forbid' for mass-assignment protection (T-04-17)"
key_files:
  created:
    - apps/backend/app/core/schemas.py
  modified: []
decisions:
  - "D-07: backend-first envelope wraps every 2xx as { data: T } via ResponseEnvelope[T]"
  - "D-08: errors stay top-level { code, message, fields? }, NOT wrapped in data"
  - "D-11: PEP 695 generics used instead of typing.Generic[T] / TypeVar"
  - "D-12: validate_by_name=True + validate_by_alias=True (Pydantic 2.11+, not populate_by_name)"
  - "D-13: Phase 4 envelope is { data: T } only — no requestId/traceId/meta/warnings yet"
  - "D-14: envelope() helper function accepted to reduce route import noise"
metrics:
  duration: "< 5 minutes"
  completed: "2026-05-02"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 04 Plan 05: Wire-Format Contract Base Classes Summary

ContractModel hierarchy with PEP 695 generics and Pydantic 2.11+ camelCase config in `app/core/schemas.py`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create app/core/schemas.py with ContractModel hierarchy + ResponseEnvelope[T] + ProblemDetails + envelope() | 3570817 | apps/backend/app/core/schemas.py |

## What Was Built

A new `apps/backend/app/core/schemas.py` providing 5 classes and 1 helper function that form the wire-format contract for all Phase 5+ API endpoints.

**ContractModel.model_config snapshot:**
```python
{
    'alias_generator': <function to_camel at ...>,
    'validate_by_name': True,
    'validate_by_alias': True,
    'from_attributes': True,
    'extra': 'ignore',
}
```

**`populate_by_name` present in file:** No (confirmed by acceptance criteria grep returning 0).

**Sample camelCase round-trip:**
```python
class SampleDTO(ContractModel):
    full_name: str

obj = SampleDTO(fullName='alice')   # validates by alias
obj.full_name == 'alice'             # snake_case in Python
obj.model_dump(by_alias=True) == {'fullName': 'alice'}  # camelCase on wire

env = ResponseEnvelope[SampleDTO](data=SampleDTO(full_name='bob'))
env.model_dump(by_alias=True) == {'data': {'fullName': 'bob'}}
```

**ProblemDetails fields:**
- `code: str`
- `message: str`
- `fields: dict[str, object] | None = None`

Mirrors exactly the `_app_error_handler` JSONResponse content (T-04-21 mitigated).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring contained forbidden pattern references**
- **Found during:** Task 1 acceptance criteria verification
- **Issue:** The module docstring originally contained `populate_by_name=True` (as an explanation of what's deprecated) and `typing.Generic[T]` / `TypeVar` (as documentation of what NOT to use). Acceptance criteria requires grep of these patterns to return 0 lines across the entire file including docstrings.
- **Fix:** Replaced docstring mentions with equivalent explanations that don't include the banned terms.
- **Files modified:** apps/backend/app/core/schemas.py
- **Commit:** 3570817

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. This plan creates only Pydantic model classes and a helper function.

**Mitigations applied (from threat model):**
- T-04-17: `RequestContract.model_config['extra'] = 'forbid'` — prevents mass-assignment
- T-04-19: `validate_by_name=True` + `validate_by_alias=True` used (not deprecated `populate_by_name`)
- T-04-20: PEP 695 syntax used; `TypeVar`/`Generic[` forbidden (grep returns 0)
- T-04-21: `ProblemDetails` fields `(code, message, fields)` mirror `_app_error_handler` output exactly

## Known Stubs

None. This plan delivers pure contract classes with no data flow stubs.

## Self-Check: PASSED

- FOUND: apps/backend/app/core/schemas.py
- FOUND: commit 3570817
