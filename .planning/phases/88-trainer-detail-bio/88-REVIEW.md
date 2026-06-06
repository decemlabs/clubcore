---
phase: 88-trainer-detail-bio
reviewed: 2026-06-06T12:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - apps/backend/app/modules/trainers/schemas.py
  - apps/backend/alembic/versions/0063_seed_trainer_profiles.py
  - apps/backend/tests/integration/trainers/test_trainers_bio_patch.py
  - apps/backend/tests/integration/client_portal/test_client_trainer_detail.py
  - apps/client-pwa/src/screens/sheets/TrainerDetailSheet.test.jsx
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/client-pwa/src/data/index.js
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 88: Code Review Report (Iteration 2 — Re-Review)

**Reviewed:** 2026-06-06T12:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** clean

## Summary

This is a targeted re-review of the six fixes applied after the initial Phase 88 review (CR-01, WR-01, WR-02, WR-03, IN-01, IN-02). All six reported issues are genuinely resolved. No new blocking or warning issues were introduced by the fixes.

### Fix-by-fix verification

**CR-01 — `photo_url` scheme validator (`apps/backend/app/modules/trainers/schemas.py:60-71`):**
The `@field_validator("photo_url", mode="before")` is present and correct. Execution order is verified: `mode='before'` means the scheme check runs before Pydantic applies `max_length=2048`, so there is no bypass path — a URL that passes the scheme check still goes through length validation, and a URL that fails the scheme check never reaches the length check. Edge case coverage:
- `None` → returned early (line 64-65); optional field semantics preserved.
- Empty string `""` → stripped lower is `""` → neither `startswith("http://")` nor `startswith("https://")` → raises `ValueError`. Rejected.
- `"javascript:alert(1)"` → stripped lower does not match either prefix → rejected.
- `"data:text/html,..."` → stripped lower does not match either prefix → rejected.
- `"JAVASCRIPT:..."` → `.lower()` normalises to `"javascript:..."` → rejected.
- `"https://cdn.example.com/a.jpg"` → passes → stored. Length cap `max_length=2048` still applied by Pydantic after the validator returns.
- Unicode homograph (e.g. `"ʜttps://..."`) → Python `.lower()` does not normalize these to ASCII `h`; the prefix check correctly rejects them.

One minor data-quality note: the validator checks `v.lower().strip()` but returns the original `v` unmodified. A URL with leading/trailing whitespace (e.g. `"  https://cdn.example.com/img.jpg"`) passes the scheme check and is stored with the surrounding whitespace intact. This is a data-quality edge case that is not exploitable and does not constitute a security bypass; it is noted here for completeness only and does not require a code change.

Non-string values (the `not isinstance(v, str): return v` branch) are passed through to Pydantic's lax coercion, which converts them to strings without a scheme check. In practice, JSON only delivers strings for string-typed fields, so this path is not reachable via the API wire. Not a blocking issue.

Backend tests added for the validator: `test_owner_patch_javascript_photo_url_returns_422` (line 84) and `test_owner_patch_https_photo_url_returns_200` (line 100) — both are genuine behavioral tests that would fail if the validator were absent.

**WR-01 — 0063 downgrade scope (`apps/backend/alembic/versions/0063_seed_trainer_profiles.py:89-99`):**
The `downgrade()` now iterates `_TRAINER_PROFILES` and issues one `UPDATE ... WHERE full_name = :name AND deleted_at IS NULL` per seeded row — exactly mirroring the upgrade path. Owner-edited rows added after the seed are untouched on downgrade. The fix is symmetric and correct.

**WR-02 — XSS test assertion (`apps/client-pwa/src/screens/sheets/TrainerDetailSheet.test.jsx:150, 165`):**
The vacuous `forEach` pattern has been replaced with `expect(document.querySelector('img')).toBeNull()`. This assertion is not vacuous: if the component were to render an `<img src="javascript:...">`, `document.querySelector('img')` would return the element (not null), and the test would genuinely fail. The `expect(screen.getByText('АС')).toBeInTheDocument()` assertion additionally verifies the Avatar fallback actually rendered — `getByText` throws if the element is absent. A positive control test (lines 190-200) asserts that a valid `https://` URL DOES render an `<img>` with the correct `src`, ensuring the guard is not over-broad. All three assertions are meaningful and non-vacuous.

The Avatar component (`apps/client-pwa/src/components/Avatar.jsx`) is not mocked in the test file; it renders the real `<div>` containing the initials text. `getInitials('Аня Соколова')` correctly produces `'АС'` (first char of each space-split part, `.toUpperCase()`). The component selects `data.fullName` when `data` is present (line 127 of `TrainerDetailSheet.jsx`), and `TRAINER_DATA.fullName` is `'Аня Соколова'` in the test fixture. The assertion is sound.

**WR-03 — 401 unauthenticated baseline (`apps/backend/tests/integration/client_portal/test_client_trainer_detail.py:248-258`):**
`test_client_get_trainer_requires_auth` is present. It seeds a real `Trainer` row, issues `GET /api/v1/client/trainers/{trainer.id}` with no cookie, and asserts `status_code == 401`. This is a genuine behavioral test consistent with the project convention for `require_client()`-gated endpoints.

**IN-01 — Stale comment in `ClientAvailableSlotItem` (`apps/backend/app/modules/client_portal/schemas.py:208-209`):**
Comment now correctly reads `"specialization is available on Trainer since Phase 88 but is not included in the slot catalog projection per D-69-05 (slot list shows name only)."` Resolved.

**IN-02 — TRAINERS header comment inconsistency (`apps/client-pwa/src/data/index.js:13-14`):**
Header now reads `"NOTE: TRAINERS was NOT removed — retained for TweaksRoot.jsx dev panel (trainer-detail tweak)"`, consistent with the export on line 74. Resolved.

## Cross-Cutting Assessment (carried forward — all clean)

**Client-safe projection:** `ClientTrainerDetailResponse` exposes only `id / full_name / photo_url / specialization / bio`. Leak guard test asserts all forbidden fields absent from the response body. CLEAN.

**404-collapse / anti-enumeration:** SQL filter collapses unknown / inactive / soft-deleted to identical `None` returns; service maps to `NotFoundError("trainer_not_found")` with no branching. Tests cover all three cases and assert identical `code + message` shapes. CLEAN.

**Owner PATCH mass-assignment safety:** `TrainerUpdateRequest` inherits `BackendSchemaBase` (`extra="forbid"`). All three new fields are explicitly declared; no implicit field promotion possible. CLEAN.

**Migration chain:** `0062_trainer_profile_fields` → `0063_seed_trainer_profiles`. Chain correct; 0063 idempotent on re-run. CLEAN.

**Cross-module discipline:** `fetch_trainer_detail` in `client_portal/repository.py` uses raw `text()` SQL; no ORM `Trainer` import in the client_portal module. CLEAN.

**Swap-seam:** `TrainerDetailSheet.jsx` imports `useClientTrainerDetail` from `@/data` (not directly from `@/lib/clientQueries`). `@/data/index.js` correctly re-exports the hook. CLEAN.

---

_Reviewed: 2026-06-06T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
