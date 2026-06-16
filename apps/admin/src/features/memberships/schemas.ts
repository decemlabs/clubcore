/**
 * Memberships domain Zod contract layer (Phase 101-03).
 *
 * Wire shapes mirror the backend camelCase alias_generator.
 * MembershipSchema is FLAT (BUG-2): the backend serializes the plan snapshot as
 * inline fields (planNameSnapshot/durationDaysSnapshot/priceKopecksSnapshot/…),
 * not a nested planSnapshot object.
 * All mutation schemas enforce business rules client-side as defense-in-depth;
 * the backend is the authority.
 *
 * Cancel vs Refund (D-33-CANCEL-REFUND):
 *   - Cancel: owner-only, reason OPTIONAL ≤500 chars.
 *   - Refund: reception+owner (B-07), reason REQUIRED 1-200 chars, full-only.
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Freeze period (embedded in Membership when frozen)
// ---------------------------------------------------------------------------

export const FreezePeriodSchema = z.object({
  id: z.string(),
  startedAt: z.string(),
  startedBy: z.string(),
  endedAt: z.string().nullable(),
  endedBy: z.string().nullable(),
});
export type FreezePeriodData = z.infer<typeof FreezePeriodSchema>;

// ---------------------------------------------------------------------------
// Membership instance (wire shape)
// ---------------------------------------------------------------------------

export const MembershipSchema = z.object({
  id: z.string(),
  clientId: z.string(),
  planId: z.string(),
  status: z.enum(['active', 'frozen', 'expired', 'cancelled']),
  planNameSnapshot: z.string(),
  durationDaysSnapshot: z.number(),
  priceKopecksSnapshot: z.number(),
  startDate: z.string(),
  endDate: z.string(),
  cancelledAt: z.string().nullable().optional(),
  cancelReason: z.string().nullable().optional(),
  cancellationReason: z.string().nullable().optional(),
  paidAt: z.string().nullable().optional(),
  notes: z.string().nullable().optional(),
  createdAt: z.string(),
  updatedAt: z.string().nullable().optional(),
  freezeDaysLimitSnapshot: z.number(),
  freezeDaysUsed: z.number(),
  freezeDaysRemaining: z.number().nullable().optional(),
  currentFreezePeriod: FreezePeriodSchema.nullable().optional(),
  previousMembershipId: z.string().nullable().optional(),
});
export type MembershipData = z.infer<typeof MembershipSchema>;

// ---------------------------------------------------------------------------
// List response
// ---------------------------------------------------------------------------

export const MembershipsListResponseSchema = z.object({
  data: z.object({
    items: z.array(MembershipSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

// ---------------------------------------------------------------------------
// Sell — clientId + planId required; paidAt and notes optional
// ---------------------------------------------------------------------------

export const MembershipSellSchema = z.object({
  clientId: z.string().min(1, 'Клиент обязателен'),
  planId: z.string().min(1, 'Тариф обязателен'),
  paidAt: z.string().optional(),
  notes: z.string().optional(),
});
export type MembershipSellInput = z.infer<typeof MembershipSellSchema>;

// ---------------------------------------------------------------------------
// Cancel — OWNER_ONLY, reason optional ≤500 chars
// ---------------------------------------------------------------------------

export const MembershipCancelSchema = z.object({
  reason: z.string().max(500, 'Не более 500 символов').optional(),
});
export type MembershipCancelInput = z.infer<typeof MembershipCancelSchema>;

// ---------------------------------------------------------------------------
// Refund — required reason 1-200 chars; full-only (no amount field)
// ---------------------------------------------------------------------------

export const MembershipRefundSchema = z.object({
  reason: z.string().min(1, 'Причина обязательна для возврата').max(200, 'Не более 200 символов'),
});
export type MembershipRefundInput = z.infer<typeof MembershipRefundSchema>;
