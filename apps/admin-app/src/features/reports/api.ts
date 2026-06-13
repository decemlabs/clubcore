/**
 * Reports domain TanStack Query hooks (Phase 103-01).
 *
 * ALL OWNER_ONLY — every hook is enabled-gated by can(role, 'view', 'reports').
 * Reception makes ZERO reports API calls (mirrors T-102-PAY-RBAC pattern).
 *
 * Buckets are SPARSE — callers must zero-fill before passing to charts.
 * Zero-fill utilities: fillHourlyBuckets(), fillDailyBuckets(), fillRevenueBuckets()
 * live in features/reports/utils.ts (pure functions, no React deps).
 *
 * IN-02: legacy useReports() + reportsKeys removed — Phase 104 is done and
 * ReportsPage.tsx no longer calls useReports() (confirmed by grep before removal).
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT).
 */
import { useQuery } from '@tanstack/react-query';
import { staffRequest, ApiError } from '@/api/client';
import { can } from '@/shared/session/can';
import { reportsQueryKeys } from './keys';
import { VisitsReportSchema, RevenueReportSchema, ClientsReportSchema, TrainersReportSchema } from './schemas';
import type { VisitsReportQuery, RevenueReportQuery, ClientsReportQuery, TrainersReportQuery } from './schemas';
import type { Role } from '@/shared/session/types';

// ---------------------------------------------------------------------------
// Phase 103 hooks — owner-gated real report endpoints
// ---------------------------------------------------------------------------

/**
 * Visits aggregate report (GET /api/v1/reports/visits — OWNER_ONLY).
 * Returns sparse hourly+daily buckets; callers must zero-fill (utils.ts).
 *
 * WR-04: accepts `role` as a parameter instead of calling useSession() internally.
 * The caller (useLoad → LoadPage) already has the resolved role from the RBAC guard,
 * so this avoids a double-waterfall (session fetch → role resolved → report fetch).
 */
export function useVisitsReport(query: VisitsReportQuery, role: Role) {
  return useQuery({
    queryKey: reportsQueryKeys.visits(query),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/visits', {
        query: { fromDate: query.fromDate, toDate: query.toDate },
      });
      return VisitsReportSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 30_000,
  });
}

/**
 * Revenue report (GET /api/v1/reports/revenue — OWNER_ONLY).
 * Returns sparse period buckets (day|month); callers must zero-fill (utils.ts).
 *
 * WR-04: accepts `role` as a parameter instead of calling useSession() internally.
 * Mirrors usePaymentsLedger which already receives role from the caller.
 */
export function useRevenueReport(query: RevenueReportQuery, role: Role) {
  return useQuery({
    queryKey: reportsQueryKeys.revenue(query),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/revenue', {
        query: { fromDate: query.fromDate, toDate: query.toDate, groupBy: query.groupBy },
      });
      return RevenueReportSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 30_000,
  });
}

/**
 * Clients aggregate report (GET /api/v1/reports/clients — OWNER_ONLY).
 * Returns activeCount / expiringCount / newClientsCount / withinDays.
 *
 * WR-04: accepts `role` as a parameter (mirrors useVisitsReport pattern).
 */
export function useClientsReport(query: ClientsReportQuery, role: Role) {
  return useQuery({
    queryKey: reportsQueryKeys.clients(query),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/clients', {
        query: { fromDate: query.fromDate, toDate: query.toDate, within: query.within ?? 30 },
      });
      return ClientsReportSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 30_000,
  });
}

/**
 * Trainers aggregate report (GET /api/v1/reports/trainers — OWNER_ONLY).
 * Returns rows[] with per-trainer usage + revenue data.
 *
 * WR-04: accepts `role` as a parameter (mirrors useVisitsReport pattern).
 */
export function useTrainersReport(query: TrainersReportQuery, role: Role) {
  return useQuery({
    queryKey: reportsQueryKeys.trainers(query),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/trainers', {
        query: { fromDate: query.fromDate, toDate: query.toDate },
      });
      return TrainersReportSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 30_000,
  });
}

export { ApiError };
