/**
 * Dashboard domain TanStack Query hooks (Phase 104-02).
 *
 * Replaces the monolithic useDashboard() mock with per-domain hooks:
 *
 *  useScheduleToday(date)       — GET /api/v1/bookings?date= (BOTH roles, no owner gate)
 *  useExpiringMemberships()     — GET /api/v1/memberships?expiring=true&withinDays=7 (BOTH roles)
 *
 * Owner-only report hooks are re-exported from features/reports (single import surface).
 * They keep their own enabled:can(role,'view','reports') gate inside features/reports/api.ts.
 *
 * T-104-04: Reception fires ZERO owner-only API calls — enforced by:
 *   1. DashboardPage not mounting owner-only cards for reception (card absence).
 *   2. Report hooks keeping their enabled:can gate (double gate).
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT).
 */
import { useQuery } from '@tanstack/react-query';
import { staffRequest, ApiError } from '@/api/client';
import { BookingsListResponseSchema } from '@/features/bookings/schemas';
import { MembershipsListResponseSchema } from '@/features/memberships/schemas';

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const dashboardKeys = {
  all: ['dashboard'] as const,
  scheduleToday: (date: string) => ['dashboard', 'schedule', date] as const,
  expiringMemberships: ['dashboard', 'expiring'] as const,
};

// ---------------------------------------------------------------------------
// Both-role hooks (no owner gate)
// ---------------------------------------------------------------------------

/**
 * Bookings for a given date (today's schedule).
 * GET /api/v1/bookings?date={date} — both roles, no enabled guard.
 */
export function useScheduleToday(date: string) {
  return useQuery({
    queryKey: dashboardKeys.scheduleToday(date),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/bookings', {
        query: { date },
      });
      return BookingsListResponseSchema.parse(raw).data;
    },
    staleTime: 30_000,
  });
}

/**
 * Memberships expiring within 7 days.
 * GET /api/v1/memberships?expiring=true&withinDays=7 — both roles, no enabled guard.
 */
export function useExpiringMemberships() {
  return useQuery({
    queryKey: dashboardKeys.expiringMemberships,
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/memberships', {
        query: { expiring: 'true', withinDays: '7' },
      });
      return MembershipsListResponseSchema.parse(raw).data;
    },
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Re-export owner-only report hooks (single import surface for DashboardPage)
// Owner-gating via enabled:can(role,'view','reports') lives in features/reports/api.ts
// ---------------------------------------------------------------------------

export {
  useRevenueReport,
  useVisitsReport,
  useClientsReport,
  useTrainersReport,
} from '@/features/reports/api';

export { ApiError };
