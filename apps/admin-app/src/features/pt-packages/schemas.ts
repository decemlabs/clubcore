/**
 * PT-package-plans + PT-package instances Zod contract layer (Phase 101 MEM-01).
 *
 * Wire shapes mirror the backend camelCase alias_generator (pt_packages module).
 *
 * KEY IMMUTABILITY RULES on PtPackagePlan:
 *   - sessionCount, priceKopecks, validityDays are IMMUTABLE after creation.
 *   - PtPackagePlanUpdateSchema accepts only {name}.
 *
 * Cancel requires a reason (unlike memberships cancel where reason is optional — D-33-10).
 * Sell requires amountKopecks (backend validates 422 amount_mismatch if it differs from plan price).
 *
 * The sell/cancel/refund/instance-list hooks land in Phase 101 Plan 03 (101-03).
 * All schemas are defined here so 101-03 can import them without circular deps.
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// PT-Package Plan (catalog entry)
// ---------------------------------------------------------------------------

export const PtPackagePlanSchema = z.object({
  id: z.string(),
  name: z.string(),
  sessionCount: z.number(),
  priceKopecks: z.number(),
  validityDays: z.number().nullable().optional(),
  // Backend PtPackagePlanResponse has NO `active` field — PT-package plans have no
  // active/inactive concept; archiving is a soft-delete and the default list
  // (includeArchived omitted) returns only alive plans. Default true so the
  // «В продаже» badge + sell-modal `p.active` filter keep working. (UAT BUG-1)
  active: z.boolean().optional().default(true),
  createdAt: z.string(),
  updatedAt: z.string().optional(),
});
export type PtPackagePlanData = z.infer<typeof PtPackagePlanSchema>;

export const PtPackagePlansListResponseSchema = z.object({
  data: z.object({
    items: z.array(PtPackagePlanSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

// ---------------------------------------------------------------------------
// PT-Package Plan Create / Update
// ---------------------------------------------------------------------------

export const PtPackagePlanCreateSchema = z.object({
  name: z.string().min(1, 'Укажите название'),
  sessionCount: z.number().int().min(1, 'Минимум 1 сеанс').max(1000, 'Максимум 1000 сеансов'),
  priceKopecks: z.number().int().min(1, 'Цена должна быть больше нуля'),
  validityDays: z
    .number()
    .int()
    .min(1, 'Срок действия: от 1 до 3650 дней')
    .max(3650, 'Срок действия: от 1 до 3650 дней')
    .optional(),
});
export type PtPackagePlanCreateInput = z.infer<typeof PtPackagePlanCreateSchema>;

// PATCH: only name is mutable (sessionCount/priceKopecks/validityDays immutable)
export const PtPackagePlanUpdateSchema = z.object({
  name: z.string().min(1, 'Укажите название'),
});
export type PtPackagePlanUpdateInput = z.infer<typeof PtPackagePlanUpdateSchema>;

// ---------------------------------------------------------------------------
// PT-Package Instance (purchased package for a client)
// ---------------------------------------------------------------------------

// Backend PtPackageResponse is FLAT (planNameSnapshot/sessionCountSnapshot/
// priceKopecksSnapshot/validityDaysSnapshot + sessionsRemaining/isActive), NOT the
// nested planSnapshot + sessionsTotal/sessionsUsed/amountKopecks the UI used to assume.
// Parse the real wire shape, then .transform() to the UI-facing shape so consumers
// (TrainingsTab, PtPackageActionDialogs) keep reading planSnapshot.name / sessionsTotal /
// sessionsUsed / amountKopecks unchanged. (UAT BUG-2)
export const PtPackageSchema = z
  .object({
    id: z.string(),
    clientId: z.string(),
    planId: z.string().optional(),
    trainerId: z.string().nullable().optional(),
    status: z.enum(['active', 'exhausted', 'expired', 'cancelled']),
    planNameSnapshot: z.string(),
    sessionCountSnapshot: z.number(),
    priceKopecksSnapshot: z.number(),
    validityDaysSnapshot: z.number().nullable().optional(),
    sessionsRemaining: z.number(),
    isActive: z.boolean().optional(),
    startDate: z.string().nullable().optional(),
    endDate: z.string().nullable().optional(),
    cancellationReason: z.string().nullable().optional(),
    createdAt: z.string(),
    updatedAt: z.string().optional(),
  })
  .transform((p) => ({
    ...p,
    planSnapshot: {
      name: p.planNameSnapshot,
      sessionCount: p.sessionCountSnapshot,
      priceKopecks: p.priceKopecksSnapshot,
      validityDays: p.validityDaysSnapshot ?? null,
    },
    sessionsTotal: p.sessionCountSnapshot,
    sessionsUsed: Math.max(0, p.sessionCountSnapshot - p.sessionsRemaining),
    amountKopecks: p.priceKopecksSnapshot,
  }));
export type PtPackageData = z.infer<typeof PtPackageSchema>;

export const PtPackagesListResponseSchema = z.object({
  data: z.object({
    items: z.array(PtPackageSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

// ---------------------------------------------------------------------------
// Sell — amountKopecks required (backend validates amount_mismatch 422)
// ---------------------------------------------------------------------------

export const PtPackageSellSchema = z.object({
  clientId: z.string().min(1, 'Клиент обязателен'),
  planId: z.string().min(1, 'Пакет обязателен'),
  amountKopecks: z.number().int().min(1, 'Сумма должна быть больше нуля'),
});
export type PtPackageSellInput = z.infer<typeof PtPackageSellSchema>;

// ---------------------------------------------------------------------------
// Cancel — reason REQUIRED (1–200 chars; unlike memberships cancel where reason is optional)
// ---------------------------------------------------------------------------

export const PtPackageCancelSchema = z.object({
  reason: z.string().min(1, 'Причина обязательна').max(200, 'Не более 200 символов'),
});
export type PtPackageCancelInput = z.infer<typeof PtPackageCancelSchema>;

// ---------------------------------------------------------------------------
// Refund — reason required 1–200
// ---------------------------------------------------------------------------

export const PtPackageRefundSchema = z.object({
  reason: z.string().min(1, 'Причина обязательна для возврата').max(200, 'Не более 200 символов'),
});
export type PtPackageRefundInput = z.infer<typeof PtPackageRefundSchema>;
