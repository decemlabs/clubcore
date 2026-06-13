---
phase: 100-foundation-authentication
fixed_at: 2026-06-13T12:43:00Z
review_path: .planning/phases/100-foundation-authentication/100-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 100: Code Review Fix Report

**Fixed at:** 2026-06-13T12:43:00Z
**Source review:** .planning/phases/100-foundation-authentication/100-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (CR-01, CR-02, WR-01, WR-02, WR-03, WR-04, WR-05, WR-06, IN-01)
- Fixed: 9
- Skipped: 0

**Verification:** `pnpm -F @clubcore/admin-app typecheck && lint && test` — 99/99 passed.
`uv run pytest tests/integration/test_rbac_parity.py -q` — 4/4 passed.

---

## Fixed Issues

### CR-01: Password reset email deep-link broken

**Files modified:** `apps/admin-app/src/pages/login/LoginPage.tsx`
**Commit:** `829c52c2`
**Applied fix:** Added `'reset'` to `DEEP_LINKABLE` array. `initialView('reset')` now returns `'reset'` instead of falling through to `'login'`, so the email deep-link `/login?state=reset&token=xxx` correctly opens `ResetScreen` which reads the token from `window.location.search`.

---

### CR-02: Transport test exercises wrong HTTP method for password-reset/confirm

**Files modified:** `apps/admin-app/src/api/client.test.ts`
**Commit:** `d75eadee`
**Applied fix:** Changed the `'sets X-CSRF-Token on PUT'` test to use `'post'` with the actual production path and body shape (`newPassword` not `password`). Renamed test title to `'sets X-CSRF-Token on POST (second mutating verb check — matches production password-reset/confirm)'`.

---

### WR-01: ResetScreen submits empty token to backend without client-side guard

**Files modified:** `apps/admin-app/src/pages/login/components/RecoveryScreens.tsx`
**Commit:** `e9cb628e`
**Applied fix:** Added a token presence check at the top of `submit()` before password validation. If `token` is empty, sets `errors.password` to a Russian-language message directing the user to follow the link from the email, and returns early without calling `confirmReset`.

---

### WR-02: AppSidebar nav filter uses URL string matching for ownerOnly resource

**Files modified:** `apps/admin-app/src/layouts/AppLayout/nav-items.ts`, `apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx`
**Commit:** `20a2c0f5`
**Applied fix:** Added `ownerResource?: Resource` field to `NavItem` interface. Updated `AppSidebar` filter to use `item.ownerResource ?? 'finance'` instead of `item.to.includes('finance') ? 'finance' : 'reports'`. Updated `Отчёты` and `Финансы` entries with explicit `ownerResource: 'reports'` and `ownerResource: 'finance'` respectively. Also imported `Resource` type from `@/shared/session/can` in `nav-items.ts`.

---

### WR-03: Настройки nav item accessible to reception

**Files modified:** `apps/admin-app/src/layouts/AppLayout/nav-items.ts`, `apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx`
**Commit:** `20a2c0f5`
**Applied fix:** Added `ownerOnly: true, ownerResource: 'settings'` to the `Настройки` nav item. Reception role has `{ action: 'view', resource: 'settings' }` in `OWNER_ONLY` (can.ts line 17), so `can('reception', 'view', 'settings')` returns `false` and the item is now hidden. Fixed together with WR-02 as a cohesive group.

---

### WR-04: ForgotScreen client-side email validation weaker than schema

**Files modified:** `apps/admin-app/src/pages/login/components/RecoveryScreens.tsx`
**Commit:** `e9cb628e`
**Applied fix:** Replaced the weak `!email.includes('@')` check with `PasswordResetRequestSchema.safeParse({ email })` (imports `PasswordResetRequestSchema` from `@/features/auth/schemas`). Error message from the schema's `z.string().email()` validator is surfaced directly. `requestReset` is called with `parsed.data` rather than the raw `{ email }` object.

---

### WR-05: test_owner_only_count_is_forty function name says forty, asserts forty-one

**Files modified:** `apps/backend/tests/integration/test_rbac_parity.py`
**Commit:** `c2be3f06`
**Applied fix:** Renamed `test_owner_only_count_is_forty` to `test_owner_only_count_is_forty_one` to match the docstring and assertion (`assert len(OWNER_ONLY) == 41`).

---

### WR-06: Parity test regex matches comment lines in can.ts

**Files modified:** `apps/backend/tests/integration/test_rbac_parity.py`
**Commit:** `c2be3f06`
**Applied fix:** Updated `_parse_owner_only_pairs()` to pre-filter lines starting with `//` before applying `_PAIR_RE`. The comment at `can.ts` line 69 mentions two pair literals that previously inflated the raw hit count to 43; the `set()` dedup collapsed them back to 41, masking future add/remove mistakes. Now only non-comment lines are scanned. Fixed together with WR-05.

---

### IN-01: LoginPage.tsx style consistency (Prettier)

**Files modified:** `apps/admin-app/src/pages/login/LoginPage.tsx`, `apps/admin-app/src/pages/login/components/RecoveryScreens.tsx`, `apps/admin-app/src/layouts/AppLayout/nav-items.ts`, `apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx`
**Commit:** `2b3f81c0`
**Applied fix:** Read `apps/admin-app/.prettierrc` first — it specifies `"semi": true`, so the admin-app's own convention is WITH semicolons (the REVIEW.md note about no-semicolons referred to the root project config, which does not apply here). Ran `prettier --config apps/admin-app/.prettierrc --write` against all four modified TypeScript files. The output confirmed `LoginPage.tsx` already used correct semicolons; the formatter also normalized whitespace/formatting in the other three files to match admin-app style.

---

_Fixed: 2026-06-13T12:43:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
