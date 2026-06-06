---
phase: 86-gym-info-cms
reviewed: 2026-06-06T00:00:00Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - apps/backend/app/modules/gym/models.py
  - apps/backend/app/modules/gym/schemas.py
  - apps/backend/app/modules/gym/repository.py
  - apps/backend/app/modules/gym/service.py
  - apps/backend/app/modules/gym/router.py
  - apps/backend/app/api/v1/router.py
  - apps/backend/app/core/permissions.py
  - apps/backend/alembic/env.py
  - apps/backend/alembic/versions/0058_gym_info.py
  - apps/backend/alembic/versions/0059_seed_gym_info.py
  - apps/backend/tests/integration/test_gym_info.py
  - apps/admin-web/src/shared/session/can.ts
  - apps/admin-web/src/shared/session/registry.ts
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/data/index.js
  - apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx
  - packages/api-client/src/schema.d.ts
findings:
  critical: 2
  warning: 6
  info: 3
  total: 11
status: issues_found
---

# Phase 86: Code Review Report

**Reviewed:** 2026-06-06
**Depth:** standard
**Files Reviewed:** 16 (packages/api-client/src/schema.d.ts reviewed as grep search due to file size)
**Status:** issues_found

## Summary

Phase 86 delivers the gym-info CMS: a singleton ORM model, owner-only PUT, client-facing GET, Alembic DDL + seed migrations, admin RBAC update, and PWA sheet. The RBAC authorization chain is correctly wired — `require_permission(EDIT, GYM)` is declared before `verify_csrf` in the PUT route signature, satisfying RBAC-04 ordering. The D-03 caller-owns-txn discipline is followed: no commit/flush in the repository, only in the service. Migration idempotency (ON CONFLICT (id) DO NOTHING) and chain linkage (0056 → 0057 → 0058 → 0059) are correct.

Two blockers were found: (1) `GymInfoSheet.jsx` imports `useClientGymInfo` from `@/data` — the file whose own module docstring explicitly prohibits net-new screens from importing from it (D-71-09 boundary violation); (2) the `email` field in `GymInfoUpdateRequest` accepts arbitrary text with no format validation, and the PWA concatenates it verbatim into a `mailto:` href, enabling a stored query-injection attack where an owner can seed query parameters (hidden `?to=`, `?cc=`, `?subject=`) into every client's mail client. Four warnings cover the JavaScript-only `replace('@', '')` in `socialUrl` that leaves secondary `@` characters intact (allowing credential-embedded `https://t.me/user@evil.com` URLs), the missing `owner_update_gym_info` operation in `packages/api-client/src/schema.d.ts`, stale counts in two test file docstrings, and the absence of per-item structure validation on the `social` JSONB list field.

---

## Critical Issues

### CR-01: `GymInfoSheet.jsx` imports from `@/data` — explicitly prohibited by D-71-09 boundary

**File:** `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx:21`

**Issue:** The file `apps/client-pwa/src/data/index.js` opens with a comment:

> Net-new screens (ChatScreen, ReferralSheet, TrainerDetailSheet, NotificationsSheet, GymInfoSheet) must NOT import from this file — ESLint boundary enforced (D-71-09).

`GymInfoSheet.jsx` nonetheless imports its query hook directly from `@/data`:

```js
import { useClientGymInfo } from '@/data'
```

`@/data` resolves to `src/data/index.js` (the swap-seam file). This is the exact boundary the comment prohibits. Sibling sheets that were wired after the boundary was established (e.g., `LoyaltySheet.jsx`) correctly import from `@/lib/clientQueries` directly. The ESLint rule referenced (D-71-09) is presumably declared to catch this, but only if configured; the presence of the import in a named file in the exclusion list suggests the rule was not caught at commit time.

**Fix:** Change the import to the direct library path:

```js
// Before (violates D-71-09):
import { useClientGymInfo } from '@/data'

// After (correct pattern — mirrors LoyaltySheet.jsx:20):
import { useClientGymInfo } from '@/lib/clientQueries'
```

---

### CR-02: `email` field in `GymInfoUpdateRequest` lacks format validation — stored `mailto:` query injection

**File:** `apps/backend/app/modules/gym/schemas.py:51`

**Issue:** The `email` field is typed as `str | None = Field(default=None, max_length=255)` with no semantic validation. An owner can persist `tverskaya@mygym.ru?cc=victim@evil.com&subject=Phishing` (52 chars, within the 255 limit). When the PWA renders:

```jsx
href={`mailto:${data.email}`}
```

every client who taps the contact row opens their mail client pre-populated with a hidden `?cc=victim@evil.com` or crafted subject line. This is a stored injection: the owner writes it once; all clients are exposed on every GymInfoSheet load. The attack surface is wider than a typical open-redirect because the email string appears to clients as a legitimate gym address (`tverskaya@mygym.ru` is what they see rendered in `data.email` text), while the actual mailto URI carries additional attacker-controlled query parameters.

**Fix — backend schema:** Replace the bare `str` type with Pydantic `EmailStr` (which validates the address portion and rejects query strings via the email address grammar) or add a field validator that ensures the value contains no `?`, `#`, or `%` characters:

```python
# Option A: EmailStr — drops query strings at validation time
from pydantic import EmailStr, Field

email: EmailStr | None = Field(default=None, max_length=255)

# Option B: regex validator
from pydantic import Field, field_validator
import re

email: str | None = Field(default=None, max_length=255)

@field_validator('email')
@classmethod
def _email_no_query(cls, v: str | None) -> str | None:
    if v is not None and re.search(r'[?#%]', v):
        raise ValueError('email must not contain query string characters')
    return v
```

**Fix — PWA (defence in depth):** Encode the email before interpolating:

```jsx
href={`mailto:${encodeURIComponent(data.email)}`}
```

Note: `encodeURIComponent` encodes `@` which would break the mailto link; the correct defence in depth is `encodeURIComponent` applied only to the local-part + domain, or `new URL('mailto:' + data.email)` with validation. Backend validation is the correct primary fix.

---

## Warnings

### WR-01: `socialUrl` — JavaScript `String.replace()` with string literal replaces only the first `@`; secondary `@` creates credential-embedded URL

**File:** `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx:111`

**Issue:** `socialUrl` strips the leading `@` from Telegram/Instagram handles:

```js
const handle = item.handle.replace('@', '')
if (item.kind === 'tg') return `https://t.me/${handle}`
```

In JavaScript, `String.prototype.replace(string, replacement)` — when the first argument is a string literal (not a RegExp) — replaces only the **first** occurrence. A handle stored as `@user@evil.com` produces:

```
https://t.me/user@evil.com
```

In URL syntax, `user` is the username component (RFC 3986 userinfo) and `evil.com` is the host. Browsers parse this differently: some (including mobile WebView) may navigate to `evil.com` while presenting the link as a Telegram URL. Even in Chrome (which warns for userinfo URLs), the constructed href is semantically wrong and could be exploited by a compromised or rogue owner to produce phishing links that visually appear to go to `t.me`.

Since `social` is `list[Any]` with no per-item schema, an owner can store arbitrary `handle` values including ones containing multiple `@` signs.

**Fix — replace with regex global replace or encodeURIComponent:**

```js
function socialUrl(item) {
  // Strip ALL @ signs, then encode remaining path component
  const handle = encodeURIComponent(item.handle.replaceAll('@', ''))
  if (item.kind === 'tg') return `https://t.me/${handle}`
  if (item.kind === 'ig') return `https://instagram.com/${handle}`
  return '#'
}
```

Or use a regex: `item.handle.replace(/@/g, '')`.

---

### WR-02: `owner_update_gym_info` PUT `/api/v1/gym` operation absent from `packages/api-client/src/schema.d.ts`

**File:** `packages/api-client/src/schema.d.ts` (grep confirmed: no `/api/v1/gym` path, no `owner_update_gym_info` operation)

**Issue:** The `schema.d.ts` is generated from the OpenAPI spec and consumed by the TypeScript client. The client-facing GET endpoint `/api/v1/client/gym` (operation `client_get_gym_info`) is present at line 892. The owner PUT `/api/v1/gym` (operation `owner_update_gym_info`) is missing entirely. Any admin-web code that needs a typed caller for the owner update endpoint cannot use the generated contract and must fall back to untyped fetch calls, defeating the contract layer.

**Fix:** Re-generate `schema.d.ts` after the backend is running with the new route registered. The generation command (typically `pnpm openapi-ts` or equivalent) must be run as part of the Phase 86 release process.

---

### WR-03: `test_owner_only_has_exactly_forty_entries` function name contradicts its body (asserts 41, not 40)

**File:** `apps/backend/tests/unit/test_permissions.py:16`

**Issue:** The function is named `test_owner_only_has_exactly_forty_entries` but its assertion body is `assert len(OWNER_ONLY) == 41`. The name says "forty" (40); the assertion says 41. When this test fails in a future phase that accidentally removes the new GYM entry, the developer sees a function name claiming the expected count is 40, which conflicts with the actual expected count of 41. This is a maintenance hazard, not an execution bug (the assertion is correct).

**Fix:**

```python
def test_owner_only_has_exactly_forty_one_entries() -> None:
```

---

### WR-04: `test_rbac_parity.py` module docstring states "35 entries" — stale by 6 entries after Phases 58 and 86

**File:** `apps/backend/tests/integration/test_rbac_parity.py:4`

**Issue:** The module docstring reads:

```
Three set-equalities (D-13; counts updated through Phase 54 INFRA-42):
  1. OWNER_ONLY pairs (35 entries: 9 v1.1 + 6 v1.2 + 10 v1.4 + 4 v1.5 + 4 v1.6
     + 2 v1.8 Phase 54 INFRA-42 (VIEW|LIST on AUDIT_LOG))
```

The actual count is 41 (Phase 58 added 5 payroll/compensation entries; Phase 86 added 1 GYM entry). The assertion at line 145 (`assert len(OWNER_ONLY) == 41`) is correct, but the module docstring directly contradicts it with "35 entries." This creates a false expectation for any reviewer reading the docstring before the assertion.

**Fix:** Update the docstring to reflect the current 41-entry count and include Phase 58 and Phase 86 in the breakdown list.

---

### WR-05: `GymInfoSheet.jsx` `getOpenStatus` — `hours` array shorter than 7 causes wrong day shown in today row and today row not excluded from remaining-days list

**File:** `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx:73-87`

**Issue:** `getMoscowNow()` derives `todayIdx` as 0–6 (Mon=0, Sun=6) from the Europe/Moscow clock. `getOpenStatus` then accesses `hours[todayIdx] ?? hours[0]`. If the owner stores an `hours` array with fewer than 7 entries (e.g. 5 weekday entries for a gym closed on weekends), two bugs manifest:

1. **Wrong "today" row:** When `todayIdx >= hours.length`, `hours[todayIdx]` is `undefined`; the nullish-coalescing fallback selects `hours[0]` (Monday), so the badge and times displayed are Monday's schedule regardless of the actual day.

2. **Today row not filtered from remaining-days list:** The filter `filter(({ origIdx }) => origIdx !== status.todayIdx)` excludes only rows where `origIdx === todayIdx`. When `todayIdx = 5` (Saturday) and `hours` has only 5 entries (indices 0–4), no row has `origIdx === 5`, so all 5 rows pass the filter and all 5 appear in the "remaining days" section — including the row that was already promoted to the "today row" (via the `hours[0]` fallback), causing a duplicate display.

The seed migration always inserts a 7-entry array, so this does not affect the seeded baseline. However, an owner PUT can replace `hours` with any array via the unvalidated `list[Any]` field.

**Fix:** Either validate on the backend that `hours`, when provided, is exactly 7 entries with the expected `{d, open, close}` shape, or make `getOpenStatus` robust to short arrays:

```js
function getOpenStatus(hours) {
  if (!hours || hours.length === 0) return null
  const { todayIdx, nowMinutes } = getMoscowNow()
  // Clamp todayIdx to actual array length
  const safeTodayIdx = todayIdx < hours.length ? todayIdx : -1
  if (safeTodayIdx === -1) return null  // array too short — skip badge
  const todayRow = hours[safeTodayIdx]
  // ...rest unchanged, using safeTodayIdx in the filter
}
```

---

### WR-06: `social` JSONB field in `GymInfoUpdateRequest` accepts unbounded `list[Any]` with no per-item structure validation — `handle` can carry arbitrary strings that `socialUrl` constructs URLs from

**File:** `apps/backend/app/modules/gym/schemas.py:55`

**Issue:** `social: list[Any] | None = None` applies no validation on item structure. The PWA `socialUrl(item)` reads `item.kind` and `item.handle` to construct external `href` values. Since `Any` accepts anything, an owner can store items such as:

```json
[{"kind": "tg", "handle": "@user@evil.com", "label": "Support"}]
```

This feeds directly into WR-01 and CR-02. Even if WR-01 is fixed (regex to strip all `@`), the absence of schema validation means item structure is only checked by the PWA at render time, with no server-side error.

A typed Pydantic model for social items would reject unexpected shapes at PUT time (validated by `extra='forbid'` if applied to the item model) and provide clear error messages via the standard 422 envelope.

**Fix:** Define a `SocialItem` model and use it:

```python
class SocialItem(BackendSchemaBase):
    kind: Literal['tg', 'ig']
    label: str = Field(max_length=64)
    handle: str = Field(max_length=64, pattern=r'^@[\w.]+$')

class GymInfoUpdateRequest(BackendSchemaBase):
    # ...
    social: list[SocialItem] | None = None
```

---

## Info

### IN-01: `GymInfoResponse.rules` is `list[str]` but `GymInfoUpdateRequest.rules` is also `list[str]` — inconsistency with other list fields typed `list[Any]` is unexplained

**File:** `apps/backend/app/modules/gym/schemas.py:32,54`

**Issue:** `rules` is typed `list[str]` in both response and request schemas, while `hours`, `amenities`, and `social` are `list[Any]`. This is technically correct for the rules field (rules are plain strings per the seed data) but creates an asymmetry: why is `rules` typed while `social` (which has a known `{kind, label, handle}` shape) is `Any`? The inconsistency may confuse maintainers who see `rules` typed and assume the other fields are intentionally untyped for extensibility.

**Fix:** Either upgrade `hours`, `amenities`, and `social` to typed models (see WR-06), or leave them as `Any` and add a comment explaining the deliberate choice. No immediate code change required.

---

### IN-02: `seeded_owner`, `seeded_reception`, `seeded_client` fixtures call `db_session.commit()` — correct for the SAVEPOINT harness, but the pattern matches service-layer semantics that could confuse future fixture authors

**File:** `apps/backend/tests/integration/test_gym_info.py:134,148,163`

**Issue:** The conftest SAVEPOINT harness (`join_transaction_mode='create_savepoint'`) demotes `session.commit()` inside a test to a nested SAVEPOINT release — the outer transaction is still rolled back on teardown. So these commits are safe. However, a fixture that calls `db_session.commit()` in one test file but omits it in another leads to inconsistency. The `seeded_owner` fixture also calls `db_session.commit()` in a pattern that looks identical to service-layer code, making it harder to identify which commits are "test fixture commits" vs "service commits" when debugging failures.

**Fix:** Consider using `db_session.flush()` (not commit) in fixtures to make data visible to subsequent queries within the same session without the semantic weight of a "commit". This is a convention suggestion for fixture hygiene; the current code is not incorrect.

---

### IN-03: `test_rbac_parity.py` module docstring comment "counts updated through Phase 54 INFRA-42" is stale — should read Phase 86 GYM-02

**File:** `apps/backend/tests/integration/test_rbac_parity.py:3`

**Issue:** The parenthetical `(D-13; counts updated through Phase 54 INFRA-42)` was not updated when Phase 58 or Phase 86 were added. The `test_owner_only_count_is_forty` function body correctly documents the Phase 58 and Phase 86 additions, but the module docstring implies the file was last kept current at Phase 54.

**Fix:** Update the phrase to `(D-13; counts updated through Phase 86 GYM-02)`.

---

_Reviewed: 2026-06-06_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
