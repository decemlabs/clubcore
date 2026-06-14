/**
 * Settings domain Zod schemas (Phase 104 SET-01).
 *
 * Defines wire shapes for the sessions list endpoint:
 *   GET /api/v1/auth/sessions → {data: {items, total, page, pageSize}}
 *
 * All fields camelCase (alias_generator=to_camel on backend ContractModel).
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Session
// ---------------------------------------------------------------------------

export const SessionSchema = z.object({
  familyId: z.string(),
  createdAt: z.string(),
  lastUsedAt: z.string(),
  userAgent: z.string().nullable(),
  channel: z.string(), // 'admin_web' | 'api'
  isCurrent: z.boolean(),
});

export const SessionsListResponseSchema = z.object({
  data: z.object({
    items: z.array(SessionSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

export type SessionData = z.infer<typeof SessionSchema>;
export type SessionsListData = z.infer<typeof SessionsListResponseSchema>['data'];
