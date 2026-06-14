/**
 * Users domain TanStack Query hooks (Phase 104 SET-02).
 *
 * Owner-only CRUD: list, invite, deactivate, reactivate, soft-delete,
 * revoke-invitation. Reception fires ZERO API calls (enabled:false gate).
 *
 * Key factory:
 *   usersKeys.all           → ['users']
 *   usersKeys.lists()       → ['users', 'list']
 *   usersKeys.list(filter)  → ['users', 'list', filter]
 *   usersKeys.detail(id)    → ['users', 'detail', id]
 *
 * CSRF: staffRequest auto-attaches X-CSRF-Token for POST/PATCH/DELETE — no
 * manual header needed.
 *
 * 409 guard handling is intentionally kept OUT of these hooks — surface ApiError
 * to the page/modal layer which maps err.code to Russian toasts.
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) so page/modal layers can
 * `instanceof ApiError` without importing @/api/client directly.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { staffRequest, ApiError } from '@/api/client';
import { can } from '@/shared/session/can';
import type { Role } from '@/shared/session/types';
import {
  UsersListResponseSchema,
  UserInviteResponseSchema,
  type UserInviteInput,
  type UsersFilter,
} from './schemas';

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const usersKeys = {
  all: ['users'] as const,
  lists: () => [...usersKeys.all, 'list'] as const,
  list: (filter: UsersFilter) => [...usersKeys.lists(), filter] as const,
  detail: (id: string) => [...usersKeys.all, 'detail', id] as const,
};

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/**
 * Owner-gated user list.
 * Reception → enabled:false → no fetch, no API calls.
 */
export function useUsers(filter: UsersFilter, role: Role) {
  return useQuery({
    queryKey: usersKeys.list(filter),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/users', {
        query: { page: filter.page ?? 1, pageSize: 20 },
      });
      return UsersListResponseSchema.parse(raw).data;
    },
    enabled: can(role, 'list', 'users'),
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations — all onSettled invalidate usersKeys.lists()
// ---------------------------------------------------------------------------

/**
 * Invite a new user.
 * POST /api/v1/users?includeInviteLink=true
 * Returns UserInviteData (includes optional inviteLinkUrl + invitationExpiresAt).
 */
export function useInviteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: UserInviteInput) => {
      const raw = await staffRequest('post', '/api/v1/users', {
        query: { includeInviteLink: true },
        body,
      });
      return UserInviteResponseSchema.parse((raw as { data: unknown }).data);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: usersKeys.lists() });
    },
  });
}

/**
 * Deactivate a user (owner-only).
 * PATCH /api/v1/users/{user_id}/deactivate
 * May throw ApiError with code: cannot_deactivate_self | cannot_deactivate_last_owner | already_inactive
 */
export function useDeactivateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      staffRequest('patch', '/api/v1/users/{user_id}/deactivate', { params: { user_id: id } }),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: usersKeys.lists() });
    },
  });
}

/**
 * Reactivate a deactivated user.
 * PATCH /api/v1/users/{user_id}/reactivate
 */
export function useReactivateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      staffRequest('patch', '/api/v1/users/{user_id}/reactivate', { params: { user_id: id } }),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: usersKeys.lists() });
    },
  });
}

/**
 * Soft-delete a user.
 * DELETE /api/v1/users/{user_id}
 */
export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      staffRequest('delete', '/api/v1/users/{user_id}', { params: { user_id: id } }),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: usersKeys.lists() });
    },
  });
}

/**
 * Revoke a pending invitation.
 * POST /api/v1/users/invitations/{token_id}/revoke
 *
 * `tokenId` is the password_reset_tokens row id (UserData.invitationTokenId from
 * the list), NOT the user id. The endpoint declares a required JSON body
 * (InvitationRevokeRequest), so a non-empty `{ reason }` is always sent — an
 * empty/absent body 422s (REV-01).
 */
export function useRevokeInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ tokenId, reason }: { tokenId: string; reason?: string }) =>
      staffRequest('post', '/api/v1/users/invitations/{token_id}/revoke', {
        params: { token_id: tokenId },
        body: { reason: reason ?? null },
      }),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: usersKeys.lists() });
    },
  });
}

// ---------------------------------------------------------------------------
// Re-export for page/modal layers (ESLint import-boundary — D-100-03-APIERROR-REEXPORT)
// ---------------------------------------------------------------------------

export { ApiError };
