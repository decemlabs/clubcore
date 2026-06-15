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
import {
  VisitsReportSchema,
  RevenueReportSchema,
  ClientsReportSchema,
  TrainersReportSchema,
  LoadNowSchema,
  CohortRetentionSchema,
  VisitAnomalySchema,
  AtRiskSchema,
} from './schemas';
import type {
  VisitsReportQuery,
  RevenueReportQuery,
  ClientsReportQuery,
  TrainersReportQuery,
  CohortRetentionQuery,
  VisitAnomalyQuery,
} from './schemas';
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

// ---------------------------------------------------------------------------
// Phase 115-03 hooks — owner-gated advanced analytics endpoints
// ---------------------------------------------------------------------------

/**
 * Cohort retention report (GET /api/v1/reports/cohort — OWNER_ONLY).
 * Returns nested cohort grid: { cohorts: [{ cohortMonth, label, months: [...] }], maxOffset }.
 * Wire shape pinned to 115-01-SUMMARY (nested, NOT the stale flat rows[] from PATTERNS.md).
 *
 * WR-04: accepts `role` as parameter to avoid double-waterfall.
 */
export function useCohortReport(query: CohortRetentionQuery, role: Role) {
  return useQuery({
    queryKey: reportsQueryKeys.cohort(query),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/cohort', {
        query: { cohortMonths: query.cohortMonths },
      });
      return CohortRetentionSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 30_000,
  });
}

/**
 * Visit anomaly report (GET /api/v1/reports/anomaly — OWNER_ONLY).
 * Returns daily visit series with >sigma anomaly flags (spike/drop).
 * Query params are optional — backend defaults to last 90 MSK days when omitted.
 *
 * WR-04: accepts `role` as parameter to avoid double-waterfall.
 */
export function useVisitAnomaly(query: VisitAnomalyQuery, role: Role) {
  return useQuery({
    queryKey: reportsQueryKeys.anomaly(query),
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (query.fromDate) params['fromDate'] = query.fromDate;
      if (query.toDate) params['toDate'] = query.toDate;
      const raw = await staffRequest('get', '/api/v1/reports/anomaly', {
        query: Object.keys(params).length > 0 ? params : undefined,
      });
      return VisitAnomalySchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 30_000,
  });
}

/**
 * At-risk members report (GET /api/v1/reports/at-risk — OWNER_ONLY).
 * Returns members with active membership + last visit > threshold days.
 * No query params — threshold is server-side constant (AT_RISK_THRESHOLD_DAYS=14).
 *
 * WR-04: accepts `role` as parameter to avoid double-waterfall.
 */
export function useAtRiskMembers(role: Role) {
  return useQuery({
    queryKey: reportsQueryKeys.atRisk(),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/at-risk');
      return AtRiskSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 30_000,
  });
}

/**
 * Live gym headcount (GET /api/v1/reports/load/now — OWNER_ONLY).
 * Rolling-window approximation (default 120 min window — no checkout column).
 * Polls every 60s to keep the "сейчас в зале" counter current.
 *
 * T-115-F3: UI shows only aggregate count + explicit approximation sub-label.
 * WR-04: accepts `role` as parameter to avoid double-waterfall.
 */
export function useLoadNow(role: Role) {
  return useQuery({
    queryKey: reportsQueryKeys.loadNow(),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/reports/load/now');
      return LoadNowSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'reports'),
    staleTime: 60_000,
    refetchInterval: 60_000, // live poll — keeps "сейчас в зале" counter current
  });
}

export { ApiError };
