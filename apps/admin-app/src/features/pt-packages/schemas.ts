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
import { z } from 'zod'

// ---------------------------------------------------------------------------
// PT-Package Plan (catalog entry)
// ---------------------------------------------------------------------------

export const PtPackagePlanSchema = z.object({
  id: z.string(),
  name: z.string(),
  sessionCount: z.number(),
  priceKopecks: z.number(),
  validityDays: z.number().nullable().optional(),
  active: z.boolean(),
  createdAt: z.string(),
})
export type PtPackagePlanData = z.infer<typeof PtPackagePlanSchema>

export const PtPackagePlansListResponseSchema = z.object({
  data: z.object({
    items: z.array(PtPackagePlanSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
})

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
})
export type PtPackagePlanCreateInput = z.infer<typeof PtPackagePlanCreateSchema>

// PATCH: only name is mutable (sessionCount/priceKopecks/validityDays immutable)
export const PtPackagePlanUpdateSchema = z.object({
  name: z.string().min(1, 'Укажите название'),
})
export type PtPackagePlanUpdateInput = z.infer<typeof PtPackagePlanUpdateSchema>

// ---------------------------------------------------------------------------
// PT-Package Instance (purchased package for a client)
// ---------------------------------------------------------------------------

export const PtPackageSchema = z.object({
  id: z.string(),
  clientId: z.string(),
  status: z.enum(['active', 'exhausted', 'expired', 'cancelled']),
  planSnapshot: PtPackagePlanSchema,
  sessionsTotal: z.number(),
  sessionsUsed: z.number(),
  sessionsRemaining: z.number(),
  amountKopecks: z.number(),
  createdAt: z.string(),
})
export type PtPackageData = z.infer<typeof PtPackageSchema>

export const PtPackagesListResponseSchema = z.object({
  data: z.object({
    items: z.array(PtPackageSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
})

// ---------------------------------------------------------------------------
// Sell — amountKopecks required (backend validates amount_mismatch 422)
// ---------------------------------------------------------------------------

export const PtPackageSellSchema = z.object({
  clientId: z.string().min(1, 'Клиент обязателен'),
  planId: z.string().min(1, 'Пакет обязателен'),
  amountKopecks: z.number().int().min(1, 'Сумма должна быть больше нуля'),
})
export type PtPackageSellInput = z.infer<typeof PtPackageSellSchema>

// ---------------------------------------------------------------------------
// Cancel — reason REQUIRED (1–200 chars; unlike memberships cancel where reason is optional)
// ---------------------------------------------------------------------------

export const PtPackageCancelSchema = z.object({
  reason: z.string().min(1, 'Причина обязательна').max(200, 'Не более 200 символов'),
})
export type PtPackageCancelInput = z.infer<typeof PtPackageCancelSchema>

// ---------------------------------------------------------------------------
// Refund — reason required 1–200
// ---------------------------------------------------------------------------

export const PtPackageRefundSchema = z.object({
  reason: z
    .string()
    .min(1, 'Причина обязательна для возврата')
    .max(200, 'Не более 200 символов'),
})
export type PtPackageRefundInput = z.infer<typeof PtPackageRefundSchema>
