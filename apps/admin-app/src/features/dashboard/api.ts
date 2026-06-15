/**
 * Dashboard domain TanStack Query hooks (Phase 104-02 / Phase 115-04).
 *
 * Replaces the monolithic useDashboard() mock with per-domain hooks:
 *
 *  useScheduleToday(date)       — GET /api/v1/bookings?date= (BOTH roles, no owner gate)
 *  useExpiringMemberships()     — GET /api/v1/memberships?expiring=true&withinDays=7 (BOTH roles)
 *  useActivityFeed(role)        — GET /api/v1/audit-log, OWNER_ONLY, mapped to ActivityFeedData
 *
 * Owner-only report hooks are re-exported from features/reports (single import surface).
 * They keep their own enabled:can(role,'view','reports') gate inside features/reports/api.ts.
 *
 * T-104-04: Reception fires ZERO owner-only API calls — enforced by:
 *   1. DashboardPage not mounting owner-only cards for reception (card absence).
 *   2. Report hooks keeping their enabled:can gate (double gate).
 * T-115-D1: useActivityFeed enabled:can(role,'view','audit-log') — reception never fetches.
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT).
 */
import { useQuery } from '@tanstack/react-query';
import { staffRequest, ApiError } from '@/api/client';
import { BookingsListResponseSchema } from '@/features/bookings/schemas';
import { MembershipsListResponseSchema } from '@/features/memberships/schemas';
import { AuditLogResponseSchema } from '@/features/audit/schemas';
import { can } from '@/shared/session/can';
import { mapAuditToActivityFeed } from './audit-activity';
import type { Role } from '@/shared/session/types';

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const dashboardKeys = {
  all: ['dashboard'] as const,
  scheduleToday: (date: string) => ['dashboard', 'schedule', date] as const,
  expiringMemberships: ['dashboard', 'expiring'] as const,
  activityFeed: ['dashboard', 'activity-feed'] as const,
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
// Owner-only activity feed hook (audit-log → ActivityFeedData)
// T-115-D1: enabled:can(role,'view','audit-log') — reception never fetches.
// Import boundary: features/dashboard → features/audit is permitted by ESLint config
// (only pages/layouts/components → api/client.ts is blocked).
// ---------------------------------------------------------------------------

/**
 * Owner-only activity feed from GET /api/v1/audit-log.
 * Returns the last 20 audit events mapped to ActivityFeedData for the <ActivityFeed> component.
 *
 * WR-04: accepts `role` as a parameter instead of calling useSession() internally.
 */
export function useActivityFeed(role: Role) {
  return useQuery({
    queryKey: dashboardKeys.activityFeed,
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/audit-log', {
        query: { pageSize: '20' },
      });
      return mapAuditToActivityFeed(AuditLogResponseSchema.parse(raw).data);
    },
    enabled: can(role, 'view', 'audit-log'),
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
