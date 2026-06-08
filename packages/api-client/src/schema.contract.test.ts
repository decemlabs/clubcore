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

// --- v1.5 surface (Phase 40 HANDOFF-02) --------------------------------
// operationIds intentionally NOT pinned — see 35-CONTEXT D-35-07.
// GET /api/v1/bookings/{booking_id} is shipped per
// apps/backend/app/modules/bookings/router.py:320-328 — committed to 11.

type _TrainerSlotsListGet = AssertNonNever<paths['/api/v1/trainer-slots']['get']>
type _TrainerSlotsCreate = AssertNonNever<paths['/api/v1/trainer-slots']['post']>
type _TrainerSlotItemGet = AssertNonNever<paths['/api/v1/trainer-slots/{slot_id}']['get']>
type _TrainerSlotCancel = AssertNonNever<
  paths['/api/v1/trainer-slots/{slot_id}/cancel']['post']
>
type _BookingsCreate = AssertNonNever<paths['/api/v1/bookings']['post']>
type _BookingItemGet = AssertNonNever<paths['/api/v1/bookings/{booking_id}']['get']>
type _BookingCancel = AssertNonNever<
  paths['/api/v1/bookings/{booking_id}/cancel']['post']
>
type _ClientBookingsList = AssertNonNever<
  paths['/api/v1/clients/{client_id}/bookings']['get']
>
type _PtPackagesSalePostBody = AssertNonNever<
  paths['/api/v1/pt-packages']['post']['requestBody']
>
type _PtSessionsRecordPostBody = AssertNonNever<
  paths['/api/v1/pt-sessions']['post']['requestBody']
>
type _TrainerSlotsListOkRealised = AssertNonNever<
  paths['/api/v1/trainer-slots']['get']['responses']['200']
>

// Static checks for v1.5 surface — each must resolve to true at compile time.
const _v15Checks: [
  _TrainerSlotsListGet,
  _TrainerSlotsCreate,
  _TrainerSlotItemGet,
  _TrainerSlotCancel,
  _BookingsCreate,
  _BookingItemGet,
  _BookingCancel,
  _ClientBookingsList,
  _PtPackagesSalePostBody,
  _PtSessionsRecordPostBody,
  _TrainerSlotsListOkRealised,
] = [true, true, true, true, true, true, true, true, true, true, true]

// --- v1.6 surface — Multi-user admin (Phase 43 USERS-*) ---------------
// All v1.6 USERS-* paths are LANDED (Phase 43 shipped); hard non-never guards.
// Path-truth (verified against regenerated schema.d.ts at Wave 1):
//   - deactivate / reactivate use PATCH (not POST — plan template was stale).
//   - DELETE /users/{user_id} returns 204 (soft-delete via deleted_at).
type _UsersListGet = AssertNonNever<paths['/api/v1/users']['get']>
type _UsersCreatePost = AssertNonNever<paths['/api/v1/users']['post']>
type _UsersDeactivatePatch = AssertNonNever<
  paths['/api/v1/users/{user_id}/deactivate']['patch']
>
type _UsersReactivatePatch = AssertNonNever<
  paths['/api/v1/users/{user_id}/reactivate']['patch']
>
type _UsersDelete = AssertNonNever<paths['/api/v1/users/{user_id}']['delete']>

// --- v1.6 surface — Password reset + invitation accept (Phase 44 RESET-*) ---
// All v1.6 RESET-* paths are LANDED (Phase 44 shipped); hard non-never guards.
type _InvitationAcceptPost = AssertNonNever<
  paths['/api/v1/users/invitations/accept']['post']
>
type _InvitationRevokePost = AssertNonNever<
  paths['/api/v1/users/invitations/{token_id}/revoke']['post']
>
type _PasswordResetRequestPost = AssertNonNever<
  paths['/api/v1/auth/password-reset/request']['post']
>
type _PasswordResetConfirmPost = AssertNonNever<
  paths['/api/v1/auth/password-reset/confirm']['post']
>

// --- v1.6 surface — Email channel (Phase 42 AUTH-EM-* + EMAIL-*) ----------
// All v1.6 EMAIL paths are LANDED (Phase 42 shipped); hard non-never guards.
// /_internal/email/webhook IS included here per D-46-07 — internal-but-typed.
// Path-truth: live router exposes /api/v1/auth/otp/request (NOT /api/v1/otp/request).
// Webhook returns 202 (Postbox protocol) with no JSON requestBody (HMAC raw-body).
type _InternalEmailWebhookPost = AssertNonNever<
  paths['/api/v1/_internal/email/webhook']['post']
>
type _OtpRequestChannelBody = AssertNonNever<
  paths['/api/v1/auth/otp/request']['post']['requestBody']
>

// Static checks for v1.6 USERS surface (Phase 43) — each must resolve to true.
const _v16UsersChecks: [
  _UsersListGet,
  _UsersCreatePost,
  _UsersDeactivatePatch,
  _UsersReactivatePatch,
  _UsersDelete,
] = [true, true, true, true, true]

// Static checks for v1.6 RESET surface (Phase 44) — each must resolve to true.
const _v16ResetChecks: [
  _InvitationAcceptPost,
  _InvitationRevokePost,
  _PasswordResetRequestPost,
  _PasswordResetConfirmPost,
] = [true, true, true, true]

// Static checks for v1.6 EMAIL surface (Phase 42 + AUTH-EM-01) — D-46-07.
// _OtpRequestChannelBody anchors the AUTH-EM-01 channel-parameter surfacing
// (proves the regenerated body type accepts the new `channel` discriminator).
const _v16EmailChecks: [
  _InternalEmailWebhookPost,
  _OtpRequestChannelBody,
] = [true, true]

// --- v1.8 surface — Reports + Audit Log read API (Phases 54-57) ---------
// All 8 v1.8 paths are LANDED post-regen (Task 1/Task 2 of Phase 57);
// hard AssertNonNever guards (no HasPath<> conditional probes).
// 4 JSON GETs: hard AssertNonNever on the GET operation.
// 4 CSV GETs: 2xx-reachability anchor via ['get']['responses']['200']
// following the _v15Checks _TrainerSlotsListOkRealised example.
type _ReportsRevenueGet = AssertNonNever<paths['/api/v1/reports/revenue']['get']>
type _ReportsClientsGet = AssertNonNever<paths['/api/v1/reports/clients']['get']>
type _ReportsVisitsGet = AssertNonNever<paths['/api/v1/reports/visits']['get']>
type _AuditLogGet = AssertNonNever<paths['/api/v1/audit-log']['get']>
type _ReportsRevenueCsvGet = AssertNonNever<
  paths['/api/v1/reports/revenue.csv']['get']['responses']['200']
>
type _ReportsClientsCsvGet = AssertNonNever<
  paths['/api/v1/reports/clients.csv']['get']['responses']['200']
>
type _ReportsVisitsCsvGet = AssertNonNever<
  paths['/api/v1/reports/visits.csv']['get']['responses']['200']
>
type _AuditLogCsvGet = AssertNonNever<
  paths['/api/v1/audit-log.csv']['get']['responses']['200']
>

// Static checks for v1.8 surface — each must resolve to true at compile time.
const _v18Checks: [
  _ReportsRevenueGet,
  _ReportsClientsGet,
  _ReportsVisitsGet,
  _AuditLogGet,
  _ReportsRevenueCsvGet,
  _ReportsClientsCsvGet,
  _ReportsVisitsCsvGet,
  _AuditLogCsvGet,
] = [true, true, true, true, true, true, true, true]

// --- v1.9 surface (Trainers Complete — Phases 58-60) -------------------
// Payroll (Phase 58 INFRA-15 / PAY-01..06):
type _PayrollTrainerConfigPut = AssertNonNever<
  paths['/api/v1/payroll/trainer-configs/{trainer_id}']['put']
>
type _PayrollTrainerConfigGet = AssertNonNever<
  paths['/api/v1/payroll/trainer-configs/{trainer_id}']['get']
>
type _PayrollPreviewGet = AssertNonNever<paths['/api/v1/payroll/preview']['get']>
type _PayrollAccrualPost = AssertNonNever<
  paths['/api/v1/payroll/accruals']['post']['responses']['201']
>
type _PayrollAccrualList = AssertNonNever<paths['/api/v1/payroll/accruals']['get']>
type _PayrollAccrualMarkPaidPost = AssertNonNever<
  paths['/api/v1/payroll/accruals/{accrual_id}/mark-paid']['post']
>

// Schedule v1.9 (Phase 59 REC-01..04 / TOFF-01..03):
type _RecurringTemplatePost = AssertNonNever<
  paths['/api/v1/recurring-templates']['post']['responses']['201']
>
type _RecurringTemplateDeactivatePost = AssertNonNever<
  paths['/api/v1/recurring-templates/{template_id}/deactivate']['post']
>
type _RecurringTemplateList = AssertNonNever<paths['/api/v1/recurring-templates']['get']>
type _TimeOffPost = AssertNonNever<paths['/api/v1/time-off']['post']['responses']['201']>
type _TimeOffDelete = AssertNonNever<
  paths['/api/v1/time-off/{time_off_id}']['delete']['responses']['204']
>
type _TimeOffList = AssertNonNever<paths['/api/v1/time-off']['get']>

// Reports v1.9 (Phase 60 RPT-01..04):
type _ReportsTrainersGet = AssertNonNever<paths['/api/v1/reports/trainers']['get']>
type _ReportsTrainersCsvGet = AssertNonNever<paths['/api/v1/reports/trainers.csv']['get']>

// Static checks for v1.9 surface — each must resolve to true at compile time.
const _v19Checks: [
  _PayrollTrainerConfigPut,
  _PayrollTrainerConfigGet,
  _PayrollPreviewGet,
  _PayrollAccrualPost,
  _PayrollAccrualList,
  _PayrollAccrualMarkPaidPost,
  _RecurringTemplatePost,
  _RecurringTemplateDeactivatePost,
  _RecurringTemplateList,
  _TimeOffPost,
  _TimeOffDelete,
  _TimeOffList,
  _ReportsTrainersGet,
  _ReportsTrainersCsvGet,
] = [true, true, true, true, true, true, true, true, true, true, true, true, true, true]

// --- v2.0 surface — Client-Portal (Phases 68–71) --------------------------
// auth/profile (Phase 68 CAUTH-*): otp/request, otp/verify, session/refresh,
//   session/logout, GET /me, PATCH /me
// read (Phase 69 CHOME/CHIST/CPLAN): membership, home, bookings-list,
//   visit-history, pt-session-history, payment-history, plans, pt-packages, trainers
// write (Phase 70 CBOOK/CCHK): booking POST, booking cancel, slots GET,
//   qr-token GET, check-in POST
// checkout (Phase 71 CPAY): checkout/memberships, checkout/pt-packages, payment status
//
// All paths are LANDED (Phase 71 complete); hard AssertNonNever guards — no HasPath<>.
type _ClientOtpRequest = AssertNonNever<paths['/api/v1/client/otp/request']['post']>
type _ClientOtpVerify = AssertNonNever<paths['/api/v1/client/otp/verify']['post']>
type _ClientSessionRefresh = AssertNonNever<paths['/api/v1/client/session/refresh']['post']>
type _ClientSessionLogout = AssertNonNever<paths['/api/v1/client/session/logout']['post']>
type _ClientGetMe = AssertNonNever<paths['/api/v1/client/me']['get']>
type _ClientPatchMe = AssertNonNever<paths['/api/v1/client/me']['patch']>
type _ClientGetMembership = AssertNonNever<paths['/api/v1/client/membership']['get']>
type _ClientGetHome = AssertNonNever<paths['/api/v1/client/home']['get']>
type _ClientListBookings = AssertNonNever<paths['/api/v1/client/bookings']['get']>
type _ClientListVisitHistory = AssertNonNever<paths['/api/v1/client/history/visits']['get']>
type _ClientListPtSessionHistory = AssertNonNever<paths['/api/v1/client/history/pt-sessions']['get']>
type _ClientListPaymentHistory = AssertNonNever<paths['/api/v1/client/history/payments']['get']>
type _ClientListPlans = AssertNonNever<paths['/api/v1/client/plans']['get']>
type _ClientListPtPackages = AssertNonNever<paths['/api/v1/client/pt-packages']['get']>
type _ClientListTrainers = AssertNonNever<paths['/api/v1/client/trainers']['get']>
type _ClientCreateBooking = AssertNonNever<paths['/api/v1/client/booking']['post']>
type _ClientCancelBooking = AssertNonNever<paths['/api/v1/client/booking/{booking_id}/cancel']['post']>
type _ClientListSlots = AssertNonNever<paths['/api/v1/client/slots']['get']>
type _ClientGetQrToken = AssertNonNever<paths['/api/v1/client/qr-token']['get']>
type _ClientCheckIn = AssertNonNever<paths['/api/v1/client/check-in']['post']>
type _ClientCheckoutMembership = AssertNonNever<paths['/api/v1/client/checkout/memberships/{plan_id}']['post']>
type _ClientCheckoutPtPackage = AssertNonNever<paths['/api/v1/client/checkout/pt-packages/{plan_id}']['post']>
type _ClientGetPaymentStatus = AssertNonNever<paths['/api/v1/client/payments/{payment_id}/status']['get']>

// Static checks for v2.0 Client-Portal surface — each must resolve to true.
const _v20Checks: [
  _ClientOtpRequest,
  _ClientOtpVerify,
  _ClientSessionRefresh,
  _ClientSessionLogout,
  _ClientGetMe,
  _ClientPatchMe,
  _ClientGetMembership,
  _ClientGetHome,
  _ClientListBookings,
  _ClientListVisitHistory,
  _ClientListPtSessionHistory,
  _ClientListPaymentHistory,
  _ClientListPlans,
  _ClientListPtPackages,
  _ClientListTrainers,
  _ClientCreateBooking,
  _ClientCancelBooking,
  _ClientListSlots,
  _ClientGetQrToken,
  _ClientCheckIn,
  _ClientCheckoutMembership,
  _ClientCheckoutPtPackage,
  _ClientGetPaymentStatus,
] = [
  true, true, true, true, true, true, true, true,
  true, true, true, true, true, true, true, true,
  true, true, true, true, true, true, true,
]

// --- v2.3 surface (Loyalty + Redemption — Phases 82-84) -------------------
// Three new v2.3 client/staff paths + the checkout-body loyaltyRedeemKopecks
// field carrier (REDM-01). Phase 84 (autopay) adds no new client HTTP paths;
// the only contract surface is the additive confirmation_type='autopay' enum
// value — no additional path guard is required.
//
// Path set (verified against the regenerated openapi.json):
//   GET  /api/v1/client/loyalty/balance       (Phase 82, LOYL-01)
//   GET  /api/v1/client/loyalty/history       (Phase 82, LOYL-02)
//   POST /api/v1/clients/{client_id}/loyalty/grant  (Phase 82, ACCR-02 — owner-only)
//   POST /api/v1/client/checkout/memberships/{plan_id} requestBody (Phase 83, REDM-01)
//     — proves the REDM-01 loyaltyRedeemKopecks field is present on the checkout body
type _ClientLoyaltyBalanceGet = AssertNonNever<paths['/api/v1/client/loyalty/balance']['get']>
type _ClientLoyaltyHistoryGet = AssertNonNever<paths['/api/v1/client/loyalty/history']['get']>
type _ClientLoyaltyGrantPost = AssertNonNever<
  paths['/api/v1/clients/{client_id}/loyalty/grant']['post']
>
type _ClientCheckoutLoyaltyField = AssertNonNever<
  NonNullable<
    paths['/api/v1/client/checkout/memberships/{plan_id}']['post']['requestBody']
  >['content']['application/json']['loyaltyRedeemKopecks']
>

const _v23Checks: [
  _ClientLoyaltyBalanceGet,
  _ClientLoyaltyHistoryGet,
  _ClientLoyaltyGrantPost,
  _ClientCheckoutLoyaltyField,
] = [true, true, true, true]

// --- v2.4 surface (Content & Communication — Gym / Inbox / Trainer-detail, Phases 86-88) ---
// Seven new v2.4 paths + the trainers-PATCH requestBody realisation guard (8 entries total).
//
// Path set (verified against the regenerated openapi.json):
//   GET   /api/v1/client/gym                                     (Phase 86, GYM-01)
//   PUT   /api/v1/gym                                            (Phase 86, GYM-02 — owner write, additive staff path)
//   GET   /api/v1/client/notifications                           (Phase 87, INBOX-01)
//   PATCH /api/v1/client/notifications/{notification_id}/read    (Phase 87, INBOX-02)
//   PATCH /api/v1/client/notifications/read-all                  (Phase 87, INBOX-02)
//   POST  /api/v1/client/push-tokens                             (Phase 87, INBOX-04)
//   GET   /api/v1/client/trainers/{trainer_id}                   (Phase 88, TRNR-01)
//   PATCH /api/v1/trainers/{trainer_id} requestBody carrier      (Phase 88, TRNR-02 — additive bio/specialization/photoUrl on TrainerUpdateRequest)
type _ClientGymGet = AssertNonNever<paths['/api/v1/client/gym']['get']>
type _OwnerGymPut = AssertNonNever<paths['/api/v1/gym']['put']>
type _ClientNotificationsGet = AssertNonNever<paths['/api/v1/client/notifications']['get']>
type _ClientNotificationReadPatch = AssertNonNever<
  paths['/api/v1/client/notifications/{notification_id}/read']['patch']
>
type _ClientNotificationsReadAllPatch = AssertNonNever<
  paths['/api/v1/client/notifications/read-all']['patch']
>
type _ClientPushTokensPost = AssertNonNever<paths['/api/v1/client/push-tokens']['post']>
type _ClientTrainerDetailGet = AssertNonNever<paths['/api/v1/client/trainers/{trainer_id}']['get']>
type _TrainerPatchBodyRealised = AssertNonNever<
  paths['/api/v1/trainers/{trainer_id}']['patch']['requestBody']
>

const _v24Checks: [
  _ClientGymGet,
  _OwnerGymPut,
  _ClientNotificationsGet,
  _ClientNotificationReadPatch,
  _ClientNotificationsReadAllPatch,
  _ClientPushTokensPost,
  _ClientTrainerDetailGet,
  _TrainerPatchBodyRealised,
] = [true, true, true, true, true, true, true, true]

// --- v2.5 surface (Messaging — Phases 90-94) ---
// Seven guards: six path×method combos + POST body realisation.
//
// Path set (verified against the frozen openapi.json from Phase 95 Plan 01):
//   GET   /api/v1/client/messages                              (MSG-01)
//   PATCH /api/v1/client/messages/read                        (MSG-04)
//   POST  /api/v1/client/messages                             (MSG-02/03)
//   POST  /api/v1/client/messages requestBody                 (MSG-02 body realised)
//   POST  /api/v1/client/messages/attachments                 (ATT-01/02)
//   GET   /api/v1/client/messages/attachments/{attachment_id} (ATT-03)
//   GET   /api/v1/client/ws/messages                          (RT-01 manual WS doc)
//
// NOTE: POST /messages/attachments is multipart — guard the operation, not the body,
// to avoid a false `never` (same precedent as _v24 trainers-PATCH-body guard).
type _ClientMessagesListGet = AssertNonNever<paths['/api/v1/client/messages']['get']>
type _ClientMessagesMarkReadPatch = AssertNonNever<paths['/api/v1/client/messages/read']['patch']>
type _ClientSendMessagePost = AssertNonNever<paths['/api/v1/client/messages']['post']>
type _ClientSendMessageBody = AssertNonNever<
  paths['/api/v1/client/messages']['post']['requestBody']
>
type _ClientUploadAttachmentPost = AssertNonNever<
  paths['/api/v1/client/messages/attachments']['post']
>
type _ClientServeAttachmentGet = AssertNonNever<
  paths['/api/v1/client/messages/attachments/{attachment_id}']['get']
>
type _ClientWsMessagesGet = AssertNonNever<paths['/api/v1/client/ws/messages']['get']>

const _v25Checks: [
  _ClientMessagesListGet,
  _ClientMessagesMarkReadPatch,
  _ClientSendMessagePost,
  _ClientSendMessageBody,
  _ClientUploadAttachmentPost,
  _ClientServeAttachmentGet,
  _ClientWsMessagesGet,
] = [true, true, true, true, true, true, true]

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

  it('compiles against the regenerated v1.5 typed paths surface (Phase 40 HANDOFF-02)', () => {
    expect(_v15Checks).toHaveLength(11)
  })

  it('compiles against the regenerated v1.6 USERS surface (Phase 43)', () => {
    expect(_v16UsersChecks).toHaveLength(5)
  })

  it('compiles against the regenerated v1.6 RESET surface (Phase 44)', () => {
    expect(_v16ResetChecks).toHaveLength(4)
  })

  it('compiles against the regenerated v1.6 EMAIL surface (Phase 42 + AUTH-EM-01 channel)', () => {
    expect(_v16EmailChecks).toHaveLength(2)
  })

  it('compiles against the regenerated v1.8 reports/audit surface (Phases 55-57)', () => {
    expect(_v18Checks).toHaveLength(8)
  })

  it('compiles against the regenerated v1.9 trainers surface (Phases 58-60)', () => {
    expect(_v19Checks).toHaveLength(14)
  })

  it('compiles against the regenerated v2.0 Client-Portal surface (Phases 68-71)', () => {
    expect(_v20Checks).toHaveLength(23)
  })

  it('compiles against the regenerated v2.3 Loyalty surface (Phases 82-84)', () => {
    expect(_v23Checks).toEqual([true, true, true, true])
  })

  it('compiles against the regenerated v2.4 Content & Communication surface (Gym / Inbox / Trainer-detail — Phases 86-88)', () => {
    expect(_v24Checks).toHaveLength(8)
  })

  it('compiles against the regenerated v2.5 Messaging surface (Phases 90-94)', () => {
    expect(_v25Checks).toHaveLength(7)
  })
})
