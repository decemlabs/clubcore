// Phase 71: React Query hooks are the primary data source for wired screens.
// Re-exported from the single mock→real swap point (D-71-07).
// Net-new screens (ChatScreen, ReferralSheet, TrainerDetailSheet, NotificationsSheet,
// GymInfoSheet) must NOT import from this file — ESLint boundary enforced (D-71-09).
//
// RETAINED MOCKS (pending Plan 06 wiring):
//   - TRAINERS, CALENDAR, TIME_SLOTS, BUSY_SLOTS, UPCOMING_BOOKING → BookScreen + BookingManageSheet (Plan 06)
//   - CONVERSATIONS → App.jsx (net-new scope; retained for App.jsx tab badge only)
//
// REMOVED in Plan 05 (screens wired to real backend):
//   - NOTIFICATIONS, GYM_INFO, TRAINER_CANCEL → HomeScreen (Plan 05 Task 1a, inlined as static demo data)
//   - VISIT_HISTORY, TRAINING_HISTORY, PURCHASE_HISTORY → ProfileScreen (Plan 05 Task 1a)
//   - PLANS, PLAN_FEATURES → PlansSheet (Plan 05 Task 1a)

// ─── React Query hooks (swap seam — D-71-07) ──────────────────────────────
export {
  useClientHome,
  useClientPlans,
  useClientPtPackages,
  useClientVisitHistory,
  useClientPtHistory,
  useClientPaymentHistory,
  useClientPaymentStatus,
  useClientCheckoutMembership,
  useClientCheckoutPtPackage,
} from '../lib/clientQueries'

// ─── Legacy mock constants (retained until each screen is wired) ──────────
export { TRAINERS } from './trainers.js'
export { CALENDAR, TIME_SLOTS, BUSY_SLOTS } from './calendar.js'
export { CONVERSATIONS } from './conversations.js'
export { UPCOMING_BOOKING } from './booking.js'
// Retained for HistorySheets.jsx (detail sheet opened from ProfileScreen — Plan 06 scope)
export { VISIT_HISTORY, TRAINING_HISTORY } from './history.js'
