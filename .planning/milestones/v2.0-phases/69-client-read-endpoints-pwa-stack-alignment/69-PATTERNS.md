# Phase 69: Client Read Endpoints + PWA Stack Alignment - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 16 new/modified files (2 clusters)
**Analogs found:** 16 / 16

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/app/modules/client_portal/__init__.py` | module-init | — | `apps/backend/app/modules/reports/__init__.py` | exact |
| `apps/backend/app/modules/client_portal/repository.py` | repository | CRUD (read-only, raw-SQL cross-module) | `apps/backend/app/modules/reports/repository.py` | exact |
| `apps/backend/app/modules/client_portal/schemas.py` | schema | request-response | `apps/backend/app/modules/client_auth/schemas.py` | role-match |
| `apps/backend/app/modules/client_portal/service.py` | service | request-response | `apps/backend/app/modules/reports/service.py` | role-match |
| `apps/backend/app/modules/client_portal/router.py` | controller | request-response | `apps/backend/app/modules/client_auth/router.py` | exact |
| `apps/backend/app/api/v1/router.py` (modify) | route-mount | — | itself (lines 93-95) | exact |
| `apps/backend/tests/integration/client_portal/test_idor_sweep.py` | test | request-response | `apps/backend/tests/integration/client_auth/test_idor.py` | exact |
| `apps/client-pwa/package.json` (modify) | config | — | `apps/admin-web/package.json` | role-match |
| `apps/client-pwa/vite.config.ts` (replace) | config | — | `apps/admin-web/vite.config.ts` | role-match |
| `apps/client-pwa/tsconfig.json` (new) | config | — | `apps/admin-web/tsconfig.json` | exact |
| `apps/client-pwa/tsconfig.app.json` (new) | config | — | `apps/admin-web/tsconfig.app.json` | role-match |
| `apps/client-pwa/eslint.config.js` (new) | config | — | `apps/admin-web/eslint.config.js` | role-match |
| `apps/client-pwa/vitest.config.ts` (new) | config | — | `apps/admin-web/vitest.config.ts` | exact |
| `apps/client-pwa/src/lib/clientFetcher.ts` (new) | utility | request-response | `packages/api-client/src/fetcher.ts` | exact |
| `apps/client-pwa/src/lib/clientFetcher.test.ts` (new) | test | request-response | `packages/api-client/src/fetcher.test.ts` | exact |
| `packages/api-client/src/fetcher.ts` (read-only reference) | utility | request-response | itself | exact |

---

## Pattern Assignments

### `apps/backend/app/modules/client_portal/repository.py` (repository, read-only cross-module)

**Analog:** `apps/backend/app/modules/reports/repository.py`

**Module docstring discipline** (lines 1-27):
```python
"""Client-portal repository — raw-SQL read aggregator across memberships, bookings,
pt_sessions, payments, and catalog tables.

CROSS-MODULE READ DISCIPLINE (D-54-08 / D-20-MODULE):
  - ``from sqlalchemy import text`` — NEVER import another module's ORM model.
  - Bind params via ``:name`` placeholders + a dict; cast UUIDs to ``str``.
  - ``.mappings().all()`` for list reads; ``.mappings().one()`` for scalar reads.
  - Each reader documents verified columns + source file:line of the foreign table.

INVARIANTS:
  - ZERO INSERT / UPDATE / DELETE in this file.
  - ORM model imports from app.modules.*: FORBIDDEN.
  - ORM model imports from app.core.*: ALLOWED (app.core is a free import target).
"""
```

**Imports pattern** (from `reports/repository.py` lines 29-43):
```python
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData
# NO imports from app.modules.* ORM models — raw SQL text() only
```

**Core raw-SQL read pattern with client_id IDOR gate** (adapted from `reports/repository.py` lines 57-98):
```python
async def fetch_client_membership(
    session: AsyncSession,
    client_id: UUID,
) -> dict[str, object] | None:
    """Active membership for a specific client (CHOME-01, D-20-IDOR).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Membership.
    Verified columns (apps/backend/app/modules/memberships/models.py):
      - status       String(16) ('active' | ...)
      - end_date     Date (inclusive)
      - plan_name_snapshot  Text NOT NULL

    IDOR: mandatory :client_id bind param — result scoped to the caller's
    own client_id; NEVER returns rows for a different client.
    Empty state → None (D-69-03: no active membership is 200 with null, not 404).
    """
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, plan_name_snapshot, start_date, end_date, status, "
                    "(end_date - (now() AT TIME ZONE 'Europe/Moscow')::date) AS days_until_end "
                    "FROM memberships "
                    "WHERE client_id = :client_id AND status = 'active' "
                    "ORDER BY start_date ASC, created_at DESC LIMIT 1"
                ),
                {"client_id": str(client_id)},
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None
```

**Pagination list pattern** (from `reports/repository.py` pattern + `memberships/repository.py` lines 270-353):
```python
async def fetch_client_visits_page(
    session: AsyncSession,
    client_id: UUID,
    page: int,
    page_size: int,
) -> dict[str, object]:
    """Paginated visit history for a client (CHIST-01, D-20-IDOR).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Visit.
    Returns {items, total, page, pageSize} per project pagination contract.
    IDOR: mandatory :client_id bind param on both COUNT and SELECT.
    """
    count_row = (
        (
            await session.execute(
                text("SELECT COUNT(*) AS cnt FROM visits WHERE client_id = :client_id"),
                {"client_id": str(client_id)},
            )
        )
        .mappings()
        .one()
    )
    total = int(count_row["cnt"])
    offset = (page - 1) * page_size
    rows = (
        (
            await session.execute(
                text(
                    "SELECT id, gym_date, checked_in_at "
                    "FROM visits WHERE client_id = :client_id "
                    "ORDER BY gym_date DESC, checked_in_at DESC "
                    "LIMIT :limit OFFSET :offset"
                ),
                {"client_id": str(client_id), "limit": page_size, "offset": offset},
            )
        )
        .mappings()
        .all()
    )
    return {"items": [dict(r) for r in rows], "total": total, "page": page, "page_size": page_size}
```

**Expiring-soon server-derived boolean** (from `memberships/repository.py` lines 307-316):
```python
# Europe/Moscow today for expiringSoon computation (D-69-02 / D-24-12):
#   within 7 days = end_date <= today_msk + 7
# Use in the raw-SQL SELECT or compute in Python after the fetch:
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

today_msk = datetime.now(ZoneInfo("Europe/Moscow")).date()
expiring_soon: bool = (
    0 <= (end_date - today_msk).days <= 7
) if end_date is not None else False
```

---

### `apps/backend/app/modules/client_portal/router.py` (controller, request-response)

**Analog:** `apps/backend/app/modules/client_auth/router.py`

**Imports pattern** (from `client_auth/router.py` lines 1-51):
```python
"""Client-portal router — read endpoints for authenticated clients.

All handlers gated via Depends(require_client()).
No CSRF dep on GET endpoints (safe methods). POST/PATCH endpoints add
Depends(verify_client_csrf) after require_client() per RBAC-04 ordering.

D-69-03: Empty states are 200 with null/[] — never 404 for own scope.
D-20-IDOR: Every owned resource read has mandatory client_id filter in repo layer.
D-20-OPENAPI: Client-Portal tag; client_ operationId prefix.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ClientPrincipal, require_client
from app.core.pagination import PaginatedData
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.client_portal import service
from app.modules.client_portal.schemas import (
    ClientHomeResponse,
    ClientMembershipResponse,
    ClientVisitPage,
    # ...
)

router = APIRouter(tags=["Client-Portal"])
```

**Auth-gated GET handler pattern** (from `client_auth/router.py` lines 171-184):
```python
@router.get(
    "/membership",
    response_model=ResponseEnvelope[ClientMembershipResponse | None],
    operation_id="client_get_membership",
    summary="Active membership for the authenticated client (CHOME-01/02; 200 null if none)",
)
async def get_client_membership(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientMembershipResponse | None]:
    """Return active membership with server-derived daysUntilEnd + expiringSoon (D-69-02).

    D-69-03: no active membership → 200 with null, not 404.
    D-20-IDOR: client_id injected from cookie principal, not URL param.
    No CSRF dep — GET is safe (mirrors client_auth GET /me).
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_client_membership(session, client.id)
    return envelope(result)
```

**Composite fan-out pattern for /home** (per D-69-01):
```python
@router.get(
    "/home",
    response_model=ResponseEnvelope[ClientHomeResponse],
    operation_id="client_get_home",
    summary="Home screen composite: membership + nextBooking + expiringSoon (CHOME-01..03)",
)
async def get_client_home(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientHomeResponse]:
    """Server-side fan-out: reuses the same query functions as the granular endpoints.
    Null slots for missing data (D-69-03).
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_client_home(session, client.id)
    return envelope(result)
```

**Paginated history handler pattern** (from `bookings/router.py` lines 199-222):
```python
@router.get(
    "/history/visits",
    response_model=ResponseEnvelope[PaginatedData[ClientVisitItem]],
    operation_id="client_list_visit_history",
    summary="Paginated visit history for the authenticated client (CHIST-01)",
)
async def list_client_visit_history(
    query: Annotated[PageQuery, Depends()],
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[ClientVisitItem]]:
    page = await service.list_client_visits(session, client.id, query)
    return envelope(page)
```

---

### `apps/backend/app/api/v1/router.py` (route-mount modification)

**Analog:** itself, lines 93-95

**Mount point pattern** (from `apps/backend/app/api/v1/router.py` lines 93-95):
```python
# Phase 68 CAUTH-01..06 / CISO-01..05 — client auth + profile self-service.
v1.include_router(client_auth_router, prefix="/client")

# Phase 69 CHOME-01..03, CHIST-01..03, CPLAN-01..03 — client read endpoints.
# Mounted at /api/v1/client alongside the Phase-68 client_auth_router (same prefix).
# Tags declared on client_portal_router itself (D-64-TAG-ORDER).
from app.modules.client_portal.router import router as client_portal_router
v1.include_router(client_portal_router, prefix="/client")
```

Note: both `client_auth_router` and `client_portal_router` use `prefix="/client"` — FastAPI merges them correctly because each declares its own sub-paths.

---

### `apps/backend/tests/integration/client_portal/test_idor_sweep.py` (test, request-response)

**Analog:** `apps/backend/tests/integration/client_auth/test_idor.py`

**Test harness pattern** (from `test_idor.py` lines 1-155 — full file):
```python
"""Parametrized IDOR sweep for Phase 69 client-portal read endpoints (D-20-IDOR).

Harness: SAVEPOINT rollback + ASGITransport async_client from root conftest.py.

Test pattern per owned resource type:
  seed clients A and B with owned data (membership, pt_packages, visits, payments);
  parametrize (attacker, victim) over both orderings;
  authenticate as attacker via OTP flow;
  request owned resource as attacker;
  assert response contains only attacker's data, never victim's.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

# Re-use _auth_as_client helper from test_idor.py — exact same OTP flow:
async def _auth_as_client(async_client, db_session, client) -> str:
    # ... same pattern as test_idor.py lines 34-77 ...

@pytest.mark.parametrize("resource_path,attacker_is_a", [
    ("/api/v1/client/membership", True),
    ("/api/v1/client/membership", False),
    ("/api/v1/client/history/visits", True),
    ("/api/v1/client/history/visits", False),
    ("/api/v1/client/history/pt-sessions", True),
    ("/api/v1/client/history/pt-sessions", False),
    ("/api/v1/client/history/payments", True),
    ("/api/v1/client/history/payments", False),
])
async def test_owned_resource_idor(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a,
    client_b,
    redis_clean,
    resource_path: str,
    attacker_is_a: bool,
) -> None:
    """D-20-IDOR: each owned endpoint returns only the cookie-principal's data."""
    attacker, victim = (client_a, client_b) if attacker_is_a else (client_b, client_a)
    token = await _auth_as_client(async_client, db_session, attacker)
    resp = await async_client.get(
        resource_path,
        headers={"Cookie": f"cc_client_access={token}"},
    )
    assert resp.status_code == 200
    # For list endpoints: assert no victim-owned IDs appear in items
    # For single-item endpoints: assert returned id matches attacker's resource only
```

**SAVEPOINT + ASGITransport fixture** (from `conftest.py` lines 57-140):
```python
# All fixtures from root conftest.py are inherited:
# - app (FastAPI, lifespan fired)
# - db_session (SAVEPOINT join_transaction_mode='create_savepoint')
# - async_client (ASGITransport, dep overrides get_db + get_redis)
# Local conftest adds seeded_staff + redis_clean (mirrors client_auth/conftest.py).
```

---

### `apps/backend/app/modules/client_portal/schemas.py` (schema, request-response)

**Analog:** `apps/backend/app/modules/client_auth/schemas.py` + `app/core/schemas.py`

**Schema base class pattern** (from `app/core/schemas.py` lines 24-53):
```python
from __future__ import annotations
from app.core.schemas import ResponseData, BackendSchemaBase
from app.core.pagination import PageQuery

class ClientMembershipResponse(ResponseData):
    """Active membership payload with server-derived temporal fields (D-69-02).

    Exposed fields only (D-69-05): no freeze_days_limit internals, no audit fields.
    """
    id: UUID
    plan_name_snapshot: str
    start_date: date
    end_date: date
    status: str
    days_until_end: int          # server-computed (D-69-02)
    expiring_soon: bool          # server-computed (D-69-02), True if days_until_end <= 7

class ClientHomeResponse(ResponseData):
    """Composite home screen payload (D-69-01)."""
    membership: ClientMembershipResponse | None   # null if no active membership (D-69-03)
    next_booking: ClientNextBookingResponse | None
    expiring_soon: bool

class ClientCatalogTrainerResponse(ResponseData):
    """Client-safe trainer projection (D-69-05): name + specialization only."""
    id: UUID
    full_name: str
    specialization: str | None   # no rates, no is_active, no audit fields
```

---

### `apps/client-pwa/package.json` (config, workspace member)

**Analog:** `apps/admin-web/package.json`

**Workspace + script pattern** (from `apps/admin-web/package.json` lines 1-20):
```json
{
  "name": "@clubcore/client-pwa",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "packageManager": "pnpm@9.15.9",
  "engines": {
    "node": ">=20.0.0",
    "pnpm": ">=9.0.0"
  },
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "test": "vitest run",
    "typecheck": "tsc -b --noEmit"
  }
}
```

Key changes from current `gym-app` package.json:
- `name` → `@clubcore/client-pwa` (workspace member name)
- Add `packageManager: pnpm@9.15.9` + `engines`
- Add `"@clubcore/api-client": "workspace:*"` to dependencies
- Bump `vite` to `^6.0.x` (from 5.4.8)
- Add `vitest`, `typescript`, `eslint`, `prettier` devDeps matching admin-web pattern
- Add `vite-plugin-pwa` for D-69-08

---

### `apps/client-pwa/vite.config.ts` (config)

**Analog:** `apps/admin-web/vite.config.ts`

**Vite 6 config pattern** (from `apps/admin-web/vite.config.ts` full file + D-69-08 PWA additions):
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'node:path'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      // PWA-07: NEVER cache /api/* — no stale authed data
      navigateFallbackDenylist: [/^\/api\//],
      workbox: {
        // No runtime caching rules for the API origin
        runtimeCaching: [],
      },
      manifest: {
        name: 'Sportzal',
        short_name: 'Sportzal',
        display: 'standalone',
        start_url: '/',
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5174,  // avoid conflict with admin-web on 5173
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: false,
      },
    },
  },
  build: {
    target: 'es2022',  // matches admin-web
  },
  esbuild: {
    target: 'es2022',
  },
})
```

---

### `apps/client-pwa/tsconfig.json` + `tsconfig.app.json` (config)

**Analog:** `apps/admin-web/tsconfig.json` + `apps/admin-web/tsconfig.app.json`

**tsconfig.json pattern** (from `apps/admin-web/tsconfig.json` full file):
```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ],
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

**tsconfig.app.json pattern for allowJs ramp** (from `apps/admin-web/tsconfig.app.json` full file, with D-69-06 allowJs addition):
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",

    /* D-69-06: allowJs ramp — existing .jsx/.js screens stay as-is */
    "allowJs": true,
    "checkJs": false,

    /* Strictness (CLAUDE.md lock — strict but relaxed for JS files) */
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "isolatedModules": true,

    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src", "vitest.config.ts", "vite.config.ts"],
  "exclude": ["node_modules", "dist"]
}
```

---

### `apps/client-pwa/eslint.config.js` (config)

**Analog:** `apps/admin-web/eslint.config.js`

**ESLint flat config pattern** (from `apps/admin-web/eslint.config.js` lines 1-60):
```javascript
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import importPlugin from 'eslint-plugin-import'

export default tseslint.config(
  {
    ignores: ['dist', 'node_modules', 'src/__fixtures/**', 'coverage'],
  },
  {
    files: ['**/*.{ts,tsx,js,jsx}'],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommended,
      reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    plugins: { import: importPlugin },
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    settings: {
      'import/resolver': { typescript: true, node: true },
    },
    rules: {
      // Import boundary: new TS files must not import clientFetcher directly;
      // go through a typed hook layer (mirrors admin-web swap-seam rule).
      'import/no-restricted-paths': ['error', { zones: [] }],
    },
  },
)
```

---

### `apps/client-pwa/vitest.config.ts` (config)

**Analog:** `apps/admin-web/vitest.config.ts` (full file — copy verbatim, only adjust paths):
```typescript
/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // @ts-expect-error — vitest augments vite's UserConfig via types reference above.
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist'],
  },
})
```

---

### `apps/client-pwa/src/lib/clientFetcher.ts` (utility, request-response)

**Analog:** `packages/api-client/src/fetcher.ts` (full file — the canonical reference)

**Key divergences from the staff fetcher** (D-69-06 / CONTEXT.md Integration Points):

```typescript
/**
 * Client-PWA typed transport (Phase 69 PWA-03).
 *
 * Thin wrapper over @clubcore/api-client's `request()`, specialized for the
 * cc_client_* cookie stack:
 *
 *  - D-A3 equivalent: /api/v1/client/otp/* and /api/v1/client/session/* are
 *    refresh-exempt (mirrors staff AUTH_EXEMPT_PATHS).
 *  - D-11 equivalent: reads `clubcore_client_csrf` cookie (NOT `clubcore_csrf`).
 *  - D-A1 equivalent: single-flight refresh hits /api/v1/client/session/refresh
 *    (NOT /api/v1/auth/refresh).
 *  - All path keys under the `Client-Portal` OpenAPI tag use client_ operationId prefix.
 */
import { request as baseRequest } from '@clubcore/api-client'
import type { paths } from '@clubcore/api-client'

// Client-scoped CSRF cookie name (D-10 / Phase 68 CISO-02)
const CLIENT_CSRF_COOKIE = 'clubcore_client_csrf'

// Client-side refresh-exempt paths (mirror staff AUTH_EXEMPT_PATHS shape)
const CLIENT_AUTH_EXEMPT_PATHS: readonly string[] = [
  '/api/v1/client/otp/request',
  '/api/v1/client/otp/verify',
  '/api/v1/client/session/refresh',
  '/api/v1/client/session/logout',
  '/api/v1/client/me',
]

function readClientCsrfCookie(): string | undefined {
  const prefix = `${CLIENT_CSRF_COOKIE}=`
  const cookies = document.cookie.split(';')
  for (const raw of cookies) {
    const c = raw.trim()
    if (c.startsWith(prefix)) return c.slice(prefix.length)
  }
  return undefined
}

// refreshOnce equivalent pointing at client session/refresh URL
let inFlightClientRefresh: Promise<Response> | null = null

function clientRefreshOnce(): Promise<Response> {
  if (inFlightClientRefresh) return inFlightClientRefresh
  inFlightClientRefresh = fetch('/api/v1/client/session/refresh', {
    method: 'POST',
    credentials: 'include',
  }).finally(() => {
    queueMicrotask(() => { inFlightClientRefresh = null })
  })
  return inFlightClientRefresh
}

// Re-export `request` for client paths; the full refresh/CSRF logic is
// either re-implemented here or the base `request()` is called with
// overridden cookie name and refresh URL via options (planner decides the
// exact wiring based on api-client extensibility).
export { readClientCsrfCookie, clientRefreshOnce, CLIENT_AUTH_EXEMPT_PATHS }
```

**Key contract from `packages/api-client/src/fetcher.ts`** to copy verbatim for the client side:
- Lines 56-73: `inFlightRefresh` / `refreshOnce()` single-flight pattern → replicate with `clientRefreshOnce()` pointing at `/api/v1/client/session/refresh`
- Lines 44-51: `readCsrfCookie()` → replicate as `readClientCsrfCookie()` reading `clubcore_client_csrf`
- Lines 76-96: `parseErrorBody()` → copy verbatim
- Lines 143-255: `request()` function body → adapt by substituting cookie name + refresh URL + exempt paths

---

### `apps/client-pwa/src/lib/clientFetcher.test.ts` (test, request-response)

**Analog:** `packages/api-client/src/fetcher.test.ts`

**Vitest smoke test pattern** (per D-69-09):
```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readClientCsrfCookie, CLIENT_AUTH_EXEMPT_PATHS } from './clientFetcher'

describe('clientFetcher', () => {
  beforeEach(() => {
    // Reset document.cookie mock between tests
    Object.defineProperty(document, 'cookie', { value: '', writable: true })
  })

  it('reads clubcore_client_csrf cookie (not clubcore_csrf)', () => {
    document.cookie = 'clubcore_client_csrf=test-csrf-token; clubcore_csrf=staff-token'
    expect(readClientCsrfCookie()).toBe('test-csrf-token')
  })

  it('marks client OTP paths as auth-exempt', () => {
    expect(CLIENT_AUTH_EXEMPT_PATHS).toContain('/api/v1/client/otp/request')
    expect(CLIENT_AUTH_EXEMPT_PATHS).toContain('/api/v1/client/session/refresh')
  })

  // One render-without-crash test (D-69-09):
  it('App renders without throwing', async () => {
    const { render } = await import('@testing-library/react')
    const { default: App } = await import('../App')  // or entry component
    expect(() => render(App)).not.toThrow()
  })
})
```

---

## Shared Patterns

### Client Authentication Gate
**Source:** `apps/backend/app/core/dependencies.py` lines 1234-1251
**Apply to:** All `client_portal/router.py` handlers
```python
# Every read endpoint in client_portal/router.py uses require_client() as the auth gate:
client: Annotated[ClientPrincipal, Depends(require_client())]

# ClientPrincipal (dependencies.py lines 1158-1169) provides:
#   client.id  -> UUID  (mandatory bind param for all IDOR-safe repo calls)
#   client.phone -> str
#   client.email -> str | None

# NEVER pass client_id as a URL parameter for own-resource reads —
# always extract from the cookie principal (D-20-IDOR anti-oracle).
```

### IDOR 404-Collapse (D-20-IDOR)
**Source:** `apps/backend/app/core/exceptions.py` lines 20-22 + service layer pattern
**Apply to:** All owned-resource reads in `client_portal/service.py`
```python
# D-20-IDOR: if a repo returns None for an owned resource, raise NotFoundError.
# This collapses "not found" and "belongs to someone else" into a single 404 —
# the caller cannot distinguish non-existence from non-ownership (anti-oracle).
from app.core.exceptions import NotFoundError

result = await repository.fetch_client_pt_package(session, pt_package_id, client_id=client.id)
if result is None:
    raise NotFoundError("not_found")  # 404 — collapses existence oracle
```

### Empty-State 200 vs. IDOR 404 (D-69-03 vs. D-20-IDOR)
**Source:** `69-CONTEXT.md` decisions D-69-03 + D-20-IDOR
**Apply to:** `client_portal/router.py` + `client_portal/service.py`
```python
# D-69-03 applies to "own scope, nothing there" (correct state):
#   GET /client/membership  → 200 with {"data": null} if no active membership
#   GET /client/home        → 200 with {"data": {"membership": null, "nextBooking": null}}
#
# D-20-IDOR applies to "fetch by owned resource ID" (e.g., a specific pt_package):
#   GET /client/pt-packages/{id} → 404 if id not found OR belongs to another client
#
# These are DISTINCT. Own-scope lists/singletons use 200+null.
# Owned-by-ID reads use 404-collapse.
```

### Raw-SQL Cross-Module Read Discipline (D-54-08)
**Source:** `apps/backend/app/modules/reports/repository.py` lines 1-27
**Apply to:** `client_portal/repository.py` — every function
```python
# MANDATORY header comment per function:
# CROSS-MODULE READ — raw SQL text() only; NO ORM import of <TableName>.
# Verified columns (<path/to/models.py>:<line range>):
#   - <column_name>  <Type> <description>

# Bind params ALWAYS via :name placeholders — never f-string user input.
# UUIDs cast to str: {"client_id": str(client_id)}
# List reads: .mappings().all()
# Scalar reads: .mappings().one() or .mappings().one_or_none()
```

### ResponseEnvelope + envelope() Pattern
**Source:** `apps/backend/app/core/schemas.py` lines 60-82
**Apply to:** All `client_portal/router.py` handlers
```python
from app.core.schemas import ResponseEnvelope, envelope

# Route return type annotation:
async def handler(...) -> ResponseEnvelope[MyResponseType]:
    result = await service.do_thing(session, client.id)
    return envelope(result)  # wraps in {"data": result}
```

### PaginatedData Contract
**Source:** `apps/backend/app/core/pagination.py` lines 32-43
**Apply to:** All history list endpoints in `client_portal/router.py`
```python
from app.core.pagination import PageQuery, PaginatedData

# History endpoints follow: {items, total, page, pageSize} — never bare arrays.
# PageQuery provides: page (default 1), page_size (default 20, max 100).
# Repository returns PaginatedData.model_construct(items=..., total=..., page=..., page_size=...)
```

### Europe/Moscow Date Discipline
**Source:** `apps/backend/app/modules/memberships/repository.py` lines 312-316
**Apply to:** `client_portal/repository.py` — any temporal computation
```python
from zoneinfo import ZoneInfo
from datetime import datetime

# Always resolve "today" via Europe/Moscow:
today_msk = datetime.now(ZoneInfo("Europe/Moscow")).date()

# In raw SQL: use AT TIME ZONE 'Europe/Moscow' for timestamptz→date conversion.
# gym_date column on visits is already stored MSK-local — no conversion needed.
# NEVER compute daysUntilEnd in the PWA (D-69-02). Backend computes it.
```

### No try/except in Route Handlers
**Source:** `apps/backend/app/modules/reports/router.py` lines 18-20
**Apply to:** All `client_portal/router.py` handlers
```python
# No try/except in route handlers — AppError subclasses bubble to the
# registered _app_error_handler (core/exceptions.py:register_exception_handlers).
# This is the project-wide convention: error handling is centralized, not per-route.
```

### SAVEPOINT Test Harness (ASGITransport)
**Source:** `apps/backend/tests/conftest.py` lines 57-140
**Apply to:** `tests/integration/client_portal/` — all test files
```python
# All test files in tests/integration/client_portal/ inherit from root conftest:
# - app: FastAPI with lifespan
# - db_session: join_transaction_mode='create_savepoint' (service commits = SAVEPOINTs)
# - async_client: ASGITransport + dep overrides get_db + get_redis
# Local conftest.py adds client-auth fixtures (seeded_staff + redis_clean)
# from tests/integration/client_auth/conftest.py.
# NEVER use real network in tests (CLAUDE.md constraint).
```

### PWA: Vite 6 Build Target
**Source:** `apps/admin-web/vite.config.ts` lines 36-41
**Apply to:** `apps/client-pwa/vite.config.ts`
```typescript
// Target ES2022 for modern browsers (matches admin-web):
build: { target: 'es2022' },
esbuild: { target: 'es2022' },
```

### PWA: Service Worker API Cache Exclusion (D-69-08 / PWA-07)
**Source:** `69-CONTEXT.md` D-69-08 + `<specifics>`
**Apply to:** `apps/client-pwa/vite.config.ts` VitePWA plugin config
```typescript
VitePWA({
  navigateFallbackDenylist: [/^\/api\//],
  workbox: {
    runtimeCaching: [],  // ZERO runtime caching rules for /api/* origin
  },
})
// PWA-07: SW MUST NEVER cache /api/* — enforced via navigateFallbackDenylist
// + absence of any runtime-caching rule for the API origin.
```

---

## No Analog Found

All files have close analogs. No entries in this section.

---

## Notes for Planner

1. **`client_portal` module has no `models.py`** — like `reports/`, it is a pure read aggregator. ORM models live in their source modules (`memberships`, `bookings`, `pt_sessions`, `payments`, `trainers`, `visits`). Cross-module reads use raw SQL `text()` only (D-54-08 / D-20-MODULE).

2. **`client_portal/router.py` mounts at `/client` prefix** alongside `client_auth_router` in `api/v1/router.py`. FastAPI merges both routers correctly because each declares its own disjoint sub-paths (`/otp/*`, `/session/*`, `/me` vs. `/membership`, `/home`, `/history/*`, `/plans`, `/pt-packages`, `/trainers`).

3. **Catalog endpoints** (`/client/plans`, `/client/pt-packages`, `/client/trainers`) use `tags=["Client-Portal"]` and `client_` operationId prefix (D-20-OPENAPI). They are NEW routes that reuse staff query logic internally but expose only client-safe fields (D-69-04/05). Do NOT reuse the staff catalog routes directly.

4. **PWA `bun.lock` deletion**: the plan must explicitly delete `apps/client-pwa/bun.lock` (PWA-01) before `pnpm install` at root. The `pnpm-workspace.yaml` already globs `apps/*`; adding `packageManager: pnpm@9.15.9` to the new `package.json` is sufficient for automatic workspace membership.

5. **`clientFetcher.ts` placement**: `apps/client-pwa/src/lib/clientFetcher.ts` — a new `lib/` directory under `src/`. The existing `src/` structure (`src/pages/`, `src/components/`, etc.) is untouched (D-69-06 minimal bootstrap ramp).

6. **OpenAPI additive discipline (D-20-OPENAPI)**: after adding Phase 69 routes, `pnpm --filter @clubcore/api-client codegen` must regenerate `schema.d.ts`. Staff paths must remain byte-identical to `contract-freeze-v1.11.0` (drift gate must stay green).

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/`, `apps/backend/app/core/`, `apps/backend/tests/`, `apps/admin-web/`, `packages/api-client/src/`
**Files scanned:** 18
**Pattern extraction date:** 2026-05-29
