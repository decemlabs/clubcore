# External Integrations

**Analysis Date:** 2026-04-30

## APIs & External Services

**Not Implemented in Phase 1:**
- No live HTTP API integrations currently wired
- HTTP service layer exists as stub at `src/shared/api/services/http/index.ts` (populated in later phases)
- All data operations use in-memory mock implementations via `src/shared/api/services/mock/index.ts`

**Planned Integration Pattern:**
- Real API integration will be added via HTTP service implementations in Phase 7+
- Entry point for API mode selection: `src/shared/api/config/env.ts` (reads `VITE_API_MODE`)
- Swap seam: `src/shared/api/services/index.ts` (branches on `API_MODE` to select mock or http impl)
- No third-party HTTP clients currently installed (axios, fetch wrapper, etc. can be added when needed)

## Data Storage

**Databases:**
- None (frontend-only v1)
- No direct database connection

**File Storage:**
- Local filesystem only - no cloud storage integration
- Mock data persisted to browser localStorage at versioned key `sportzal:mock:v1`

**Caching:**
- TanStack Query 5.59.0 (React Query) - client-side caching of server state
  - Default staleTime: 30,000ms (30 seconds)
  - refetchOnWindowFocus: disabled
  - Retry policy: 1 attempt on queries, 0 on mutations
  - Configuration: `src/app/queryClient.ts`
- localStorage (Zustand) - persists session and UI preferences
  - `sportzal:session:v1` - Session state (role)
  - `sportzal:ui:v1` - UI preferences (theme)

## Authentication & Identity

**Auth Provider:**
- Custom in-memory session management (v1)
- Implementation: `src/shared/session/store.ts` (Zustand with localStorage persistence)
- Session state: `{ role: 'owner' | 'reception' }`
- Roles enforce access via `can(role, action, resource)` function at `src/shared/session/can.ts`
- No real auth service (OAuth, SAML, custom backend auth) — mock services enforce role-based access

**Real Auth (Deferred to Phase 7+):**
- When backend auth is added, only `src/shared/session/store.ts` and `src/shared/api/services/http/**` change
- UI, routes, and role gates remain unchanged (SessionState interface stable)

## Monitoring & Observability

**Error Tracking:**
- None installed
- Errors handled locally:
  - Critical errors: inline alerts or dialogs (not toasts)
  - Non-critical acks: Sonner toasts for user feedback

**Logs:**
- console.log/warn/error (browser dev console)
- Single environment-check log in `src/shared/api/config/env.ts` if `VITE_API_MODE` is invalid

**Analytics:**
- Not implemented

## CI/CD & Deployment

**Hosting:**
- Not specified (frontend-only v1)
- Static site delivery (any CDN, GitHub Pages, Vercel, Netlify, etc.)

**CI Pipeline:**
- Not configured (no GitHub Actions, GitLab CI, etc.)
- Manual build: `pnpm build` (tsc + vite build)

**Build Output:**
- `dist/` directory (Vite default)
- Entry: `index.html` with inline theme bootstrap script

## Environment Configuration

**Required env vars:**
- `VITE_API_MODE` - 'mock' (default) or 'http' (deferred)
  - Defaults to 'mock' in development (`.env.development`)
  - Validated in `src/shared/api/config/env.ts`

**Secrets location:**
- `.env.example` - Template (committed, non-sensitive)
- `.env.development` - Development overrides (not committed, local-only)
- No secrets currently needed (v1 has no real integrations)

**Configuration Files:**
- `.env.example` - Template for required vars
- `.env.development` - Local development env

## Webhooks & Callbacks

**Incoming:**
- None (frontend-only, no server)

**Outgoing:**
- None (no real API in v1)

## Third-Party Registries & Themes

**shadcn/ui + reui.io:**
- Primary registry: shadcn/ui (new-york style, components.json points to `@/shared/ui`)
- Secondary registry: `@reui` at `https://reui.io/r/{style}/{name}.json` (configured in `components.json`)
- Components: manually copied into `src/shared/ui/` (not npm package)

**React Component Ecosystem:**
- TanStack ecosystem (Router, Query, Table) - upstream React libraries, not external integrations
- Radix UI - upstream primitive components (not external integrations)

## Test Data Generation

**Faker:**
- `@faker-js/faker` v9.3.0 with fixed seed (42) for reproducible mock data
- Used by mock service implementations (populated in later phases)
- Ensures same data on every dev session and test run

---

*Integration audit: 2026-04-30*
