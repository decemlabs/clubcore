/**
 * Reports domain query-key factory (Phase 103-01).
 *
 * Hierarchy:
 *   all → visits(query) | revenue(query)
 *
 * NOTE: root key is 'reports-data' (NOT 'reports') to avoid collision with the
 * legacy reportsKeys.all = ['reports'] in the existing mock-based api.ts.
 */
import type { VisitsReportQuery, RevenueReportQuery, ClientsReportQuery, TrainersReportQuery } from './schemas';

export const reportsQueryKeys = {
  all: ['reports-data'] as const, // distinct from legacy reportsKeys.all = ['reports']
  visits: (q: VisitsReportQuery) => [...reportsQueryKeys.all, 'visits', q] as const,
  revenue: (q: RevenueReportQuery) => [...reportsQueryKeys.all, 'revenue', q] as const,
  clients: (q: ClientsReportQuery) => [...reportsQueryKeys.all, 'clients', q] as const,
  trainers: (q: TrainersReportQuery) => [...reportsQueryKeys.all, 'trainers', q] as const,
} as const;
