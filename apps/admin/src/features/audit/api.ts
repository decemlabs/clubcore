/**
 * Audit domain TanStack Query hooks (Phase 104-01 RPT-03).
 *
 * OWNER_ONLY — useAuditLog is enabled-gated by can(role,'view','audit-log').
 * Reception makes ZERO audit-log API calls (mirrors T-104-01 pattern).
 *
 * Pagination: page + pageSize=25, keyset ordered created_at DESC, id DESC.
 * Filter params are spread conditionally — undefined values are NOT sent.
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT).
 */
import { useQuery } from '@tanstack/react-query';
import { staffRequest, ApiError } from '@/api/client';
import { can } from '@/shared/session/can';
import { AuditLogResponseSchema } from './schemas';
import type { AuditFilter } from './schemas';
import type { Role } from '@/shared/session/types';

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const auditKeys = {
  all: ['audit'] as const,
  lists: () => [...auditKeys.all, 'list'] as const,
  list: (filter: AuditFilter) => [...auditKeys.lists(), filter] as const,
};

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Paginated audit log (GET /api/v1/audit-log — OWNER_ONLY).
 * Filters are spread conditionally — only SET params are sent to the server.
 *
 * WR-04: accepts `role` as a parameter instead of calling useSession() internally.
 */
export function useAuditLog(filter: AuditFilter, role: Role) {
  return useQuery({
    queryKey: auditKeys.list(filter),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/audit-log', {
        query: {
          ...(filter.actorEmailSnapshot && { actorEmailSnapshot: filter.actorEmailSnapshot }),
          ...(filter.resourceType && { resourceType: filter.resourceType }),
          ...(filter.action && { action: filter.action }),
          ...(filter.from && { from: filter.from }),
          ...(filter.to && { to: filter.to }),
          page: filter.page ?? 1,
          pageSize: 25,
        },
      });
      return AuditLogResponseSchema.parse(raw).data;
    },
    enabled: can(role, 'view', 'audit-log'),
    staleTime: 30_000,
  });
}

export { ApiError };
