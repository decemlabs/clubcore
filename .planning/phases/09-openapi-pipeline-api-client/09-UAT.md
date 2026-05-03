---
status: complete
phase: 09-openapi-pipeline-api-client
source:
  - .planning/phases/09-openapi-pipeline-api-client/09-01-SUMMARY.md
  - .planning/phases/09-openapi-pipeline-api-client/09-02-SUMMARY.md
  - .planning/phases/09-openapi-pipeline-api-client/09-03-SUMMARY.md
started: 2026-05-03T17:58:34Z
updated: 2026-05-03T21:10:00Z
---

## Current Test

(none — UAT complete)

## Tests

### 1. Cold Start Smoke Test — backend boots & /healthz responds
expected: |
  Run `uv run uvicorn app.main:create_app --factory --reload` from
  `apps/backend/` with the venv active. Hit `GET /healthz`. The app
  boots without import or lifespan errors and the health endpoint
  returns 200.
result: issue
issue: |
  Boot failed during `uvicorn ... --factory --reload`:
    pydantic_core._pydantic_core.ValidationError: 2 validation errors for Settings
      telegram_bot_token   Field required
      telegram_bot_username  Field required
  Settings declares both fields as required without defaults. The
  user's `.env` does not provide them, so the app cannot start.
  Phase 9 already documented this Settings-vs-.env gap in
  `09-01-SUMMARY.md` (the export CLI does `os.environ.setdefault(...)`
  for the same fields). NOT a Phase 9 regression — pre-existing
  project setup issue exposed by the smoke test.
severity: medium
classification: out-of-scope (pre-existing — likely Phase ≤8 hygiene gap)
remediation: |
  Either add `TELEGRAM_BOT_TOKEN` / `TELEGRAM_BOT_USERNAME` to
  `apps/backend/.env.example` and the user's local `.env`, OR
  give them safe dev defaults in `app/core/config.py` (e.g.
  `Field(default="dev-stub")`) so dev boot doesn't require live
  Telegram credentials. Recommend opening a follow-up phase or
  treating as a 999.x backlog item.

### 2. OpenAPI Export CLI is lifespan-safe and byte-stable
expected: |
  From `apps/backend/` (using the documented module form, matching
  CI's invocation in `.github/workflows/ci.yml:51`):
    uv run python -m scripts.export_openapi
    cp openapi.json /tmp/openapi.run1.json
    uv run python -m scripts.export_openapi
    diff -q /tmp/openapi.run1.json openapi.json
  Both runs exit 0, the script does NOT require a real Postgres/Redis
  (env stubs satisfy Settings), and the two runs produce byte-identical
  JSON (diff prints nothing). `openapi.json` ends with a newline and
  contains `"version": "1.1.0"`.
result: passed
note: |
  Two consecutive runs each wrote 37266 bytes to
  `apps/backend/openapi.json`; `diff -q` was silent. File ends with
  `}\n}\n` (trailing newline ✓) and `grep -c '"version": "1.1.0"'`
  returned 1. CI uses the same `-m scripts.export_openapi` form
  (`.github/workflows/ci.yml:51`), so the gate is exercised exactly
  the way the script is documented.
  (Initial UAT instruction told the user to invoke as a path
  (`python scripts/export_openapi.py`) which fails with
  `ModuleNotFoundError: No module named 'app'` because that form
  doesn't put `apps/backend/` on sys.path. UAT instruction corrected.)

### 3. api-client package typechecks under pnpm
expected: |
  `pnpm --filter @sportzal/api-client typecheck` exits 0; `pnpm -r
  typecheck` also exits 0 across all 3 workspace projects.
result: passed
note: |
  `pnpm --filter @sportzal/api-client typecheck` → exit 0 (`tsc
  --noEmit` clean). `pnpm -r typecheck` → all 3 workspace projects
  done (api-client + admin-web), exit 0.

### 4. Predev codegen hook regenerates schema from current openapi.json
expected: |
  `apps/admin-web` has a `predev` script that invokes
  `pnpm --filter @sportzal/api-client codegen`, and the codegen
  command regenerates `packages/api-client/src/schema.d.ts` from
  the current `apps/backend/openapi.json` byte-deterministically.
result: passed
note: |
  `apps/admin-web/package.json` predev: `pnpm --filter
  @sportzal/api-client codegen`. `dependencies['@sportzal/api-client']`:
  `workspace:*`. Verified the codegen pipeline three ways:
    1. Running `pnpm --filter @sportzal/api-client codegen` against
       the current spec produces a schema.d.ts byte-equal to the
       committed copy (drift-gate semantics).
    2. Adding a new path `/uat-test-only` to `openapi.json` and
       re-running codegen yields a 16-line schema delta containing
       the new path's operation entry — confirming the codegen
       reacts to real type-changing spec edits.
    3. Restoring the spec via the same export CLI restores the
       schema byte-for-byte. Both temporary edits cleaned up.
  (Note: bumping only `info.version` produces NO schema delta —
  `openapi-typescript` doesn't emit `info` into the type output.
  This is expected and not a defect.)

### 5. CI drift-gate fails on out-of-sync openapi.json / schema.d.ts
expected: |
  Backend gate: `git diff --exit-code apps/backend/openapi.json`
  exits non-zero when the spec is locally edited.
  Frontend gate: `git diff --exit-code packages/api-client/src/schema.d.ts`
  exits non-zero when the schema is locally edited.
  CI uses the same logic, plus `git ls-files --error-unmatch` per
  WR-06 fix to assert the file is tracked before diffing.
result: passed
note: |
  Locally simulated both gates:
    - `sed -i '' 's/"version": "1.1.0"/"version": "9.9.9"/' apps/backend/openapi.json`
      → `git diff --exit-code` exits 1 (drift detected).
    - `echo '// drift' >> packages/api-client/src/schema.d.ts`
      → `git diff --exit-code` exits 1.
  Both files restored cleanly afterwards. CI workflow at
  `.github/workflows/ci.yml:63-64` and `:113-114` runs
  `git ls-files --error-unmatch` before `git diff --exit-code` for
  both files, closing the WR-06 untracked-file silent-pass gap.

### 6. CR-01 fix — request() interpolates path parameters
expected: |
  `request('GET', '/api/v1/clients/{client_id}', { params: { client_id: 'abc-123' } })`
  fetches `/api/v1/clients/abc-123`, NOT the literal templated string.
  Missing required param throws `ApiError('client_error', ...)`.
  Path with no placeholders is unchanged.
result: passed
note: |
  Vitest smoke test (jsdom, run via admin-web's vitest install)
  confirmed all three behaviors:
    ✓ substitutes {client_id} with provided param
    ✓ throws ApiError(client_error) when path param missing
    ✓ returns path unchanged when no placeholders
  Test file written to `packages/api-client/src/__uat__/fetcher.uat.test.ts`,
  ran clean, then deleted (UAT smoke only — not part of permanent
  package surface). Permanent regression coverage should be added
  via /gsd-add-tests or in a follow-up phase.

### 7. CR-02 fix — single-flight refresh under 401 storm
expected: |
  Three concurrent `request(...)` calls all hitting 401 simultaneously
  trigger exactly ONE call to `/api/v1/auth/refresh`, then all three
  retries complete via the rotated cookies.
result: passed
note: |
  Same vitest smoke test as test 6. Mocked fetch returned 401 for the
  first three non-refresh calls and 200 thereafter; counted refresh
  calls explicitly. Result: `refreshCalls === 1` after three concurrent
  `request()` calls all settled `fulfilled`. The `queueMicrotask`
  deferral in `refreshOnce()` correctly holds the in-flight slot
  across the same-tick 401 burst (CR-02 fix verified).

### 8. REQUIREMENTS.md API-05 wording matches committed-spec reality
expected: |
  `.planning/REQUIREMENTS.md` API-05 entry no longer says the schema is
  "gitignored locally" — it describes the committed schema with CI
  drift-gates as the enforcement mechanism (per Phase 9 D-07).
result: passed
note: |
  Line 91: "API-05: ... produces src/schema.d.ts (committed to git per
  Phase 9 D-07 — required for API-07 drift-gate to be meaningful) ..."
  Wording aligned with D-07. (The status table at line 229 still shows
  API-05/06/07 as "Pending" — that's a tracking-table update for the
  verifier/orchestrator, not a wording defect, and is the normal
  pre-verification state.)

## Summary

total: 8
passed: 7
issues: 1
pending: 0
skipped: 0

## Gaps

### Gap 1 — Backend boot requires Telegram env vars (pre-existing)
- **From test:** 1. Cold Start Smoke Test
- **Severity:** medium
- **Phase 9 regression:** no
- **Classification:** out-of-scope — pre-existing project hygiene gap exposed by smoke test
- **Symptom:** `uvicorn app.main:create_app --factory --reload` aborts with
  `ValidationError: telegram_bot_token / telegram_bot_username Field required`
  when the developer's `.env` does not include those fields.
- **Phase 9 already noted this** in `09-01-SUMMARY.md` (export CLI uses
  `os.environ.setdefault(...)` for the same Settings fields, precisely
  because the same problem affects the export pipeline in clean shells).
- **Suggested remediation:** add the two fields to `.env.example` with
  safe dev placeholders, or give them defaults in `app/core/config.py`.
  Track as a 999.x backlog item or a tiny standalone phase. NOT a
  Phase 9 fix — Phase 9's deliverables (export CLI, api-client package,
  CI drift-gates) all work as specified despite this gap.

### Gap 2 — Permanent regression test coverage for fetcher fixes
- **From test:** 6 (CR-01) + 7 (CR-02)
- **Severity:** low (advisory)
- **Phase 9 regression:** no — fixes verified via temporary UAT test
- **Symptom:** `packages/api-client` ships with no test runner configured;
  the CR-01/CR-02 fixes were verified via a throwaway vitest file run
  through admin-web's vitest install. There is no permanent guard against
  regression in `request()` path interpolation or single-flight refresh.
- **Suggested remediation:** add vitest as a devDep on `packages/api-client`
  (or a shared workspace test setup), port the UAT smoke tests to permanent
  test files, and wire `pnpm --filter @sportzal/api-client test` into CI.
  Best handled by `/gsd-add-tests 09` or as part of Phase 10 frontend
  wiring work.
