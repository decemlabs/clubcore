# Phase 117: OpenAPI Handoff + Milestone Gate - Pattern Map

**Mapped:** 2026-06-15
**Files analyzed:** 8 new/modified file groups
**Analogs found:** 7 / 8 (1 mechanism is new — see "No Analog Found")

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/openapi.json` | config/artifact | batch | existing `openapi.json` (regenerated in place) | exact |
| `packages/api-client/src/schema.d.ts` | config/artifact | batch | existing `schema.d.ts` (regenerated via codegen) | exact |
| `packages/api-client/src/schema.contract.test.ts` | test | type-level | same file — extend with `_v32Checks` block | exact |
| `apps/backend/scripts/export_openapi.py` | utility | batch | same file — no change needed | exact |
| `apps/backend/tests/integration/*/test_*_capture.py` (NEW per domain) | test | request-response | `tests/integration/payments/test_payments_refund.py` | role-match |
| `apps/admin-app/src/features/*/capture/*.json` (fixtures dir, NEW) | config/artifact | file-I/O | none — new mechanism | no analog |
| `apps/admin-app/src/features/*/*.contract.test.ts` (NEW per domain) | test | transform | `apps/admin-app/src/features/reports/schemas.test.ts` | role-match |
| `apps/admin-app/src/features/promoCodes/api.ts` (MODIFY — drop casts) | service | request-response | `apps/admin-app/src/features/payments/api.ts` | role-match |

---

## Pattern Assignments

### `packages/api-client/src/schema.contract.test.ts` — extend with `_v32Checks`

**Analog:** same file, lines 354–387 (`_v18Checks` block) and lines 107–113 (`_MembershipRefundBody` pattern)

**Established block structure** (lines 354–387 — v1.8 CSV-endpoint anchor style):
```typescript
// --- v1.8 surface — Reports + Audit Log read API (Phases 54-57) ---------
type _ReportsRevenueGet = AssertNonNever<paths['/api/v1/reports/revenue']['get']>
type _ReportsRevenueCsvGet = AssertNonNever<
  paths['/api/v1/reports/revenue.csv']['get']['responses']['200']
>
// ...
const _v18Checks: [
  _ReportsRevenueGet,
  _ReportsRevenueCsvGet,
  // ...
] = [true, true, ...]

// ... inside describe():
it('compiles against the regenerated v1.8 reports/audit surface (Phases 55-57)', () => {
  expect(_v18Checks).toHaveLength(8)
})
```

**Body realisation probe style** (lines 107–113 — `_MembershipRefundBody`):
```typescript
// --- v1.4 membership refund (Phase 32) ---
type _MembershipRefundPost = AssertNonNever<
  paths['/api/v1/memberships/{membership_id}/refund']['post']
>
type _MembershipRefundBody = AssertNonNever<
  paths['/api/v1/memberships/{membership_id}/refund']['post']['requestBody']
>
```

**Tuple constant + describe `it` style** (lines 272–285, 717–779 — how every version block closes):
```typescript
const _v15Checks: [
  _TrainerSlotsListGet,
  // ... one entry per type alias
] = [true, true, ...]

// inside describe('schema.contract'):
it('compiles against the regenerated v1.5 typed paths surface (Phase 40 HANDOFF-02)', () => {
  expect(_v15Checks).toHaveLength(11)
})
```

**New `_v32Checks` block must cover (one type alias each):**
- `POST /api/v1/payments/{payment_id}/refund` — operation + requestBody (already in schema.d.ts at line 2531; confirm after regen)
- `PATCH /api/v1/users/{user_id}/role` — operation + requestBody (already in schema.d.ts at line 3892)
- `GET /api/v1/promo-codes` — operation + `responses['200']` anchor
- `POST /api/v1/promo-codes` — operation + requestBody
- `PATCH /api/v1/promo-codes/{promo_id}` — operation
- `PATCH /api/v1/promo-codes/{promo_id}/deactivate` — operation
- `GET /api/v1/reports/cohort` — operation (already in schema.d.ts at line 3352)
- `GET /api/v1/reports/anomaly` — operation (line 3378)
- `GET /api/v1/reports/at-risk` — operation (line 3404)
- `GET /api/v1/reports/load/now` — operation (line 3430)
- `GET /api/v1/messages/threads` — operation + `responses['200']` anchor
- `GET /api/v1/messages/threads/{thread_id}` — operation
- `POST /api/v1/messages/threads/{thread_id}/reply` — operation + requestBody
- `POST /api/v1/messages/threads/{thread_id}/read` — operation
- `GET /api/v1/reports/payments.csv` — `responses['200']` reachability anchor (same style as `_ReportsRevenueCsvGet`)

---

### `apps/backend/openapi.json` — regenerated via `export_openapi.py`

**Analog:** `apps/backend/scripts/export_openapi.py` (no changes needed to the script)

**Regen command** (lines 1–14 of the script docstring):
```bash
cd apps/backend && uv run python -m scripts.export_openapi
```

Script mechanism (lines 58–76):
```python
spec = create_app().openapi()
payload = json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
target = pathlib.Path(__file__).resolve().parents[1] / "openapi.json"
target.write_text(payload, encoding="utf-8")
```

Output is ADDITIVE (new v3.2 paths appear); not byte-stable vs v3.1 file.

---

### `packages/api-client/src/schema.d.ts` — regenerated via codegen

**Analog:** `packages/api-client/package.json` script (line 16):
```json
"codegen": "openapi-typescript ../../apps/backend/openapi.json --output src/schema.d.ts"
```

**Run command:**
```bash
pnpm -F @clubcore/api-client codegen
```

After codegen, the `as unknown as keyof paths` casts in `features/promoCodes/api.ts` (lines 61, 87, 110, 132) must be replaced with direct typed path strings — the real paths now exist in the generated file.

---

### `apps/admin-app/src/features/promoCodes/api.ts` — remove temporary casts

**Analog:** Any existing feature api.ts that uses typed paths WITHOUT casts — e.g. `features/payments/api.ts` or `features/users/api.ts`.

**Current stub pattern to REMOVE** (lines 61, 87, 110, 132 of `promoCodes/api.ts`):
```typescript
// NOTE (lines 15-18) — explains the cast:
// NOTE: promo-codes admin paths are not yet in schema.d.ts (Phase 117 regenerates
// the OpenAPI contract). Paths are cast via `as unknown as keyof paths` until
// the schema is regenerated. All wire shapes are validated by Zod at runtime.

staffRequest(
  '/api/v1/promo-codes' as unknown as keyof paths,
  // ...
)
```

**Target pattern after regen** — drop the cast; the path string must be typed directly:
```typescript
staffRequest(
  '/api/v1/promo-codes',
  // ...
)
```

Also remove the NOTE comment block (lines 15–18) once casts are gone.

---

### `apps/backend/tests/integration/*/test_*_snapshot.py` (NEW — capture real responses)

**Analog:** `apps/backend/tests/integration/payments/test_payments_refund.py`

**ASGITransport fixture pattern** (lines 80–84):
```python
@pytest_asyncio.fixture
async def http_client(_overridden_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """ASGITransport client that persists cookies across requests."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
```

**Dependency override pattern** (lines 62–76):
```python
@pytest_asyncio.fixture
async def _overridden_app(app: FastAPI, db_session: AsyncSession) -> AsyncIterator[FastAPI]:
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = lambda: app.state.redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()
```

**JSON response capture** (idiomatic in existing tests, e.g. line 77):
```python
r = await http_client.get("/api/v1/...", headers=csrf_headers)
assert r.status_code == 200
snapshot = r.json()   # This is what gets serialized to the fixture file
```

**NEW addition for snapshot capture** — write the JSON to the shared fixtures dir:
```python
import json, pathlib

FIXTURES_DIR = pathlib.Path(__file__).resolve().parents[4] / "apps/admin-app/src/features/<domain>/capture"

def test_capture_<domain>_response(http_client, ...):
    r = await http_client.get("/api/v1/...", headers=...)
    assert r.status_code == 200
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURES_DIR / "<endpoint>.json").write_text(
        json.dumps(r.json(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
```

**Domains requiring a capture test:**
- `payments` — `POST /api/v1/payments/{id}/refund` → `refund-response.json`
- `users` — `PATCH /api/v1/users/{id}/role` → `role-change-response.json`
- `promoCodes` — `GET /api/v1/promo-codes` → `promo-codes-list-response.json`
- `reports` — `GET /api/v1/reports/load/now` → `load-now-response.json` (representative for all 4 analytics endpoints)
- `messages` — `GET /api/v1/messages/threads` → `threads-list-response.json`

CSV route (`GET /api/v1/reports/payments.csv`) is asserted at the backend tier (BOM/headers/status 200), not captured as a JSON fixture.

---

### `apps/admin-app/src/features/*/*.contract.test.ts` (NEW — FE Zod parse of captured JSON)

**Analog:** `apps/admin-app/src/features/reports/schemas.test.ts`

**Import pattern** (lines 1–14):
```typescript
import { describe, expect, it } from 'vitest'
import {
  LoadNowSchema,
  CohortRetentionSchema,
  // ...
} from './schemas'
```

**Parse + assert pattern** (lines 109–114):
```typescript
it('parses a valid load/now response (matching real wire shape)', () => {
  const result = LoadNowSchema.parse(validResponse).data
  expect(result.count).toBe(5)
  expect(result.asOf).toBe('2026-06-15T14:30:00Z')
  expect(result.windowMinutes).toBe(120)
})
```

**NEW contract test pattern** — load captured JSON file instead of inline fixture:
```typescript
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { RefundResponseSchema } from './schemas'

const captured = JSON.parse(
  readFileSync(join(__dirname, 'capture/refund-response.json'), 'utf-8'),
)

describe('refund contract — real backend JSON × FE Zod schema', () => {
  it('parses captured ASGITransport response with RefundResponseSchema', () => {
    expect(() => RefundResponseSchema.parse(captured)).not.toThrow()
    const result = RefundResponseSchema.parse(captured).data
    expect(result.status).toBe('cancelled')
  })
})
```

File naming: `<domain>.contract.test.ts` co-located next to the feature's `schemas.ts`.

---

## Shared Patterns

### CSRF headers for staff mutation tests
**Source:** `apps/backend/tests/integration/payments/test_payments_refund.py` lines 40–50
```python
def _refund_headers(client: AsyncClient) -> dict[str, str]:
    """Headers for POST /memberships/{id}/refund — NO Idempotency-Key."""
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}
```
**Apply to:** All new backend capture tests that call POST or PATCH endpoints.

### pytestmark asyncio
**Source:** `apps/backend/tests/messaging/test_messaging_rest.py` line 42
```python
pytestmark = pytest.mark.asyncio(loop_scope="function")
```
**Apply to:** All new backend capture test files.

### `staffRequest` typed call (FE api.ts)
**Source:** `apps/admin-app/src/features/promoCodes/api.ts` lines 23–25
```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { staffRequest, ApiError } from '@/api/client'
import type { paths } from '@clubcore/api-client'
```
**Apply to:** Any new feature api.ts files; this is the model for the cleaned-up promoCodes/api.ts.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `apps/admin-app/src/features/*/capture/*.json` (shared fixture dir) | fixture/artifact | file-I/O | The "backend generates → FE contract test reads" captured-JSON snapshot mechanism is new to this codebase. No existing cross-tier snapshot fixture directory exists. |

**Proposed pattern for the new mechanism:**
- Backend pytest writes the captured JSON to `apps/admin-app/src/features/<domain>/capture/<endpoint>.json` via `pathlib.Path.write_text` (pytest-generated, committed as snapshot).
- FE vitest contract test reads the file with `node:fs readFileSync` + `JSON.parse`, then calls `Schema.parse(captured)` — closest analog is `schemas.test.ts` inline fixtures but sourced from disk instead of inline.
- The `capture/` subdirectory should have a `.gitkeep` initially; the backend pytest generates its contents. The FE `*.contract.test.ts` is marked skipped (or uses `skipIf`) when the capture file is absent, so the test suite stays green in CI before the backend capture step runs.

---

## Metadata

**Analog search scope:** `packages/api-client/src/`, `apps/backend/tests/integration/`, `apps/admin-app/src/features/`
**Files scanned:** ~12 (schema.contract.test.ts, export_openapi.py, test_payments_refund.py, test_messaging_rest.py, schemas.test.ts for reports, promoCodes/api.ts, package.json for api-client, schema.d.ts spot-checks)
**Pattern extraction date:** 2026-06-15
