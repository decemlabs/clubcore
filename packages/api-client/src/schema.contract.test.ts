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

// --- Phase 23 CD-05: sessions positive assertions (Phase 23 merged) ----
// Both /sessions GET and /sessions/{family_id}/revoke POST must be present.
// These assertions fail the TypeScript build if codegen does not emit the paths.
type _GetSessions = AssertNonNever<paths['/api/v1/auth/sessions']['get']>
type _PostRevokeSession = AssertNonNever<
  paths['/api/v1/auth/sessions/{family_id}/revoke']['post']
>
const _sessionsGetCheck: _GetSessions = true
const _sessionsRevokeCheck: _PostRevokeSession = true

// --- v1.4 surface (Phases 31-34, backend-only handoff) -----------------
// operationIds intentionally NOT pinned — see 35-CONTEXT D-35-07. The
// forward-guard checks paths + methods + body realisation + 2xx
// reachability; operation-id naming is a v1.5 hygiene topic (Postman
// collection + curated TS client method names land then).
//
// All v1.4 paths are LANDED (Phases 31-34 shipped); no HasPath<...>
// conditional probes — every assertion is a hard AssertNonNever.

// --- v1.4 trainers (Phase 31) ---
type _TrainersListGet = AssertNonNever<paths['/api/v1/trainers']['get']>
type _TrainersListPost = AssertNonNever<paths['/api/v1/trainers']['post']>
type _TrainersItemGet = AssertNonNever<paths['/api/v1/trainers/{trainer_id}']['get']>
type _TrainersItemPatch = AssertNonNever<paths['/api/v1/trainers/{trainer_id}']['patch']>
type _TrainersItemDelete = AssertNonNever<paths['/api/v1/trainers/{trainer_id}']['delete']>
type _TrainersCreateBody = AssertNonNever<paths['/api/v1/trainers']['post']['requestBody']>
type _TrainersListOkRealised = AssertNonNever<paths['/api/v1/trainers']['get']['responses']['200']>

// --- v1.4 payments (Phase 32) ---
type _PaymentsListGet = AssertNonNever<paths['/api/v1/payments']['get']>
type _PaymentsByClientGet = AssertNonNever<paths['/api/v1/payments/by-client/{client_id}']['get']>
type _PaymentsByMembershipGet = AssertNonNever<
  paths['/api/v1/payments/by-membership/{membership_id}']['get']
>
type _PaymentsListOkRealised = AssertNonNever<paths['/api/v1/payments']['get']['responses']['200']>

// --- v1.4 membership refund (Phase 32) ---
type _MembershipRefundPost = AssertNonNever<
  paths['/api/v1/memberships/{membership_id}/refund']['post']
>
type _MembershipRefundBody = AssertNonNever<
  paths['/api/v1/memberships/{membership_id}/refund']['post']['requestBody']
>

// --- v1.4 pt-package-plans (Phase 33) ---
type _PtPlansListGet = AssertNonNever<paths['/api/v1/pt-package-plans']['get']>
type _PtPlansListPost = AssertNonNever<paths['/api/v1/pt-package-plans']['post']>
type _PtPlansItemGet = AssertNonNever<paths['/api/v1/pt-package-plans/{plan_id}']['get']>
type _PtPlansItemPatch = AssertNonNever<paths['/api/v1/pt-package-plans/{plan_id}']['patch']>
type _PtPlansItemDelete = AssertNonNever<paths['/api/v1/pt-package-plans/{plan_id}']['delete']>
type _PtPlansCreateBody = AssertNonNever<paths['/api/v1/pt-package-plans']['post']['requestBody']>
type _PtPlansListOkRealised = AssertNonNever<
  paths['/api/v1/pt-package-plans']['get']['responses']['200']
>

// --- v1.4 pt-packages (Phase 33) ---
type _PtPackagesListGet = AssertNonNever<paths['/api/v1/pt-packages']['get']>
type _PtPackagesListPost = AssertNonNever<paths['/api/v1/pt-packages']['post']>
type _PtPackagesItemGet = AssertNonNever<paths['/api/v1/pt-packages/{pt_package_id}']['get']>
type _PtPackagesCancelPost = AssertNonNever<
  paths['/api/v1/pt-packages/{pt_package_id}/cancel']['post']
>
type _PtPackagesRefundPost = AssertNonNever<
  paths['/api/v1/pt-packages/{pt_package_id}/refund']['post']
>
type _PtPackagesCreateBody = AssertNonNever<paths['/api/v1/pt-packages']['post']['requestBody']>
type _PtPackagesRefundBody = AssertNonNever<
  paths['/api/v1/pt-packages/{pt_package_id}/refund']['post']['requestBody']
>
type _PtPackagesListOkRealised = AssertNonNever<
  paths['/api/v1/pt-packages']['get']['responses']['200']
>

// --- v1.4 pt-sessions (Phase 34) ---
// NOTE: /api/v1/pt-sessions exposes POST only (record); the list/history surface
// lives at /api/v1/pt-packages/{pt_package_id}/sessions GET (D-34-08 subject-side
// ownership). 2xx-reachability anchor for this module is the by-package list 200.
type _PtSessionsItemGet = AssertNonNever<paths['/api/v1/pt-sessions/{pt_session_id}']['get']>
type _PtSessionsRecordPost = AssertNonNever<paths['/api/v1/pt-sessions']['post']>
type _PtSessionsCancelPost = AssertNonNever<
  paths['/api/v1/pt-sessions/{pt_session_id}/cancel']['post']
>
type _PtSessionsByPackageGet = AssertNonNever<
  paths['/api/v1/pt-packages/{pt_package_id}/sessions']['get']
>
type _PtSessionsCreateBody = AssertNonNever<paths['/api/v1/pt-sessions']['post']['requestBody']>
type _PtSessionsCancelBody = AssertNonNever<
  paths['/api/v1/pt-sessions/{pt_session_id}/cancel']['post']['requestBody']
>
type _PtSessionsRecordCreatedRealised = AssertNonNever<
  paths['/api/v1/pt-sessions']['post']['responses']['201']
>
type _PtSessionsByPackageOkRealised = AssertNonNever<
  paths['/api/v1/pt-packages/{pt_package_id}/sessions']['get']['responses']['200']
>

// Static checks for v1.4 surface — each must resolve to true at compile time.
const _v14Checks: [
  _TrainersListGet,
  _TrainersListPost,
  _TrainersItemGet,
  _TrainersItemPatch,
  _TrainersItemDelete,
  _TrainersCreateBody,
  _TrainersListOkRealised,
  _PaymentsListGet,
  _PaymentsByClientGet,
  _PaymentsByMembershipGet,
  _PaymentsListOkRealised,
  _MembershipRefundPost,
  _MembershipRefundBody,
  _PtPlansListGet,
  _PtPlansListPost,
  _PtPlansItemGet,
  _PtPlansItemPatch,
  _PtPlansItemDelete,
  _PtPlansCreateBody,
  _PtPlansListOkRealised,
  _PtPackagesListGet,
  _PtPackagesListPost,
  _PtPackagesItemGet,
  _PtPackagesCancelPost,
  _PtPackagesRefundPost,
  _PtPackagesCreateBody,
  _PtPackagesRefundBody,
  _PtPackagesListOkRealised,
  _PtSessionsItemGet,
  _PtSessionsRecordPost,
  _PtSessionsCancelPost,
  _PtSessionsByPackageGet,
  _PtSessionsCreateBody,
  _PtSessionsCancelBody,
  _PtSessionsRecordCreatedRealised,
  _PtSessionsByPackageOkRealised,
] = [
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
  true,
]

describe('schema.contract', () => {
  it('compiles against the regenerated v1.2 typed paths surface', () => {
    // The real assertions are above (compile-time). This block exists so
    // vitest counts the file. We touch the type-checks at runtime to
    // keep noUnusedLocals happy.
    expect(_checks).toHaveLength(10)
    expect(_sessionsCheck).toBe(true)
    expect(_sessionsGetCheck).toBe(true)
    expect(_sessionsRevokeCheck).toBe(true)
  })

  it('compiles against the regenerated v1.4 typed paths surface (Phases 31-34, backend-only handoff)', () => {
    expect(_v14Checks).toHaveLength(36)
  })
})
