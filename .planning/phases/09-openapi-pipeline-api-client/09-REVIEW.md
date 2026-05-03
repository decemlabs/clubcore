---
phase: 09-openapi-pipeline-api-client
reviewed: 2026-05-03T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - apps/backend/scripts/export_openapi.py
  - apps/backend/app/main.py
  - packages/api-client/tsconfig.json
  - packages/api-client/src/errors.ts
  - packages/api-client/src/fetcher.ts
  - packages/api-client/src/index.ts
  - packages/api-client/.gitignore
  - packages/api-client/package.json
  - packages/api-client/README.md
  - .github/workflows/ci.yml
  - apps/admin-web/package.json
findings:
  critical: 2
  warning: 6
  info: 4
  total: 12
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-05-03
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 9 lands the OpenAPI export pipeline, the `@sportzal/api-client` package, and the
matching CI drift gates. The backend export script is solid and well-justified; the CI
workflow correctly pins pnpm and uses least-privilege tokens; the README is thorough.

The fetcher, however, has two correctness defects that will bite the first consumer:

1. **No path-parameter interpolation** — the schema already contains `/api/v1/clients/{client_id}`,
   and `request<P, M>` casts the path straight into `fetch(url, ...)`. A call to
   `request('GET', '/api/v1/clients/{client_id}')` literally sends a URL containing
   `{client_id}`. There is no helper, no `params` field, and no compile-time guard.
2. **Single-flight refresh wedges on parsing failure** — `refreshOnce()`'s shared promise
   resolves to a `Response` even when the body parses non-OK. That part is fine, but the
   failure path inside `request` swallows refresh-side network errors with `catch {}` and
   throws `session_expired` — with no original error context preserved (also see WR-04
   regarding lost stack frames).

Other findings are smaller (ApiError is not a real `Error` subclass for the purposes of
`cause` propagation, the headers spread silently drops `Headers`/`[string,string][]` shapes,
auth-exempt list is duplicated by string literals, etc.). All BLOCKERs below should be
fixed before any feature module is wired up to `request()`.

The two auto-generated artifacts (`packages/api-client/src/schema.d.ts` and
`apps/backend/openapi.json`) exist on disk and are gated by the CI drift jobs. Generated
content was not reviewed per scope.

## Critical Issues

### CR-01: No path-parameter interpolation in `request()` — parameterized endpoints are broken

**File:** `packages/api-client/src/fetcher.ts:99`
**Issue:** `request<P, M>(method, path, init?)` types `path` as `keyof paths`, but `paths`
already includes templated keys like `"/api/v1/clients/{client_id}"`. The implementation does:

```ts
const url = path as unknown as string
// ...
res = await fetch(url, baseInit)
```

There is no path-param interpolation, no `params` field on `RequestInitWithBody`, and no
runtime check that `path` does not contain unsubstituted `{...}` segments. The first
consumer that calls `request('GET', '/api/v1/clients/{client_id}')` will literally request
`/api/v1/clients/%7Bclient_id%7D` (or `/{client_id}` raw, depending on the fetch impl).
The backend will return 404 — silently for the type system, since the call type-checks.

This is the entire reason `paths` is keyed by templated strings: callers are expected to
pass parameter values, and the client is supposed to substitute them before issuing fetch.
Without that, the typed client is a worse API than `fetch` directly (because it lies
about safety).

**Fix:** Either (a) add a `params` field to `RequestInitWithBody` and substitute `{name}`
segments before calling `fetch`, or (b) explicitly document that only static-path
endpoints are supported in Phase 9 and add a runtime assertion that throws if the path
contains `{`. Option (a) is the production-grade choice:

```ts
export interface RequestInitWithBody extends Omit<RequestInit, 'method' | 'body'> {
  body?: unknown
  params?: Record<string, string | number>
}

function interpolate(path: string, params?: Record<string, string | number>): string {
  if (!path.includes('{')) return path
  return path.replace(/\{(\w+)\}/g, (_, key) => {
    const v = params?.[key]
    if (v === undefined) {
      throw new ApiError('client_error', `Missing path param '${key}' for ${path}`)
    }
    return encodeURIComponent(String(v))
  })
}

// inside request():
const url = interpolate(path as unknown as string, init?.params)
```

If deferring to a later phase, at minimum add a runtime guard so a bug is loud, not silent:

```ts
if (url.includes('{')) {
  throw new ApiError('client_error', `Path '${url}' has unsubstituted parameters`)
}
```

---

### CR-02: `refreshOnce()` always resolves — non-OK refresh response is treated as a "successful" promise, masking the actual failure

**File:** `packages/api-client/src/fetcher.ts:58-67, 136-144`
**Issue:** `refreshOnce()` returns `fetch(...).finally(() => { inFlightRefresh = null })`.
`fetch()` only rejects on network failure; a 401/403/5xx from `/api/v1/auth/refresh` is a
**resolved** Response. The caller pattern is:

```ts
try {
  refreshRes = await refreshOnce()
} catch {
  throw new ApiError('session_expired', 'Session expired, please log in again.')
}
if (!refreshRes.ok) {
  throw new ApiError('session_expired', 'Session expired, please log in again.')
}
```

This works for the happy path, but the bug is in concurrency: when refresh fails with a
4xx, every concurrent caller correctly observes `!refreshRes.ok` and throws
`session_expired`. **However**, because `inFlightRefresh` is reset in `.finally()` while
the resolved Response is still being consumed by parallel awaiters, a *new* arrival
immediately after the rejection clears the slot will trigger a **second** refresh attempt
— defeating single-flight semantics under back-pressure (rapid 401 storms).

More concretely: the contract claims "max 1 refresh per failed call" and "single-flight",
but the slot resets the moment the fetch settles, not after all retries complete. So:

- Request A → 401 → starts refresh (R1)
- Request B → 401 → joins R1 (good)
- R1 settles with 401 → `.finally` resets `inFlightRefresh = null`
- Request C → 401 → starts refresh (R2) — even though R1 just failed

If the refresh-token cookie is dead, R2 will also fail. Under the 401 fan-out on a
broken session this can issue N refresh calls instead of one, hitting backend rate
limits and emitting confusing telemetry.

**Fix:** Cache the refresh result (or the failure decision) for at least the duration of
the original retry, or hold the slot until the consuming `request()` decides to throw:

```ts
let inFlightRefresh: Promise<boolean> | null = null  // boolean = "did refresh succeed?"

function refreshOnce(): Promise<boolean> {
  if (inFlightRefresh) return inFlightRefresh
  inFlightRefresh = (async () => {
    try {
      const r = await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include' })
      return r.ok
    } catch {
      return false
    }
  })().finally(() => {
    // Defer slot reset to next microtask so concurrent awaiters latch on
    // before a fresh 401 storm starts a second refresh.
    queueMicrotask(() => { inFlightRefresh = null })
  })
  return inFlightRefresh
}
```

Or alternatively, gate "permanent session-expired" state in a second flag so the
SECOND request after a known-failed refresh goes straight to `session_expired` without
issuing R2. Either way, the current implementation does not match the README claim
"параллельные запросы ждут тот же promise" once the promise settles.

## Warnings

### WR-01: `ApiError` does not preserve the original cause — debugging refresh failures is impossible

**File:** `packages/api-client/src/errors.ts:16-25`, `fetcher.ts:139-141, 157-159`
**Issue:** `ApiError`'s constructor takes only `(code, message, fields?)`. When the
fetcher catches a network error during refresh, it does:

```ts
} catch {
  throw new ApiError('session_expired', 'Session expired, please log in again.')
}
```

The original `TypeError: Failed to fetch` (or whatever) is gone — no `cause`, no original
message, no stack. Same for the retry branch at line 157-159, except there at least
`err.message` is forwarded into `network_error`. Refresh-side network errors are
indistinguishable from token expiry to the consumer.

**Fix:** Plumb `cause` through (ES2022 native, all targets support it):

```ts
export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly fields?: Record<string, unknown>,
    options?: { cause?: unknown },
  ) {
    super(message, options)
    this.name = 'ApiError'
  }
}
```

Then:

```ts
} catch (err) {
  throw new ApiError('session_expired', 'Session expired, please log in again.', undefined, { cause: err })
}
```

### WR-02: `headers` spread loses non-`Record` shapes, breaking valid `RequestInit` callers

**File:** `packages/api-client/src/fetcher.ts:101-104, 148`
**Issue:** The fetcher does:

```ts
const headers: Record<string, string> = {
  Accept: 'application/json',
  ...((init?.headers as Record<string, string> | undefined) ?? {}),
}
```

`HeadersInit` (the real type of `RequestInit['headers']`) is
`Headers | Record<string, string> | [string, string][]`. The `as Record<string, string>`
cast lies for the other two shapes:

- `Headers` instance → spreading it yields `{}` (Headers is not enumerable as own props)
- `[string, string][]` → spreading yields `{ '0': ['k','v'], '1': ['k','v'] }` (array indexing)

So a caller doing `request('GET', path, { headers: new Headers({ 'X-Foo': 'bar' }) })`
will silently lose `X-Foo`. The type signature accepts it (it extends `RequestInit`), the
runtime drops it.

**Fix:** Normalize via the `Headers` constructor:

```ts
const merged = new Headers(init?.headers)
merged.set('Accept', 'application/json')
if (bodyPayload) merged.set('Content-Type', 'application/json')
if (isMutating(upper)) {
  const csrf = readCsrfCookie()
  if (csrf) merged.set('X-CSRF-Token', csrf)
}
// fetch() accepts Headers directly
const baseInit: RequestInit = { ...init, method: upper, credentials: 'include', headers: merged, body: bodyPayload }
```

This also fixes the retry branch at line 148, which clones `headers` (already broken) and
re-derives CSRF from the same broken object.

### WR-03: `init.body` of type `unknown` is JSON-stringified unconditionally — `FormData` / `Blob` / `URLSearchParams` are corrupted

**File:** `packages/api-client/src/fetcher.ts:91-93, 105-109`
**Issue:** `RequestInitWithBody.body` is `unknown` and the fetcher unconditionally does
`JSON.stringify(init.body)` whenever `body !== undefined`. A caller passing `FormData`
(file uploads), `Blob`, `URLSearchParams`, or `ArrayBuffer` ends up sending the literal
string `"[object FormData]"` or similar. The Content-Type is also forced to
`application/json` regardless.

Phase 9 may only target JSON endpoints, but the public API silently mis-handles every
other case. At minimum this should be documented; better, detect non-plain-object bodies:

**Fix:** Either restrict the type to `Record<string, unknown> | unknown[] | null | string | number | boolean | undefined` so non-JSON bodies don't compile, or branch:

```ts
if (init?.body !== undefined) {
  const b = init.body
  if (b instanceof FormData || b instanceof Blob || b instanceof URLSearchParams || b instanceof ArrayBuffer) {
    bodyPayload = b
    // do NOT set Content-Type — let fetch infer multipart boundary etc.
  } else {
    headers['Content-Type'] = 'application/json'
    bodyPayload = JSON.stringify(b)
  }
}
```

### WR-04: `finishResponse` throws on empty `application/json` 200 bodies

**File:** `packages/api-client/src/fetcher.ts:168-179`
**Issue:** When the response is OK and Content-Type contains `application/json`, the
fetcher calls `await res.json()` unconditionally. If the body is empty (e.g., a 200 with
no payload but a `Content-Type: application/json` header — surprisingly common from
proxies and some FastAPI endpoints), `res.json()` throws `SyntaxError: Unexpected end of
JSON input`. This propagates as an unhandled rejection — not wrapped in `ApiError`, so
consumers using `if (err instanceof ApiError)` won't catch it.

**Fix:** Wrap and convert:

```ts
if (ct.includes('application/json')) {
  const text = await res.text()
  if (!text) return undefined
  try {
    return JSON.parse(text) as unknown
  } catch (err) {
    throw new ApiError('unknown_error', 'Failed to parse JSON response', undefined, { cause: err })
  }
}
```

Same defensive parsing should be considered in `parseErrorBody`, though it already has
a try/catch.

### WR-05: `register_user_loader` is called on every `create_app()` — test isolation risk

**File:** `apps/backend/app/main.py:81`
**Issue:** `register_user_loader(load_user_by_id)` is invoked inside `create_app()`.
Tests, the export script (CR-N/A — that calls `.openapi()` only), and any code that
constructs multiple FastAPI instances will re-register the loader on every call. If
`register_user_loader` writes to module-level state (which the docstring strongly
implies — "fills the Phase 4 D-24 slot"), this is at best idempotent, at worst racey or
order-dependent across parallel test workers.

**Fix:** Either confirm `register_user_loader` is idempotent and add a comment to that
effect, or guard with a sentinel:

```python
_loader_registered = False

def create_app() -> FastAPI:
    global _loader_registered
    # ...
    if not _loader_registered:
        register_user_loader(load_user_by_id)
        _loader_registered = True
```

(Out-of-file context required to confirm. Flagging as warning since `app.main` is
explicitly the composition root and `create_app` is the factory called per-test; this is
a likely footgun.)

### WR-06: CI drift gate runs `git diff --exit-code` without `--quiet` and against an unstaged file — false negatives possible

**File:** `.github/workflows/ci.yml:55-57, 100-101`
**Issue:** `git diff --exit-code <file>` exits non-zero when there are **unstaged** diffs
in the working tree against the index. But if the file isn't tracked at all (e.g., a
fresh clone where `schema.d.ts` was somehow gitignored or never committed), `git diff`
exits 0 — silently passing the gate. This is unlikely given current `.gitignore` (only
`dist/` + `node_modules/`), but the README explicitly says `schema.d.ts` is committed
"Phase 9 D-07 — отступление от REQUIREMENTS API-05 wording 'gitignored locally'", which
implies the gate's correctness depends on a not-yet-enforced rule.

**Fix:** Either add explicit `git ls-files --error-unmatch <file>` before the diff (fails
the job if the file isn't tracked), or use `git status --porcelain <file>` and assert empty:

```yaml
- name: Drift gate — packages/api-client/src/schema.d.ts
  run: |
    git ls-files --error-unmatch packages/api-client/src/schema.d.ts
    git diff --exit-code packages/api-client/src/schema.d.ts
```

Same for `apps/backend/openapi.json`.

## Info

### IN-01: `AUTH_EXEMPT_PATHS` duplicates a server-side list with no enforcement of sync

**File:** `packages/api-client/src/fetcher.ts:20-29`
**Issue:** Eight string literals duplicate `app/modules/auth/router.py` endpoint list.
The comment claims "Exact list verified against apps/backend/app/modules/auth/router.py"
— but there is no test, codegen step, or assertion that keeps this in sync. A new
`/api/v1/auth/foo` endpoint added to the backend will silently NOT be exempt on the FE,
causing infinite-loop refresh attempts.

**Fix:** Derive from `paths` at compile time using a type-level filter on the schema, or
add a unit test that loads the OpenAPI JSON and asserts every `/api/v1/auth/*` path is
either in `AUTH_EXEMPT_PATHS` or explicitly opted out.

### IN-02: `package.json` `main` and `exports` point at `.ts` source, not built `.js` — non-bundler consumers break

**File:** `packages/api-client/package.json:7-14`
**Issue:** `main: "./src/index.ts"` and `exports."."` point at `src/index.ts`. This works
because admin-web is a Vite/TS workspace and consumes via `workspace:*`. Any consumer
outside Vite (Node script, Jest without `ts-node`, a future SDK extraction) will fail to
import. The tsconfig has `composite: true` and `outDir: "dist"` set up for builds, but
nothing wires `dist` into the `exports` map.

**Fix (deferred OK):** When the package is consumed outside Vite, switch to:

```json
"exports": {
  ".": {
    "types": "./dist/index.d.ts",
    "import": "./dist/index.js",
    "default": "./dist/index.js"
  }
}
```

and add a `build` script. Acceptable for Phase 9 to defer; flag in Phase 10 backlog.

### IN-03: README CSRF section claims `X-CSRF-Token` is omitted on safe methods, but fetcher only omits when cookie is missing

**File:** `packages/api-client/README.md:53` vs `packages/api-client/src/fetcher.ts:110-114`
**Issue:** The README states "На GET / HEAD / OPTIONS header не добавляется". The code
agrees — `if (isMutating(upper))` gates the entire CSRF block. This is correct, but the
README would benefit from also documenting the missing-cookie pass-through behavior
(line 113: "missing-cookie → still send; server returns 403 csrf_mismatch"), since
that's surprising semantics for a developer reading the doc.

**Fix:** Add one sentence: "Если cookie `sportzal_csrf` отсутствует на mutating
запросе — header просто не добавляется, и backend ответит `403 csrf_mismatch` через
стандартный error path."

### IN-04: Export script placeholder env vars include strings that look like secrets

**File:** `apps/backend/scripts/export_openapi.py:38-42`
**Issue:** `SECRET_KEY = "openapi-export-placeholder"` and
`TELEGRAM_BOT_TOKEN = "openapi-export-placeholder"` are set via `setdefault`. They are
harmless because `.openapi()` does not exercise the lifespan, and `setdefault` won't
override real values in CI/prod. However, secret-scanning tools (gitleaks, GitHub secret
scanning, trufflehog) often flag any hardcoded string assigned to a variable named
`SECRET_KEY` or `TELEGRAM_BOT_TOKEN`. Future-proof by making the placeholder unmistakably
non-secret:

**Fix:**

```python
os.environ.setdefault("SECRET_KEY", "PLACEHOLDER_NOT_A_REAL_SECRET_openapi_export_only")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "PLACEHOLDER_NOT_A_REAL_TOKEN_openapi_export_only")
```

Or move them into a separate `_export_env_defaults()` helper with a comment explaining
they're intentionally fake, so secret scanners can be configured to allowlist by file/line.

---

_Reviewed: 2026-05-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
