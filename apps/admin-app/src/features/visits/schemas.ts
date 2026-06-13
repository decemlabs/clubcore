/**
 * Visits domain Zod contract layer (Phase 101-04).
 *
 * Wire shape (camelCase via Pydantic `to_camel` alias):
 *   id, clientId, membershipId, checkedInAt, gymDate, channel, checkedInBy (nullable), createdAt
 *
 * Backend: GET /api/v1/visits?clientId=… → {data:{items,total,page,pageSize}}
 * Permissions: reception+owner (VIEW, VISITS)
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Visit wire shape
// ---------------------------------------------------------------------------

export const VisitSchema = z.object({
  id: z.string(),
  clientId: z.string(),
  membershipId: z.string(),
  checkedInAt: z.string(),
  gymDate: z.string(),
  channel: z.string(),
  checkedInBy: z.string().nullable().optional(),
  createdAt: z.string(),
});
export type VisitData = z.infer<typeof VisitSchema>;

// ---------------------------------------------------------------------------
// List response (data-wrapped paginated list)
// ---------------------------------------------------------------------------

export const VisitsListResponseSchema = z.object({
  data: z.object({
    items: z.array(VisitSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});
export type VisitsListResponse = z.infer<typeof VisitsListResponseSchema>;
