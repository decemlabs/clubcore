# Phase 65: Handoff Artifacts - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 9 new/modified files
**Analogs found:** 8 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tools/newman/augment-collection.mjs` | utility | transform (file-I/O) | `apps/backend/scripts/export_postman.py` | role-match |
| `.planning/handoff/v1.11-clubcore.postman_collection.json` | config/artifact | file-I/O (generated) | `.planning/handoff/v1.6-postman.json` | exact |
| `.planning/handoff/v1.11-clubcore.postman_environment.json` | config/artifact | file-I/O (generated) | `.planning/handoff/v1.6-postman.json` (env block) | partial |
| `tools/newman/clubcore-smoke.postman_environment.json` | config | file-I/O | `apps/backend/scripts/verify/_lib.sh` (env vars) | partial |
| `.planning/handoff/clubcore-auth-runbook.md` | documentation | — | `.planning/handoff/v1.4-auth-runbook.md` | exact |
| `package.json` (repo root) | config | — | `packages/api-client/package.json` | role-match |
| `redocly.yaml` (edit: add `preview-docs` note) | config | — | `redocly.yaml` | exact (modify) |
| `.gitignore` (edit: add `.docs-site/`) | config | — | `.gitignore` | exact (modify) |
| `tools/newman/` smoke runner script (optional shell or npm script) | utility | request-response | `apps/backend/scripts/verify/01_sale_with_payment.sh` | role-match |

---

## Pattern Assignments

### `tools/newman/augment-collection.mjs` (utility, transform/file-I/O)

**Analog:** `apps/backend/scripts/export_postman.py`

**Path resolution pattern** (lines 36-40):
```python
HERE = pathlib.Path(__file__).resolve()
SOURCE = HERE.parents[1] / "openapi.json"
TARGET = HERE.parents[3] / ".planning" / "handoff" / "v1.6-postman.json"
```
Node.js equivalent: use `import.meta.url` + `new URL(...)` or `path.resolve(import.meta.dirname, '../../..', ...)` for cwd-independent resolution.

**_internal tag exclusion pattern** (lines 61-66):
```python
INTERNAL_TAG = "_internal"

def _operation_is_internal(operation: dict[str, Any]) -> bool:
    """D-46-08: drop operations tagged with INTERNAL_TAG."""
    tags = operation.get("tags") or []
    return INTERNAL_TAG in tags
```
Apply in the augment script: after `openapi-to-postmanv2` generates the base collection, walk all items and remove any folder/request whose tag is `_internal`. The npm tool's `folderStrategy=Tags` will create a folder named `_internal`; the augment step removes that folder entirely.

**Byte-stable write pattern** (line 186):
```python
payload = json.dumps(collection, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
TARGET.write_text(payload, encoding="utf-8")
```
Node equivalent: `JSON.stringify(collection, null, 2) + '\n'` written via `fs.writeFileSync(target, payload, 'utf-8')`. Do NOT use `sort_keys` equivalent (`JSON.stringify` replacer) unless the tool already produces a stable key order — `openapi-to-postmanv2` output key order is fixed by the library; the augment script should preserve it and add a trailing newline only.

**Collection variables block pattern** (lines 155-163):
```python
return {
    "info": {
        "_postman_id": str(uuid.uuid5(NAMESPACE, "sportzal-v1.6-handoff")),
        "name": COLLECTION_NAME,
        "schema": COLLECTION_SCHEMA,
    },
    "item": root_items,
    "variable": [{"key": "baseUrl", "value": "http://localhost:8000"}],
}
```
For v1.11 the augment script must extend `variable` with `accessToken` and `csrfToken` (placeholder empty strings) at the collection level.

**Auth pre-request script injection pattern (Postman v2.1 structure):**
The augment script must inject `event` blocks into the collection root and onto the login request. Copy the v1.6 `id` + `name` + `request` item structure from `.planning/handoff/v1.6-postman.json` lines 1-80 as the item shape reference:
```json
{
  "id": "e8504658-7d2c-5a5f-a998-6de4ec275914",
  "name": "Login",
  "request": {
    "method": "POST",
    "url": { "raw": "{{baseUrl}}/api/v1/auth/login", ... }
  },
  "event": [
    {
      "listen": "test",
      "script": {
        "type": "text/javascript",
        "exec": ["// injected by augment-collection.mjs"]
      }
    }
  ]
}
```
Collection-level `event` with `listen: "prerequest"` is the Postman v2.1 mechanism for the CSRF auto-injection on non-GET requests.

---

### `.planning/handoff/v1.11-clubcore.postman_collection.json` (generated artifact)

**Analog:** `.planning/handoff/v1.6-postman.json`

**Top-level structure** (lines 1-6):
```json
{
  "info": {
    "_postman_id": "<uuid5 over 'clubcore-v1.11-handoff'>",
    "name": "clubcore v1.11 — ...",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [...],
  "variable": [
    {"key": "baseUrl",     "value": "http://localhost:8000"},
    {"key": "accessToken", "value": ""},
    {"key": "csrfToken",   "value": ""}
  ],
  "event": [...]
}
```
Generated by `openapi-to-postmanv2@6.0.1 --folderStrategy=Tags`, then post-processed by `tools/newman/augment-collection.mjs`. The `_internal` tag folder is removed in post-processing.

**Request item shape** (lines 18-80 of v1.6 analog):
Each item carries `id`, `name`, `request` (with `method`, `url.raw={{baseUrl}}/...`, `url.path[]`, `url.host=["{{baseUrl}}"]`, `url.variable[]` for `{param}` path params, `header[]` with Accept + Content-Type on non-GET, optional `body.mode=raw`), and `event[]` for test assertions.

---

### `.planning/handoff/v1.11-clubcore.postman_environment.json` (config artifact)

**Pattern:** Postman v2.1 environment JSON schema. No close analog in the codebase; base on Postman's documented format:
```json
{
  "_postman_id": "<uuid>",
  "name": "clubcore v1.11 local",
  "values": [
    {"key": "baseUrl",     "value": "http://localhost:8000", "enabled": true, "type": "default"},
    {"key": "accessToken", "value": "",                      "enabled": true, "type": "secret"},
    {"key": "csrfToken",   "value": "",                      "enabled": true, "type": "secret"}
  ],
  "_exporter_id": "clubcore-v1.11"
}
```
This file ships **placeholder values only** — no real credentials (D-65-NEWMAN-CREDS). It is the human GUI environment; the Newman smoke uses a separate env file.

---

### `tools/newman/clubcore-smoke.postman_environment.json` (config)

**Analog:** `apps/backend/scripts/verify/_lib.sh` (lines 44-51)

**Env-var convention pattern** (lines 44-51 of `_lib.sh`):
```bash
BASE_URL="${BASE_URL:-http://localhost:8000}"
VERIFY_OWNER_EMAIL="${VERIFY_OWNER_EMAIL:-verify_owner@local.dev}"
VERIFY_OWNER_PASSWORD="${VERIFY_OWNER_PASSWORD:?must be exported}"
```
Apply: the Newman env JSON commits `baseUrl` and `ownerEmail` (`verify_owner@local.dev`) — fixture email is deterministic and safe to commit. Password is supplied at runtime via `newman --env-var "password=$SEED_VERIFY_OWNER_PASSWORD"` (never in the committed file). Pattern from `seed_verification_fixtures.py` lines 80-88:
```python
_OPERATOR_USERS = (
    ("verify_owner@local.dev",     Role.OWNER,     "Verify Owner",     "SEED_VERIFY_OWNER_PASSWORD"),
    ("verify_reception@local.dev", Role.RECEPTION, "Verify Reception", "SEED_VERIFY_RECEPTION_PASSWORD"),
)
```
Newman env JSON shape:
```json
{
  "_postman_id": "<uuid>",
  "name": "clubcore smoke — local docker compose",
  "values": [
    {"key": "baseUrl",    "value": "http://localhost:8000",   "enabled": true, "type": "default"},
    {"key": "ownerEmail", "value": "verify_owner@local.dev",  "enabled": true, "type": "default"},
    {"key": "password",   "value": "",                        "enabled": true, "type": "secret"}
  ]
}
```

---

### `.planning/handoff/clubcore-auth-runbook.md` (documentation)

**Analog:** `.planning/handoff/v1.4-auth-runbook.md` (exact structure extension)

**Header pattern** (lines 1-12 of v1.4 runbook):
```markdown
# Sportzal Backend Auth Setup Runbook (v1.4 DRAFT)

**Audience:** внешняя дизайн-команда v2.0 (production admin + client apps).
**Backend version:** v1.4 (commit `10eb78d`+...)
**Source-of-truth contract:** `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts`.
```
v1.11 update: rename header to `# clubcore Backend Auth Runbook (v1.11)`, update backend version reference, keep bilingual convention.

**Section structure to replicate** (all 5 sections from v1.4, plus 3 new for v1.11):
1. Login (email/password) — pattern from lines 15-38
2. Refresh rotation — pattern from lines 40-57
3. CSRF on mutating requests — pattern from lines 59-83
4. Telegram OTP — pattern from lines 85-108
5. Email OTP (**new section**, not in v1.4)
6. Logout-all — pattern from lines 110-128
7. Idempotency-Key semantics (**new section**, Phase 66 handoff seam)
8. `sportzal_csrf` carry-over note + v2.0 cutover plan (**new section**)

**Bilingual prose+curl pattern** (lines 59-83):
```markdown
## 3. CSRF on mutating requests

Каждый mutating HTTP verb (POST / PATCH / PUT / DELETE) **должен** содержать header
`X-CSRF-Token: <значение sportzal_csrf cookie>`. ...

```bash
CSRF=$(awk '/sportzal_csrf/ {print $7}' cookies.txt)
curl -i -s -X POST http://localhost:8000/api/v1/memberships \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Idempotency-Key: $(uuidgen)" \
  -b cookies.txt \
  -d '{"clientId":"<uuid>","planId":"<uuid>","amountKopecks":300000}'
```
```
Each section: Russian prose paragraph, then English `bash` code block. Pair each curl example with its Postman collection request name (per D-65-RUNBOOK-EXTEND).

**Cookie name pattern** (from `_lib.sh` line 82):
```bash
CSRF_TOKEN="$(awk '$6=="sportzal_csrf"{print $7}' "$COOKIE_JAR")"
```
The runbook must use the literal cookie name `sportzal_csrf` (D-11-CSRF-DEFER carry-over) in all curl examples.

**Idempotency-Key section new content** — source from `.planning/handoff/v1.11-idempotency-audit.md` lines 52-58 for Category-A endpoint list; semantics from 66-CONTEXT.md:
- Key format: `^[A-Za-z0-9_:-]{16,128}$`
- Scope: user-scoped (two users may reuse the same key string without collision)
- TTL: 24h replay window
- Verbatim replay: cached first-success response returned; NOT live DB state — point to resource GET for current state
- Absent key on Category-A endpoint: `422 idempotency_key_required`
- Same key + different body: `422 idempotency_key_reuse`

**Idempotency replay curl pattern** (from `10_online_refund_and_idempotent_replay.sh` lines 67-80 as structural model):
```bash
IDEM="$(uuidgen)"
# First call — creates the membership
curl -i -s -X POST http://localhost:8000/api/v1/memberships \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Idempotency-Key: $IDEM" \
  -b cookies.txt \
  -d '{"clientId":"<uuid>","planId":"<uuid>"}'

# Replay — returns cached first-success response (no new DB row)
curl -i -s -X POST http://localhost:8000/api/v1/memberships \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Idempotency-Key: $IDEM" \
  -b cookies.txt \
  -d '{"clientId":"<uuid>","planId":"<uuid>"}'
```

---

### `package.json` (repo root, new private root) (config)

**Analog:** `packages/api-client/package.json` (lines 1-30)

**Private package pattern** (lines 2-4):
```json
{
  "name": "@clubcore/api-client",
  "private": true,
  "version": "0.0.0",
  "type": "module",
```
Root `package.json` uses `"private": true`, no `"version"` field (omit or `"0.0.0"`), `"type": "module"` (so `.mjs` augment script runs with `node` natively).

**Scripts + devDependencies pattern** (lines 15-26):
```json
"scripts": {
  "codegen": "openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts",
  "typecheck": "tsc --noEmit",
},
"devDependencies": {
  "openapi-typescript": "^7.13.0",
  "typescript": "~5.7.2",
  "vitest": "~2.1.8"
},
"engines": {
  "node": ">=20.0.0",
  "pnpm": ">=9.0.0"
}
```
Root adaptation — scripts for Phase 65:
```json
"scripts": {
  "docs":            "redocly preview-docs apps/backend/openapi.json --port 8080",
  "newman":          "newman run .planning/handoff/v1.11-clubcore.postman_collection.json -e tools/newman/clubcore-smoke.postman_environment.json --bail",
  "postman:gen":     "openapi2postmanv2 -s apps/backend/openapi.json -o tools/newman/base-collection.json -O folderStrategy=Tags,requestNameSource=summary",
  "postman:augment": "node tools/newman/augment-collection.mjs"
},
"devDependencies": {
  "@redocly/cli":          "2.31.4",
  "newman":                "<pinned>",
  "openapi-to-postmanv2":  "6.0.1"
},
"engines": {
  "node": ">=20.0.0",
  "pnpm": ">=9.0.0"
}
```
Note: `tools/` is outside `pnpm-workspace.yaml` globs (`apps/*`, `packages/*`) — the root `package.json` is the workspace root itself (standard pnpm monorepo convention); `tools/` is not a workspace package.

**Precedent for reading `apps/backend/openapi.json` from a tool script** (`packages/api-client/package.json` line 16):
```json
"codegen": "openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts"
```
Root `package.json` scripts reference the same file as `apps/backend/openapi.json` (relative from repo root).

---

### `redocly.yaml` (edit: doc-site privacy note) (config, modify)

**Analog:** `redocly.yaml` (current file, lines 1-46)

The existing `redocly.yaml` is reused unchanged for HND-06. `pnpm docs` calls `redocly preview-docs apps/backend/openapi.json --port 8080` — it consumes the existing config automatically (Redocly CLI auto-discovers `redocly.yaml` in cwd). No edits to `redocly.yaml` itself are required beyond confirming `preview-docs` works with the current ruleset.

The D-64-NO-EXAMPLES / `operation-4xx-response: off` rule (line 37) is relevant: `preview-docs` renders the spec without enforcing lint rules — it is a pure rendering command. The existing `recommended` + three `off` overrides remain correct.

---

### `.gitignore` (edit: add `.docs-site/`) (config, modify)

**Analog:** `.gitignore` (current file, lines 1-26)

**Existing pattern** — cross-cutting ignores with inline comments (lines 14-26):
```gitignore
# Root-level dependency caches (per-app caches are covered by the per-app .gitignore files)
node_modules/

# Claude Code per-project installation (GSD agents/hooks/settings — user-specific, auto-generated)
.claude/

# Logs
*.log
pnpm-debug.log*
```
**Add after the existing block:**
```gitignore
# Redocly static doc-site build output (D-11-DOCS-PRIVATE — private artifact, never published)
.docs-site/
```

---

## Shared Patterns

### No-credentials-committed rule
**Source:** `apps/backend/scripts/seed_verification_fixtures.py` lines 94-127 + `apps/backend/scripts/verify/_lib.sh` lines 48-51
**Apply to:** `tools/newman/clubcore-smoke.postman_environment.json`, `package.json` newman script, `clubcore-auth-runbook.md`

Pattern: env vars supply secrets at runtime; committed files contain email/URL but never password. The Newman smoke parallels the `_lib.sh` convention:
```bash
# _lib.sh line 49 — password required at runtime, not defaulted
VERIFY_OWNER_PASSWORD="${VERIFY_OWNER_PASSWORD:?must be exported}"
```
Newman equivalent: `newman run ... --env-var "password=$SEED_VERIFY_OWNER_PASSWORD"`. The committed env JSON has `"value": ""` for the password key.

### CSRF cookie name literal
**Source:** `apps/backend/scripts/verify/_lib.sh` line 82
**Apply to:** `tools/newman/augment-collection.mjs` (Postman pre-request script body), `clubcore-auth-runbook.md`

```bash
CSRF_TOKEN="$(awk '$6=="sportzal_csrf"{print $7}' "$COOKIE_JAR")"
```
The literal cookie name is `sportzal_csrf` in v1.11 (D-11-CSRF-DEFER). In Postman pre-request script:
```javascript
const csrf = pm.cookies.get('sportzal_csrf') || pm.response.headers.get('sportzal_csrf') || '';
pm.collectionVariables.set('csrfToken', csrf);
```

### Mutation headers (CSRF + Idempotency-Key)
**Source:** `apps/backend/scripts/verify/_lib.sh` lines 91-104
**Apply to:** `tools/newman/augment-collection.mjs` (collection-level pre-request event), `clubcore-auth-runbook.md`

```bash
mut() {
  local method="$1" path="$2" body="$3"
  local idem
  idem="$(uuidgen)"
  curl -i -s -X "$method" "$BASE_URL$path" \
    -H 'Content-Type: application/json' \
    -H "Idempotency-Key: $idem" \
    -H "X-CSRF-Token: $CSRF_TOKEN" \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    -d "$body"
}
```
Postman collection-level pre-request: inject `X-CSRF-Token: {{csrfToken}}` on non-GET methods. Idempotency-Key is injected per-request on Category-A endpoints (see idempotency audit Category-A list in `.planning/handoff/v1.11-idempotency-audit.md` lines 52-60).

### Byte-stable artifact discipline
**Source:** `apps/backend/scripts/export_postman.py` line 186
**Apply to:** `tools/newman/augment-collection.mjs`

```python
payload = json.dumps(collection, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
TARGET.write_text(payload, encoding="utf-8")
```
Node equivalent: trailing newline required; `indent=2` → `JSON.stringify(..., null, 2) + '\n'`. Re-running produces zero git diff (D-64-BYTE-STABLE / D-65-AUGMENT). The augment script must produce identical bytes on macOS and Linux.

### _internal tag exclusion
**Source:** `apps/backend/scripts/export_postman.py` lines 43, 61-66
**Apply to:** `tools/newman/augment-collection.mjs` (post-processing step after `openapi-to-postmanv2` generates base collection)

```python
INTERNAL_TAG = "_internal"

def _operation_is_internal(operation: dict[str, Any]) -> bool:
    tags = operation.get("tags") or []
    return INTERNAL_TAG in tags
```
The npm tool with `folderStrategy=Tags` will create a top-level folder item whose `name` equals `"_internal"`. The augment script removes it from `collection.item` by filtering: `collection.item = collection.item.filter(f => f.name !== '_internal')`.

### Runbook bilingual convention
**Source:** `.planning/handoff/v1.4-auth-runbook.md` (entire document structure)
**Apply to:** `.planning/handoff/clubcore-auth-runbook.md`

- Section header: English title (`## N. Section name`)
- Prose body: Russian
- Code/curl block: English bash, with `bash` fence
- Each section ends with a note of the Postman collection request name/ID where applicable

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tools/newman/augment-collection.mjs` (Postman pre-request/test script bodies) | utility | transform | No existing Postman JavaScript pm.* scripting in the codebase — must be authored from Postman v2.1 API docs. The structural outer pattern (file read/transform/write) copies `export_postman.py`; the inner `pm.*` API calls have no codebase analog. |

---

## Metadata

**Analog search scope:** `apps/backend/scripts/`, `.planning/handoff/`, `packages/api-client/`, repo root config files
**Files scanned:** 9 analog files read directly; 3 workspace/config files read for structural reference
**Pattern extraction date:** 2026-05-29
