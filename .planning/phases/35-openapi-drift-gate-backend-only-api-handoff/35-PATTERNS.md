# Phase 35: OpenAPI Drift Gate (backend-only API handoff) — Pattern Map

**Mapped:** 2026-05-16
**Files analyzed:** 4 (2 regenerated artifacts + 1 extended test + 1 appended doc)
**Analogs found:** 4 / 4

## Phase shape recap

Phase 35 is a **backend-only API contract handoff**: zero source-code authoring, zero admin-web edits. The phase produces a single atomic regen of the OpenAPI artifact + its TypeScript codegen output, extends the existing forward-guard with v1.4 path/method assertions, and appends a changelog section to the api-client README so an external design team can consume the contract independently.

Two precedent iterations (v1.2 Phase 21, v1.3 Phase 28) established the exact mechanics. Phase 35 is a direct replay minus the admin-web wiring plans (descoped to v2.0 per 2026-05-15 pivot).

## File Classification

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `apps/backend/openapi.json` | generated artifact (JSON spec) | byte-stable export | itself — prior regen via `apps/backend/scripts/export_openapi.py` (v1.3 Phase 28) | exact (same tool, same script) |
| `packages/api-client/src/schema.d.ts` | generated artifact (TS types) | codegen | itself — prior regen via `pnpm --filter @sportzal/api-client codegen` (v1.3 Phase 28) | exact (same tool, same script) |
| `packages/api-client/src/schema.contract.test.ts` | extended forward-guard test | compile-time type assertion | the file's own existing v1.2 surface block (lines 23–45) — Phase 21 D-21-4 pattern | exact (template lives in the file itself) |
| `packages/api-client/README.md` | appended doc | static markdown | existing `## Codegen` / `## CSRF` / `## Single-flight refresh` sections (same file) | exact (style template lives in the file itself) |

**Frozen / do-not-modify (planner must reject any plan touching these):**
- `apps/backend/scripts/export_openapi.py` — canonical exporter (CONTEXT § canonical_refs).
- `apps/backend/app/modules/**` — Phases 31–34 landed code. Any drift surfaced by regen = backend bug, not Phase 35 task (D-35-19).
- `apps/admin-web/src/**` — entire tree frozen-as-of-v1.3 (D-35-14).
- `apps/backend/app/api/v1/router.py` — read-only source-of-truth for path enumeration (lines 35–53).
- `packages/api-client/package.json` — `openapi-typescript: "^7.13.0"` pin must NOT be bumped (CONTEXT § canonical_refs).

## Pattern Assignments

### `apps/backend/openapi.json` (generated artifact, byte-stable export)

**Analog:** itself (re-run of `apps/backend/scripts/export_openapi.py`).

**Generation pattern** (must be invoked verbatim — `apps/backend/scripts/export_openapi.py:1-19,49-67`):

```python
"""Export the FastAPI OpenAPI spec (API-01 / Phase 9 D-04..D-06).

Lifespan-safe: calls `create_app().openapi()` directly. FastAPI's
`combined_lifespan` (db_lifespan + redis_lifespan) is NEVER entered, so
Postgres and Redis are not touched. The script can run in any environment
that has the Python deps installed.

Run from `apps/backend/`:

    uv run python -m scripts.export_openapi

Writes `apps/backend/openapi.json` (resolved relative to this file, so the
script is cwd-independent). Output is byte-stable: `indent=2, sort_keys=True,
ensure_ascii=False, trailing newline` — identical bytes on macOS and Linux.
"""

def main() -> int:
    # D-05: `.openapi()` is a sync property; lifespan never runs.
    spec = create_app().openapi()
    if "paths" not in spec:
        print("openapi() returned no 'paths' — FastAPI surface broken.", file=sys.stderr)
        return 1

    # D-06: byte-stable across macOS↔Linux.
    payload = json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    target = pathlib.Path(__file__).resolve().parents[1] / "openapi.json"
    target.write_text(payload, encoding="utf-8")
    print(f"Wrote {target} ({len(payload)} bytes).")
    return 0
```

**Plan instructions for the executor:**
1. `cd apps/backend && uv run python -m scripts.export_openapi`
2. Do NOT edit `openapi.json` by hand under any circumstance (D-35-02). If the diff looks wrong, fix the router/schema source in `apps/backend/app/modules/**` — though for Phase 35 such a fix would surface a Phase 31–34 bug that should escalate, not be silently patched in Phase 35 (D-35-19).
3. After regen, sanity-check the new `paths` block of the JSON contains every prefix from `apps/backend/app/api/v1/router.py:35-53` (auth, clients, membership-plans, memberships, payments, pt-package-plans, pt-packages, pt-sessions, trainers, visits).

**Current size for context:** 3,571 lines pre-Phase-35 (will grow with v1.4 paths).

---

### `packages/api-client/src/schema.d.ts` (generated artifact, codegen)

**Analog:** itself (re-run of `pnpm --filter @sportzal/api-client codegen`).

**Generation pattern** (`packages/api-client/package.json:16`):

```json
"scripts": {
  "codegen": "openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts",
  "typecheck": "tsc --noEmit",
  "test": "vitest run"
}
```

**Output style (do NOT edit by hand — file header tells future readers exactly this):**

```typescript
/**
 * This file was auto-generated by openapi-typescript.
 * Do not make direct changes to the file.
 */

export interface paths {
    "/api/v1/auth/login": {
        parameters: { query?: never; header?: never; path?: never; cookie?: never };
        get?: never;
        put?: never;
        /**
         * Login
         * @description Authenticate email+password; issue cookies + envelope ...
         */
        post: operations["login_api_v1_auth_login_post"];
        delete?: never;
        ...
    };
    ...
}
```

**Plan instructions for the executor:**
1. Run `pnpm --filter @sportzal/api-client codegen` *after* the openapi.json regen lands locally (D-35-01 atomicity — both deltas in ONE commit).
2. Do NOT bump `openapi-typescript` version in `devDependencies` (currently `^7.13.0`); a tool bump would produce a non-content-meaningful diff and break the drift-gate semantics (D-35-03).
3. Do NOT touch the auto-generated header comment — it documents the contract.

**Current size for context:** 2,291 lines pre-Phase-35.

---

### `packages/api-client/src/schema.contract.test.ts` (extended forward-guard)

**Analog:** the file itself — its existing v1.2 surface block IS the template for new v1.4 assertions. Mode: **APPEND ONLY** — do not reshape helpers, do not move existing blocks, do not change the trailing `describe(...)` block (D-35-08, CONTEXT § canonical_refs).

**Existing helper scaffold to keep verbatim** (lines 9–21):

```typescript
import { describe, it, expect } from 'vitest'
import type { paths } from './schema'

// --- helpers -----------------------------------------------------------

/** Returns false if T resolves to never; true otherwise. */
type AssertNonNever<T> = [T] extends [never] ? false : true

/**
 * Phase 21 D-21-2: sessions paths land in Phase 23. The conditional probe
 * stays green whether or not Phase 23 has merged.
 */
type HasPath<P extends string> = P extends keyof paths ? true : false
```

**Existing v1.2 surface block — the EXACT pattern to copy for v1.4** (lines 23–45):

```typescript
// --- v1.2 surface (must always be present after Phase 21) --------------

type _PlansListGet = AssertNonNever<paths['/api/v1/membership-plans']['get']>
type _PlansListPost = AssertNonNever<paths['/api/v1/membership-plans']['post']>
type _PlansItemGet = AssertNonNever<paths['/api/v1/membership-plans/{plan_id}']['get']>
type _MembershipsListPost = AssertNonNever<paths['/api/v1/memberships']['post']>
type _MembershipsCancel = AssertNonNever<
  paths['/api/v1/memberships/{membership_id}/cancel']['post']
>
type _VisitsListGet = AssertNonNever<paths['/api/v1/visits']['get']>
type _VisitsListPost = AssertNonNever<paths['/api/v1/visits']['post']>

// requestBody guard — openapi-typescript v7 types absent bodies as `never`,
// so a non-empty POST body must NOT collapse to never.
type _MembershipsPostBody = paths['/api/v1/memberships']['post']['requestBody']
type _BodyIsRealised = AssertNonNever<_MembershipsPostBody>

// 200 response reachability for visits list.
type _VisitsListOk = paths['/api/v1/visits']['get']['responses']['200']
type _VisitsListOkRealised = AssertNonNever<_VisitsListOk>

// Phase 22 D-22-1: gym hours metadata endpoint (Wave 1 — downstream FE plans depend on this).
type _VisitsMetaGet = AssertNonNever<paths['/api/v1/visits/_meta']['get']>
```

**Existing static-checks tuple** (lines 47–59) — planner MUST extend this tuple (or add a sibling tuple) for every new v1.4 assertion, otherwise `noUnusedLocals` will flag the new types:

```typescript
const _checks: [
  _PlansListGet,
  _PlansListPost,
  _PlansItemGet,
  _MembershipsListPost,
  _MembershipsCancel,
  _VisitsListGet,
  _VisitsListPost,
  _BodyIsRealised,
  _VisitsListOkRealised,
  _VisitsMetaGet,
] = [true, true, true, true, true, true, true, true, true, true]
```

**Existing Phase 23 positive block** (lines 70–78) — closest in shape to the v1.4 block planner will author:

```typescript
// --- Phase 23 CD-05: sessions positive assertions (Phase 23 merged) ----
// Both /sessions GET and /sessions/{family_id}/revoke POST must be present.
// These assertions fail the TypeScript build if codegen does not emit the paths.
type _GetSessions = AssertNonNever<paths['/api/v1/auth/sessions']['get']>
type _PostRevokeSession = AssertNonNever<
  paths['/api/v1/auth/sessions/{family_id}/revoke']['post']
>
const _sessionsGetCheck: _GetSessions = true
const _sessionsRevokeCheck: _PostRevokeSession = true
```

**Existing trailing vitest shell** (lines 80–90) — keep, extend the `expect(_checks).toHaveLength(N)` assertion to match the new tuple length:

```typescript
describe('schema.contract', () => {
  it('compiles against the regenerated v1.2 typed paths surface', () => {
    expect(_checks).toHaveLength(10)
    expect(_sessionsCheck).toBe(true)
    expect(_sessionsGetCheck).toBe(true)
    expect(_sessionsRevokeCheck).toBe(true)
  })
})
```

**Pattern for the new v1.4 surface block (planner authors this — module-grouped per CONTEXT § Claude's Discretion):**

```typescript
// --- v1.4 surface (Phases 31-34, backend-only handoff) -----------------
// operationIds intentionally NOT pinned — see 35-CONTEXT D-35-07. The
// forward-guard checks paths + methods + body realisation + 2xx
// reachability; operation-id naming is a v1.5 hygiene topic.

// --- v1.4 trainers (Phase 31) ---
type _TrainersListGet = AssertNonNever<paths['/api/v1/trainers']['get']>
type _TrainersCreate = AssertNonNever<paths['/api/v1/trainers']['post']>
type _TrainersItemGet = AssertNonNever<paths['/api/v1/trainers/{trainer_id}']['get']>
type _TrainersPatch = AssertNonNever<paths['/api/v1/trainers/{trainer_id}']['patch']>
type _TrainersDelete = AssertNonNever<paths['/api/v1/trainers/{trainer_id}']['delete']>
type _TrainersCreateBody = AssertNonNever<paths['/api/v1/trainers']['post']['requestBody']>

// --- v1.4 payments (Phase 32) ---
type _PaymentsListGet = AssertNonNever<paths['/api/v1/payments']['get']>
// ... per-module + per-method + at least one body + one 2xx response check
```

Method-level granularity per D-35-06; body-realisation guard for every POST taking a non-empty body per D-35-08; one 2xx-reachability guard per module per D-35-09. Path enumeration must be RE-DERIVED from the regenerated `openapi.json` (D-35-05) — the v1.4 path list in CONTEXT § decisions is for reference only.

**No `HasPath<...>` conditional probes for v1.4** — all v1.4 endpoints are landed in Phases 31–34, so every assertion is a hard `AssertNonNever` (CONTEXT § Established Patterns, "Conditional probes" entry).

---

### `packages/api-client/README.md` (appended doc)

**Analog:** the file itself — existing section style (H2 headers + bullet lists + Russian/English mix). Mode: **APPEND ONLY** — insert new sections between existing § "Codegen" (ends line 43) and existing § "Single-flight refresh" (starts line 45). Do NOT edit existing sections (D-35-12).

**Existing style template — § "Codegen" section** (lines 33–43, the format to mirror):

```markdown
## Codegen

`src/schema.d.ts` генерируется из `apps/backend/openapi.json`:

```bash
pnpm --filter @sportzal/api-client codegen
```

Локально перед `pnpm dev` в `apps/admin-web` это выполняется автоматически через `predev` hook (см. `apps/admin-web/package.json`). Не редактируй `src/schema.d.ts` руками — CI откатит изменения через `git diff --exit-code` (Phase 9 API-07).

`src/schema.d.ts` **закоммичен в git** (Phase 9 D-07) — отступление от REQUIREMENTS API-05 wording 'gitignored locally'. Без коммита drift-gate бессмыслен.
```

**Existing § "CSRF" section** (lines 51–53) — auth-quickstart pointer references this:

```markdown
## CSRF

На mutating методы (POST / PATCH / PUT / DELETE) fetcher читает cookie `sportzal_csrf` (выставляется backend'ом на `/auth/login` и `/auth/refresh`) и отправляет header `X-CSRF-Token`. На GET / HEAD / OPTIONS header не добавляется — соответствует server-side `_SAFE_METHODS` short-circuit (Phase 6 D-04).
```

**Existing § "Single-flight refresh" section** (lines 45–49) — auth-quickstart pointer references this:

```markdown
## Single-flight refresh

Fetcher держит module-scoped `inFlightRefresh: Promise<Response> | null`. На 401 от non-`/auth/*` путей запускается ОДИН `/api/v1/auth/refresh`; параллельные запросы ждут тот же promise. ...
```

**Pattern for the new sections (planner authors these per D-35-10, D-35-11):**

```markdown
## v1.4 changelog

Новые типизированные paths в v1.4 (Phases 31–34, backend-only handoff per 2026-05-15 pivot — production frontends разрабатываются дизайн-командой вне репо):

- **Trainers** (Phase 31): owner-only CRUD каталога тренеров, reception видит только active в PT-session picker.
- **Payments ledger** (Phase 32): append-only журнал; GET-listing (owner) + per-client / per-membership history (reception+owner).
- **Membership refund** (Phase 32): `POST /memberships/{id}/refund` — full-only, B-08/B-09 guards.
- **PT-package plans** (Phase 33): owner-only CRUD каталога; `session_count` / `price_kopecks` / `validity_days` immutable post-creation.
- **PT-packages** (Phase 33): продажа / отмена / refund инстансов; status machine `active → exhausted|expired|cancelled`.
- **PT-package refund** (Phase 33): `POST /pt-packages/{id}/refund` — симметрично membership refund.
- **PT-sessions** (Phase 34): запись / отмена тренировок; race-safe декремент `sessions_remaining`.

Полный surface — в `apps/backend/openapi.json` (source-of-truth, не дублируется здесь чтобы избежать rot).

## Auth quick-start

Внешние потребители контракта (дизайн-команда v2.0):

- **Login**: `POST /api/v1/auth/login` принимает `{email, password}`, проверяет Argon2id; ставит cookies `sportzal_session` + `sportzal_csrf` и возвращает access JWT в body.
- **Token rotation**: `POST /api/v1/auth/refresh` — refresh-rotation family; см. § "Single-flight refresh" ниже для runtime contract.
- **Mutating requests**: добавляй header `X-CSRF-Token` из cookie `sportzal_csrf`; см. § "CSRF" ниже.
- **Telegram OTP path** (client-app): `POST /api/v1/auth/telegram/start` → `GET /api/v1/auth/telegram/status` → `POST /api/v1/auth/telegram/verify`.

Sample curl examples будут опубликованы вместе с Postman collection в v1.5 API Handoff milestone.
```

**Plan instructions:**
- Insertion point: between line 43 (end of § Codegen) and line 45 (start of § Single-flight refresh).
- NO module-level READMEs touched (D-35-12) — backend module READMEs are not part of the contract handoff.
- No path/method tables — they rot (D-35-10).
- No inline curl examples — defer to v1.5 Postman collection (D-35-11).

## Shared Patterns

### Atomic single-commit regen (applies to wave-1 plan)

**Source:** v1.2 Phase 21 + v1.3 Phase 28 precedent (D-35-01).
**Apply to:** the regen plan (wave-1).
**Mechanics:**
1. `cd apps/backend && uv run python -m scripts.export_openapi` → updates `apps/backend/openapi.json`
2. `pnpm --filter @sportzal/api-client codegen` → updates `packages/api-client/src/schema.d.ts`
3. Both deltas land in ONE git commit so CI drift-gate evaluates a coherent contract.

### Local pre-commit verification sequence (applies to BOTH plans per wave)

**Source:** D-35-18 verbatim.
**Apply to:** wave-1 plan AND wave-2 plan as final-step gate.
**Command sequence (the executor MUST run all six before commit):**

```bash
cd apps/backend && uv run python -m scripts.export_openapi
pnpm --filter @sportzal/api-client codegen
pnpm --filter @sportzal/api-client typecheck
pnpm --filter @sportzal/api-client test
pnpm --filter @sportzal/admin-web typecheck && pnpm --filter @sportzal/admin-web lint && pnpm --filter @sportzal/admin-web test
# After staging both files:
git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts
```

The admin-web step is the **canary** (D-35-13): 233 vitest specs MUST continue passing unchanged. If any break, STOP — that signals a backwards-incompatible schema change in Phases 31–34 that needs a backend fix, NOT an admin-web edit (Phase 35 plans MUST NOT modify `apps/admin-web/src/**` per D-35-14).

### CI drift-gate contract (the gate Phase 35 must satisfy)

**Source:** `.github/workflows/ci.yml` lines 54–64 (backend) and 109–117 (frontend).
**Apply to:** verification section of both plans.

```yaml
- name: Drift gate — apps/backend/openapi.json
  working-directory: ${{ github.workspace }}
  run: |
    git ls-files --error-unmatch apps/backend/openapi.json
    git diff --exit-code apps/backend/openapi.json

- name: Drift gate — packages/api-client/src/schema.d.ts
  run: |
    git ls-files --error-unmatch packages/api-client/src/schema.d.ts
    git diff --exit-code packages/api-client/src/schema.d.ts
```

The `git ls-files --error-unmatch` line (WR-06 defensive guard) means the gate fails loudly if either artifact is accidentally untracked/gitignored — Phase 35 inherits this safety without any workflow edit.

### Path enumeration source-of-truth

**Source:** `apps/backend/app/api/v1/router.py:34-53` (the file mounts every v1 prefix).
**Apply to:** the forward-guard extension plan (wave-2) when enumerating which paths must be pinned.

Concrete excerpt of the router mounting (lines 34–53):

```python
v1 = APIRouter()
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
v1.include_router(clients_router, prefix="/clients", tags=["clients"])
v1.include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])
v1.include_router(memberships_router, prefix="/memberships", tags=["memberships"])
v1.include_router(payments_router, prefix="/payments", tags=["payments"])
v1.include_router(pt_package_plans_router, prefix="/pt-package-plans", tags=["pt-package-plans"])
v1.include_router(pt_packages_router, prefix="/pt-packages", tags=["pt-packages"])
v1.include_router(pt_sessions_router, prefix="/pt-sessions", tags=["pt-sessions"])
v1.include_router(pt_sessions_package_scoped_router, prefix="/pt-packages", tags=["pt-sessions"])
v1.include_router(trainers_router, prefix="/trainers", tags=["trainers"])
v1.include_router(visits_router, prefix="/visits", tags=["visits"])
```

The wave-2 planner cross-references this list against the regenerated `openapi.json` `paths` keys — any v1.4 path in CONTEXT § D-35-05 that doesn't appear after regen signals a misrouting bug, not a contract-test bug.

### Append-only doc discipline

**Source:** `packages/api-client/README.md` lines 33–53 (existing sections to leave verbatim).
**Apply to:** wave-2 plan (README append).
**Rule:** Insertion only between § Codegen and § Single-flight refresh. No edits to existing sections. No new sections elsewhere (D-35-12 — module-level READMEs are out of scope).

## No Analog Found

None. Every Phase 35 deliverable has either a direct precedent (the file itself in its prior regenerated state) or a template that lives inside the file being extended.

## Plan Topology Implication (for the planner)

Per D-35-16, two plans:

- **Wave 1: Atomic regen** — produces `openapi.json` + `schema.d.ts` in a single commit.
  - File pattern assignments: `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts`.
  - Shared patterns to apply: "Atomic single-commit regen", "Local pre-commit verification sequence", "CI drift-gate contract".

- **Wave 2: Forward-guard + README** — depends on Wave 1 (needs the regenerated artifacts for path enumeration).
  - File pattern assignments: `packages/api-client/src/schema.contract.test.ts` + `packages/api-client/README.md`.
  - Shared patterns to apply: "Local pre-commit verification sequence" (full re-run), "Path enumeration source-of-truth", "Append-only doc discipline".
  - Exit criterion: admin-web canary (233 vitest specs) passes unchanged (D-35-17 — no separate canary plan).

No third plan. No admin-web edits. No backend module edits.

## Metadata

**Analog search scope:**
- `packages/api-client/` (full directory — 5 files)
- `apps/backend/scripts/export_openapi.py`
- `apps/backend/app/api/v1/router.py`
- `apps/backend/openapi.json` (header only, sizing)
- `.github/workflows/ci.yml` (drift-gate jobs §§)

**Files scanned:** 7 source files + 1 CI workflow.
**Pattern extraction date:** 2026-05-16.
**Precedent phases referenced:** v1.2 Phase 21 (first regen), v1.3 Phase 28 (second regen — UI-heavy, dropped here).
