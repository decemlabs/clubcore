---
phase: 65-handoff-artifacts
reviewed: 2026-05-29T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - tools/newman/augment-collection.mjs
  - package.json
  - tools/newman/clubcore-smoke.postman_environment.json
  - .gitignore
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 65: Code Review Report

**Reviewed:** 2026-05-29
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the Phase 65 API-handoff tooling: the `augment-collection.mjs` Postman post-processor, the root `package.json` NPM scripts, the committed Newman environment file, and `.gitignore`. This is build tooling, not production runtime code — severity is calibrated accordingly.

No credential leaks found: the committed environment file (`clubcore-smoke.postman_environment.json`) ships `password` as an empty string with `type: "secret"`, and the generated collection uses `{{ownerEmail}}`/`{{password}}` template variables throughout. Cookie names are correct (`sportzal_csrf`, `sz_access`, `sz_refresh` — no stale `cc_*` references). The `Internal` folder is correctly excluded. The smoke folder is present with 14 items, all safe GETs plus the idempotency replay pair; no destructive mutations (`refund`/`sell`) are included. Byte-stability requirements are met: `JSON.stringify(collection, null, 2) + '\n'` produces a deterministic trailing newline, and the dedup/filter logic is idempotent on re-run.

Three warning-level issues were found, all in `package.json`'s `newman` script configuration. Three info-level observations are noted in `augment-collection.mjs` logic.

---

## Warnings

### WR-01: `pnpm newman` runs the entire collection — not the smoke folder

**File:** `package.json:11`
**Issue:** The `newman` script runs the full collection without `--folder smoke`. When `pnpm newman` is invoked, Newman executes every request in the collection (all domain folders), not just the curated smoke subset. Most non-smoke requests carry `<string>`/`<email>` placeholder bodies from `openapi-to-postmanv2` and will produce 4xx/5xx responses. With `--bail` set, the first failure stops the run, meaning even smoke requests that come later will never execute. The smoke folder comment at line 592 says to invoke with `--folder smoke`, but the `package.json` script does not do this.

**Fix:**
```json
"newman": "newman run .planning/handoff/v1.11-clubcore.postman_collection.json -e tools/newman/clubcore-smoke.postman_environment.json --folder smoke --bail"
```

---

### WR-02: `pnpm newman` has no mechanism to inject the runtime password

**File:** `package.json:11`
**Issue:** The environment file ships `password` as an empty string (correct — no hardcoded secret). But the `newman` script provides no way for the caller to supply the runtime password. Running `pnpm newman` as written will attempt login with `password=""`, which will return a 401 and immediately bail. The smoke folder description (line 592 of `augment-collection.mjs`) documents `SEED_VERIFY_OWNER_PASSWORD=<pwd> pnpm newman run --env-var "password=$SEED_VERIFY_OWNER_PASSWORD"`, but this is a manual `newman` invocation that bypasses the `pnpm` script wrapper entirely.

The `pnpm` script should either (a) document that it is not self-contained and must be run as `newman` directly with `--env-var`, or (b) propagate the env var:

**Fix (option a — explicit wrapper that forwards the variable):**
```json
"newman": "newman run .planning/handoff/v1.11-clubcore.postman_collection.json -e tools/newman/clubcore-smoke.postman_environment.json --folder smoke --bail --env-var password=$SEED_VERIFY_OWNER_PASSWORD"
```
Callers then invoke: `SEED_VERIFY_OWNER_PASSWORD=<pwd> pnpm newman`

---

### WR-03: `accessToken` collection variable is set to the CSRF cookie value — misleading name and potential future breakage

**File:** `tools/newman/augment-collection.mjs:133` (also `smokeLogin` exec, line 436)
**Issue:** Both the main `walkRequests` injection and the smoke `smokeLogin` item set `accessToken` to the value of `sportzal_csrf`:
```js
pm.collectionVariables.set("accessToken", csrfCookie); // marker: session active
```
The comment acknowledges `sz_access` is httpOnly and cannot be extracted — `accessToken` here is a session-active sentinel, not the actual access token. This is harmless today because no request in the collection uses `{{accessToken}}` as a `Bearer` token header (confirmed by inspection). However, if any future request is added that uses `{{accessToken}}` in an `Authorization: Bearer {{accessToken}}` header, it will silently send the CSRF token value as a bearer token, producing a hard-to-diagnose 401. The variable should be renamed to something unambiguous, or its purpose should be gated more explicitly.

**Fix:** Rename to `sessionActive` (a boolean flag) to avoid misleading any future request that might wire `{{accessToken}}` to a Bearer header:
```js
pm.collectionVariables.set("sessionActive", "true"); // sz_access is httpOnly; auth via cookie jar
```
And update `collection.variable` in Step 2 to declare `sessionActive` instead of `accessToken`.

---

## Info

### IN-01: `writeFileSync` will throw `ENOENT` if the output directory does not yet exist

**File:** `tools/newman/augment-collection.mjs:605`
**Issue:** The output path `.planning/handoff/` is not created before writing. If the directory is absent (e.g., a fresh clone or CI environment where the handoff directory hasn't been created yet), `fs.writeFileSync` throws `ENOENT` with no helpful diagnostic.

**Fix:** Add `fs.mkdirSync(path.dirname(OUTPUT), { recursive: true })` immediately before the `writeFileSync` call:
```js
fs.mkdirSync(path.dirname(OUTPUT), { recursive: true })
fs.writeFileSync(OUTPUT, payload, 'utf-8')
```

---

### IN-02: `extractPath` fallback silently includes Postman `{{param}}` segments

**File:** `tools/newman/augment-collection.mjs:175`
**Issue:** The fallback path reconstruction (used when `url.raw` is absent) filters out `:param`-style path parameters but not `{{param}}`-style Postman variable segments. If `openapi-to-postmanv2` ever emits `url.path` entries as `{{clientId}}` instead of `:clientId`, the reconstructed path would include those segments (e.g., `/api/v1/clients/{{clientId}}`), producing a false non-match against `BODY_SHAPE_MAP`. This is low impact because `url.raw` is always populated by the current generator version, but the fallback is silently wrong.

**Fix:**
```js
const pathSegs = (url.path || []).filter(
  (seg) => typeof seg === 'string' && !seg.startsWith(':') && !seg.startsWith('{{'),
)
```

---

### IN-03: `report` shape assertion omits the `total` field present in pagination envelopes

**File:** `tools/newman/augment-collection.mjs:138`
**Issue:** `bodyShapeLines('report')` checks only for `items` array, unlike the `list` shape which also asserts `total` is a number. If `/api/v1/reports/clients` returns a standard paginated envelope (per the `Pagination` convention in `CLAUDE.md`: `{ items, total, page, pageSize }`), the `total` assertion is silently skipped. This is not incorrect if the reports endpoint intentionally omits `total`, but if it follows the standard pagination contract, the body-shape test is under-specified.

**Fix:** If the reports endpoint follows the standard pagination envelope, use `list` shape:
```js
'/api/v1/reports/clients': 'list',
```
Otherwise, document explicitly why `total` is not asserted for this endpoint.

---

_Reviewed: 2026-05-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
