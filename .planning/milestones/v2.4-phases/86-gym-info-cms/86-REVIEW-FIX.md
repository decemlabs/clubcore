---
phase: 86-gym-info-cms
fixed_at: 2026-06-06T00:00:00Z
review_path: .planning/phases/86-gym-info-cms/86-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 86: Code Review Fix Report

**Fixed at:** 2026-06-06
**Source review:** .planning/phases/86-gym-info-cms/86-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (2 Critical + 6 Warning; Info findings excluded per scope)
- Fixed: 8
- Skipped: 0

## Fixed Issues

### CR-01: GymInfoSheet import boundary violation

**Files modified:** `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx`
**Commit:** 5ac18298
**Applied fix:** Changed `import { useClientGymInfo } from '@/data'` to `import { useClientGymInfo } from '@/lib/clientQueries'` — the direct library path that mirrors LoyaltySheet.jsx and satisfies D-71-09 boundary.

---

### WR-01: socialUrl replace only strips first @

**Files modified:** `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx`
**Commit:** 5ac18298
**Applied fix:** Changed `item.handle.replace('@', '')` to `encodeURIComponent(item.handle.replaceAll('@', ''))` — strips all `@` signs via `replaceAll` and then `encodeURIComponent`-encodes remaining path-unsafe characters, preventing credential-embedded URLs.

---

### WR-05: getOpenStatus breaks on short hours arrays

**Files modified:** `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx`
**Commit:** 5ac18298
**Applied fix:** Added `if (todayIdx >= hours.length) return null` guard after the existing empty-array check. When `todayIdx` is out of range, the function returns `null` rather than silently falling back to `hours[0]` (Monday). The JSX `status &&` condition already suppresses the hours section when `null`. The tomorrow lookup was changed from `(todayIdx + 1) % 7` to `(todayIdx + 1) % hours.length` so it wraps correctly within the actual array length. Removed the unsafe `?? hours[0]` fallbacks on `todayRow` and `tomorrowRow`.

---

### CR-02: email field accepts mailto query injection

**Files modified:** `apps/backend/app/modules/gym/schemas.py`
**Commit:** 7efdc167
**Applied fix:** Changed `email: str | None = Field(default=None, max_length=255)` to `email: EmailStr | None = Field(default=None, max_length=255)` on `GymInfoUpdateRequest`. Added `from pydantic import EmailStr` import. `email-validator` was already in `pyproject.toml`. Seed value `tverskaya@mygym.ru` passes; `tverskaya@mygym.ru?cc=evil@x.com` is rejected with ValidationError. `GymInfoResponse.email` intentionally left as `str | None` (response-only; serializes existing DB content without re-validating).

---

### WR-06: social field is list[Any] with no per-item validation

**Files modified:** `apps/backend/app/modules/gym/schemas.py`
**Commit:** 7efdc167
**Applied fix:** Defined a new `SocialItem(BackendSchemaBase)` model with `kind: Literal['tg', 'ig']`, `label: str = Field(max_length=64)`, and `handle: str = Field(max_length=64, pattern=r'^@[\w.]+$')`. Changed `social: list[Any] | None = None` on `GymInfoUpdateRequest` to `social: list[SocialItem] | None = None`. The `^@[\w.]+$` pattern rejects multi-@ handles (e.g. `@user@evil.com`) while accepting standard usernames. `GymInfoResponse.social` left as `list[Any]` for permissive serialization of seed data already in the DB. Validated: `SocialItem(kind='tg', label='Telegram', handle='@mygym')` passes; `handle='@user@evil.com'` is rejected.

---

### WR-03: test function name claims 40 but asserts 41

**Files modified:** `apps/backend/tests/unit/test_permissions.py`
**Commit:** f4b36686
**Applied fix:** Renamed `test_owner_only_has_exactly_forty_entries` to `test_owner_only_has_exactly_forty_one_entries`. The assertion body (`assert len(OWNER_ONLY) == 41`) was already correct; only the name was wrong.

---

### WR-04 + IN-03: test_rbac_parity.py module docstring stale counts and phase reference

**Files modified:** `apps/backend/tests/integration/test_rbac_parity.py`
**Commit:** d9463974
**Applied fix:** Updated the module docstring:
- Changed "35 entries" to "41 entries" with the full breakdown including Phase 58 (+5) and Phase 86 GYM-02 (+1).
- Changed "counts updated through Phase 54 INFRA-42" to "counts updated through Phase 86 GYM-02".
Assertions in the file were already correct (41); only prose was stale.

---

### WR-02: owner PUT /api/v1/gym missing from schema.d.ts

**Files modified:** `packages/api-client/src/schema.d.ts`
**Commit:** 17f7550e
**Applied fix:** Added two entries:
1. A `"/api/v1/gym"` path block (between `/api/v1/clients/{client_id}/loyalty/grant` and `/api/v1/membership-plans`) with `put: operations["owner_update_gym_info"]`.
2. An `owner_update_gym_info` operation block in the `operations` interface (placed before `client_get_gym_info`) with typed `requestBody` (partial-upsert fields) and `200` response matching `GymInfoResponse` shape, plus `422: components["responses"]["422_ValidationError"]`.
This is a stopgap for type consistency; Phase 89 regenerates byte-stable from the OpenAPI spec.

---

_Fixed: 2026-06-06_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
