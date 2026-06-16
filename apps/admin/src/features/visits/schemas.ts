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

// ---------------------------------------------------------------------------
// Paginated list query params (GET /api/v1/visits)
// ---------------------------------------------------------------------------

export const VisitsListQuerySchema = z.object({
  from: z.string().optional(),
  to: z.string().optional(),
  clientId: z.string().optional(),
  page: z.number().optional(),
  pageSize: z.number().optional(),
});
export type VisitsListQuery = z.infer<typeof VisitsListQuerySchema>;

// ---------------------------------------------------------------------------
// Gym meta (GET /api/v1/visits/_meta) — cacheable
// ---------------------------------------------------------------------------

export const GymMetaSchema = z.object({
  data: z.object({
    gymHoursStart: z.string(), // e.g. "07:00"
    gymHoursEnd: z.string(), // e.g. "23:00"
  }),
});
export type GymMetaData = z.infer<typeof GymMetaSchema>['data'];

// ---------------------------------------------------------------------------
// Check-in input (POST /api/v1/visits)
// ---------------------------------------------------------------------------

export const CheckInInputSchema = z.object({
  clientId: z.string().min(1, 'Клиент обязателен'),
});
export type CheckInInput = z.infer<typeof CheckInInputSchema>;
