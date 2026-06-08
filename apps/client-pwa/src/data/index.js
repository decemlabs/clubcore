// Phase 71: React Query hooks are the primary data source for wired screens.
// Re-exported from the single mock→real swap point (D-71-07).
// All net-new screens have graduated (D-71-09 fully resolved as of Phase 98):
//   GymInfoSheet (Phase 86), NotificationsSheet (Phase 87), TrainerDetailSheet (Phase 88),
//   ChatScreen (Phase 94), ReferralSheet (Phase 98) — all import freely via @/data alias.
//
// RETAINED MOCKS (post Plan 06 wiring):
//   - UPCOMING_BOOKING → BookingManageSheet.jsx (manage sheet; read-only display)
//   - VISIT_HISTORY, TRAINING_HISTORY → HistorySheets.jsx (detail sheet from ProfileScreen)
//
// REMOVED in Plan 06 (BookScreen + QRSheet wired to real backend):
//   - CALENDAR, TIME_SLOTS, BUSY_SLOTS → replaced by useClientAvailableSlots
// NOTE: TRAINERS was NOT removed — retained for TweaksRoot.jsx dev panel (trainer-detail tweak)
//
// REMOVED in Plan 05 (screens wired to real backend):
//   - NOTIFICATIONS, GYM_INFO, TRAINER_CANCEL → HomeScreen (inlined as static demo data)
//   - VISIT_HISTORY, TRAINING_HISTORY, PURCHASE_HISTORY → ProfileScreen
//   - PLANS, PLAN_FEATURES → PlansSheet

// ─── React Query hooks (swap seam — D-71-07) ──────────────────────────────
export {
  ApiError,
  // Plan 07: auth probe + OTP login hooks
  useClientMe,
  useOtpRequest,
  useOtpVerify,
  useClientHome,
  useClientMembership,
  useClientPlans,
  useClientTrainers,
  useClientPtPackages,
  useClientVisitHistory,
  useClientPtHistory,
  useClientPaymentHistory,
  useClientPaymentStatus,
  useClientCheckoutMembership,
  useClientCheckoutPtPackage,
  usePromoValidate,
  // Plan 06: Book/QR hooks
  useClientBookings,
  useClientAvailableSlots,
  useCreateBooking,
  useCancelBooking,
  useRescheduleBooking,
  useClientQrToken,
  // Plan 999.5-04: onboarding profile mutations
  useUpdateClientProfile,
  useCompleteOnboarding,
  useUpdateClientEmail,
  // Phase-81 WACT-02 + PAYM-05: weekly activity + payment method hooks
  useClientWeeklyActivity,
  useClientPaymentMethod,
  useUnlinkPaymentMethod,
  usePatchAutopay,
  // Phase-82 LOYL-01 + LOYL-02: loyalty balance + history hooks
  useClientLoyaltyBalance,
  useClientLoyaltyHistory,
  // Phase-86 GYM-01: gym info hook
  useClientGymInfo,
  // Phase-87 INBOX-05: notifications hooks
  useClientNotifications,
  useMarkNotificationRead,
  useMarkAllNotificationsRead,
  // Phase-88 TRNR-04: trainer detail hook
  useClientTrainerDetail,
  // Phase-94 PWA-01: messaging hooks
  useClientMessages,
  useSendMessage,
  useUploadAttachment,
  useMarkMessagesRead,
  // Phase-98 REFER-06: referral summary hook
  useClientReferralSummary,
} from '../lib/clientQueries'

// ─── Legacy mock constants (retained for non-wired consumers) ─────────────
export { UPCOMING_BOOKING } from './booking.js'
// Retained for HistorySheets.jsx (detail sheet opened from ProfileScreen)
export { VISIT_HISTORY, TRAINING_HISTORY } from './history.js'
// Retained for TweaksRoot.jsx dev panel (trainer-detail tweak button)
export { TRAINERS } from './trainers.js'
// Retained for BookingManageSheet.jsx (reschedule UI — Plan 06 scope boundary)
export { CALENDAR, TIME_SLOTS, BUSY_SLOTS } from './calendar.js'
