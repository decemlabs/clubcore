---
phase: 86-gym-info-cms
reviewed: 2026-06-06T12:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx
  - apps/client-pwa/src/screens/sheets/GymInfoSheet.test.jsx
  - apps/backend/app/modules/gym/schemas.py
  - apps/backend/tests/unit/test_permissions.py
  - apps/backend/tests/integration/test_rbac_parity.py
  - packages/api-client/src/schema.d.ts
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 86: Code Review Report (Iteration 2 — Fix Verification)

**Reviewed:** 2026-06-06
**Depth:** standard
**Files Reviewed:** 6
**Status:** clean

## Summary

This is a re-review verifying that all 8 findings from iteration 1 (2 blockers, 6 warnings) are genuinely resolved and that the fixes did not introduce new defects. Every finding is confirmed resolved. No new issues were found.

### Prior findings — resolution status

| ID | Description | Status |
|----|-------------|--------|
| CR-01 | `GymInfoSheet.jsx` imported `useClientGymInfo` from `@/data` barrel (D-71-09 violation) | **RESOLVED** — import is now `from '@/lib/clientQueries'` (line 21) |
| CR-02 | `email` in `GymInfoUpdateRequest` was bare `str`, enabling stored `mailto:` query injection | **RESOLVED** — field is now `EmailStr \| None = Field(default=None, max_length=255)` (line 71); `email-validator>=2.0` is a declared dependency and correctly rejects query-string injection at validation time (verified in project venv) |
| WR-01 | `socialUrl` used `String.replace('@', '')` (first occurrence only), leaving secondary `@` chars | **RESOLVED** — `replaceAll('@', '')` at line 114; all `@` signs stripped before `encodeURIComponent` |
| WR-02 | `owner_update_gym_info` PUT `/api/v1/gym` absent from `schema.d.ts` | **RESOLVED** — operation present at line 1494 (path) and lines 7445–7496 (operation detail) |
| WR-03 | Test function named `test_owner_only_has_exactly_forty_entries` but asserted 41 | **RESOLVED** — function renamed `test_owner_only_has_exactly_forty_one_entries` (line 16) |
| WR-04 | Module docstring in `test_rbac_parity.py` stated "35 entries" / "through Phase 54" | **RESOLVED** — docstring now states "41 entries" with full Phase 86 breakdown (lines 1–13) |
| WR-05 | `getOpenStatus` would access `hours[todayIdx]` without bounds-check on short arrays | **RESOLVED** — guard `if (todayIdx >= hours.length) return null` at line 75; short arrays return null and no hours section is rendered |
| WR-06 | `social: list[Any]` accepted unbounded, unstructured JSONB — no per-item validation | **RESOLVED** — `SocialItem` model introduced (lines 16–26) with `kind: Literal['tg', 'ig']`, `label: str = Field(max_length=64)`, `handle: str = Field(max_length=64, pattern=r'^@[\w.]+$')`; `GymInfoUpdateRequest.social` is now `list[SocialItem] | None` (line 75) |

### Fix correctness — spot-checks

**CR-02 (EmailStr):** Verified in the project venv (`apps/backend/.venv/bin/python3`) that `EmailStr | None = Field(max_length=255)` accepts `'test@example.com'`, accepts `None`, and raises `ValidationError` for `'test@example.com?cc=evil@x.com'`. The `email-validator>=2.0` package is declared in `apps/backend/pyproject.toml` line 12. No runtime `ImportError` risk.

**WR-01 / WR-06 (socialUrl + SocialItem):** The backend pattern `^@[\w.]+$` confines handle characters to alphanumerics, underscores, dots, and a leading `@`. After `replaceAll('@', '')` + `encodeURIComponent`, the URL path segment contains only characters that `encodeURIComponent` leaves unreserved (`[A-Za-z0-9_.]`). No userinfo injection is possible for any input passing the pattern. Dots are not encoded by `encodeURIComponent` and are valid in both `t.me/` and `instagram.com/` URL paths.

**WR-05 (getOpenStatus):** The guard at line 75 returns `null` when `todayIdx >= hours.length`. The hours section in JSX renders only when `status` is non-null (line 293: `{data.hours && data.hours.length > 0 && status && ...}`), so a partial array simply hides the hours section rather than crashing. The tomorrow-wrap logic `(todayIdx + 1) % hours.length` always produces a valid index (0 ≤ tomorrowIdx < hours.length) for any array that passes the guard, so `tomorrowRow` is never `undefined`.

**WR-03 / WR-04 (test docstrings):** `test_permissions.py` line 16 function name matches the asserted value (41). `test_rbac_parity.py` module docstring lines 1–13 state "41 entries" with a complete breakdown including Phase 86. Both assertions (`assert len(OWNER_ONLY) == 41`) are internally consistent with the updated docstrings.

All reviewed files meet quality standards. No issues found.

---

_Reviewed: 2026-06-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
_Iteration: 2 (fix verification)_
