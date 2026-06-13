/**
 * Payroll domain Zod schemas (Phase 102-04 TRN-02).
 *
 * Wire shapes mirror camelCase Pydantic aliases from backend.
 * Money values are integer kopecks (sessionFeeKopecks, fixedKopecks, etc.).
 * Commission values are integer basis points (commissionPctBps: 0–10000 = 0–100%).
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// PayrollConfig — comp-config read/write
// ---------------------------------------------------------------------------

export const PayrollConfigSchema = z.object({
  id: z.string(),
  trainerId: z.string(),
  commissionPctBps: z.number().int().min(0).max(10000),
  sessionFeeKopecks: z.number().int().min(0),
  effectiveFrom: z.string(),
  createdAt: z.string(),
});
export type PayrollConfigData = z.infer<typeof PayrollConfigSchema>;

/** Input for PUT (INSERT-only versioned) — Russian range error messages. */
export const PayrollConfigInputSchema = z.object({
  commissionPctBps: z
    .number()
    .int()
    .min(0, 'Комиссия: от 0 до 100%')
    .max(10000, 'Комиссия: от 0 до 100%'),
  sessionFeeKopecks: z.number().int().min(0, 'Ставка не может быть отрицательной'),
  effectiveFrom: z.string().min(1, 'Укажите дату начала действия'),
});
export type PayrollConfigInput = z.infer<typeof PayrollConfigInputSchema>;

// ---------------------------------------------------------------------------
// AccrualPreview — zero-persistence preview
// ---------------------------------------------------------------------------

export const AccrualPreviewSchema = z.object({
  sessionCount: z.number(),
  fixedKopecks: z.number(),
  commissionKopecks: z.number(),
  totalKopecks: z.number(),
});
export type AccrualPreviewData = z.infer<typeof AccrualPreviewSchema>;

// ---------------------------------------------------------------------------
// Accrual — append-only accrual record
// ---------------------------------------------------------------------------

export const AccrualSchema = z.object({
  id: z.string(),
  trainerId: z.string(),
  periodStart: z.string(),
  periodEnd: z.string(),
  sessionCount: z.number(),
  fixedKopecks: z.number(),
  commissionKopecks: z.number(),
  totalKopecks: z.number(),
  status: z.enum(['pending', 'paid', 'clawback']),
  accruedAt: z.string(),
});
export type AccrualData = z.infer<typeof AccrualSchema>;

export const AccrualsListResponseSchema = z.object({
  data: z.object({
    items: z.array(AccrualSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

// ---------------------------------------------------------------------------
// RunAccrual — POST /payroll/accruals input
// ---------------------------------------------------------------------------

export const RunAccrualSchema = z.object({
  trainerId: z.string().min(1),
  periodStart: z.string().min(1),
  periodEnd: z.string().min(1),
});
export type RunAccrualInput = z.infer<typeof RunAccrualSchema>;
