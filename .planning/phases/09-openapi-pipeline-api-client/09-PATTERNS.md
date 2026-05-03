# Phase 9: OpenAPI Pipeline + packages/api-client — Pattern Map

**Mapped:** 2026-05-03
**Files analyzed:** 12 (8 NEW, 4 MODIFIED)
**Analogs found:** 11 / 12 (one file — `.github/workflows/ci.yml` — has no in-repo analog: project has zero pre-existing GitHub Actions; that file is greenfield by external convention.)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/scripts/export_openapi.py` | script (Python CLI, stdlib I/O) | file-I/O (read app → write JSON) | `apps/backend/scripts/seed_demo_data.py` | strong (same role + idiomatic shape) |
| `.github/workflows/ci.yml` | workflow (GH Actions YAML) | event-driven (PR/push trigger) | none in-repo; closest stylistic anchor is `apps/backend/Dockerfile` (multi-stage uv-aware build) and `apps/backend/docker-compose.yml` (multi-service composition) | external-only |
| `packages/api-client/tsconfig.json` | config (TS compiler) | request-response (compile-time) | `apps/admin-web/tsconfig.app.json` (strict mode flags) + `apps/admin-web/tsconfig.json` (path alias shape) | partial — admin-web is `noEmit`, lib mode here must `emit` declarations |
| `packages/api-client/src/index.ts` | source-module (barrel) | request-response (re-export) | `apps/admin-web/src/shared/api/services/index.ts` (swap-seam barrel with English narrative comment) | role-match |
| `packages/api-client/src/fetcher.ts` | source-module (transport) | request-response with retry + single-flight | none — first hand-rolled transport in the repo. Closest anchor: `apps/backend/app/core/dependencies.py:verify_csrf` (mirrors header/cookie names + safe-method exempt list); `apps/backend/app/core/exceptions.py:_app_error_handler` (server-side wire shape that fetcher must parse) | role-mirror (server↔client) |
| `packages/api-client/src/errors.ts` | source-module (error class) | request-response (throw/catch) | `apps/backend/app/core/exceptions.py:AppError` (wire-format counterpart — D-12 mandate "shape mirror") | strong (cross-language mirror) |
| `packages/api-client/src/schema.d.ts` | type-decl (generated, committed) | generated artifact | none in-repo — first generated TS-type artifact. Closest precedent for "committed generated file": `apps/admin-web/src/routeTree.gen.ts` (referenced in `tsconfig.app.json`'s exclude list and `.gitignore` line 25) | partial (precedent for committed-or-gitignored generated TS) |
| `apps/backend/openapi.json` | generated-spec (JSON, committed) | generated artifact | none — first JSON spec produced by export script | new-class |
| `packages/api-client/package.json` | manifest (pnpm package) | n/a | `packages/api-client/package.json` (current placeholder) + `apps/admin-web/package.json` (scripts shape, devDeps mix) + `packages/ui/package.json` (sibling placeholder) | strong (file is being grown, not invented) |
| `apps/admin-web/package.json` | manifest (modify) | n/a | itself (current shape is the analog; only adding 1 dep + 1 script) | self |
| `packages/api-client/README.md` | doc | n/a | `packages/api-client/README.md` placeholder + `apps/backend/README.md` style | self |
| `apps/backend/app/main.py` | source-module (factory; **possible** edit only — confirm `app.title` + `app.version` for byte-stability) | request-response | itself (already sets `title="Sportzal API"`; D-06 candidate for `version="1.1.0"` if currently absent) | self |
| `apps/backend/pyproject.toml` | manifest (Python deps; **possible** edit only) | n/a | itself | self |

---

## Pattern Assignments

### `apps/backend/scripts/export_openapi.py` (NEW — script, file-I/O)

**Role:** standalone Python CLI invoked by `uv run python -m scripts.export_openapi` (per the seeder convention, runs as `python -m scripts.<name>`). Lifespan-safe — no DB/Redis touch.

**Analog:** `apps/backend/scripts/seed_demo_data.py` — the only sibling script in `apps/backend/scripts/` (alongside `backup_db.sh`). Establishes the file-shape: top-doc rationale block, `from __future__ import annotations`, env-driven config reads, `def main() -> int`, `if __name__ == "__main__": raise SystemExit(main())`.

**Top-doc + imports pattern** (`apps/backend/scripts/seed_demo_data.py:1-29`):
```python
"""Seed the bootstrap owner (AUTH-EP-04 / D-25).
...
    uv run python -m scripts.seed_demo_data
...
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select
...
from app.core.config import get_settings
```
Mirror this header style: phase-tagged title (`OpenAPI export (API-01 / Phase 9 D-04..D-06)`), the operator-invocation example as a literal `uv run` line, and `from __future__ import annotations` even though Python 3.12 does not require it (project convention — every script in `apps/backend/scripts/` opens with it).

**Entry-point shape pattern** (`apps/backend/scripts/seed_demo_data.py:91-96`):
```python
def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
```
Phase 9 export script differs: there is **no async work** — `create_app().openapi()` is sync and `pathlib.Path.write_text` is sync. So drop `_run()`/`asyncio.run` and inline the work in `main() -> int` directly. Keep the `if __name__ == "__main__": raise SystemExit(main())` tail verbatim.

**stderr-on-error pattern** (`apps/backend/scripts/seed_demo_data.py:36-47`):
```python
if not email or not password:
    print(
        "SEED_OWNER_EMAIL and SEED_OWNER_PASSWORD must be set "
        "(see .env.example).",
        file=sys.stderr,
    )
    return 1
```
Apply the same `print(..., file=sys.stderr); return 1` when the post-export sanity-check fails (D-05 mandates `assert 'paths' in spec` — convert that to a stderr-print + return 1 so the script exits with a usable code rather than a Python traceback).

**Differences to introduce** (Phase 9 deliberately deviates):
1. **`os.environ.setdefault('ENVIRONMENT', 'dev')` MUST appear before `from app.main import create_app`** (D-04). The seeder does not do this — it runs in any environment because it does not call `create_app`. The export script does, and `create_app` raises `RuntimeError` in prod with `cookie_secure=False` (Phase 4 D-25, see `apps/backend/app/main.py:61-65`). Comment that this `setdefault` exists *only* so the script can run in a clean shell with no `.env` loaded.
2. **No `asyncio` / no engine** — the seeder opens `create_async_engine` + `async_sessionmaker`; the export script imports neither. `create_app()` is a sync factory and `.openapi()` is a sync property. Lifespan never executes (D-05).
3. **JSON-write contract** — the seeder writes nothing to disk. Phase 9 must:
   ```python
   spec = create_app().openapi()
   assert "paths" in spec, "openapi() returned no paths — FastAPI surface broken"
   payload = json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
   pathlib.Path("apps/backend/openapi.json").write_text(payload, encoding="utf-8")
   ```
   `sort_keys=True` + `ensure_ascii=False` + trailing `\n` together give byte stability across macOS↔Linux (D-06).
4. **Path resolution** — script runs with cwd=`apps/backend/` (per the `python -m scripts.<name>` convention proven by the seeder). So `pathlib.Path("apps/backend/openapi.json")` is **wrong** if cwd is `apps/backend/` — write to `pathlib.Path("openapi.json")` and document the cwd assumption in the top-doc, OR resolve via `pathlib.Path(__file__).resolve().parents[1] / "openapi.json"` for cwd-independence. Pick the latter; planner should lock it.

---

### `.github/workflows/ci.yml` (NEW — workflow, event-driven)

**Role:** GitHub Actions workflow with two jobs (`backend`, `frontend`). Phase 9 D-01..D-03 lock: single file, two parallel jobs, concurrency-cancel on push-to-PR.

**Analog:** No GH Actions workflow exists in this repo (verified — `.github/` directory does not exist). Closest in-repo style anchors:
- `apps/backend/Dockerfile` — for the *uv invocation pattern* (`uv sync --frozen` → `uv run <cmd>`).
- `apps/admin-web/package.json` scripts (`lint`, `typecheck`, `test`) — for the exact pnpm command names CI must call.
- `apps/backend/pyproject.toml` `[dependency-groups].dev` — establishes that `ruff`, `mypy`, `import-linter`, `pytest` are all available via `uv sync` (one install gets every tool).
- `apps/backend/.importlinter` — `lint-imports` is the import-linter CLI invocation.
- `apps/backend/ruff.toml` — confirms `ruff check` + `ruff format --check` are both wanted (lint and format-check are separate gates).

**uv-pattern excerpt** (`apps/backend/Dockerfile:6-19` — establishes how this project drives uv):
```dockerfile
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
```
The CI backend job mirrors the *spirit* (uv + frozen lock) but uses the standard `astral-sh/setup-uv@v3` GH action (per CONTEXT canonical_refs, line 130) instead of the Docker image. Always `uv sync --frozen` (lockfile authority, never relock in CI).

**pnpm-pattern excerpt** (`apps/admin-web/package.json:11-21`):
```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "lint:fix": "eslint . --fix",
  "lint:fixtures": "node scripts/assert-eslint-fixtures.mjs",
  "test": "vitest run",
  "typecheck": "tsc -b --noEmit"
}
```
Frontend job calls these by name via `pnpm -r <script>` (D-02). Note: `pnpm -r lint` will only fire in workspaces where `lint` exists — it skips the backend silently. That is intended.

**Project ESLint fixture-assert pattern** (`apps/admin-web/scripts/assert-eslint-fixtures.mjs:1-22`):
```js
#!/usr/bin/env node
import { ESLint } from 'eslint'
...
const EXPECTED = [
  { file: 'src/__fixtures/raw-palette.tsx', rule: 'no-restricted-syntax' },
  ...
]
```
Phase 9 CI does **not** call `lint:fixtures` — it is admin-web-internal and not on the `pnpm -r` script set unless the package.json declares it. Document the omission so future phases (Phase 10 FE-07) can add it without surprise.

**Differences to introduce** (no in-repo workflow analog, so these are the load-bearing decisions):
1. **Single file `ci.yml`, two jobs `backend` + `frontend`, parallel (no `needs:`)** — D-01.
2. **Triggers:**
   ```yaml
   on:
     pull_request:
     push:
       branches: [main]
   concurrency:
     group: ${{ github.workflow }}-${{ github.ref }}
     cancel-in-progress: true
   ```
   D-03 nails the concurrency group verbatim.
3. **Backend job step order** (D-02):
   - `actions/checkout@v4`
   - `astral-sh/setup-uv@v3` with `python-version: 3.12`
   - `uv sync --frozen` (working-directory: `apps/backend`)
   - `uv run ruff check`
   - `uv run ruff format --check`
   - `uv run mypy`
   - `uv run lint-imports`
   - `uv run python -m scripts.export_openapi`
   - `git diff --exit-code apps/backend/openapi.json` (run from repo root, not from `apps/backend`)
4. **Frontend job step order** (D-02):
   - `actions/checkout@v4`
   - `pnpm/action-setup@v3` (no version — read from `packageManager` in root package.json or admin-web)
   - `actions/setup-node@v4` with `node-version: 20` and `cache: pnpm`
   - `pnpm install --frozen-lockfile` (run at repo root)
   - `pnpm -r lint`
   - `pnpm -r typecheck`
   - `pnpm -r test`
   - `pnpm --filter @sportzal/api-client codegen`
   - `git diff --exit-code packages/api-client/src/schema.d.ts`
5. **No matrix, no fail-fast tweaks, no Postgres/Redis services** — D-02 explicitly defers pytest+Postgres-services to backlog.
6. **`working-directory:` discipline** — backend steps run from `apps/backend/` (where `pyproject.toml` + `uv.lock` live); the diff-check returns to repo root. Frontend root commands run from repo root (pnpm workspace roots there, per `pnpm-workspace.yaml`).

---

### `packages/api-client/tsconfig.json` (NEW — config)

**Analog:** `apps/admin-web/tsconfig.app.json` (the strict-mode block) + `apps/admin-web/tsconfig.json` (path-alias shape). Both establish CLAUDE.md-locked strictness flags.

**Strict-mode pattern** (`apps/admin-web/tsconfig.app.json:11-25`):
```json
"target": "ES2022",
"lib": ["ES2023", "DOM", "DOM.Iterable"],
"module": "ESNext",
"moduleResolution": "bundler",
"verbatimModuleSyntax": true,
"strict": true,
"noUncheckedIndexedAccess": true,
"noUnusedLocals": true,
"noUnusedParameters": true,
"noFallthroughCasesInSwitch": true,
"isolatedModules": true
```
Copy this strictness block verbatim into `packages/api-client/tsconfig.json`. CLAUDE.md (admin-web) lists these as locked.

**Composite/declaration intent** (referenced in CONTEXT D-09):
> tsconfig в packages/api-client настраивает `composite: true` + `declaration: true` чтобы admin-web (через workspace import) получил публичные типы.

**Differences to introduce**:
1. **`composite: true` + `declaration: true` + `emitDeclarationOnly` consideration** — admin-web tsconfigs use `noEmit: true`. The library package must emit `.d.ts` so consumers (admin-web Phase 10) get types via workspace import. Decide between:
   - `"declaration": true, "emitDeclarationOnly": true, "outDir": "dist"` (emit `.d.ts` only — runtime is consumed via `src/*.ts` source) — simplest if admin-web uses Vite to transpile workspace deps;
   - `"declaration": true, "outDir": "dist"` (emit `.js` + `.d.ts`) — required if a non-Vite consumer ever needs prebuilt JS. Phase 9 has no such consumer, so prefer the first option.
2. **Path alias** — drop `@/*` alias. The admin-web alias is admin-web-specific; api-client is small and uses relative imports (D-09: `import type { paths } from './schema'`).
3. **`include`** — `["src"]`. Do **not** include `src/schema.d.ts` separately; `.d.ts` files inside `src/` are picked up automatically by `"include": ["src"]` and excluded from emit by TS rules.
4. **`lib`** — match admin-web (`["ES2023", "DOM", "DOM.Iterable"]`) — fetcher uses `fetch`, `document.cookie`, `RequestInit` (DOM types). Do not drop DOM.
5. **No `references`** — admin-web's root `tsconfig.json` uses project references (`{ "path": "./tsconfig.app.json" }, ...`); api-client is a single tsconfig and stays single-file.

---

### `packages/api-client/src/index.ts` (NEW — barrel re-export)

**Analog:** `apps/admin-web/src/shared/api/services/index.ts` — the only other barrel in the project that re-exports a public API surface with a top-doc rationale block.

**Barrel-with-narrative pattern** (`apps/admin-web/src/shared/api/services/index.ts:1-21`):
```typescript
/**
 * Swap seam.
 *
 * The one place in the codebase that branches on `VITE_API_MODE`. UI, features,
 * hooks, and routes import from here and never from `./mock` or `./http`.
 ...
 * Real-API migration = implement `./http/*`, flip default `VITE_API_MODE=http`.
 */
import { API_MODE } from '../config/env'
import { services as mockServices } from './mock'
import { services as httpServices } from './http'

export const services = API_MODE === 'http' ? httpServices : mockServices

export { API_MODE }
```
Mirror the **top-doc style** (English block comment, explains role + downstream consumer + what NOT to change), and the **flat `export { ... }` list** at the bottom.

**Phase 9 surface** (D-10):
```typescript
/**
 * @sportzal/api-client — typed transport for the Sportzal backend.
 *
 * Public surface (Phase 9 D-10):
 *  - `request<P, M>(method, path, init?)` — single typed entry point.
 *  - `ApiError` — error class mirroring backend AppError envelope.
 *  - `paths`, `components` — generated openapi-typescript types.
 *
 * Convenience wrappers (`get`/`post`/...) are deferred — see Phase 9 D-10 backlog.
 */
export { request } from './fetcher'
export { ApiError } from './errors'
export type { paths, components } from './schema'
```

**Differences to introduce**:
1. Use `export type` (not `export`) for `paths` / `components` so `verbatimModuleSyntax` is honored (admin-web tsconfig flag is locked; api-client tsconfig will inherit it).
2. Re-export `request` and `ApiError` as values (no `type` prefix) — they are runtime exports.
3. **No default export** — admin-web convention is named-only (CLAUDE.md "Component Patterns" / "Imports").

---

### `packages/api-client/src/fetcher.ts` (NEW — transport, request-response with single-flight)

**Role:** ~80 LOC hand-rolled `fetch` wrapper with single-flight `/auth/refresh` and typed errors. No in-repo TS analog (this is the first transport file). Server-side mirrors guide the contract.

**Analog (server mirror — header/exempt-path policy):** `apps/backend/app/core/dependencies.py:_SAFE_METHODS` + `verify_csrf` (lines 167-212).

**Server safe-method exempt set** (`apps/backend/app/core/dependencies.py:167`):
```python
_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
```
Fetcher D-11 mirror: `const MUTATING = method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS'` (drop TRACE — browsers do not issue it). Inject `X-CSRF-Token` only when mutating.

**Server cookie/header names** (`apps/backend/app/core/dependencies.py:194-195`):
```python
cookie_val = request.cookies.get("sportzal_csrf")
header_val = request.headers.get("x-csrf-token")
```
Fetcher reads `document.cookie` for `sportzal_csrf=<value>` and sets header `X-CSRF-Token`. **The names are load-bearing — must be byte-equal to the server constants** above. (D-11.)

**Refresh-skip path list** (CONTEXT D-A3 — sourced from Phase 6 D-09 + Phase 7 telegram endpoints):
- `/auth/login`, `/auth/refresh`, `/auth/me`, `/auth/logout`, `/auth/logout-all`
- `/auth/telegram/start`, `/auth/telegram/status`, `/auth/telegram/verify`

Encode as a constant set; check via `path.startsWith('/api/v1/auth/')` after stripping query. Server-side exempt list lives in Phase 6 router config (not core); D-A3 documents the exact list — planner should grep the auth router for the canonical list before locking.

**Server error envelope** (`apps/backend/app/core/exceptions.py:105-114`):
```python
@app.exception_handler(AppError)
async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "fields": exc.fields,
        },
    )
```
Fetcher D-12 parses this exact shape on non-2xx — see `errors.ts` analog below for the mirror.

**Single-flight skeleton** (no in-repo analog — D-A4 spells it out):
```typescript
let inFlightRefresh: Promise<Response> | null = null

async function refreshOnce(): Promise<Response> {
  if (inFlightRefresh) return inFlightRefresh
  inFlightRefresh = fetch('/api/v1/auth/refresh', {
    method: 'POST',
    credentials: 'include',
  }).finally(() => {
    inFlightRefresh = null
  })
  return inFlightRefresh
}
```
Module-scoped `let` — D-A4 explicitly forbids any framework primitive (no Subject/EventEmitter, no React state).

**Differences to introduce** (this file invents most of its own structure — list every load-bearing rule):
1. **`credentials: 'include'` on every call** — cookies are httpOnly per AUTH-04; without `include`, the browser will not send `sz_access`/`sz_refresh`.
2. **Generic signature** (D-10): `request<P extends keyof paths, M extends keyof paths[P]>(method: M, path: P, init?: RequestInit & {body?: unknown; params?: ...}): Promise<...>`. `paths` is the openapi-typescript-emitted type. The return type is `paths[P][M]['responses'][200]['content']['application/json']` (the success branch); plan should consult openapi-typescript v7 type helpers to write this cleanly.
3. **Body serialization** — JSON only (mirror server `ContractModel` camelCase wire); fetcher does `JSON.stringify(body)` and sets `Content-Type: application/json` on mutating methods.
4. **401 handling tree** (the longest rule, D-A1..D-A4):
   - 401 on a `/auth/*` exempt path → parse body → `throw new ApiError(server.code, server.message, server.fields)` (pass-through).
   - 401 on any other path → `await refreshOnce()`. If the refresh response is 2xx → retry the original request **once**. If retry yields another 401 → `throw new ApiError('session_expired', ...)` (no second refresh; "max 1 refresh per failed call").
   - If `refreshOnce()` rejects or returns non-2xx → `throw new ApiError('session_expired', 'Session expired, please log in again.')`.
5. **No router/window imports** — D-A2 framework-agnostic. The fetcher must be jsdom-testable with no router mock.
6. **`session_expired` is synthetic** — no server endpoint emits this code. Document this in a comment so future hands do not look for it server-side.
7. **CSRF header from `document.cookie` parse**, lowercase-trim:
   ```typescript
   const csrf = document.cookie
     .split(';')
     .map(c => c.trim())
     .find(c => c.startsWith('sportzal_csrf='))
     ?.slice('sportzal_csrf='.length)
   ```
   D-11: missing-cookie path → still send the request without header → server returns 403 `csrf_mismatch` → fetcher maps via standard error path. Do not throw client-side.

---

### `packages/api-client/src/errors.ts` (NEW — error class)

**Analog (cross-language mirror):** `apps/backend/app/core/exceptions.py:AppError`.

**Server class shape** (`apps/backend/app/core/exceptions.py:7-16`):
```python
class AppError(Exception):
    """Base domain error. Subclasses set class-level `code` and `status_code`."""

    code: str = "app_error"
    status_code: int = 500

    def __init__(self, message: str = "", *, fields: dict[str, object] | None = None) -> None:
        self.message = message
        self.fields = fields
        super().__init__(message)
```

**Phase 9 TS mirror** (D-12 verbatim):
```typescript
export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly fields?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}
```

**Differences to introduce**:
1. **Single class, no subclass tree.** Server has many subclasses (`NotFoundError`, `ForbiddenError`, `CsrfMismatch`, ...) — TS keeps a flat shape and discriminates on `error.code`. Phase 10 hooks (`onError` handler, router error boundary) match on the string code. This is intentional: subclassing in TS would force consumers to import `CsrfMismatch`/etc., which inflates the public surface and forces every error path to exhaustively switch.
2. **`name = 'ApiError'`** — required so `instanceof ApiError` works after class extension across realms (jsdom edge case).
3. **`fields?: Record<string, unknown>`** — match the server's `dict[str, object] | None`. Use `unknown`, not `any`, per `apps/admin-web` strict TS conventions.
4. **No status_code field** — the server stamps `status_code` for HTTP routing; on the client, the HTTP status has already been consumed by `fetch`. If a consumer needs the status, the planner should add `httpStatus?: number` later (backlog).
5. **No constructor overload `(payload: ProblemDetails)`** — keep the constructor positional and predictable. The fetcher does the `body.code ?? 'unknown_error'` defaulting before calling `new ApiError(...)` (D-12).

---

### `packages/api-client/src/schema.d.ts` (NEW — generated, committed)

**Analog (committed-generated TS precedent):** `apps/admin-web/src/routeTree.gen.ts` — generated by `@tanstack/router-plugin`, listed in `apps/admin-web/.gitignore` line 25.

That precedent points the *opposite* way (gitignored) — and that mismatch is exactly what D-07 calls out. Phase 9 deliberately departs:

**Differences to introduce** (the controversial deviation — call out explicitly in the plan):
1. **Committed**, not gitignored. Reason: API-07 drift-gate (`git diff --exit-code packages/api-client/src/schema.d.ts`) only works on tracked files. Untracked files are silent in `git diff`.
2. **Do NOT add this file to `packages/api-client/.gitignore`** (CONTEXT line 120 explicitly notes this). If a `.gitignore` is added later, exclude `schema.d.ts` from the patterns.
3. **Header banner** — generated files in this codebase do not yet have a "DO NOT EDIT" header convention (`routeTree.gen.ts` has one inserted by the plugin). `openapi-typescript` v7 emits its own header automatically; verify it does and rely on it. If absent, add a single-line `// AUTO-GENERATED — do not edit; run \`pnpm --filter @sportzal/api-client codegen\`` at the top via a postprocess step (last resort).
4. **REQUIREMENTS.md API-05 conflicts** ("gitignored locally"). The plan must call this out and either (a) update API-05 to "committed", or (b) reframe API-07. CONTEXT D-07 marks this as "Recommended: коммитим" — planner files an explicit deviation note.
5. **No type narrowing edits** — never hand-edit. Every change goes through regen.

---

### `apps/backend/openapi.json` (NEW — generated spec, committed)

**Analog:** none (first JSON spec in the repo). Closest precedent: `apps/admin-web/src/routeTree.gen.ts` (committed-or-gitignored TS generated artifact — see schema.d.ts entry).

**Differences to introduce**:
1. **Committed** — Phase 9 commits the first export-script output as part of the phase-completion commit. Subsequent PRs that touch FastAPI schemas regenerate it; CI fails if a PR forgets.
2. **Byte stability** — `indent=2, sort_keys=True, ensure_ascii=False, trailing newline`. D-06.
3. **Location** — `apps/backend/openapi.json` (sibling to `pyproject.toml`, NOT inside `app/`). The `git diff` in CI references this path.
4. **Not in `apps/backend/.gitignore`** — verify the current `.gitignore` does not glob-match `*.json`. (Inspected: it does not — current entries are dotfile/cache/env-only.)

---

### `packages/api-client/package.json` (MODIFY — placeholder → real)

**Analog (current placeholder — the file we are growing):** `packages/api-client/package.json` itself.

**Current placeholder** (`packages/api-client/package.json:1-11`):
```json
{
  "name": "@sportzal/api-client",
  "private": true,
  "version": "0.0.0",
  "description": "Phase 1 placeholder for the generated API client. Real implementation lands in a later phase.",
  "engines": {
    "node": ">=20.0.0",
    "pnpm": ">=9.0.0"
  }
}
```

**Sibling for scripts/devDeps shape** (`apps/admin-web/package.json:11-21`):
```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "test": "vitest run",
  "typecheck": "tsc -b --noEmit"
}
```

**Phase 9 expansion**:
```json
{
  "name": "@sportzal/api-client",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "exports": {
    ".": {
      "types": "./src/index.ts",
      "default": "./src/index.ts"
    }
  },
  "scripts": {
    "codegen": "openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts",
    "typecheck": "tsc --noEmit"
  },
  "devDependencies": {
    "openapi-typescript": "^7.13.0",
    "typescript": "~5.7.2"
  },
  "engines": {
    "node": ">=20.0.0",
    "pnpm": ">=9.0.0"
  }
}
```

**Differences to introduce**:
1. **`"type": "module"`** — admin-web uses `"type": "module"` (line 5). Phase 1 placeholder did not. Add it.
2. **`"main"` + `"types"` + `"exports"`** — the placeholder has none; consumers (admin-web Phase 10) rely on these to locate the public surface. Pointing both at `./src/index.ts` (instead of a built `dist/`) is fine because Vite (the consumer) transpiles workspace deps natively.
3. **Pin `typescript: ~5.7.2`** — exact match to admin-web's pin (line 73). Repo-wide TS version uniformity is a CLAUDE.md lock.
4. **`openapi-typescript@^7.13.0`** — exact version per CONTEXT line 18 + REQUIREMENTS API-05.
5. **Scripts:**
   - `codegen` — relative path `../../apps/backend/openapi.json` (this works because pnpm runs scripts with cwd=`packages/api-client/`, and `openapi-typescript` is invoked through pnpm's dep resolution from the workspace root — verify with `pnpm --filter @sportzal/api-client codegen` in the dev-loop step of the plan).
   - `typecheck` — `tsc --noEmit` (consistent with admin-web's `tsc -b --noEmit` simplification, since this package has a single tsconfig and no project references).
6. **No `lint` / `test` scripts** — Phase 9 does not add ESLint or Vitest to api-client. Frontend job will run `pnpm -r lint`/`-r test` which silently skip workspaces that lack the script. Backlog if Phase 10 ever needs unit tests on the fetcher.
7. **NO runtime dependencies** — fetcher uses only browser globals (`fetch`, `document`). `openapi-typescript` is **dev**, not runtime.
8. **`"description"` updated** — drop the "Phase 1 placeholder" line — replace with a one-liner describing the real role. Sibling `packages/ui/package.json` keeps its placeholder description; do not modify it.

---

### `apps/admin-web/package.json` (MODIFY — add predev + workspace dep)

**Analog (the file itself):** see lines 11-46 of the current file.

**Modifications (D-08 + CONTEXT line 123):**
1. **Add `predev` hook** to the `scripts` block:
   ```json
   "predev": "pnpm --filter @sportzal/api-client codegen"
   ```
   Place between `dev` and `build` for clarity. pnpm runs `predev` automatically before `dev`.
2. **Add workspace dependency** to `dependencies`:
   ```json
   "@sportzal/api-client": "workspace:*"
   ```
   Add even though Phase 9 does not import it — Phase 10 will. Adding now lets the codegen script be invoked successfully (the filter requires the package to be resolvable, which it already is via `pnpm-workspace.yaml`; the dep entry is for type-resolution in admin-web TS).

**Differences to introduce**:
1. **No `postinstall` hook** — D-08 explicitly forbids it (slow installs, surprise CI side-effects).
2. **No `prebuild` hook** — admin-web's `build` step does not need fresh OpenAPI types in CI; CI regenerates and diffs separately.
3. **`workspace:*` (not `workspace:^0.0.0`)** — pnpm-monorepo idiom; mirrors how api-client would be added if it had a real version.

---

### `packages/api-client/README.md` (MODIFY — placeholder → real)

**Analog (current placeholder):** `packages/api-client/README.md:1-5`:
```markdown
# @sportzal/api-client

Phase 1 placeholder — no code yet. Real implementation lands in a later phase (after the backend exposes endpoints; see roadmap and v2 requirement FE-02).

This package exists so the pnpm workspace at the repo root can resolve `packages/*`. Do not add code here in Phase 1 (locked decision D-10 in `.planning/phases/01-monorepo-restructure-frontend-move/01-CONTEXT.md`).
```

**Sibling style anchor** (`apps/backend/README.md` — read for header/section style; English; concise; example commands).

**Phase 9 expansion outline** (Russian narrative for usage + English code per CLAUDE.md "Russian-narrative + English-code" Phase 3 D-05):
1. Title + 1-line role description (English code reference, Russian explanation).
2. Public surface example:
   ```typescript
   import { request, ApiError, type paths } from '@sportzal/api-client'
   ```
3. Codegen workflow — when and how to run `pnpm --filter @sportzal/api-client codegen`; mention the `predev` hook (transparent for `pnpm dev`).
4. Drift-gate note — "Не редактируй `src/schema.d.ts` руками; CI откатит изменения через `git diff --exit-code`."
5. Single-flight refresh + ApiError contract — 4-5 sentences pointing to D-A1..D-A4.

**Differences to introduce**:
1. Drop the "Phase 1 placeholder" framing entirely.
2. Do **not** add a usage example for convenience wrappers (`get`, `post`) — they do not exist (D-10).
3. Do **not** document `session_expired` as a server code; mark it explicitly as client-synthetic.

---

### `apps/backend/app/main.py` (POSSIBLY MODIFY — D-06 byte-stability)

**Analog (the file itself):** `apps/backend/app/main.py:67-72`:
```python
app = FastAPI(
    title="Sportzal API",
    lifespan=combined_lifespan,
    docs_url="/docs" if settings.environment == "dev" else None,
    redoc_url=None,
)
```

**Differences to introduce** (only if needed — planner verifies first):
1. **Add explicit `version="1.1.0"` (or current milestone string)** if missing. FastAPI defaults to `"0.1.0"`, which is stable but uninformative. D-06 says: "FastAPI app.openapi() детерминирован по app.title, app.version, app.servers — все они задаются в create_app() и не зависят от platform." Pinning version explicitly removes the implicit FastAPI default and makes the OpenAPI spec self-documenting.
2. **Do NOT add `servers=[...]`** — D-06 marks customization as v1.2+ deferred.
3. **No other change to `main.py`** — composition order (configure_logging → assertion → FastAPI() → middleware → handlers → loader → router) is locked by Phase 5 D-08; any reorder would break startup contracts.

---

### `apps/backend/pyproject.toml` (POSSIBLY MODIFY — D-04 environment script support)

**Analog (the file itself):** `apps/backend/pyproject.toml:1-32`.

**Likely outcome:** **no change required**. Export script uses only stdlib (`os`, `sys`, `pathlib`, `json`) + already-installed `fastapi` (line 13). Verify with the planner; if everything resolves, leave the file alone.

**Differences to introduce** (only if a verification step finds a missing dep):
- Nothing currently anticipated. CONTEXT line 125 says "*возможно* добавить ... вероятно, ничего нового" — set the planner's expectation accordingly.

---

## Shared Patterns

### Server↔Client error envelope mirror
**Source:** `apps/backend/app/core/exceptions.py:7-16` + `:102-114` (server) → `packages/api-client/src/errors.ts` (client mirror).
**Apply to:** `errors.ts`, `fetcher.ts` parsing branch.
**Excerpt** (server JSONResponse body shape):
```python
content={
    "code": exc.code,
    "message": exc.message,
    "fields": exc.fields,
},
```
Fetcher parsing must accept exactly these three keys; missing-key defaults: `code → 'unknown_error'`, `message → ''`, `fields → undefined`. Do not invent additional keys client-side.

### CSRF cookie/header naming (server↔client)
**Source (server):** `apps/backend/app/core/dependencies.py:194-195`.
**Apply to:** `fetcher.ts` (must read cookie `sportzal_csrf` and send header `X-CSRF-Token`; case-insensitive header name OK on outbound — server uses `headers.get("x-csrf-token")` which lowercases).
**Excerpt:**
```python
cookie_val = request.cookies.get("sportzal_csrf")
header_val = request.headers.get("x-csrf-token")
```

### Safe-method exempt set (server↔client)
**Source (server):** `apps/backend/app/core/dependencies.py:167`.
**Apply to:** `fetcher.ts` mutating-method gate (drop TRACE — not browser-issued).
**Excerpt:**
```python
_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
```

### Generated artifacts in this codebase
**Source:** `apps/admin-web/src/routeTree.gen.ts` + `.gitignore` line 25 (gitignored precedent).
**Apply to:** `schema.d.ts` (deliberately deviates — committed) and `openapi.json` (committed by construction).
**Differential rationale:** drift-gate CI step requires tracked files. `routeTree.gen.ts` is gitignored because there is no parallel server source-of-truth to drift against; OpenAPI artifacts have a server source-of-truth (FastAPI app) and need explicit drift detection.

### Script idiom (Python CLIs in `apps/backend/scripts/`)
**Source:** `apps/backend/scripts/seed_demo_data.py`.
**Apply to:** `apps/backend/scripts/export_openapi.py` (new sibling).
**Pattern:**
- Top-doc with phase tag + `uv run python -m scripts.<name>` invocation example.
- `from __future__ import annotations`.
- Stdlib imports first; `app.*` imports after env-prep (D-04 specific to export script).
- `def main() -> int` returning exit code; `if __name__ == "__main__": raise SystemExit(main())`.
- Errors via `print(..., file=sys.stderr); return 1`.

### TS strict-mode locks
**Source:** `apps/admin-web/tsconfig.app.json:11-25` (CLAUDE.md "TypeScript" section enumerates these as locked).
**Apply to:** `packages/api-client/tsconfig.json`.
**Excerpt:**
```json
"strict": true,
"noUncheckedIndexedAccess": true,
"noUnusedLocals": true,
"noUnusedParameters": true,
"verbatimModuleSyntax": true,
"isolatedModules": true,
"target": "ES2022"
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.github/workflows/ci.yml` | workflow | event-driven | Project has zero pre-existing GitHub Actions; `.github/` directory does not exist. Style anchors come from external GH Actions docs (consulted in CONTEXT canonical_refs lines 130-131) plus internal pnpm/uv invocation strings from `apps/admin-web/package.json` and `apps/backend/Dockerfile`. Planner should treat the workflow as greenfield with the script-step list locked by D-02 above. |

---

## Metadata

**Analog search scope:**
- `apps/backend/scripts/` (2 files — `seed_demo_data.py`, `backup_db.sh`)
- `apps/backend/app/main.py`, `app/core/{config,dependencies,exceptions,schemas}.py`
- `apps/backend/{pyproject.toml, ruff.toml, .importlinter, Dockerfile, docker-compose.yml, .gitignore}`
- `apps/admin-web/{package.json, tsconfig*.json, eslint.config.js, vitest.config.ts, .gitignore}`
- `apps/admin-web/src/shared/api/{config/env.ts, services/index.ts, services/{mock,http}/index.ts, contracts/index.ts}`
- `apps/admin-web/scripts/assert-eslint-fixtures.mjs`
- `packages/{api-client,ui}/{package.json, README.md}`
- `pnpm-workspace.yaml`
- `.github/` (verified absent)
- `.planning/REQUIREMENTS.md` (REQ-IDs API-01, API-02, API-05, API-06, API-07)
- `.planning/ROADMAP.md` (Phase 9 success criteria)

**Files scanned:** ~32 source/config files.

**Pattern extraction date:** 2026-05-03.
