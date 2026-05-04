---
phase: 10-admin-web-auth-clients-wiring
fixed_at: 2026-05-04T20:20:00Z
review_path: .planning/phases/10-admin-web-auth-clients-wiring/10-REVIEW.md
fix_scope: critical_warning
findings_in_scope: 11
fixed: 11
skipped: 0
iteration: 1
status: all_fixed
---

# Phase 10: Code Review Fix Report

**Fixed at:** 2026-05-04T20:20:00Z
**Source review:** `.planning/phases/10-admin-web-auth-clients-wiring/10-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 11 (4 Critical + 7 Warning; Info skipped per scope)
- Fixed: 11
- Skipped: 0

## Fixed Issues

### CR-01: Open-redirect via `forbidden` search param renders a full `location.href` in the DOM

**Files modified:**
- `apps/admin-web/src/routes/_protected/clients.tsx`
- `apps/admin-web/src/routes/_protected/finance.tsx`
- `apps/admin-web/src/routes/_protected/staff.tsx`
- `apps/admin-web/src/routes/_protected/schedule.tsx`
- `apps/admin-web/src/routes/_protected/settings.tsx`
**Commit:** 9fdc8e2
**Applied fix:** Replaced `location.href` (full absolute URL with origin) with `location.pathname + (location.search ?? '')` in every RBAC `beforeLoad` redirect, mirroring the safe pattern already used for `next` in `_protected.tsx`. This stops the origin from leaking into the DOM via the `forbidden` query param.

### CR-02: Unsanitised `deepLinkUrl` used as `href` — potential `javascript:` injection

**Files modified:** `apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx`
**Commit:** 5a4eec5
**Applied fix:** In `handleStart.onSuccess`, refuse to set `deepLink` state when the response URL does not start with `https://t.me/`. Logs the rejected URL via `console.error` so backend regressions are visible during dev/QA.

### CR-03: Mock services import schemas from `features/` — violates the layered architecture

**Files modified:**
- `apps/admin-web/src/entities/client/schema.ts` (new)
- `apps/admin-web/src/entities/client/index.ts`
- `apps/admin-web/src/shared/api/contracts/authSchema.ts` (new)
- `apps/admin-web/src/shared/api/contracts/index.ts`
- `apps/admin-web/src/features/auth/model/schema.ts`
- `apps/admin-web/src/features/clients/model/schema.ts`
- `apps/admin-web/src/shared/api/services/mock/auth.ts`
- `apps/admin-web/src/shared/api/services/mock/clients.ts`
**Commit:** 63254d9
**Applied fix:** Moved `clientCreateSchema` / `clientUpdateSchema` / `clientsListQuerySchema` to `src/entities/client/schema.ts`, and `emailLoginSchema` / `telegramOtpSchema` to `src/shared/api/contracts/authSchema.ts`. Feature `model/schema.ts` files now thin re-export from these canonical locations so existing form imports continue to work, and mock services import from the new locations — no longer crossing `shared → features` in reverse.

### CR-04: `redirecting` flag reset is not guarded against dynamic import failure

**Files modified:**
- `apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts`
- `apps/admin-web/src/features/auth/api/redirect-on-session-expired.test.ts`
**Commit:** 97538c7
**Applied fix:** Moved `queryClient.clear()` to fire only after `router.navigate()` resolves successfully, avoiding the broken intermediate state (cache cleared, still on protected page). Added `.catch(() => {})` after the `.finally()` so navigate-rejection or import-rejection does not surface as an unhandled promise rejection. Added a regression test asserting that on `navigate.mockRejectedValueOnce(...)` the flag still resets and `clearMock` is **not** called.
**Verification note:** Logic change verified by new test plus existing happy-path test; both pass.

### WR-01: Optimistic update spreads `ClientUpdateInput` directly onto `Client` — `fullName` is never updated optimistically

**Files modified:** `apps/admin-web/src/features/clients/api/hooks.ts`
**Commit:** 4b9db85
**Applied fix:** Added `applyOptimisticUpdate(current, input)` and `buildOptimisticFullName(current, input)` helpers that mirror the mock service's split-by-space composition. The optimistic update now writes the correct `Client` shape (no extra `firstName`/`lastName`/`middleName` keys) and recomputes `fullName` when any name part changes.
**Verification note:** Logic correctness — flagged for human verification of the split-by-space heuristic for 4+ token names (the mock service has the same heuristic by design, see comment).

### WR-02: Telegram OTP timed-out retry race

**Files modified:** `apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx`
**Commit:** 47abb36
**Applied fix:** Removed the eager `setTimedOut(false)` from the timed-out screen's "Получить новую ссылку" button. `handleStart.onSuccess` already flips `timedOut` once the new token arrives, so the timed-out screen now stays visible during a failed retry instead of silently reverting to the idle screen with no error. Added a `start.isError` alert in the timed-out branch so retry failures surface to the user.

### WR-03: `redirectOnSessionExpired` imports `ApiError` directly from `@sportzal/api-client`

**Files modified:** `apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts`
**Commit:** c29c519
**Applied fix:** Changed import to `import { ApiError } from '@/shared/api/errors'`, the canonical re-export documented in CLAUDE.md.

### WR-04: `useClientsList` does not specify `staleTime` — inconsistent with project convention

**Files modified:** `apps/admin-web/src/features/clients/api/hooks.ts`
**Commit:** 6810d27
**Applied fix:** Added explicit `staleTime: 30_000` to both `useClientsList` and `useClient`, matching the convention set by `useMe` and the project's documented per-feature query hygiene rule.

### WR-05: `ru.ts` defines `auth.errors.otpMaxAttempts` but `TelegramLoginTab` never handles the `otp_max_attempts` error code

**Files modified:** `apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx`
**Commit:** 861d2cb
**Applied fix:** Added an `else if (c === 'otp_max_attempts')` branch in `handleVerify.onError` that surfaces "Код заблокирован. Начните процесс заново." on the OTP code field. The literal string is used inline (matches the existing pattern of inline literals in this handler); the dictionary entry remains as the canonical source for any future i18n refactor.

### WR-06: `ClientForm` does not show error messages for `birthDate`, `middleName`, `notes`

**Files modified:** `apps/admin-web/src/features/clients/components/ClientForm.tsx`
**Commit:** 40cdee7
**Applied fix:** Added the standard `{form.formState.errors.<field> && <p>...}` blocks below the `middleName`, `birthDate`, and `notes` inputs so server-side validation errors bound to those fields by `handleError` actually render.

### WR-07: `http/auth.ts` constructs Telegram status URL with manual string interpolation

**Files modified:** `apps/admin-web/src/shared/api/services/http/auth.ts`
**Commit:** 4cd681d
**Applied fix:** Refactored the inline interpolated URL into a `const url = ...` and expanded the comment to document why `as never` is safe here (encoded token, literal path prefix, openapi-fetch types do not represent dynamic query strings yet). Added a `TODO` to swap to typed query params when `@sportzal/api-client` gains a `query` field.

---

_Fixed: 2026-05-04T20:20:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
