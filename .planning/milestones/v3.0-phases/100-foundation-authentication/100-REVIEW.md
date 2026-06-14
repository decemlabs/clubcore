---
phase: 100-foundation-authentication
reviewed: 2026-06-13T00:00:00Z
depth: standard
files_reviewed: 27
files_reviewed_list:
  - apps/admin-app/src/api/client.ts
  - apps/admin-app/src/api/client.test.ts
  - apps/admin-app/src/api/query-client.ts
  - apps/admin-app/src/lib/authBus.ts
  - apps/admin-app/src/features/auth/api.ts
  - apps/admin-app/src/features/auth/schemas.ts
  - apps/admin-app/src/features/auth/schemas.test.ts
  - apps/admin-app/src/features/auth/RequireAuth.tsx
  - apps/admin-app/src/pages/login/LoginPage.tsx
  - apps/admin-app/src/pages/login/components/LoginForm.tsx
  - apps/admin-app/src/pages/login/components/RecoveryScreens.tsx
  - apps/admin-app/src/shared/session/can.ts
  - apps/admin-app/src/shared/session/can.test.ts
  - apps/admin-app/src/shared/session/registry.ts
  - apps/admin-app/src/shared/session/types.ts
  - apps/admin-app/src/components/feedback/ComingSoon.tsx
  - apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx
  - apps/admin-app/src/layouts/AppLayout/nav-items.ts
  - apps/admin-app/src/lib/format.ts
  - apps/admin-app/src/app/router.tsx
  - apps/admin-app/vite.config.ts
  - apps/admin-app/eslint.config.js
  - apps/admin-app/package.json
  - apps/admin-app/.gitignore
  - .github/workflows/ci.yml
  - apps/backend/tests/integration/test_rbac_parity.py
findings:
  critical: 2
  warning: 6
  info: 3
  total: 11
status: fixes_applied
---

# Phase 100: Code Review Report

**Reviewed:** 2026-06-13
**Depth:** standard
**Files Reviewed:** 27
**Status:** issues_found

## Summary

Phase 100 implements the authentication transport, session management, RBAC port, and the login UI. The core security-critical pieces — CSRF double-submit injection, single-flight refresh, 401-storm collapse, anti-oracle error mapping, and the owner-short-circuit `can()` function — are all structurally correct. The `OWNER_ONLY` matrix has the right 41 unique entries and the backend parity test will pass. The CI wiring correctly excludes `@clubcore/admin-app` from all three recursive steps.

Two blockers were found. First, the password reset deep-link flow is entirely broken: the email link lands at `/login?state=reset&token=xxx` but `'reset'` is absent from `DEEP_LINKABLE`, so `initialView` always returns `'login'` and the token is silently discarded. Second, the transport test exercises `PUT /api/v1/auth/password-reset/confirm` to verify CSRF injection on mutating verbs, but the real `api.ts` mutation uses `POST` for that endpoint; the test covers a code path that does not exist in production.

Six warnings and three info items follow.

## Critical Issues

### CR-01: Password reset email deep-link broken — `'reset'` missing from `DEEP_LINKABLE`

**File:** `apps/admin-app/src/pages/login/LoginPage.tsx:17-20`

**Issue:** `DEEP_LINKABLE` contains only `['expired', 'logout']`. The backend sends password-reset emails with a link of the form `/login?state=reset&token=<value>`. When a user follows that link, `initialView(params.get('state'))` is called with `'reset'`. Because `'reset'` is not in `DEEP_LINKABLE`, `initialView` falls through and returns `'login'`, rendering the default login screen. The `?token=` query param is never consumed. The entire email-link reset flow silently degrades to "show login page" — the user cannot reset their password via the emailed link.

Note: `ResetScreen` itself reads `window.location.search` for the token (line 198 of `RecoveryScreens.tsx`), confirming that the deep-link intent was there; only the `DEEP_LINKABLE` guard was not updated.

**Fix:**
```ts
// LoginPage.tsx line 17
const DEEP_LINKABLE: AuthView[] = ['expired', 'logout', 'reset']
```

That one change makes `initialView('reset')` return `'reset'`, and `ResetScreen` will find the `?token=` param in `window.location.search`.

---

### CR-02: Transport test exercises wrong HTTP method for `password-reset/confirm` — production code path untested

**File:** `apps/admin-app/src/api/client.test.ts:90-98`

**Issue:** The test titled `'sets X-CSRF-Token on PUT'` calls:
```ts
await staffRequest('put', '/api/v1/auth/password-reset/confirm', ...)
```
But `features/auth/api.ts:110` calls:
```ts
staffRequest('post', '/api/v1/auth/password-reset/confirm', { body })
```
The production mutation is `POST`; the test covers `PUT`. The test passes only because both `PUT` and `POST` go through the same `isMutating()` branch, so it does confirm that CSRF is injected on any mutating verb — but it fails to test the actual production path. A future refactor that changed CSRF behaviour specifically for `PUT` would not be caught here.

**Fix:** Change the test to use `'post'` to match the production call:
```ts
// client.test.ts line 90-98
it('sets X-CSRF-Token on POST (second mutating verb check)', async () => {
  vi.mocked(fetch).mockResolvedValueOnce(make204Response())

  await staffRequest('post', '/api/v1/auth/password-reset/confirm', {
    body: { token: 't', newPassword: 'StrongPass123!' },
  })

  const [, init] = vi.mocked(fetch).mock.calls[0]!
  const headers = init?.headers instanceof Headers
    ? init.headers
    : new Headers(init?.headers as HeadersInit | undefined)
  expect(headers.get('X-CSRF-Token')).toBe(CSRF_TOKEN)
})
```

---

## Warnings

### WR-01: `ResetScreen` submits empty token to backend without client-side guard

**File:** `apps/admin-app/src/pages/login/components/RecoveryScreens.tsx:198-211`

**Issue:** `token` is extracted from `window.location.search` with `?? ''` fallback. The `submit` handler (lines 204-209) validates password length and match but does not check whether `token` is non-empty before calling `confirmReset`. When the form is reached via the in-memory path (`SentScreen → setView('reset')`) without an actual email-link URL, `token` is `''`. The submit then fires `{ token: '', newPassword: ... }` to the backend, producing a network round-trip that always fails. `PasswordResetConfirmSchema` has `token: z.string().min(1)` which would catch this — but the schema is never invoked client-side in this component.

**Fix:** Add a token presence check before calling `confirmReset`:
```ts
// RecoveryScreens.tsx inside submit(), before confirmReset()
if (!token) {
  setErrors({ password: 'Ссылка для сброса пароля недействительна. Перейдите по ссылке из письма.' })
  return
}
```

---

### WR-02: `AppSidebar` nav filter uses URL string matching for `ownerOnly` resource — fragile coupling

**File:** `apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx:49-55`

**Issue:** The filter resolves which `can()` resource to check using `item.to.includes('finance')`:
```ts
can(role, 'view', item.to.includes('finance') ? 'finance' : 'reports')
```
This means ALL `ownerOnly` items that don't have `'finance'` in their route path are gated as `'reports'`. If a future `ownerOnly` item maps to `'settings'` or `'payroll'`, the filter silently uses `'reports'` as the resource — a semantic mismatch that could incorrectly show or hide the item. The correct approach is to carry the resource directly on `NavItem`.

**Fix:** Add a `resource` field to `NavItem`:
```ts
// nav-items.ts
export interface NavItem {
  // ...
  ownerOnly?: boolean
  /** Resource to check when ownerOnly=true */
  ownerResource?: Resource
}

// AppSidebar.tsx
items.filter(
  (item) => !item.ownerOnly || can(role, 'view', item.ownerResource ?? 'finance'),
)
```

---

### WR-03: `Настройки` nav item accessible to reception despite `can('reception','view','settings') === false`

**File:** `apps/admin-app/src/layouts/AppLayout/nav-items.ts:71`

**Issue:** The `Настройки` nav item has no `ownerOnly` flag. Yet `{ action: 'view', resource: 'settings' }` is entry #5 in `OWNER_ONLY` (can.ts line 17), meaning `can('reception', 'view', 'settings')` returns `false`. Reception users will see "Настройки" in the sidebar and can navigate to `/settings` without any UI gate. The backend is authoritative, but a UI gap in a security-sensitive feature is still a defence-in-depth failure.

**Fix:**
```ts
// nav-items.ts line 71
{ label: 'Настройки', to: ROUTES.settings, icon: Settings, ownerOnly: true, ownerResource: 'settings' },
```
And update the filter in `AppSidebar.tsx` per WR-02 to handle `ownerResource: 'settings'`.

---

### WR-04: `ForgotScreen` client-side email validation weaker than the corresponding schema

**File:** `apps/admin-app/src/pages/login/components/RecoveryScreens.tsx:35`

**Issue:** `ForgotScreen` validates the email with `!email.includes('@')`. This passes malformed strings like `'@'`, `'a@'`, `'@b'`. The corresponding schema `PasswordResetRequestSchema` uses `z.string().email()` (RFC-compliant validation). The mutation calls `staffRequest` directly with the unvalidated input. The backend returns 202 regardless (anti-oracle), so no data corruption occurs, but the UX validation message could mislead the user when they type `'@'` and submit successfully.

**Fix:** Use `PasswordResetRequestSchema.safeParse` for the form validation:
```ts
// RecoveryScreens.tsx ForgotScreen submit handler
import { PasswordResetRequestSchema } from '@/features/auth/schemas'

const result = PasswordResetRequestSchema.safeParse({ email })
if (!result.success) {
  setError(result.error.flatten().fieldErrors.email?.[0] ?? 'Введите корректный адрес почты')
  return
}
setError(undefined)
requestReset(result.data, { ... })
```

---

### WR-05: `test_owner_only_count_is_forty` function name says forty, asserts forty-one

**File:** `apps/backend/tests/integration/test_rbac_parity.py:140-152`

**Issue:** The test function is named `test_owner_only_count_is_forty` but both the docstring and the assertions say the expected count is **41** (`assert len(OWNER_ONLY) == 41`). The count was 40 at Phase 58 and grew to 41 in Phase 86 (GYM-02 `edit|gym`). The stale name will confuse the next developer who sees a failing assertion at "forty-one" from a function named "forty".

**Fix:**
```python
# test_rbac_parity.py line 140
def test_owner_only_count_is_forty_one() -> None:
    """Sanity belt — `OWNER_ONLY` is exactly 41 entries.
    ...
    """
```

---

### WR-06: Parity test regex matches comment lines in `can.ts` — count assertion is silently fragile

**File:** `apps/backend/tests/integration/test_rbac_parity.py:57-58`

**Issue:** `_parse_owner_only_pairs()` applies `_PAIR_RE` to the entire text of `can.ts`, including comment lines. Can.ts line 69 contains the comment:
```
// Existing { action: 'view', resource: 'payroll' } and { action: 'view', resource: 'compensation' }
```
The regex matches both pairs in the comment, producing 43 raw hits. The function wraps in `set()` so 43 collapses to 41 unique pairs — the count test still passes. However, the deduplication via `set()` creates a blind spot: if a future editor adds a new pair to the `OWNER_ONLY` array but also mentions that exact same pair in a comment (e.g., a copy-paste from the array), the count assertion still passes even though the new entry was added correctly. Conversely, removing an entry from the array while a comment still mentions it would not decrease the set count. The test appears to assert correctness but is weaker than it looks.

**Fix:** Pre-filter comment lines before applying the regex:
```python
def _parse_owner_only_pairs() -> set[tuple[str, str]]:
    non_comment_lines = [
        ln for ln in _read_text(_CAN_TS).splitlines()
        if not ln.lstrip().startswith('//')
    ]
    return set(_PAIR_RE.findall('\n'.join(non_comment_lines)))
```

---

## Info

### IN-01: `LoginPage.tsx` uses semicolons throughout — project style is no-semicolons (ASI)

**File:** `apps/admin-app/src/pages/login/LoginPage.tsx:20,30-36` (and throughout)

**Issue:** The project Prettier config specifies no semicolons (ASI). `LoginPage.tsx` consistently uses trailing semicolons on every statement (`const navigate = useNavigate();`, `return ...;`, etc.). All other Phase 100 files (`api.ts`, `schemas.ts`, `authBus.ts`, `can.ts`) are semicolon-free. This file was not run through Prettier before commit.

**Fix:** Run `pnpm prettier --write apps/admin-app/src/pages/login/LoginPage.tsx`.

---

### IN-02: ESLint `VITE_API_MODE` chokepoint exempts all of `features/auth/**`, not just `api.ts`

**File:** `apps/admin-app/eslint.config.js:66`

**Issue:** The `no-restricted-syntax` ignore list is `'src/features/auth/**'`. The intent (per the comment) is to allow `features/*/api.ts` swap-seam files to read `VITE_API_MODE`. But the glob exempts `RequireAuth.tsx`, `schemas.ts`, `schemas.test.ts`, and any future file added under `features/auth/`. None of those files use `VITE_API_MODE` today, but the exemption is broader than intended and could silently permit a future access in a non-swap-seam file.

**Fix:**
```js
// eslint.config.js line 66
ignores: ['src/features/*/api.ts'],
```

---

### IN-03: `remember-me` state is tracked and rendered but the value is never sent to the login mutation

**File:** `apps/admin-app/src/pages/login/components/LoginForm.tsx:35,60`

**Issue:** `const [remember, setRemember] = useState(true)` tracks the checkbox state, but `login(result.data, ...)` passes only `result.data` (which is `LoginRequest = { email, password }`). The `remember` value is not forwarded to the mutation. A Callout in the UI explicitly informs the user that the parameter has no effect (line 139), so this is intentional. However, holding tracked-but-unused state that the framework considers "live" is unnecessary. If `remember` is truly a documented no-op, the checkbox and state can be removed entirely, or the Callout can replace the checkbox.

**Fix (if keeping the disclosure):** Remove the checkbox and state, keep only the Callout:
```tsx
// LoginForm.tsx — remove lines 35 and 131-133 (state + checkbox label)
// Keep the Callout div to maintain the disclosure to the user
```

---

_Reviewed: 2026-06-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
