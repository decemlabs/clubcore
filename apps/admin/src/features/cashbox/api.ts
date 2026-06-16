/**
 * Cashbox feature API hooks (Phase 103-03 — wire from mock to real).
 *
 * Delegates to features/payments usePaymentsLedger (OWNER_ONLY).
 * Daily totals computed client-side via computeDailyTotals().
 *
 * No shift concept — removed (no backend endpoint for shifts).
 * No refund action — refund rows are READ-ONLY in the ledger.
 * No default-mock branch — the mock path is removed entirely;
 * owner gating (enabled: can(role,'view','payments')) keeps reception
 * from making any API calls.
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT).
 */
import { useSession } from '@/features/auth/api';
import { usePaymentsLedger } from '@/features/payments/api';
import { computeDailyTotals } from '@/features/cashbox/utils';
import type { PaymentsLedgerQuery } from '@/features/payments/schemas';

export { paymentsKeys as cashboxPaymentsKeys } from '@/features/payments/api';
export { ApiError } from '@/features/payments/api';

/**
 * Cashbox ledger hook (OWNER_ONLY).
 *
 * Wraps usePaymentsLedger and appends client-side dailyTotals.
 * Enabled only when session role is 'owner' (inherited from usePaymentsLedger).
 * Returns { ...queryResult, dailyTotals: DailyTotal[] }.
 */
export function useCashbox(filter: PaymentsLedgerQuery) {
  const session = useSession();
  const role = session.data?.role ?? 'reception';
  const result = usePaymentsLedger(filter, role);
  const dailyTotals = result.data ? computeDailyTotals(result.data.items) : [];
  return { ...result, dailyTotals };
}
