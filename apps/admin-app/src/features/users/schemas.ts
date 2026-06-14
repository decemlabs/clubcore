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
import { z } from 'zod';

// ---------------------------------------------------------------------------
// User wire shape
// ---------------------------------------------------------------------------

export const UserSchema = z.object({
  id: z.string(),
  email: z.string(),
  fullName: z.string(),
  role: z.enum(['owner', 'reception']),
  status: z.enum(['active', 'pending_invitation', 'deactivated']),
  // password_reset_tokens row id for a live pending invitation (REV-01 Variant B);
  // null for active/deactivated rows or pending rows whose token has expired.
  invitationTokenId: z.string().nullable().optional(),
});
export type UserData = z.infer<typeof UserSchema>;

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
});

// ---------------------------------------------------------------------------
// Invite response shape (POST /users?includeInviteLink=true)
// ---------------------------------------------------------------------------

export const UserInviteResponseSchema = z.object({
  id: z.string(),
  email: z.string(),
  // The real POST /users invite response omits fullName and returns
  // inviteLinkUrl: null when delivery is by email — so fullName is optional and
  // the URL/expiry are nullable. A required fullName + non-null URL made the 201
  // success response throw → the invite always showed a generic error. (INV-01)
  fullName: z.string().optional(),
  role: z.enum(['owner', 'reception']),
  inviteLinkUrl: z.string().nullable().optional(),
  invitationExpiresAt: z.string().nullable().optional(),
});
export type UserInviteData = z.infer<typeof UserInviteResponseSchema>;

// ---------------------------------------------------------------------------
// Input types
// ---------------------------------------------------------------------------

/** Body for POST /api/v1/users (invite) */
export type UserInviteInput = {
  email: string;
  fullName: string;
  role: 'owner' | 'reception';
};

/** Pagination filter for list query */
export type UsersFilter = {
  page?: number;
};
