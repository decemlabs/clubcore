/**
 * Promo codes domain Zod contract layer (Phase 113 PROMO-01/02).
 *
 * Wire shapes mirror the backend camelCase alias_generator.
 * Match the REAL wire from 113-01 PromoCodeListItemResponse — camelCase fields.
 * All mutation schemas enforce business rules client-side as defense-in-depth;
 * the backend field validators + DB CheckConstraints are the real authority.
 *
 * NOTE on wire-shape drift: validFrom/validUntil come back as ISO strings or
 * null — kept as nullable strings (do NOT coerce to Date in this schema).
 *
 * Conversion at the UI boundary (PromoCodeModal):
 *   - percentage: FE input is whole percent (1–100); wire value = percent * 100
 *   - fixed: FE input is whole rubles; wire value = rubles * 100 (kopecks)
 */
import { z } from 'zod'

// ---------------------------------------------------------------------------
// Promo code (wire shape)
// ---------------------------------------------------------------------------

export const PromoCodeSchema = z.object({
  id: z.string(),
  code: z.string(),
  discountType: z.enum(['percentage', 'fixed']),
  discountValue: z.number(),
  maxUses: z.number().nullable(),
  perClientLimit: z.number().nullable(),
  validFrom: z.string().nullable(),
  validUntil: z.string().nullable(),
  isActive: z.boolean(),
  applicableTo: z.string().nullable(),
  description: z.string().nullable(),
  usedCount: z.number(),
  createdAt: z.string(),
})
export type PromoCodeData = z.infer<typeof PromoCodeSchema>

// ---------------------------------------------------------------------------
// Write response (POST create / PATCH edit)
// ---------------------------------------------------------------------------
//
// The backend create/edit response is `PromoCodeResponse`, which deliberately
// OMITS the `usedCount` aggregate (that field is list-only, served by
// `PromoCodeListItemResponse`). Reusing the list-shaped `PromoCodeSchema` to
// parse a mutation response would throw a ZodError on every successful write
// (missing `usedCount`) — CR-01. Parse write responses with this schema.
export const PromoCodeWriteResponseSchema = PromoCodeSchema.omit({ usedCount: true })
export type PromoCodeWriteData = z.infer<typeof PromoCodeWriteResponseSchema>

// ---------------------------------------------------------------------------
// List response — paginated envelope
// ---------------------------------------------------------------------------

export const PromoCodesListResponseSchema = z.object({
  data: z.object({
    items: z.array(PromoCodeSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
})

// ---------------------------------------------------------------------------
// Create input (all required fields)
// ---------------------------------------------------------------------------

export const PromoCodeCreateSchema = z.object({
  code: z.string().min(1, 'Укажите код').max(32),
  discountType: z.enum(['percentage', 'fixed']),
  discountValue: z.number().int().min(1),
  maxUses: z.number().int().min(1).optional(),
  perClientLimit: z.number().int().min(1).optional(),
  validFrom: z.string().nullable().optional(),
  validUntil: z.string().nullable().optional(),
  applicableTo: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
})
export type PromoCodeCreateInput = z.infer<typeof PromoCodeCreateSchema>

// ---------------------------------------------------------------------------
// Update input — same shape as create (all fields optional on update)
// ---------------------------------------------------------------------------

export const PromoCodeUpdateSchema = PromoCodeCreateSchema.partial()
export type PromoCodeUpdateInput = z.infer<typeof PromoCodeUpdateSchema>
