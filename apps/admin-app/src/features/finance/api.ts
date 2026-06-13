/**
 * Finance feature API hooks (Phase 103-04 — wire from mock to real).
 *
 * Revenue tab: useRevenueReport (OWNER_ONLY, sparse → zero-filled by caller page).
 * Online-payments tab: usePaymentsLedger(filter, role) aliased as useOnlinePayments,
 *   caller passes method:'online' in the filter.
 *
 * Both are OWNER_ONLY (can(role,'view','reports') / can(role,'view','payments')).
 * Reception makes ZERO API calls — Finance page Lock-guards before any hook fires.
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) for ESLint import boundary.
 */
export { useRevenueReport } from '@/features/reports/api';
export { usePaymentsLedger as useOnlinePayments } from '@/features/payments/api';
export { ApiError } from '@/features/reports/api';
