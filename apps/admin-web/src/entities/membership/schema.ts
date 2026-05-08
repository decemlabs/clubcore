import { z } from 'zod'

export const sellMembershipSchema = z.object({
  planId: z.string().uuid('Выберите тариф'),
  paidAt: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .optional(),
  notes: z.string().max(500).optional(),
})
export type SellMembershipFormInput = z.infer<typeof sellMembershipSchema>

export const cancelMembershipSchema = z.object({
  reason: z.string().max(500).optional(),
})
export type CancelMembershipFormInput = z.infer<typeof cancelMembershipSchema>

export const membershipsListQuerySchema = z.object({
  page: z.number().int().min(1).default(1),
  pageSize: z.number().int().min(10).max(100).default(20),
  clientId: z.string().uuid().optional(),
  expiring: z.boolean().optional(), // D-22-10 D-2 client-side filter
})
export type MembershipsListQueryInput = z.infer<typeof membershipsListQuerySchema>

export const membershipPlanFormSchema = z.object({
  name: z.string().min(1, 'Введите название').max(120),
  priceRoubles: z.number().int().min(0), // UI in roubles, converts to kopecks at submit
  durationDays: z.number().int().positive(),
  active: z.boolean().default(true),
})
export type MembershipPlanFormInput = z.infer<typeof membershipPlanFormSchema>
