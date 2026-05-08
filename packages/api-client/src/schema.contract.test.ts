/**
 * Schema contract test (Phase 21 D-21-4).
 *
 * Type-level smoke test — most assertions compile or fail at tsc time.
 * The single it(...) block exists so vitest counts the file as a test.
 *
 * Sessions paths (Phase 23) are probed conditionally per D-21-2.
 */
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

// Static checks: each must resolve to true at compile time.
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

// --- Phase 21 D-21-2: sessions conditional probe -----------------------
// Sessions paths land in Phase 23. The conditional probe stays green
// whether or not Phase 23 has merged. No hardcoded path-list assertions.
type _HasSessions = HasPath<'/api/v1/auth/sessions'>
type _SessionsProbe = _HasSessions extends true
  ? AssertNonNever<paths['/api/v1/auth/sessions' & keyof paths]['get']>
  : true
const _sessionsCheck: _SessionsProbe = true

describe('schema.contract', () => {
  it('compiles against the regenerated v1.2 typed paths surface', () => {
    // The real assertions are above (compile-time). This block exists so
    // vitest counts the file. We touch the type-checks at runtime to
    // keep noUnusedLocals happy.
    expect(_checks).toHaveLength(10)
    expect(_sessionsCheck).toBe(true)
  })
})
