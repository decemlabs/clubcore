/**
 * Payments domain Zod contract layer (Phase 101-04).
 *
 * Wire shape (camelCase via Pydantic `to_camel` alias):
 *   id, subjectKind, subjectId, amountKopecks, method, receivedAt,
 *   receivedByUserId, refundOf (nullable), auditLogId (nullable)
 *
 * Backend: GET /api/v1/payments/by-client/{client_id} → {data:{items,total,page,pageSize}}
 * Permissions: reception+owner via require_payments_view_for_subject()
 *
 * Note: the scoped path /by-client/{client_id} (NOT GET /payments?clientId=)
 * is intentional — the global /payments route 403s for non-privileged staff
 * by design (T-101-12-IDOR).
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Payment wire shape
// ---------------------------------------------------------------------------

export const PaymentSchema = z.object({
  id: z.string(),
  subjectKind: z.string(),
  subjectId: z.string(),
  amountKopecks: z.number(),
  method: z.string(),
  receivedAt: z.string(),
  receivedByUserId: z.string(),
  refundOf: z.string().nullable().optional(),
  auditLogId: z.string().nullable().optional(),
});
export type PaymentData = z.infer<typeof PaymentSchema>;

// ---------------------------------------------------------------------------
// List response (data-wrapped paginated list)
// ---------------------------------------------------------------------------

export const PaymentsListResponseSchema = z.object({
  data: z.object({
    items: z.array(PaymentSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});
export type PaymentsListResponse = z.infer<typeof PaymentsListResponseSchema>;

// ---------------------------------------------------------------------------
// Global ledger query params (GET /api/v1/payments — OWNER_ONLY)
// ---------------------------------------------------------------------------

export const PaymentsLedgerQuerySchema = z.object({
  receivedFrom: z.string().optional(),
  receivedTo: z.string().optional(),
  method: z.enum(['cash', 'online']).optional(),
  page: z.number().optional(),
  pageSize: z.number().optional(),
});
export type PaymentsLedgerQuery = z.infer<typeof PaymentsLedgerQuerySchema>;

// ---------------------------------------------------------------------------
// Client-side computed daily total
// ---------------------------------------------------------------------------

export type DailyTotal = {
  date: string; // ISO date string 'YYYY-MM-DD' (MSK)
  totalKopecks: number; // signed sum (refunds subtract)
};
