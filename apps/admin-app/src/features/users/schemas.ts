/**
 * Users domain Zod contract layer (Phase 104 SET-02).
 *
 * Wire shapes mirror backend camelCase aliases (Pydantic alias_generator=to_camel).
 *
 *  - UserSchema: single user item in list/detail
 *  - UsersListResponseSchema: GET /api/v1/users → {data:{items,total,page,pageSize}}
 *  - UserInviteResponseSchema: POST /api/v1/users → {id,email,fullName,role,inviteLinkUrl?,invitationExpiresAt?}
 *  - UserInviteInput: invite form body
 *  - UsersFilter: pagination params for list query
 */
import { z } from 'zod'

// ---------------------------------------------------------------------------
// User wire shape
// ---------------------------------------------------------------------------

export const UserSchema = z.object({
  id: z.string(),
  email: z.string(),
  fullName: z.string(),
  role: z.enum(['owner', 'reception']),
  status: z.enum(['active', 'pending_invitation', 'deactivated']),
})
export type UserData = z.infer<typeof UserSchema>

// ---------------------------------------------------------------------------
// List response envelope (paginated)
// ---------------------------------------------------------------------------

export const UsersListResponseSchema = z.object({
  data: z.object({
    items: z.array(UserSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
})

// ---------------------------------------------------------------------------
// Invite response shape (POST /users?includeInviteLink=true)
// ---------------------------------------------------------------------------

export const UserInviteResponseSchema = z.object({
  id: z.string(),
  email: z.string(),
  fullName: z.string(),
  role: z.enum(['owner', 'reception']),
  inviteLinkUrl: z.string().optional(),
  invitationExpiresAt: z.string().optional(),
})
export type UserInviteData = z.infer<typeof UserInviteResponseSchema>

// ---------------------------------------------------------------------------
// Input types
// ---------------------------------------------------------------------------

/** Body for POST /api/v1/users (invite) */
export type UserInviteInput = {
  email: string
  fullName: string
  role: 'owner' | 'reception'
}

/** Pagination filter for list query */
export type UsersFilter = {
  page?: number
}
