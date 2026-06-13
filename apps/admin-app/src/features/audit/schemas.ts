/**
 * Audit domain Zod contract layer (Phase 104-01 RPT-03).
 *
 * Endpoint: GET /api/v1/audit-log (OWNER_ONLY)
 * Ordered: created_at DESC, id DESC (stable keyset pagination).
 *
 * payload is arbitrary JSONB — typed as z.record(z.unknown()).nullable().
 * Wave 2 AuditPage renders it as escaped text/JSON.stringify (T-104-03).
 */
import { z } from 'zod';

export const AuditEventSchema = z.object({
  id: z.string(),
  createdAt: z.string(),
  actorUserId: z.string(),
  actorEmailSnapshot: z.string(),
  action: z.string(),
  resourceType: z.string(),
  resourceId: z.string().nullable(),
  payload: z.record(z.unknown()).nullable(),
});

export const AuditLogResponseSchema = z.object({
  data: z.object({
    items: z.array(AuditEventSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

export type AuditEvent = z.infer<typeof AuditEventSchema>;
export type AuditLogData = z.infer<typeof AuditLogResponseSchema>['data'];

export type AuditFilter = {
  actorEmailSnapshot?: string;
  resourceType?: string;
  action?: string;
  from?: string;
  to?: string;
  page?: number;
};
