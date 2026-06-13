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
 * LEGACY COMPAT: useReports() + reportsKeys are preserved so pages/reports/ReportsPage.tsx
 * (Phase 104 scope) continues to build without changes. Both resolve the mock via
 * VITE_API_MODE (mockResponse) — Phase 104 will flip to real data.
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT).
 */
import { useQuery } from '@tanstack/react-query';
import { staffRequest, mockResponse, ApiError } from '@/api/client';
import { can } from '@/shared/session/can';
import { reportsData } from '@/mocks/reports';
import type { ReportsData } from './types';
import { reportsQueryKeys } from './keys';
import { VisitsReportSchema, RevenueReportSchema } from './schemas';
import type { VisitsReportQuery, RevenueReportQuery } from './schemas';
import type { Role } from '@/shared/session/types';

// ---------------------------------------------------------------------------
// Legacy key factory — preserved for Phase 104 (ReportsPage.tsx)
// ---------------------------------------------------------------------------

/** @deprecated Use reportsQueryKeys from './keys' for Phase 103+ hooks. */
export const reportsKeys = {
  all: ['reports'] as const,
  summary: ['reports', 'summary'] as const,
};

// ---------------------------------------------------------------------------
// Legacy hook — preserved so ReportsPage (Phase 104) does not break the build
// ---------------------------------------------------------------------------

/**
 * Данные аналитического дашборда «Отчёты».
 * @deprecated Phase 104 will replace this with real report hooks.
 *             Kept here to avoid breaking pages/reports/ReportsPage.tsx import.
 */
export function useReports() {
  return useQuery({
    queryKey: reportsKeys.summary,
    queryFn: () => mockResponse<ReportsData>(reportsData),
  });
}

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

export { ApiError };
