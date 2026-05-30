// Phase 71: React Query hooks are the primary data source for wired screens.
// Re-exported from the single mock→real swap point (D-71-07).
// Net-new screens (ChatScreen, ReferralSheet, TrainerDetailSheet, NotificationsSheet,
// GymInfoSheet) must NOT import from this file — ESLint boundary enforced (D-71-09).
//
// Mock constants below are retained until the corresponding wired screens (HomeScreen,
// ProfileScreen, BookScreen, PlansSheet, CheckoutSheet, QRSheet) are wired in Plans 05/06
// and their imports are removed. Each mock exported here documents its wiring plan.
//
// RETAINED MOCKS (pending Plan 05 / Plan 06 wiring):
//   - TRAINERS, CALENDAR, TIME_SLOTS, BUSY_SLOTS → BookScreen (Plan 06)
//   - NOTIFICATIONS, GYM_INFO, TRAINER_CANCEL, UPCOMING_BOOKING → HomeScreen (Plan 05)
//   - VISIT_HISTORY, TRAINING_HISTORY, PURCHASE_HISTORY → ProfileScreen (Plan 05 Task 1a)
//   - PLANS, PLAN_FEATURES → PlansSheet (Plan 05)
//   - CONVERSATIONS → App.jsx (net-new scope; retained for App.jsx tab badge only)
//
// REMOVE each mock export as its consumer is wired.

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
export { NOTIFICATIONS } from './notifications.js'
export { CONVERSATIONS } from './conversations.js'
export { VISIT_HISTORY, TRAINING_HISTORY, PURCHASE_HISTORY } from './history.js'
export { PLANS, PLAN_FEATURES } from './plans.js'
export { TRAINER_CANCEL, UPCOMING_BOOKING } from './booking.js'
export { GYM_INFO } from './gym.js'
