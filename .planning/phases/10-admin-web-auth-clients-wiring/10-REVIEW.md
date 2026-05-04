---
phase: 10-admin-web-auth-clients-wiring
reviewed: 2026-05-04T14:43:59Z
depth: standard
files_reviewed: 73
files_reviewed_list:
  - apps/admin-web/.env.example
  - apps/admin-web/components.json
  - apps/admin-web/eslint.config.js
  - apps/admin-web/package.json
  - apps/admin-web/scripts/assert-eslint-fixtures.mjs
  - apps/admin-web/scripts/eslint.fixtures.config.js
  - apps/admin-web/src/__fixtures/raw-fetch-leak.ts
  - apps/admin-web/src/app/index.css
  - apps/admin-web/src/app/main.tsx
  - apps/admin-web/src/app/queryClient.ts
  - apps/admin-web/src/app/router.ts
  - apps/admin-web/src/entities/client/index.ts
  - apps/admin-web/src/entities/client/types.ts
  - apps/admin-web/src/features/auth/api/hooks.ts
  - apps/admin-web/src/features/auth/api/keys.ts
  - apps/admin-web/src/features/auth/api/redirect-on-session-expired.test.ts
  - apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts
  - apps/admin-web/src/features/auth/components/EmailLoginForm.tsx
  - apps/admin-web/src/features/auth/components/LoginPage.test.tsx
  - apps/admin-web/src/features/auth/components/LoginPage.tsx
  - apps/admin-web/src/features/auth/components/TelegramLoginTab.test.tsx
  - apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx
  - apps/admin-web/src/features/auth/index.ts
  - apps/admin-web/src/features/auth/model/schema.ts
  - apps/admin-web/src/features/clients/api/hooks.delete.test.tsx
  - apps/admin-web/src/features/clients/api/hooks.ts
  - apps/admin-web/src/features/clients/api/keys.test.ts
  - apps/admin-web/src/features/clients/api/keys.ts
  - apps/admin-web/src/features/clients/components/ClientDeleteDialog.tsx
  - apps/admin-web/src/features/clients/components/ClientForm.tsx
  - apps/admin-web/src/features/clients/components/ClientFormDialog.tsx
  - apps/admin-web/src/features/clients/components/ClientsPage.tsx
  - apps/admin-web/src/features/clients/components/ClientsTable.rbac.test.tsx
  - apps/admin-web/src/features/clients/components/ClientsTable.tsx
  - apps/admin-web/src/features/clients/components/ClientsTableSkeleton.tsx
  - apps/admin-web/src/features/clients/index.ts
  - apps/admin-web/src/features/clients/model/schema.ts
  - apps/admin-web/src/routes/__root.tsx
  - apps/admin-web/src/routes/_protected.tsx
  - apps/admin-web/src/routes/_protected/clients.tsx
  - apps/admin-web/src/routes/_protected/finance.tsx
  - apps/admin-web/src/routes/_protected/index.tsx
  - apps/admin-web/src/routes/_protected/schedule.tsx
  - apps/admin-web/src/routes/_protected/settings.tsx
  - apps/admin-web/src/routes/_protected/staff.tsx
  - apps/admin-web/src/_routes/_public.tsx
  - apps/admin-web/src/routes/_public/login.tsx
  - apps/admin-web/src/shared/api/contracts/auth.ts
  - apps/admin-web/src/shared/api/contracts/clients.ts
  - apps/admin-web/src/shared/api/contracts/index.ts
  - apps/admin-web/src/shared/api/errors.ts
  - apps/admin-web/src/shared/api/services/http/_envelope.test.ts
  - apps/admin-web/src/shared/api/services/http/_envelope.ts
  - apps/admin-web/src/shared/api/services/http/auth.ts
  - apps/admin-web/src/shared/api/services/http/clients.ts
  - apps/admin-web/src/shared/api/services/http/index.ts
  - apps/admin-web/src/shared/api/services/mock/_db.ts
  - apps/admin-web/src/shared/api/services/mock/_latency.ts
  - apps/admin-web/src/shared/api/services/mock/auth.ts
  - apps/admin-web/src/shared/api/services/mock/clients.crud.test.ts
  - apps/admin-web/src/shared/api/services/mock/clients.rbac.test.ts
  - apps/admin-web/src/shared/api/services/mock/clients.ts
  - apps/admin-web/src/shared/api/services/mock/index.ts
  - apps/admin-web/src/shared/i18n/ru.ts
  - apps/admin-web/src/shared/lib/brand.ts
  - apps/admin-web/src/shared/lib/hooks/useDebounceValue.ts
  - apps/admin-web/src/shared/session/RoleGate.tsx
  - apps/admin-web/src/shared/session/index.ts
  - apps/admin-web/src/shared/session/useCurrentRole.ts
  - apps/admin-web/src/shared/ui/app-shell/ProfileMenu.test.tsx
  - apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx
  - apps/admin-web/src/shared/ui/app-shell/RoleSwitcher.tsx
  - apps/admin-web/src/shared/ui/data-grid.tsx
  - apps/admin-web/src/shared/ui/splash.tsx
findings:
  critical: 4
  warning: 7
  info: 4
  total: 15
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-05-04T14:43:59Z
**Depth:** standard
**Files Reviewed:** 73
**Status:** issues_found

## Summary

Phase 10 wires up email/password + Telegram OTP auth, HTTP transport via `@sportzal/api-client`, mock auth and clients services, full `/clients` CRUD with optimistic mutations, a single-flight `session_expired` redirect, and an ESLint ban on raw `fetch()`. The overall architecture is sound: the swap-seam pattern is clean, RBAC enforcement is consistent between mock services and `RoleGate`, and the optimistic mutation / rollback pattern for delete is correct.

Four blockers were found: two are security issues (open-redirect via `forbidden` search param, deepLink `href` unsanitized), one is an architectural layer violation (mock services importing from `features/`), and one is a missing test case that leaves the `redirecting` flag reset timing unverified across module reloads. Seven warnings cover correctness gaps (fullName optimistic update, missing OTP brute-force handling, `redirecting` reset on import error, missing token parameter construction type-safety, i18n dead code) and quality issues. Four info items cover minor quality and naming issues.

---

## Critical Issues

### CR-01: Open-redirect via `forbidden` search param renders a full `location.href` in the DOM

**File:** `apps/admin-web/src/routes/_protected/clients.tsx:19` (and `finance.tsx:9`, `staff.tsx:9`, `schedule.tsx:9`, `settings.tsx:9`)

**Issue:** Every RBAC-blocked route redirects to `/?forbidden=location.href`. The `location.href` value is the full absolute URL including origin (e.g. `https://example.com/clients?q=x`). This value is stored in the `forbidden` URL search parameter. On the index page (`_protected/index.tsx:24`) it is rendered inside a `<code>` element as `{search.forbidden}`. While React escapes the text content, the URL is exposed in the query string of the rendered page and surfaced verbatim to operators. More critically, if an attacker can craft a navigation to `/clients` while logged in as reception (which they can, since `beforeLoad` runs before auth check on the parent route in mock mode), they can set `forbidden` to any string they like because `validateSearch` on the index route only accepts `z.string().optional()` — no sanitisation. The `forbidden` param on `_protected/index.tsx` accepts an arbitrary string from the URL and renders it; the path is `RBAC redirect → index page`. The protective assumption is that only authenticated, RBAC-gated routes can reach the index page, but in mock mode the parent `_protected.beforeLoad` is skipped (`if (API_MODE === 'mock') return`), and `?forbidden=<script>alert(1)</script>` would be visible in the DOM (though React escapes it). The more concrete risk: `location.href` includes the full origin, which means the displayed error message in production will read "Доступ запрещён: https://attacker.com/..." if a cross-site redirect somehow lands there, misleading operators.

The `next` param used in `_protected.tsx:19` correctly uses `location.pathname + location.search` (no origin). The `forbidden` param should follow the same pattern.

**Fix:**
```tsx
// In every _protected/<route>.tsx beforeLoad:
throw redirect({
  to: '/',
  search: { forbidden: location.pathname + (location.search ?? '') },
})
```

---

### CR-02: Unsanitised `deepLinkUrl` used as `href` — potential `javascript:` injection

**File:** `apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx:127`

**Issue:** The `deepLink` state is populated directly from `services.auth.telegramStart()` response (`r.deepLinkUrl`) and rendered as `href={deepLink ?? '#'}` on a plain `<a>` tag. In mock mode the value is always `https://t.me/...`, but in http mode the value comes from the backend API response. There is no client-side validation that the URL starts with `https://t.me/`. If the backend returns (or an attacker produces via MITM in http mode without TLS) a `javascript:alert(1)` string, clicking the link executes arbitrary JavaScript. React does NOT sanitise `href` values for `<a>` tags — it only sanitises `javascript:` in specific DOM APIs. For `<a href="javascript:...">`, the browser executes the URL on click.

**Fix:**
```tsx
// Validate before setting state:
const handleStart = () => {
  start.mutate(undefined, {
    onSuccess: (r) => {
      const url = r.deepLinkUrl
      if (!url.startsWith('https://t.me/')) {
        // Log and refuse; don't expose a potentially malicious href
        console.error('[TelegramLoginTab] Unexpected deepLinkUrl:', url)
        return
      }
      setToken(r.deepLinkToken)
      setDeepLink(url)
      // ...
    },
  })
}
```

---

### CR-03: Mock services import schemas from `features/` — violates the layered architecture

**File:** `apps/admin-web/src/shared/api/services/mock/auth.ts:12`
**File:** `apps/admin-web/src/shared/api/services/mock/clients.ts:12-15`

**Issue:** Both mock service files import Zod schemas from feature layers:

- `mock/auth.ts:12`: `import { emailLoginSchema } from '@/features/auth/model/schema'`
- `mock/clients.ts:12-15`: `import { clientCreateSchema, clientUpdateSchema } from '@/features/clients/model/schema'`

The project's FSD-lite rule (CLAUDE.md architecture) mandates: `shared → entities` but NOT `shared → features`. The mock services live in `src/shared/api/services/mock/` and should not depend on `src/features/`. This creates a circular dependency risk: features import from `shared/api/services` (through the swap seam), and `shared/api/services/mock` imports from `features`. Currently the ESLint `import/no-restricted-paths` rule does not cover `src/shared/api/services/mock/**` as a target zone, so the violation is silent. If schemas diverge between the mock service validation and what the form submits, the mock will silently validate with different rules.

The schemas used for mock service input validation should live in `src/entities/<entity>/` or `src/shared/api/contracts/` — the location the CLAUDE.md describes as holding "Domain types + Zod schemas + pure helpers". Moving them there would also mean the HTTP service layer could validate responses against the same schemas.

**Fix:** Move `clientCreateSchema`, `clientUpdateSchema`, and `emailLoginSchema` to their respective entity or contracts locations (e.g. `src/entities/client/schema.ts`, `src/shared/api/contracts/authSchema.ts`), then update imports in both feature forms and mock services.

---

### CR-04: `redirecting` flag reset is not guarded against dynamic import failure — can permanently block redirect

**File:** `apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts:28-46`

**Issue:** The `.finally()` that resets `redirecting = false` is attached to the dynamic import chain: `void import('@/app/router').then(...).finally(...)`. If the dynamic import itself fails (e.g. the module cannot be loaded — a real risk if Vite chunk loading fails under poor network conditions), the `.finally()` still runs because `Promise.finally()` always runs on both resolution and rejection. This is correct.

However, there is a subtler issue: if `router.navigate(...)` throws synchronously inside `.then()` (an unlikely but possible case if `router.state.location` is undefined on early boot), the exception escapes the `.then()` but the `.finally()` is still attached — so the flag resets. This part is correct.

The real risk: the test suite's `beforeEach` manually resets the flag via `__resetRedirectingFlagForTests()`, but in production the flag is module-scoped and lives for the entire page lifetime. There is **no test** that verifies the flag is reset when the import succeeds but navigate rejects. The existing test "resets the flag after navigation settles" (line 74) only verifies the happy path. If `navigateMock.mockRejectedValueOnce(...)` is used instead, the flag should still reset — but this is untested. A rejected `navigate()` would cause the flag to remain `true` after `.finally()` runs... wait — `.finally()` IS on the outer chain, not just on `.then()`. Actually tracing: `import().then(fn).finally(reset)` — if `fn` throws, the promise rejects, but `.finally()` still fires. So the flag does reset on navigate rejection.

The actual blocker: the code uses `void import(...)` (fire-and-forget). If a **second** `session_expired` error fires after the `redirecting` flag is set but **before** the import resolves (very possible in a 401 storm), the second call correctly returns early. This is the intended behavior. However, if the first call's import chain rejects entirely (network error, etc.), the flag is still reset by `.finally()`, which is correct. 

Re-examining: the real issue is that `queryClient.clear()` is called **before** the dynamic import resolves (line 25). If the navigation subsequently fails (module load error, navigate throws), the query cache is already destroyed but the user is still on the protected page. The user's session state is wiped but they are not redirected to login. This leaves the UI in a broken state: all query cache is gone, queries will refetch and get 401s again, triggering a new `session_expired` which will now work since `redirecting` was reset. So this is self-healing in practice, but the intermediate state (cache cleared, still on protected page, queries refetching) is visible to the user as a flash of empty/error states.

**Fix:** Move `queryClient.clear()` inside the `.then()` callback, after navigation completes:
```ts
void import('@/app/router')
  .then(({ router }) => {
    const loc = router.state.location
    const next = loc.pathname + (loc.search ?? '')
    return (router.navigate as (opts: any) => Promise<void>)({
      to: '/login',
      search: { next },
      replace: true,
    }).then(() => {
      queryClient.clear() // Clear AFTER navigation succeeds
    })
  })
  .finally(() => {
    redirecting = false
  })
```

---

## Warnings

### WR-01: Optimistic update spreads `ClientUpdateInput` directly onto `Client` — `fullName` is never updated optimistically

**File:** `apps/admin-web/src/features/clients/api/hooks.ts:49` and `53`

**Issue:** The optimistic update in `useUpdateClient.onMutate` spreads `input` directly onto cached `Client` objects:

```ts
const items = data.items.map((c) => (c.id === id ? { ...c, ...input } : c))
qc.setQueryData<Client>(clientsKeys.detail(id), { ...detailSnapshot, ...input })
```

`ClientUpdateInput` contains `firstName`, `lastName`, `middleName` — but `Client` does not have these fields. `Client` has `fullName` (a composite string). So spreading `input` onto `Client` results in: the cached client gaining extra `firstName`/`lastName`/`middleName` fields (extra keys, no TypeScript error since spread), while `fullName` remains the stale pre-edit value until the server response arrives and `onSettled` invalidates. During the optimistic window the UI shows the old `fullName`. This is a UX bug — the optimistic update does not actually show the new name. The server mock (`clients.ts:115-123`) does the correct reconstruction but the frontend hook bypasses it.

**Fix:** Either do not attempt to optimistically update `fullName` (only update non-composite fields like `phone`, `email`, `notes`, `birthDate`), or reconstruct `fullName` locally before setting:
```ts
function buildOptimisticFullName(current: Client, input: ClientUpdateInput): string {
  const parts = current.fullName.split(' ')
  const last = input.lastName ?? parts[0] ?? ''
  const first = input.firstName ?? parts[1] ?? ''
  const middle = input.middleName ?? parts[2]
  return [last, first, middle].filter(Boolean).join(' ')
}
// Then in onMutate:
const updatedClient = {
  ...c,
  phone: input.phone ?? c.phone,
  email: input.email !== undefined ? input.email || undefined : c.email,
  notes: input.notes ?? c.notes,
  birthDate: input.birthDate !== undefined ? input.birthDate || undefined : c.birthDate,
  fullName: (input.lastName || input.firstName || input.middleName)
    ? buildOptimisticFullName(c, input)
    : c.fullName,
}
```

---

### WR-02: Telegram OTP polling continues after `timedOut` flag is set but a concurrent in-flight poll can still resolve `bound=true`

**File:** `apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx:25` and `72-80`

**Issue:** The timeout watcher (`useEffect` at line 72) checks `Date.now() - startedAtRef.current! > TIMEOUT_MS` and sets `timedOut`. The polling hook (`useTelegramStatus`) uses `enabled: !!token && enabled` where `enabled = !timedOut`. However, there is a window between the last poll dispatch and `timedOut` being set where an in-flight `telegramStatus` request can return `bound=true` and set `status.data.bound = true`. The component renders the bound/OTP entry state based on `const bound = !!status.data?.bound` at line 82. Because the render after `timedOut=true` early-returns at line 85 (timed-out screen), `bound` is never checked — but if the data arrives concurrently with `setTimedOut`, the React batched state update could render the bound OTP form briefly before switching to timed-out. More critically: `status.data?.bound` is stale-safe because `refetchInterval` stops when `enabled=false`. So after `timedOut=true`, no further polls occur and `status.data` stays stale. The timed-out screen renders correctly.

However, there is a separate race: if the user clicks "Получить новую ссылку" in the timed-out screen (lines 91-97), `handleStart()` is called which mutates and sets a new token. But `timedOut` is set to `false` before `handleStart()` completes (line 93 `setTimedOut(false)`) — the new `useTelegramStatus` query fires with `enabled=true` immediately, but `token` is still `null` at the time `setTimedOut(false)` is called (the `setToken` in `handleStart.onSuccess` is async). So `status` briefly polls with `token=null` and `enabled=true` but the `queryFn` uses `token!` (non-null assertion) — while `enabled: !!token && enabled` prevents the call when `token` is null. This is actually safe because `useTelegramStatus` checks `!!token` inside `enabled`. The ordering is safe. **However**, `setTimedOut(false)` on line 93 is called before `start.mutate` resolves — if `start.mutate` fails (network error), `timedOut` is `false` but `token` is still `null`, leaving the component in a state where it shows the "idle" screen again with no error message. The start failure silently swallows.

**Fix:** Add `start.isError` error display in the timed-out recovery branch, and use `onError` callback in the timed-out "new link" button's `handleStart` invocation:
```tsx
onClick={() => {
  setToken(null)
  setDeepLink(null)
  startedAtRef.current = null
  // Don't reset timedOut until start succeeds
  handleStart()
}}
```
Move `setTimedOut(false)` to inside `handleStart`'s `onSuccess`.

---

### WR-03: `redirectOnSessionExpired` imports `ApiError` directly from `@sportzal/api-client` instead of the re-export in `shared/api/errors`

**File:** `apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts:1`

**Issue:** The file imports `ApiError` from `@sportzal/api-client` directly, bypassing the canonical re-export at `@/shared/api/errors`. The project's error handling convention (CLAUDE.md) establishes `shared/api/errors.ts` as the single entry point for both `ApiError` and `DomainError`. If the `@sportzal/api-client` package is replaced or the `ApiError` class is re-wrapped in the future, `redirect-on-session-expired.ts` will not pick up the change while every other consumer (checked) goes through `shared/api/errors`. Additionally, the `instanceof` check at line 21 could fail if `shared/api/errors.ts` wraps `ApiError` (it currently re-exports it unchanged, but this is a fragility).

**Fix:**
```ts
import { ApiError } from '@/shared/api/errors'
```

---

### WR-04: `useClientsList` does not specify `staleTime` — inconsistent with project convention

**File:** `apps/admin-web/src/features/clients/api/hooks.ts:11-16`

**Issue:** `useClientsList` omits `staleTime` entirely, relying on the `QueryClient` global default of `30_000`. While the global default is correctly set in `queryClient.ts`, the convention in this codebase (CLAUDE.md: "per-feature `xKeys` factory, `staleTime: 30_000`") and the pattern set by `useMe` (hooks.ts:11) is to be explicit. `useClient` (the detail hook) also omits `staleTime`. If the global `QueryClient` default is ever changed for a different domain, the clients list silently inherits the new value. Compare with `useMe` which is explicit at `staleTime: 30_000`.

**Fix:** Add explicit `staleTime: 30_000` to `useClientsList` and `useClient`:
```ts
export function useClientsList(query: ClientsListQuery) {
  return useQuery({
    queryKey: clientsKeys.list(query),
    queryFn: () => services.clients.list(query),
    staleTime: 30_000,
  })
}
```

---

### WR-05: `ru.ts` defines `auth.errors.otpMaxAttempts` but `TelegramLoginTab` never handles the `otp_max_attempts` error code

**File:** `apps/admin-web/src/shared/i18n/ru.ts:68`
**File:** `apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx:49-65`

**Issue:** The i18n dictionary at `ru.ts:68` contains `otpMaxAttempts: 'Код заблокирован. Начните процесс заново.'` for the case when too many wrong OTP attempts occur. The mock service `auth.ts` does not enforce this limit (no `attemptCount` tracking), but the HTTP service will presumably return an `otp_max_attempts` error code from the real backend. The `TelegramLoginTab.handleVerify.onError` handler checks for `otp_invalid`, `expired`, and `bot_not_started` — but falls through to "Ошибка соединения" for `otp_max_attempts`. When the real backend ships, incorrect OTP code submissions after lockout will display "Ошибка соединения. Проверьте сеть и попробуйте снова" instead of the correct "Код заблокирован. Начните процесс заново." The `ru.ts` entry is unreachable dead code until this is wired.

**Fix:** Add the `otp_max_attempts` case to `handleVerify.onError`:
```ts
} else if (c === 'otp_max_attempts') {
  otpForm.setError('code', {
    type: 'server',
    message: t('auth.errors.otpMaxAttempts'),
  })
}
```

---

### WR-06: `ClientForm` does not show error messages for `birthDate` field; server-side validation errors for `birthDate` are silently dropped

**File:** `apps/admin-web/src/features/clients/components/ClientForm.tsx:114-116`

**Issue:** The form renders `birthDate` with `<Input id="birthDate" type="date" {...form.register('birthDate')} />` but there is no error display below this field — unlike `lastName`, `firstName`, `phone`, and `email` which all have `{form.formState.errors.<field> && <p>...}` blocks. If the server returns a `validation_failed` error with a `birthDate` field (possible via the schema `clientCreateSchema.birthDate` regex), `handleError` calls `form.setError('birthDate', ...)` but the UI never renders it. The same applies to `middleName` (no error display either) and `notes`.

**Fix:**
```tsx
<Input id="birthDate" type="date" {...form.register('birthDate')} />
{form.formState.errors.birthDate && (
  <p className="text-destructive text-sm">{form.formState.errors.birthDate.message}</p>
)}
```
Add similar blocks for `middleName` and `notes`.

---

### WR-07: `http/auth.ts` constructs Telegram status URL with manual string interpolation — bypasses type-safe path parameters

**File:** `apps/admin-web/src/shared/api/services/http/auth.ts:43-48`

**Issue:** The HTTP auth service constructs the Telegram status URL by manually appending the query parameter:
```ts
await request(
  'get',
  `/api/v1/auth/telegram/status?token=${encodeURIComponent(token)}` as never,
)
```
The `as never` cast silences TypeScript. While `encodeURIComponent` is correctly applied, the `as never` cast means the type checker cannot validate this path against the OpenAPI schema. Additionally, the comment at line 41-42 says "RequestInitWithBody has no `query` field" — if the `@sportzal/api-client` package ever gains a `query` typed field (which is idiomatic for OpenAPI clients), this manual URL construction will not be refactored by `tsc` errors. The `as never` pattern here is repeated from `http/clients.ts` (list query params) but is more dangerous for auth endpoints.

**Fix:** If `@sportzal/api-client` does not support query params yet, document it explicitly and use a typed helper:
```ts
const url = `/api/v1/auth/telegram/status?token=${encodeURIComponent(token)}`
// TODO: replace with typed query params when api-client gains `query` support
return unwrap<TelegramStatusResponse>(await request('get', url as never))
```
At minimum, add a type assertion comment explaining why `as never` is safe here.

---

## Info

### IN-01: `redirect-on-session-expired.ts` exposes test-only helpers via named exports — not barrel-guarded

**File:** `apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts:49-57`

**Issue:** `__resetRedirectingFlagForTests` and `__getRedirectingForTests` are exported as named exports from the implementation file. The comment says "NOT exported in barrels", which is respected in `features/auth/index.ts`. However, any file can still import them directly, and tree-shaking in production will only remove them if they are not imported anywhere. The `__` prefix naming convention signals test-only by convention, but there is no enforcement. If a developer imports `redirect-on-session-expired.ts` directly (rather than through the barrel), they could accidentally use these helpers in production code.

**Fix:** Consider using a pattern like `if (import.meta.env.TEST)` guard or moving them to the test file via `vi.spyOn` instead of exporting from the implementation.

---

### IN-02: `TelegramLoginTab.tsx` uses raw Tailwind palette colors — violates the semantic token convention

**File:** `apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx:145`

**Issue:** Line 145 uses `text-green-600 dark:text-green-400` for the "Чат привязан" success message. Per CLAUDE.md: "Use semantic shadcn tokens (`bg-background`, `text-muted-foreground`); raw palette colors are banned by ESLint." The `RAW_PALETTE_REGEX` in `eslint.config.js` matches `text-green-600` and `text-green-400` and should fire `no-restricted-syntax`. Checking the ESLint config more carefully: the regex covers `text-` with named colors including `green`, and suffix digits `\d{2,3}`. Both `600` and `400` are 3-digit matches. This should be caught by the linter, yet it is in the submitted code — suggesting either the ESLint check is not running in CI or the palette ban was intentionally skipped. If the linter was run, this is a broken guard; if it wasn't, this is a convention violation.

**Fix:** Use `text-success` (the `--color-success` token defined in `index.css` via `reui-extras`) or `text-primary` depending on design intent:
```tsx
<p className="text-success text-sm" aria-live="polite">
```

---

### IN-03: `mock/auth.ts` leaks the mock OTP code in the DomainError message

**File:** `apps/admin-web/src/shared/api/services/mock/auth.ts:104`

**Issue:** The error message exposed via `DomainError` reads: `'Неверный код. Используйте 123456 в моке.'`. This message will be surfaced to the UI via the `TelegramLoginTab` error display. In development this is helpful, but if `VITE_API_MODE=mock` is deployed to a staging environment accessible to non-engineers, the hardcoded OTP is advertised in the UI error message. This is a minor issue in a mock-only context but is poor practice.

**Fix:**
```ts
throw new DomainError('otp_invalid', 'Неверный код. Попробуйте ещё раз.')
// Note: mock OTP is 123456 (dev only)
```

---

### IN-04: `useDebounceValue` does not cancel the timer when the component unmounts — but the pattern is safe

**File:** `apps/admin-web/src/shared/lib/hooks/useDebounceValue.ts:9-12`

**Issue:** The `useEffect` returns `() => clearTimeout(id)` which correctly cleans up. However, the `setDebounced(value)` call inside the timeout fires after the timer resolves — if the component unmounts before the timer fires, `clearTimeout` in the cleanup handles it. This is correct. Noting this as INFO because the implementation is actually safe, but a common mistake in hooks is to omit the cleanup; this one has it.

No fix required — documented for completeness.

---

_Reviewed: 2026-05-04T14:43:59Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
