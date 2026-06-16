/**
 * Cashbox domain client-side computation utilities (Phase 103-03).
 *
 * MSK date note: `date-fns-tz` is NOT installed and this plan adds NO new dependency.
 * The backend stores and returns MSK-anchored timestamps. We derive the date by slicing
 * the 'YYYY-MM-DD' prefix of the backend `receivedAt` ISO string rather than applying
 * a local-TZ new Date() conversion that could shift the day for users in UTC+3+.
 *
 * The backend guarantees receivedAt is an ISO datetime string starting with 'YYYY-MM-DD',
 * so `receivedAt.slice(0, 10)` reliably extracts the MSK calendar date.
 * (If that assumption ever breaks, fall back to formatDateRu(receivedAt, 'yyyy-MM-dd').)
 */
import type { PaymentData } from '@/features/payments/schemas';
import type { DailyTotal } from '@/features/payments/schemas';

/**
 * Group payments by MSK calendar date and sum signed amountKopecks.
 * Refund items (negative amountKopecks) subtract from the daily total.
 * Returns results sorted ascending by date.
 *
 * @returns DailyTotal[] sorted ascending — never contains NaN.
 */
export function computeDailyTotals(items: PaymentData[]): DailyTotal[] {
  const map = new Map<string, number>();

  for (const item of items) {
    // Slice the YYYY-MM-DD prefix — MSK-anchored; see module note above.
    const date = item.receivedAt.slice(0, 10);
    map.set(date, (map.get(date) ?? 0) + item.amountKopecks);
  }

  return Array.from(map.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, totalKopecks]) => ({ date, totalKopecks }));
}
