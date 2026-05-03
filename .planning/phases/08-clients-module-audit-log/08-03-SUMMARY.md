---
phase: 08-clients-module-audit-log
plan: 03
subsystem: api
tags: [pydantic, dto, validation, fastapi, e164, patch-semantics]

requires:
  - phase: 08-clients-module-audit-log
    provides: [Plan 01 — Client ORM model + Gender StrEnum]
  - phase: 04-contracts-and-pagination
    provides: [ContractModel, RequestContract, ResponseData, PageQuery, alias_generator=to_camel]
provides:
  - "ClientCreateRequest — POST body DTO (CLIENTS-06; required lastName/firstName/phone, E.164)"
  - "ClientUpdateRequest — PATCH body DTO with explicit-null rejection (CLIENTS-07, D-01)"
  - "ClientResponse — read-side DTO (omits deleted_at; soft-deletes are 404'd at repo)"
  - "ClientListQuery — list query DTO extending PageQuery with q/tag/gender/createdFrom/createdTo/hasTelegram/sort"
  - "EmergencyContact — embedded JSONB shape with E.164 phone (D-17)"
  - "ClientSort enum — created_at_desc (default) | last_name_asc"
  - "Shared _validate_tags helper enforcing D-16 (max 16, max 32 chars, lowercase, regex)"
affects: [08-04 repository, 08-06 service, 08-07 router, packages/api-client codegen]

tech-stack:
  added: []
  patterns:
    - "Module-level shared _validate_tags() reused by create + update validators"
    - "model_validator(mode='before') for cross-field PATCH null-rejection"
    - "field_validator(mode='before') with ValidationInfo.field_name for asymmetric date boundary normalisation (start vs end of day)"

key-files:
  created:
    - "apps/backend/app/modules/clients/schemas.py — all five DTOs + ClientSort + helpers"
  modified: []

key-decisions:
  - "Shared _validate_tags module-level function instead of duplicating tag rules in two validator methods (DRY without leaking validators across classes)"
  - "EmergencyContact subclasses ResponseData (not RequestContract) so it does not carry extra='forbid'; the embedded shape is owned by the JSONB column and we want it tolerant on read while validators still gate writes via the create/update DTOs that compose it"
  - "noqa: RUF001 on TAG_REGEX — D-16 explicitly allows literal Cyrillic а-я; the ambiguity hint is intentional and suppressed at the constant declaration only"
  - "Date boundary normaliser inspects info.field_name to apply 23:59:59.999999 only to created_to, keeping the validator decorator on both fields without splitting them"

patterns-established:
  - "DTO module hosts only Pydantic models + pure validator helpers — zero ORM imports beyond StrEnum"
  - "PATCH DTOs reject explicit null via model_validator(mode='before') and rely on model_dump(exclude_unset=True) downstream for selective updates"
  - "List query DTOs extend PageQuery rather than re-declaring page/page_size, inheriting wire-format alias rules"

requirements-completed: [CLIENTS-01, CLIENTS-04, CLIENTS-06, CLIENTS-07]

duration: 18min
completed: 2026-05-03
---

# Phase 08 Plan 03: Clients Pydantic DTOs Summary

**Five Pydantic DTOs (EmergencyContact, ClientCreateRequest, ClientUpdateRequest, ClientResponse, ClientListQuery) for the clients module wired to ContractModel chain — E.164 phone, tag normaliser, PATCH null-rejection, q-minimum, and date-boundary normalisation all enforced at the contract boundary.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-05-03T08:38:00Z
- **Completed:** 2026-05-03T08:56:21Z
- **Tasks:** 2
- **Files modified:** 1 (created)

## Accomplishments

- Single-file DTO module `apps/backend/app/modules/clients/schemas.py` carrying every contract for clients endpoints (POST/PATCH/list-query/read).
- All wire-format decisions enforced in code (D-01, D-10, D-12, D-14, D-15, D-16, D-17) with validators that reject malformed inputs before the request reaches service or repository layers.
- ruff + mypy --strict both green on the new module; functional verifications cover every adversarial case in the plan acceptance criteria.

## Task Commits

Each task was committed atomically:

1. **Task 1: EmergencyContact + ClientCreateRequest + ClientResponse** — `86e815e` (feat)
2. **Task 2: ClientUpdateRequest + ClientListQuery + ClientSort** — `ce1895b` (feat)

_No plan-metadata commit yet — STATE/ROADMAP updates handled by orchestrator after wave merge._

## Files Created/Modified

- `apps/backend/app/modules/clients/schemas.py` (created, 262 lines) — all five DTOs, ClientSort enum, shared _validate_tags helper, PHONE_REGEX/TAG_REGEX/MAX_TAGS/MAX_TAG_LENGTH constants.

## Validator Coverage Map

| Decision | Validator                                           | Where                                       |
| -------- | --------------------------------------------------- | ------------------------------------------- |
| D-01     | `_reject_explicit_null` (model_validator, mode=before) | ClientUpdateRequest                         |
| D-10     | `Field(pattern=PHONE_REGEX)`                        | ClientCreateRequest, ClientUpdateRequest, EmergencyContact |
| D-12     | `_normalise_q` (field_validator on `q`)             | ClientListQuery                             |
| D-14     | `_normalise_date_boundary` (field_validator, mode=before) | ClientListQuery (`created_from`, `created_to`) |
| D-15     | `gender: Gender \| None` (StrEnum)                  | All Client DTOs                             |
| D-16     | `_validate_tags` helper via field_validator on `tags` | ClientCreateRequest, ClientUpdateRequest |
| D-17     | `EmergencyContact` Pydantic model                   | Composed in Create/Update                   |

## Wire-Format Examples

**Valid POST /api/v1/clients body (camelCase wire):**

```json
{
  "lastName": "Иванов",
  "firstName": "Иван",
  "phone": "+79991234567",
  "gender": "male",
  "tags": ["VIP", "gym"],
  "emergencyContact": { "name": "Иванова", "phone": "+79997654321", "relation": "spouse" }
}
```

After validation: `tags == ['vip', 'gym']` (lowercased), `phone` passes E.164.

**Rejected PATCH body (D-01 explicit null):**

```json
{ "email": null }
```

→ `422 Unprocessable Entity` with message containing `Explicit null not supported for: ['email']. Omit the key to leave the field unchanged.`

**Rejected list query (D-12 short q passes through silently):**

```
GET /api/v1/clients?q=a
```

→ HTTP 200, but `q` is normalised to `None` server-side; the service must skip the ILIKE filter rather than scan the full table.

**Date boundary normalisation:**

```
GET /api/v1/clients?createdFrom=2026-01-01&createdTo=2026-01-31
```

→ `created_from = 2026-01-01T00:00:00.000000+00:00`, `created_to = 2026-01-31T23:59:59.999999+00:00` (inclusive).

## Decisions Made

- Used module-level `_validate_tags()` so create + update validators stay DRY without classmethod gymnastics.
- Kept `EmergencyContact` as a `ResponseData` subclass — `extra='ignore'` is the right policy for an embedded JSONB shape that may carry future fields the server doesn't yet know about; the gating happens via the Create/Update DTOs that compose it (which carry `extra='forbid'`).
- Suppressed `RUF001` on the TAG_REGEX line only (not project-wide) because the literal Cyrillic range is required by D-16; the `noqa` is scoped to the single declaration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] ruff RUF001/RUF002/RUF003 fired on intentional Cyrillic literals**
- **Found during:** Task 1 (initial ruff check on schemas.py)
- **Issue:** ruff's flake8-bandit-style rules (RUF001/002/003) flagged the literal Cyrillic `а-я` range inside `TAG_REGEX` and supporting docstring/comment text as "ambiguous unicode" — but D-16 explicitly mandates Cyrillic support in tags, so the literal cannot be replaced.
- **Fix:** Rewrote the docstrings to describe the allowed character set in prose without embedding the literal Cyrillic range, then placed a single `# noqa: RUF001` directive on the `TAG_REGEX = re.compile(...)` line where the literal must remain. Surrounding comment was edited to avoid retriggering RUF003.
- **Files modified:** `apps/backend/app/modules/clients/schemas.py`
- **Verification:** `cd apps/backend && uv run ruff check app/modules/clients/schemas.py` exits 0; `uv run mypy --strict` exits 0.
- **Committed in:** `86e815e` (Task 1 commit) — fixes were inline before Task 1 was committed.

**2. [Rule 1 — Bug] Plan-pasted code used `from datetime import datetime as _dt, timezone` shadowing inside the validator body**
- **Found during:** Task 2 implementation
- **Issue:** The plan's reference snippet did `from datetime import datetime as _dt, timezone` inside the `_normalise_date_boundary` body, plus a separate `from datetime import timezone` for the date-instance branch. Both block-local imports in a hot validator path, plus stylistically inferior to a top-level import. mypy/ruff would flag the `timezone` import as redundant relative to the existing module-level import surface.
- **Fix:** Replaced with a single top-level `from datetime import UTC, date, datetime` (`UTC` is the modern alias since Python 3.11 and matches DTZ ruff rules) and removed all in-function imports. Logic unchanged.
- **Files modified:** `apps/backend/app/modules/clients/schemas.py`
- **Verification:** All Task 2 functional tests still pass (boundary normalisation, q-minimum, default sort, PageQuery inheritance).
- **Committed in:** `ce1895b` (Task 2 commit).

---

**Total deviations:** 2 auto-fixed (1 blocking lint, 1 stylistic bug from pasted reference)
**Impact on plan:** No scope changes. Both fixes were necessary for the file to pass the plan's own ruff + mypy verification.

## Threat Flags

None — no security-relevant surface introduced beyond what the plan's `<threat_model>` already documents (T-08-12..T-08-18 all covered by the validators listed above).

## Issues Encountered

None — the only adjustments were the two auto-fixes documented above.

## Self-Check: PASSED

- `apps/backend/app/modules/clients/schemas.py` — FOUND.
- Commit `86e815e` (Task 1 — EmergencyContact + ClientCreateRequest + ClientResponse) — FOUND in `git log`.
- Commit `ce1895b` (Task 2 — ClientUpdateRequest + ClientListQuery + ClientSort) — FOUND in `git log`.
- All five exported classes import cleanly: `ClientCreateRequest, ClientUpdateRequest, ClientResponse, ClientListQuery, EmergencyContact` (plus `ClientSort` enum) — verified via `python -c "from app.modules.clients.schemas import ..."`.
- `cd apps/backend && uv run ruff check app/modules/clients/schemas.py && uv run mypy --strict app/modules/clients/schemas.py` — both green.
- All 15 functional verification cases pass (E.164 happy + reject, tag lowercase + reject + cap, EmergencyContact phone, PATCH null-rejection + exclude_unset + tags lowercase, q-minimum, date boundary, default sort, PageQuery inheritance, ClientResponse from_attributes).

## Next Phase Readiness

- Plan 04 (repository) can immediately import `ClientCreateRequest`, `ClientUpdateRequest`, `ClientListQuery` as input contracts.
- Plan 06 (service) consumes these DTOs and produces `ClientResponse`.
- Plan 07 (router) declares them as FastAPI `body=` and `Query=` types — `alias_generator=to_camel` and PageQuery inheritance mean the OpenAPI schema and parameter shapes are wire-correct without per-route aliasing.

---
*Phase: 08-clients-module-audit-log*
*Completed: 2026-05-03*
