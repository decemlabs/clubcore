/**
 * Load feature API hooks (Phase 103-03 — wire from mock to real; Phase 115-03 extended).
 *
 * Wraps useVisitsReport and applies client-side zero-fill so the
 * IntensityHeatmap / AreaTrendChart always receive complete arrays (no NaN).
 *
 * Zero-fill:
 *   - hourly: always 24 points (hours 0–23)
 *   - daily: every calendar day in [fromDate, toDate]
 *
 * OWNER_ONLY: enabled gate inherited from useVisitsReport
 * (can(role,'view','reports') inside reports/api.ts).
 *
 * No default-mock branch — removed entirely (Phase 103-03).
 *
 * Phase 115-03: re-exports useLoadNow, useCohortReport, useVisitAnomaly, useAtRiskMembers
 * for colocation with LoadPage (import from '@/features/load/api', not '@/features/reports/api').
 */
import { useVisitsReport } from '@/features/reports/api';
import { fillHourlyBuckets, fillDailyBuckets } from '@/features/reports/utils';
import type { VisitsReportQuery } from '@/features/reports/schemas';
import type { Role } from '@/shared/session/types';

export { reportsQueryKeys as loadKeys } from '@/features/reports/keys';
export { useLoadNow, useCohortReport, useVisitAnomaly, useAtRiskMembers } from '@/features/reports/api';

/**
 * Load page data hook (OWNER_ONLY, zero-filled).
 *
 * Transforms the sparse server response into complete arrays:
 * - hourly: 24 points (hours 0–23), missing → count:0
 * - daily: every day in [fromDate, toDate], missing → count:0
 * averagePerDay is passed through unchanged.
 *
 * WR-04: accepts `role` parameter, forwarded to useVisitsReport to avoid
 * the double-waterfall (session fetch → role resolved → report fetch).
 */
export function useLoad(query: VisitsReportQuery, role: Role) {
  const result = useVisitsReport(query, role);
  // Transform sparse → complete only when data is present
  const data = result.data
    ? {
        ...result.data,
        hourly: fillHourlyBuckets(result.data.hourly),
        daily: fillDailyBuckets(result.data.daily, result.data.fromDate, result.data.toDate),
      }
    : undefined;
  return { ...result, data };
}
