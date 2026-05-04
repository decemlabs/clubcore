---
phase: 11-clients-http-shape-adapter
reviewed: 2026-05-04T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - apps/admin-web/src/features/clients/api/hooks.test.ts
  - apps/admin-web/src/features/clients/api/hooks.ts
  - apps/admin-web/src/shared/api/services/http/_clientsAdapter.test.ts
  - apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts
  - apps/admin-web/src/shared/api/services/http/clients.ts
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-05-04
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

The phase delivers a clean, pure-function adapter (`_clientsAdapter.ts`) that
correctly bridges backend `Client*` schemas (`birthday`, separate name parts) to
the FE `Client` domain type (`birthDate`, composed `fullName`). Adapter unit
tests are thorough, exercising null/empty-string/whitespace edge cases and
explicitly asserting the `birthDate → birthday` rename and the "omit, never
null" Phase 8 D-01 contract. The optimistic-update hardening in
`buildOptimisticFullName` correctly tolerates `current.fullName === undefined`.

The defects below are not blockers — they are localized robustness gaps and a
semantic mismatch between the optimistic path and the request path that can
produce a brief flicker of stale state but no data loss.

No security issues, no hardcoded secrets, no dangerous functions, no debug
artifacts. Naming and formatting are conformant (no semicolons, single quotes,
under 100 chars). TypeScript strict + `noUncheckedIndexedAccess` are respected.

## Warnings

### WR-01: Optimistic clear of `email`/`notes`/`birthDate` contradicts request-path semantics

**File:** `apps/admin-web/src/features/clients/api/hooks.ts:58-61`
**Issue:**
`applyOptimisticUpdate` treats an empty string as "clear the field":

```ts
email: input.email !== undefined ? input.email || undefined : current.email,
notes: input.notes !== undefined ? input.notes || undefined : current.notes,
birthDate: input.birthDate !== undefined ? input.birthDate || undefined : current.birthDate,
```

But `updateInputToRequest` (`_clientsAdapter.ts:84-93`) treats an empty string
as "omit the key entirely" per Phase 8 D-01 — meaning the backend will leave
the field unchanged. Result: when a user submits `email: ''`, the cache
optimistically blanks the email, the request is sent without `email`, the
backend returns the OLD email, and `onSettled` invalidation revalidates back to
the old value. The user sees the field briefly empty, then re-populated. This
is the exact UX inconsistency Phase 11 was meant to harden against.

The `_clientsAdapter.test.ts` test on line 234 (`'omits empty-string birthDate
per Phase 8 D-01 (omit, do NOT send null)'`) makes the request-side contract
explicit; the optimistic path silently violates it.

**Fix:** Mirror the request-side contract — treat empty strings as "no-op" in
the optimistic path:

```ts
phone: input.phone || current.phone,
email: input.email ? input.email : current.email,
notes: input.notes ? input.notes : current.notes,
birthDate: input.birthDate ? input.birthDate : current.birthDate,
fullName: nameChanged ? buildOptimisticFullName(current, input) : current.fullName,
```

Add a test asserting `applyOptimisticUpdate({ email: 'old@x.ru', ... }, { email: '' }).email === 'old@x.ru'` to lock the contract.

---

### WR-02: `clients.ts list()` does not validate `raw.items` is an array before `.map`

**File:** `apps/admin-web/src/shared/api/services/http/clients.ts:33-36`
**Issue:**
```ts
const raw = unwrap<PaginatedClientResponse>(
  await request('get', `/api/v1/clients?${params.toString()}` as never),
)
return { ...raw, items: raw.items.map(responseToClient) }
```

`unwrap` is a structural cast (`as T`) with no runtime validation. If the
backend ever returns a non-paginated shape (raw array, error envelope leak,
204), `raw.items` is `undefined` and `raw.items.map` throws
`TypeError: Cannot read properties of undefined (reading 'map')`. This is the
exact failure mode Phase 11 was created to prevent at the response shape
boundary — but it's only handled for `responseToClient`, not for the wrapper.

**Fix:** Defensively coerce or fail loudly with a typed `DomainError`:

```ts
if (!raw || !Array.isArray(raw.items)) {
  throw new Error('clients.list: malformed paginated response')
}
return { ...raw, items: raw.items.map(responseToClient) }
```

Or add a Zod parse at the boundary (preferred, matches project pattern of "one
Zod schema per resource").

---

### WR-03: `buildOptimisticFullName` silently truncates 4+ token names

**File:** `apps/admin-web/src/features/clients/api/hooks.ts:44-50`
**Issue:**
The split-by-space heuristic assumes a 3-token name (`lastName firstName
middleName`). For compound surnames with 4+ tokens (e.g. `'Голенищев-Кутузов
Иван Сергеевич Петрович'` or hyphenless variants), splitting and re-joining
drops trailing tokens. Specifically:

```ts
const parts = (current.fullName ?? '').split(' ')
const last = input.lastName ?? parts[0] ?? ''
const first = input.firstName ?? parts[1] ?? ''
const middle = input.middleName ?? parts[2]
return [last, first, middle].filter(Boolean).join(' ')
```

For `current.fullName = 'А Б В Г'` and `input = { firstName: 'X' }`, output is
`'А X В'` — `'Г'` is lost. The cache shows truncated name until `onSettled`
invalidation fetches the canonical value. The function comment acknowledges
"Mock service mirrors this composition" but does not flag the truncation risk
when real backend data arrives.

This is **optimistic-only** — server response replaces the cache on success —
so impact is a brief visual flicker, not data loss.

**Fix:** Either (a) accept the truncation explicitly with a comment ("compound
surnames will flicker; corrected by server response on settle"), or (b) when
`input` provides `lastName`/`firstName`/`middleName` partially, use the prior
`current.fullName` verbatim and let `onSettled` correct it:

```ts
function buildOptimisticFullName(current: Client, input: ClientUpdateInput): string {
  // Optimistic best-effort. Server response on settle is canonical.
  const allNamePartsProvided =
    input.lastName !== undefined && input.firstName !== undefined
  if (allNamePartsProvided) {
    return [input.lastName, input.firstName, input.middleName].filter(Boolean).join(' ')
  }
  return current.fullName ?? ''
}
```

Note that change would break the existing test "rebuilds fullName when
firstName changes (3-token mock parity)" — the test encodes the current,
truncation-prone behavior. Decide whether the test is documenting intent or
codifying a bug.

## Info

### IN-01: Truthy-check on names treats string `'0'` as omitted

**File:** `apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts:70-93`
**Issue:** `if (input.middleName)`, `if (input.lastName)`, etc. use truthy
checks. Empty string is correctly omitted (intended), but a hypothetical
`'0'` would also be falsy — `'0'` is truthy in JavaScript actually
(non-empty strings are truthy), so this is fine. However, `if (input.notes)`
also treats whitespace-only strings (`' '`) as truthy and forwards them. Names
with leading/trailing whitespace would be sent verbatim. Backend Pydantic
likely strips, but it's worth noting the FE does not normalize.
**Fix:** Optional — apply `.trim()` defensively before the truthy check, or
rely on form-level validation (preferred, single source of truth):

```ts
if (input.middleName?.trim()) out.middleName = input.middleName.trim()
```

Skip this if the Zod schema in `entities/client/schema.ts` already enforces
trimmed values on the form side.

---

### IN-02: `responseToClient` does not normalize internal whitespace in `fullName`

**File:** `apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts:38-41`
**Issue:**
```ts
const fullName = [r.lastName, r.firstName, r.middleName]
  .filter((s): s is string => Boolean(s))
  .join(' ')
  .trim()
```

If the backend ever returns `lastName = 'Иванов '` (trailing space) and
`firstName = ' Пётр'`, the join produces `'Иванов   Пётр'` (3 spaces) which
`.trim()` does NOT collapse. The "trims pathological whitespace-only" test on
line 50 covers a leading-only edge case, not this one.
**Fix:** Replace `.trim()` with a multi-space collapser, or trim each part
before filtering:

```ts
const fullName = [r.lastName, r.firstName, r.middleName]
  .map((s) => s?.trim() ?? '')
  .filter(Boolean)
  .join(' ')
```

Low priority — backend Pydantic likely trims.

---

### IN-03: `Phase 8 D-XX` placeholder reference in doc comment

**File:** `apps/admin-web/src/shared/api/services/http/_clientsAdapter.ts:35`
**Issue:** The JSDoc says `(backend 404s soft-deleted rows; Phase 8 D-XX)` —
the decision number is unfilled. Documentation drift will compound.
**Fix:** Replace `D-XX` with the concrete decision number from Phase 8's
PLAN/SUMMARY (likely `D-09` or similar — verify against
`.planning/phases/08-*/`), or remove the parenthetical if the decision id is
not yet stable.

---

### IN-04: Test calls `run()` twice instead of capturing the result

**File:** `apps/admin-web/src/features/clients/api/hooks.test.ts:23-26`
**Issue:**
```ts
const run = () => applyOptimisticUpdate(broken, { firstName: 'Сергей', lastName: 'Иванов' })
expect(run).not.toThrow()
expect(run().fullName).toBe('Иванов Сергей')
```

`run()` is invoked twice — once via `not.toThrow()` and again for the
`.fullName` assertion. Pure function so harmless, but the test reads as if
two separate behaviors are being verified when in fact only one call
matters.
**Fix:**
```ts
let result: Client | undefined
expect(() => { result = applyOptimisticUpdate(broken, { firstName: 'Сергей', lastName: 'Иванов' }) }).not.toThrow()
expect(result?.fullName).toBe('Иванов Сергей')
```

Or split into two tests: one for "does not throw," one for "produces correct
output."

---

### IN-05: `as never` casts on `request()` first argument silence path-typing

**File:** `apps/admin-web/src/shared/api/services/http/clients.ts:34, 40, 55, 62`
**Issue:** Four call sites use `as never` to bypass the openapi `paths` type.
The `list()` case is unavoidable given URL-encoded query params, but the
comment is on `list` only — the other three (`get`, `update`, `remove`) use
`as never` purely because the second-arg `params` shape isn't picked up.
This shifts a typing concern to runtime. If the openapi paths object grows,
a typo in the path string will not be caught.
**Fix:** Investigate whether `params: { client_id: id }` is the
expected shape (the openapi spec likely uses `clientId` or `client_id`
per backend convention — verify against `packages/api-client`'s generated
types). If shapes match, the `as never` may be removable. Track as a
follow-up; not a v1 blocker.

---

_Reviewed: 2026-05-04_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
