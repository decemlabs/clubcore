/**
 * Reports domain zero-fill utilities (Phase 103-01).
 *
 * Pure functions — no React deps. Used by Load and Finance pages to ensure
 * chart data never contains NaN or missing buckets.
 *
 * fromDate/toDate are plain 'yyyy-MM-dd' strings; parseISO at local midnight
 * is safe for day/month enumeration (no timezone arithmetic needed).
 * Do NOT import date-fns-tz (not installed).
 */
import { eachDayOfInterval, eachMonthOfInterval, parseISO, format } from 'date-fns';
import type {
  VisitsReportHourlyBucket,
  VisitsReportDailyBucket,
  RevenueBucket,
} from './schemas';

/** Fill sparse hourly array to full 24 hours (0–23). Missing hours → count: 0. */
export function fillHourlyBuckets(sparse: VisitsReportHourlyBucket[]): VisitsReportHourlyBucket[] {
  const map = new Map(sparse.map((b) => [b.hour, b.count]));
  return Array.from({ length: 24 }, (_, hour) => ({ hour, count: map.get(hour) ?? 0 }));
}

/** Fill sparse daily array to every calendar day in [fromDate, toDate]. Missing dates → count: 0. */
export function fillDailyBuckets(
  sparse: VisitsReportDailyBucket[],
  fromDate: string,
  toDate: string,
): VisitsReportDailyBucket[] {
  const map = new Map(sparse.map((b) => [b.date, b.count]));
  const days = eachDayOfInterval({ start: parseISO(fromDate), end: parseISO(toDate) });
  return days.map((d) => {
    const date = format(d, 'yyyy-MM-dd');
    return { date, count: map.get(date) ?? 0 };
  });
}

const ZERO_BUCKET: Omit<RevenueBucket, 'period'> = {
  netKopecks: 0,
  byMethod: { cash: 0, online: 0 },
  bySubjectKind: { membership: 0, ptPackage: 0 },
};

/**
 * Fill sparse revenue buckets to cover every period in [fromDate, toDate].
 * groupBy='day': one bucket per calendar day (period = 'YYYY-MM-DD').
 * groupBy='month': one bucket per calendar month (period = 'YYYY-MM').
 * Missing periods → zero-filled bucket (never NaN).
 */
export function fillRevenueBuckets(
  sparse: RevenueBucket[],
  fromDate: string,
  toDate: string,
  groupBy: 'day' | 'month',
): RevenueBucket[] {
  const map = new Map(sparse.map((b) => [b.period, b]));

  if (groupBy === 'day') {
    const days = eachDayOfInterval({ start: parseISO(fromDate), end: parseISO(toDate) });
    return days.map((d) => {
      const period = format(d, 'yyyy-MM-dd');
      return map.get(period) ?? { period, ...ZERO_BUCKET };
    });
  }

  // groupBy === 'month': enumerate every calendar month in range
  const months = eachMonthOfInterval({ start: parseISO(fromDate), end: parseISO(toDate) });
  return months.map((d) => {
    const period = format(d, 'yyyy-MM');
    return map.get(period) ?? { period, ...ZERO_BUCKET };
  });
}
