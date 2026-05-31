// Phase 71: React Query hooks are the primary data source for wired screens.
// Re-exported from the single mock→real swap point (D-71-07).
// Net-new screens (ChatScreen, ReferralSheet, TrainerDetailSheet, NotificationsSheet,
// GymInfoSheet) must NOT import from this file — ESLint boundary enforced (D-71-09).
//
// RETAINED MOCKS (post Plan 06 wiring):
//   - CONVERSATIONS → App.jsx (net-new scope; retained for App.jsx tab badge only)
//   - UPCOMING_BOOKING → BookingManageSheet.jsx (manage sheet; read-only display)
//   - VISIT_HISTORY, TRAINING_HISTORY → HistorySheets.jsx (detail sheet from ProfileScreen)
//
// REMOVED in Plan 06 (BookScreen + QRSheet wired to real backend):
//   - TRAINERS, CALENDAR, TIME_SLOTS, BUSY_SLOTS → replaced by useClientAvailableSlots
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
  useClientPlans,
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
  useClientQrToken,
} from '../lib/clientQueries'

// ─── Legacy mock constants (retained for non-wired consumers) ─────────────
export { CONVERSATIONS } from './conversations.js'
export { UPCOMING_BOOKING } from './booking.js'
// Retained for HistorySheets.jsx (detail sheet opened from ProfileScreen)
export { VISIT_HISTORY, TRAINING_HISTORY } from './history.js'
// Retained for TweaksRoot.jsx dev panel (trainer-detail tweak button)
export { TRAINERS } from './trainers.js'
// Retained for BookingManageSheet.jsx (reschedule UI — Plan 06 scope boundary)
export { CALENDAR, TIME_SLOTS, BUSY_SLOTS } from './calendar.js'
