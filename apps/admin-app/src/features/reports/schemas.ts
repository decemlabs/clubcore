/**
 * Reports domain Zod contract layer (Phase 103-01).
 *
 * Two report endpoints:
 *   GET /api/v1/reports/visits  → VisitsReportSchema (sparse hourly/daily buckets)
 *   GET /api/v1/reports/revenue → RevenueReportSchema (sparse period buckets, signed kopecks)
 *
 * Both are OWNER_ONLY (VIEW REPORTS). Buckets are SPARSE — client-side zero-fill required.
 * Wire shape: camelCase via Pydantic to_camel alias.
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Visits report (GET /api/v1/reports/visits)
// ---------------------------------------------------------------------------

export const VisitsReportDailyBucketSchema = z.object({
  date: z.string(), // 'YYYY-MM-DD'
  count: z.number(),
});

export const VisitsReportHourlyBucketSchema = z.object({
  hour: z.number(), // 0–23
  count: z.number(),
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
    pt_package: z.number(),
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
  name: z.string(),
  sessionCount: z.number(),
  totalHours: z.number(),
  uniqueClients: z.number(),
  utilizationPct: z.number(),
  totalRevenueKopecks: z.number(),
});
export const TrainersReportSchema = z.object({
  data: z.object({
    rows: z.array(TrainerRowSchema),
  }),
});
export type TrainersReportData = z.infer<typeof TrainersReportSchema>['data'];
export type TrainerRow = z.infer<typeof TrainerRowSchema>;

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
