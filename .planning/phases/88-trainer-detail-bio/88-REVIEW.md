---
phase: 88-trainer-detail-bio
reviewed: 2026-06-06T00:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - apps/backend/app/modules/trainers/models.py
  - apps/backend/app/modules/trainers/schemas.py
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/app/modules/client_portal/repository.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/app/modules/client_portal/router.py
  - apps/backend/alembic/versions/0062_trainer_profile_fields.py
  - apps/backend/alembic/versions/0063_seed_trainer_profiles.py
  - apps/backend/tests/integration/client_portal/test_client_trainer_detail.py
  - apps/backend/tests/integration/trainers/test_trainers_bio_patch.py
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/data/index.js
  - apps/client-pwa/src/screens/sheets/TrainerDetailSheet.jsx
  - apps/client-pwa/src/screens/sheets/TrainerDetailSheet.test.jsx
  - apps/client-pwa/eslint.config.js
  - packages/api-client/src/schema.d.ts
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 88: Code Review Report

**Reviewed:** 2026-06-06
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Phase 88 adds three profile columns to the Trainer model (`bio`, `specialization`, `photo_url`), a client-safe GET detail endpoint, and a frontend sheet that renders the live data. The core security requirements are largely met: the client detail projection correctly exposes only `id / full_name / photo_url / specialization / bio`; the 404-collapse anti-enumeration is complete; the owner PATCH routes through the existing `extra='forbid'` schema; and the frontend `isSafePhotoUrl` guard rejects non-http(s) schemes. One critical finding concerns the absence of server-side URL scheme validation for `photo_url` on the write path — a `javascript:` value can be persisted to the database by an owner and then served to every client via the GET endpoint. Three warnings cover the 0063 downgrade scope, a weak XSS test assertion pattern, and a missing unauthenticated-access test case. Two info items cover a stale comment and a minor test documentation gap.

## Critical Issues

### CR-01: `photo_url` accepts `javascript:` and `data:` schemes server-side — stored in DB and served to clients

**File:** `apps/backend/app/modules/trainers/schemas.py:58`
**Issue:** `TrainerUpdateRequest.photo_url` is validated only by `max_length=2048`. There is no server-side scheme allow-list. An authenticated owner can PATCH `photo_url = "javascript:alert(document.cookie)"` and the backend stores it in the database without error. The value is then returned verbatim to every authenticated client via `GET /api/v1/client/trainers/{id}`. The frontend `isSafePhotoUrl` guard (TrainerDetailSheet line 45–53) prevents the value from reaching an `<img src>` attribute in the current React sheet, but the dangerous URL now lives in the API response body. Any future consumer of the endpoint (another frontend, a native app, an admin panel) that does not implement the same guard would be vulnerable. The risk is not theoretical: the admin panel's `TrainerResponse` schema (`apps/backend/app/modules/trainers/schemas.py:78`) also includes `photo_url` with no restriction — a future admin UI rendering it could be affected.

The project comment at line 57 explicitly defers scheme validation to "render time (Plan 03 T-88-03)" — this is an architectural decision documented in the plan, but as a stored-and-served value the scheme check belongs at the persistence boundary, not only at the render boundary.

**Fix:** Add a Pydantic field validator on `photo_url` that rejects non-http(s) schemes before the value reaches the database. The `AnyUrl` type or a custom `@field_validator` are both acceptable:

```python
from pydantic import field_validator

class TrainerUpdateRequest(BackendSchemaBase):
    ...
    photo_url: str | None = Field(default=None, max_length=2048)

    @field_validator("photo_url", mode="before")
    @classmethod
    def _validate_photo_url_scheme(cls, v: object) -> object:
        if v is None:
            return v
        if not isinstance(v, str):
            return v
        lower = v.lower()
        if not (lower.startswith("http://") or lower.startswith("https://")):
            raise ValueError("photo_url must use http or https scheme")
        return v
```

This means a malformed or deliberately injected URL raises a 422 before the row is written, eliminating the stored-XSS risk at the source.

## Warnings

### WR-01: 0063 `downgrade()` over-broadly resets ALL alive trainers, not just the six seeded rows

**File:** `apps/backend/alembic/versions/0063_seed_trainer_profiles.py:88-93`
**Issue:** The `downgrade()` runs `UPDATE trainers SET specialization = NULL, bio = NULL, photo_url = NULL WHERE deleted_at IS NULL`. This blanket wipe covers every non-deleted trainer in the database, including rows that existed before the migration ran and rows added by the owner after the seed. Running `alembic downgrade -1` on a production database would silently destroy all owner-edited bios and photos for trainers added outside the six hardcoded names. The `upgrade()` path is safe (UPDATE by `full_name` only affects the six named rows); the downgrade is not symmetric.

**Fix:** Scope the downgrade to only the rows that the upgrade touched, mirroring the upgrade's `full_name` filter:

```python
def downgrade() -> None:
    names = [profile[0] for profile in _TRAINER_PROFILES]
    # Build a parameterised ANY array to reset only the seeded rows.
    for full_name in names:
        op.execute(
            sa.text(
                "UPDATE trainers "
                "SET specialization = NULL, bio = NULL, photo_url = NULL "
                "WHERE full_name = :name AND deleted_at IS NULL"
            ).bindparams(name=full_name)
        )
```

### WR-02: XSS test assertion is vacuous when `img` NodeList is empty

**File:** `apps/client-pwa/src/screens/sheets/TrainerDetailSheet.test.jsx:149-152` and `167-170`
**Issue:** The XSS guard tests query `document.querySelectorAll('img')` and then iterate with `forEach`. When `safePhotoUrl` is `null` (the expected outcome for `javascript:` / `data:` inputs), the component renders an `<Avatar>` which is a `<div>`, not an `<img>`. The `NodeList` is empty and the `forEach` body never runs — the `expect(…).not.toContain(…)` assertions are never evaluated. The test passes trivially whether or not the unsafe URL leaks into a hypothetical `<img>`. The positive guard (`expect(screen.getByText('АС')).toBeInTheDocument()`) does provide real coverage by verifying the Avatar fallback rendered, but a developer reading the test sees the `forEach` pattern and may believe the negative assertion is meaningful.

**Fix:** Assert directly that no `<img>` element is present in the DOM when the URL is unsafe, rather than asserting all (zero) images have safe src attributes:

```js
// Instead of:
const imgs = document.querySelectorAll('img')
imgs.forEach((img) => {
  expect(img.getAttribute('src')).not.toContain('javascript:')
})

// Use:
const img = document.querySelector('img')
expect(img).toBeNull() // no img should render at all for unsafe URLs
expect(screen.getByText('АС')).toBeInTheDocument()
```

### WR-03: Integration test suite has no unauthenticated-access test for the trainer detail endpoint

**File:** `apps/backend/tests/integration/client_portal/test_client_trainer_detail.py`
**Issue:** All six test cases in this file call `_get_trainer_authed` which attaches a valid `cc_client_access` cookie. There is no test that issues the same `GET /api/v1/client/trainers/{id}` request without any cookie and asserts the server returns 401. The endpoint is gated by `require_client()` in the router (line 347), so the 401 behavior is mechanically guaranteed by the existing RBAC machinery, but per the project's convention for client-portal endpoints (confirmed in other test files such as `test_idor_sweep.py`), an explicit 401 check is the expected baseline coverage for each new endpoint.

**Fix:** Add a test:

```python
async def test_client_get_trainer_requires_auth(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /client/trainers/{id} without credentials → 401."""
    trainer = Trainer(full_name="Auth Required Trainer", is_active=True)
    db_session.add(trainer)
    await db_session.commit()

    resp = await async_client.get(f"/api/v1/client/trainers/{trainer.id}")
    assert resp.status_code == 401, resp.json()
```

## Info

### IN-01: Stale comment in `ClientAvailableSlotItem` references `specialization` as "NOT on the Trainer model in v1"

**File:** `apps/backend/app/modules/client_portal/schemas.py:209`
**Issue:** The comment on `ClientAvailableSlotItem` reads "specialization is NOT on the Trainer model in v1 (reserved for future)". Phase 88 adds `specialization` as a real column on the Trainer model. The comment is now factually wrong and will mislead future reviewers who read it.

**Fix:** Update the comment to remove the stale note, e.g.:
```python
# specialization is available on Trainer since Phase 88 but is not included
# in the slot catalog projection per D-69-05 (slot list shows name only).
```

### IN-02: `TRAINERS` legacy mock re-exported from `@/data` is still consumed by `TweaksRoot.jsx` — D-71-09 de-list is partial

**File:** `apps/client-pwa/src/data/index.js:73`
**Issue:** The `TRAINERS` mock constant is still exported from `@/data/index.js` (line 73) with the comment "Retained for TweaksRoot.jsx dev panel (trainer-detail tweak button)". The Phase 88 review criteria asks to confirm that D-71-09 de-list is complete (grep 0). `TRAINERS` is intentionally retained for the dev-only Tweaks panel, so this is not a regression — but the comment in the file header (line 13) also says `TRAINERS` was "REMOVED in Plan 06", which contradicts line 73 where it is still exported. The two statements are inconsistent: the header says removed, the export list says retained. This will confuse future maintainers about whether the constant is live or dead.

**Fix:** Reconcile the comment at line 13 to match the retained export. Update the header to note that `TRAINERS` was retained (not removed) because TweaksRoot.jsx uses it:

```js
// REMOVED in Plan 06 (BookScreen + QRSheet wired to real backend):
//   - CALENDAR, TIME_SLOTS, BUSY_SLOTS → replaced by useClientAvailableSlots
// NOTE: TRAINERS was NOT removed — retained for TweaksRoot.jsx dev panel (trainer-detail tweak)
```

---

## Cross-Cutting Assessment

**Client-safe projection:** `ClientTrainerDetailResponse` correctly exposes only `id / full_name / photo_url / specialization / bio`. The raw SQL in `fetch_trainer_detail` (`repository.py:549`) selects exactly those five columns. No phone, is_active, deleted_at, created_at, updated_at, or rates appear in the projection. The leak guard integration test (`test_client_get_trainer_leak_guard`) explicitly asserts all forbidden field names are absent from the response body. CLEAN.

**404-collapse / anti-enumeration:** The SQL filter `WHERE id = CAST(:trainer_id AS UUID) AND is_active = true AND deleted_at IS NULL` collapses unknown / soft-deleted / inactive to identical `None` returns. The service layer maps `None` to `NotFoundError("trainer_not_found")` with no branching. Tests cover all three cases and assert identical `code` + `message` shapes. CLEAN.

**Owner PATCH mass-assignment safety:** `TrainerUpdateRequest` inherits `BackendSchemaBase` which carries `extra="forbid"` (confirmed in `app/core/schemas.py:52`). Sending unknown fields raises 422. The three new fields (`bio`, `specialization`, `photo_url`) are explicitly listed; no implicit field promotion is possible. CLEAN (see CR-01 for the scheme validation gap on photo_url).

**Migration chain:** `0061_client_push_tokens` → `0062_trainer_profile_fields` → `0063_seed_trainer_profiles`. Chain is correct. 0062 adds three nullable Text columns (ADD COLUMN is metadata-only on Postgres 16 — correct). 0063 is idempotent on re-run (UPDATE by full_name sets the same values). CLEAN.

**Cross-module discipline:** `fetch_trainer_detail` in `repository.py` uses raw `text()` SQL only. No ORM import of `Trainer` is present in `client_portal/repository.py`. CLEAN.

**Swap-seam:** `TrainerDetailSheet.jsx` imports `useClientTrainerDetail` from `@/data` (line 21), not directly from `@/lib/clientQueries`. `@/data/index.js` correctly re-exports the hook (line 65). CLEAN.

**schema.d.ts consistency:** `ClientTrainerDetailResponse` at line 3784 has `id: string`, `fullName: string`, `photoUrl: string | null`, `specialization: string | null`, `bio: string | null` — matches the Pydantic schema exactly. The `client_get_trainer` operation at line 8069 references the correct envelope type. CLEAN.

---

_Reviewed: 2026-06-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
