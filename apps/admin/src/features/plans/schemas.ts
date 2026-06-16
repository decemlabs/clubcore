/**
 * Membership-plans domain Zod contract layer (Phase 101 MEM-01).
 *
 * Wire shapes mirror the backend camelCase alias_generator.
 * All mutation schemas enforce business rules client-side as defense-in-depth;
 * the backend `extra='forbid'` + field validators are the authority.
 *
 * KEY IMMUTABILITY RULE: durationDays is IMMUTABLE after plan creation.
 * MembershipPlanUpdateSchema intentionally omits durationDays so it cannot
 * be sent from the client. A backend 422 for this surfaces as:
 * «Длительность тарифа нельзя изменить после создания».
 */
import { z } from 'zod'

// ---------------------------------------------------------------------------
// Membership Plan (wire shape)
// ---------------------------------------------------------------------------

export const MembershipPlanSchema = z.object({
  id: z.string(),
  name: z.string(),
  durationDays: z.number(),
  priceKopecks: z.number(),
  freezeDaysLimit: z.number().nullable().optional(),
  active: z.boolean(),
  createdAt: z.string(),
})
export type MembershipPlanData = z.infer<typeof MembershipPlanSchema>

// ---------------------------------------------------------------------------
// List response
// ---------------------------------------------------------------------------

export const PlansListResponseSchema = z.object({
  data: z.object({
    items: z.array(MembershipPlanSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
})

// ---------------------------------------------------------------------------
// Create input (all required fields)
// ---------------------------------------------------------------------------

export const MembershipPlanCreateSchema = z.object({
  name: z.string().min(1, 'Укажите название тарифа'),
  durationDays: z
    .number()
    .int()
    .min(1, 'Длительность: от 1 до 3650 дней')
    .max(3650, 'Длительность: от 1 до 3650 дней'),
  priceKopecks: z.number().int().min(0, 'Цена не может быть отрицательной'),
  freezeDaysLimit: z
    .number()
    .int()
    .min(1, 'Лимит заморозки: от 1 до 365 дней')
    .max(365, 'Лимит заморозки: от 1 до 365 дней')
    .optional(),
  active: z.boolean().optional(),
})
export type MembershipPlanCreateInput = z.infer<typeof MembershipPlanCreateSchema>

// ---------------------------------------------------------------------------
// Update input — durationDays OMITTED (immutable after creation)
// Backend extra='forbid' → 422 if sent; frontend schema prevents sending it.
// ---------------------------------------------------------------------------

export const MembershipPlanUpdateSchema = MembershipPlanCreateSchema.omit({
  durationDays: true,
}).partial()
export type MembershipPlanUpdateInput = z.infer<typeof MembershipPlanUpdateSchema>
