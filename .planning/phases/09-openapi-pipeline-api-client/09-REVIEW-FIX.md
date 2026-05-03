---
phase: 09-openapi-pipeline-api-client
fixed_at: 2026-05-03T00:00:00Z
review_path: .planning/phases/09-openapi-pipeline-api-client/09-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 9: Code Review Fix Report

**Fixed at:** 2026-05-03
**Source review:** .planning/phases/09-openapi-pipeline-api-client/09-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (Critical: 2, Warning: 6)
- Fixed: 8
- Skipped: 0

Info findings (IN-01..IN-04) were out of scope (`fix_scope = critical_warning`)
and remain in the source review for follow-up.

## Fixed Issues

### CR-01: No path-parameter interpolation in `request()` — parameterized endpoints are broken

**Files modified:** `packages/api-client/src/fetcher.ts`
**Commit:** 659e9da
**Applied fix:** Added `params?: Record<string, string | number>` to
`RequestInitWithBody`. Introduced `interpolatePath(path, params)` that
substitutes `{name}` segments with `encodeURIComponent`-escaped values and
throws `ApiError('client_error', ...)` when a required key is missing.
Stripped `params` from the `RequestInit` spread so the synthetic field never
reaches `fetch()`. **Logic-bug class: requires human verification of the
client_error code choice and the regex semantics.**

### CR-02: `refreshOnce()` always resolves — non-OK refresh response is treated as a "successful" promise, masking the actual failure

**Files modified:** `packages/api-client/src/fetcher.ts`
**Commit:** de2ba3a
**Applied fix:** Wrapped the `inFlightRefresh = null` reset in
`queueMicrotask(...)` so concurrent awaiters in the same microtask latch
onto the in-flight promise instead of triggering a second refresh.
Additionally propagated the original network error as `cause` when the
refresh fetch itself rejects, so `session_expired` carries actionable
debugging context. **Logic-bug class: requires human verification that
microtask deferral matches the intended single-flight semantics under all
401-storm scenarios.**

### WR-01: `ApiError` does not preserve the original cause — debugging refresh failures is impossible

**Files modified:** `packages/api-client/src/errors.ts`
**Commit:** 18cab7f
**Applied fix:** Extended the `ApiError` constructor to accept an optional
`{ cause?: unknown }` options bag (ES2022-native) and forwarded it to
`super(message, options)`. Existing call sites continue to work because the
new parameter is optional. The CR-02 commit threads `cause` through the
session_expired refresh-network path; WR-04 also benefits.

### WR-02: `headers` spread loses non-`Record` shapes, breaking valid `RequestInit` callers

**Files modified:** `packages/api-client/src/fetcher.ts`
**Commit:** 5a49974
**Applied fix:** Replaced the lossy
`{ ...init.headers as Record<string, string> }` spread with a `Headers`
instance constructed from `init.headers`. All three valid HeadersInit
shapes (`Headers`, `Record<string, string>`, `[string, string][]`) now
round-trip correctly. Applied the same normalization to the retry path so
a `Headers` argument survives across the refresh-and-retry cycle.

### WR-03: `init.body` of type `unknown` is JSON-stringified unconditionally — `FormData` / `Blob` / `URLSearchParams` are corrupted

**Files modified:** `packages/api-client/src/fetcher.ts`
**Commit:** eef3155
**Applied fix:** Branched on body type before stringifying. `FormData`,
`Blob`, `URLSearchParams`, `ArrayBuffer`, typed-array views (via
`ArrayBuffer.isView`), and `ReadableStream` are passed through verbatim
with no `Content-Type` override (so fetch can derive multipart boundaries
etc.). Only plain JSON values are stringified and tagged with
`Content-Type: application/json`.

### WR-04: `finishResponse` throws on empty `application/json` 200 bodies

**Files modified:** `packages/api-client/src/fetcher.ts`
**Commit:** 608696d
**Applied fix:** Read the body as text first; return `undefined` for empty
bodies; wrap genuine `JSON.parse` failures in
`ApiError('unknown_error', 'Failed to parse JSON response', undefined,
{ cause: err })`. Consumers using the
`if (err instanceof ApiError)` discriminator now catch malformed-JSON
failures uniformly with all other API errors.

### WR-05: `register_user_loader` is called on every `create_app()` — test isolation risk

**Files modified:** `apps/backend/app/main.py`
**Commit:** 756dd9c
**Applied fix:** Confirmed via `app/core/dependencies.py:54-61` that
`register_user_loader` is documented as idempotent — re-registering replaces
the slot, which is intentional so tests can inject stub loaders through
`create_app()`. Added an explanatory comment at the call site cross-
referencing the contract so the next reader does not mis-diagnose this
pattern. No sentinel guard added, because the existing behavior is the
intended test-isolation seam.

### WR-06: CI drift gate runs `git diff --exit-code` without `--quiet` and against an unstaged file — false negatives possible

**Files modified:** `.github/workflows/ci.yml`
**Commit:** 2d364f0
**Applied fix:** Added `git ls-files --error-unmatch <file>` before each
`git diff --exit-code <file>` invocation in the drift-gate steps for both
`apps/backend/openapi.json` and `packages/api-client/src/schema.d.ts`. The
job now fails fast if either generated artifact is ever untracked or
gitignored, closing the silent-pass loophole.

## Skipped Issues

None.

## Verification

- `pnpm --filter @sportzal/api-client typecheck` — clean after every fix.
- `pnpm -r typecheck` — clean across `packages/api-client` and
  `apps/admin-web` after the final commit.
- `python3 -c "import ast; ast.parse(...)"` on `apps/backend/app/main.py` — clean.
- `python3 -c "import yaml; yaml.safe_load(...)"` on `.github/workflows/ci.yml` — clean.

Logic-class fixes (CR-01, CR-02) are flagged above for human verification:
syntax/structural correctness is confirmed, but the semantic correctness of
single-flight microtask deferral and the path-interpolation regex still
benefits from a developer eyeball pass before the phase ships.

---

_Fixed: 2026-05-03_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
