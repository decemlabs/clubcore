/**
 * Reports domain query-key factory (Phase 103-01, extended Phase 115-03).
 *
 * Hierarchy:
 *   all → visits(query) | revenue(query) | clients(query) | trainers(query)
 *       | cohort(query) | anomaly(query) | atRisk() | loadNow()
 *
 * NOTE: root key is 'reports-data' (NOT 'reports') to avoid collision with the
 * legacy reportsKeys.all = ['reports'] in the existing mock-based api.ts.
 */
import type {
  VisitsReportQuery,
  RevenueReportQuery,
  ClientsReportQuery,
  TrainersReportQuery,
  CohortRetentionQuery,
  VisitAnomalyQuery,
} from './schemas';

export const reportsQueryKeys = {
  all: ['reports-data'] as const, // distinct from legacy reportsKeys.all = ['reports']
  visits: (q: VisitsReportQuery) => [...reportsQueryKeys.all, 'visits', q] as const,
  revenue: (q: RevenueReportQuery) => [...reportsQueryKeys.all, 'revenue', q] as const,
  clients: (q: ClientsReportQuery) => [...reportsQueryKeys.all, 'clients', q] as const,
  trainers: (q: TrainersReportQuery) => [...reportsQueryKeys.all, 'trainers', q] as const,
  // Phase 115-03: advanced analytics keys
  cohort: (q: CohortRetentionQuery) => [...reportsQueryKeys.all, 'cohort', q] as const,
  anomaly: (q: VisitAnomalyQuery) => [...reportsQueryKeys.all, 'anomaly', q] as const,
  atRisk: () => [...reportsQueryKeys.all, 'at-risk'] as const,
  loadNow: () => [...reportsQueryKeys.all, 'load-now'] as const,
} as const;
