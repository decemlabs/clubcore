/**
 * Reports domain Zod contract layer (Phase 103-01, extended Phase 115-03).
 *
 * Endpoints:
 *   GET /api/v1/reports/visits       → VisitsReportSchema (sparse hourly/daily buckets)
 *   GET /api/v1/reports/revenue      → RevenueReportSchema (sparse period buckets, signed kopecks)
 *   GET /api/v1/reports/clients      → ClientsReportSchema (aggregate KPI counts)
 *   GET /api/v1/reports/trainers     → TrainersReportSchema (per-trainer usage + revenue)
 *   GET /api/v1/reports/load/now     → LoadNowSchema (rolling-window live headcount)
 *   GET /api/v1/reports/cohort       → CohortRetentionSchema (nested cohort grid)
 *   GET /api/v1/reports/anomaly      → VisitAnomalySchema (daily visit series with anomaly flags)
 *   GET /api/v1/reports/at-risk      → AtRiskSchema (members at churn risk)
 *
 * All are OWNER_ONLY (VIEW REPORTS). Wire shape: camelCase via Pydantic to_camel alias.
 * Shapes for the Phase 115 endpoints are pinned to the REAL wire keys confirmed by
 * the ASGITransport tests in 115-02-SUMMARY.md (drift lesson D-V32-DRIFT-LESSON).
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Visits report (GET /api/v1/reports/visits)
// ---------------------------------------------------------------------------

export const VisitsReportDailyBucketSchema = z.object({
  date: z.string(), // 'YYYY-MM-DD'
  count: z.number().int().nonnegative(), // visit counts are never negative
});

export const VisitsReportHourlyBucketSchema = z.object({
  hour: z.number(), // 0–23
  count: z.number().int().nonnegative(), // visit counts are never negative
});

export const VisitsReportSchema = z.object({
  data: z.object({
    daily: z.array(VisitsReportDailyBucketSchema),
    hourly: z.array(VisitsReportHourlyBucketSchema),
    averagePerDay: z.number(),
    fromDate: z.string(),
    toDate: z.string(),
  }),
});
export type VisitsReportData = z.infer<typeof VisitsReportSchema>['data'];
export type VisitsReportDailyBucket = z.infer<typeof VisitsReportDailyBucketSchema>;
export type VisitsReportHourlyBucket = z.infer<typeof VisitsReportHourlyBucketSchema>;

// ---------------------------------------------------------------------------
// Revenue report (GET /api/v1/reports/revenue)
// ---------------------------------------------------------------------------

export const RevenueBucketSchema = z.object({
  period: z.string(), // 'YYYY-MM-DD' (day) or 'YYYY-MM' (month)
  netKopecks: z.number(), // signed — refunds make it negative
  byMethod: z.object({
    cash: z.number(),
    online: z.number(),
  }),
  bySubjectKind: z.object({
    membership: z.number(),
    ptPackage: z.number(),
  }),
});

export const RevenueReportSchema = z.object({
  data: z.object({
    buckets: z.array(RevenueBucketSchema),
    fromDate: z.string(),
    toDate: z.string(),
    groupBy: z.enum(['day', 'month']),
  }),
});
export type RevenueReportData = z.infer<typeof RevenueReportSchema>['data'];
export type RevenueBucket = z.infer<typeof RevenueBucketSchema>;

// ---------------------------------------------------------------------------
// Clients report (GET /api/v1/reports/clients)
// ---------------------------------------------------------------------------

export const ClientsReportSchema = z.object({
  data: z.object({
    activeCount: z.number(),
    expiringCount: z.number(),
    newClientsCount: z.number(),
    withinDays: z.number(),
  }),
});
export type ClientsReportData = z.infer<typeof ClientsReportSchema>['data'];

// ---------------------------------------------------------------------------
// Trainers report (GET /api/v1/reports/trainers)
// ---------------------------------------------------------------------------

export const TrainerRowSchema = z.object({
  trainerId: z.string(),
  trainerNameSnapshot: z.string(),
  sessionCount: z.number(),
  cancelledSessionCount: z.number(),
  totalHours: z.number(),
  uniqueClientCount: z.number(),
  utilizationPct: z.number().nullable(),
  revenueKopecks: z.number(),
  avgRevenuePerSession: z.number().nullable(),
  totalAccruedKopecks: z.number(),
  totalPaidKopecks: z.number(),
});
export const TrainersReportSchema = z.object({
  data: z.object({
    trainers: z.array(TrainerRowSchema),
    fromDate: z.string(),
    toDate: z.string(),
    revenueAttributionNote: z.string(),
  }),
});
export type TrainersReportData = z.infer<typeof TrainersReportSchema>['data'];
export type TrainerRow = z.infer<typeof TrainerRowSchema>;

// ---------------------------------------------------------------------------
// Load/now report (GET /api/v1/reports/load/now) — Phase 115-03
// Wire shape pinned by 115-01/02 SUMMARYs: { data: { count, asOf, windowMinutes } }
// ---------------------------------------------------------------------------

export const LoadNowSchema = z.object({
  data: z.object({
    count: z.number().int().nonnegative(),
    asOf: z.string(), // ISO-8601 datetime (UTC)
    windowMinutes: z.number().int().positive(),
  }),
});
export type LoadNowData = z.infer<typeof LoadNowSchema>['data'];

// ---------------------------------------------------------------------------
// Cohort retention report (GET /api/v1/reports/cohort) — Phase 115-03
// Wire shape pinned by 115-01/02 SUMMARYs: nested { cohorts: [{ cohortMonth, label, months: [...] }], maxOffset }
// NOTE: PATTERNS.md shows a flat rows[] shape — that is STALE. The SUMMARY is authoritative.
// ---------------------------------------------------------------------------

export const CohortMonthSchema = z.object({
  offset: z.number().int().nonnegative(),
  retentionPct: z.number().nullable(),
});

export const CohortEntrySchema = z.object({
  cohortMonth: z.string(), // 'YYYY-MM'
  label: z.string(), // e.g. 'янв 2026'
  months: z.array(CohortMonthSchema),
});

export const CohortRetentionSchema = z.object({
  data: z.object({
    cohorts: z.array(CohortEntrySchema),
    maxOffset: z.number().int().nonnegative(),
  }),
});
export type CohortRetentionData = z.infer<typeof CohortRetentionSchema>['data'];
export type CohortEntry = z.infer<typeof CohortEntrySchema>;
export type CohortMonth = z.infer<typeof CohortMonthSchema>;

// ---------------------------------------------------------------------------
// Visit anomaly report (GET /api/v1/reports/anomaly) — Phase 115-03
// Wire shape pinned by 115-01/02 SUMMARYs: { data: { points, windowDays, sigmaThreshold, anomalyCount } }
// ---------------------------------------------------------------------------

export const VisitAnomalyPointSchema = z.object({
  date: z.string(), // 'YYYY-MM-DD' (gym_date MSK)
  count: z.number().int().nonnegative(),
  isAnomaly: z.boolean(),
  direction: z.enum(['spike', 'drop']).nullable(), // null when not anomalous
  label: z.string(), // short Russian label e.g. '12 июн'
});

export const VisitAnomalySchema = z.object({
  data: z.object({
    points: z.array(VisitAnomalyPointSchema),
    windowDays: z.number(),
    sigmaThreshold: z.number(),
    anomalyCount: z.number().int().nonnegative(),
  }),
});
export type VisitAnomalyData = z.infer<typeof VisitAnomalySchema>['data'];
export type VisitAnomalyPoint = z.infer<typeof VisitAnomalyPointSchema>;

// ---------------------------------------------------------------------------
// At-risk members report (GET /api/v1/reports/at-risk) — Phase 115-03
// Wire shape pinned by 115-01/02 SUMMARYs: { data: { count, items, thresholdDays } }
// ---------------------------------------------------------------------------

export const AtRiskItemSchema = z.object({
  clientId: z.string(),
  name: z.string(),
  membershipType: z.string(),
  lastVisitDate: z.string().nullable(), // 'YYYY-MM-DD' or null if never visited
  daysSinceVisit: z.number().int(),
  lastVisitLabel: z.string(), // pre-formatted Russian e.g. '18 дней назад'
});

export const AtRiskSchema = z.object({
  data: z.object({
    count: z.number().int().nonnegative(),
    items: z.array(AtRiskItemSchema),
    thresholdDays: z.number().int(),
  }),
});
export type AtRiskData = z.infer<typeof AtRiskSchema>['data'];
export type AtRiskItem = z.infer<typeof AtRiskItemSchema>;

// ---------------------------------------------------------------------------
// Query param types
// ---------------------------------------------------------------------------

export type VisitsReportQuery = {
  fromDate: string;
  toDate: string;
};

export type RevenueReportQuery = {
  fromDate: string;
  toDate: string;
  groupBy: 'day' | 'month';
};

export type ClientsReportQuery = {
  fromDate: string;
  toDate: string;
  within?: number;
};

export type TrainersReportQuery = {
  fromDate: string;
  toDate: string;
};

export type CohortRetentionQuery = {
  cohortMonths: number;
};

export type VisitAnomalyQuery = {
  fromDate?: string;
  toDate?: string;
};
