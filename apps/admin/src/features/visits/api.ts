/**
 * Visits domain TanStack Query hooks (Phase 101-04, extended Phase 103-01).
 *
 * Phase 101: useClientVisits (read-only, by-client filter)
 * Phase 103: useVisitsList (paginated list), useGymMeta (cacheable meta),
 *            useCheckIn (optimistic check-in mutation with rollback)
 *
 * Transport: staffRequest(...) → Schema.parse(raw).data
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) so page/tab layers can
 * `instanceof ApiError` without importing @/api/client directly (ESLint boundary).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { staffRequest, ApiError } from '@/api/client';
import {
  VisitsListResponseSchema,
  VisitSchema,
  GymMetaSchema,
  type VisitData,
  type VisitsListQuery,
} from './schemas';

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const visitsKeys = {
  all: ['visits'] as const,
  byClient: (clientId: string) => [...visitsKeys.all, 'byClient', clientId] as const,
  // NEW Phase 103
  lists: () => [...visitsKeys.all, 'list'] as const,
  list: (filter: VisitsListQuery) => [...visitsKeys.lists(), filter] as const,
  meta: () => [...visitsKeys.all, '_meta'] as const,
};

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/**
 * Fetch visits for a client (GET /api/v1/visits?clientId=…).
 * Enabled only when clientId is truthy.
 */
export function useClientVisits(clientId: string) {
  return useQuery({
    queryKey: visitsKeys.byClient(clientId),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/visits', {
        query: { clientId },
      });
      return VisitsListResponseSchema.parse(raw).data;
    },
    enabled: !!clientId,
    staleTime: 30_000,
  });
}

/**
 * Fetch paginated visits list (GET /api/v1/visits with date/client/page filters).
 * Reception + owner (VIEW VISITS).
 */
export function useVisitsList(filter: VisitsListQuery) {
  return useQuery({
    queryKey: visitsKeys.list(filter),
    queryFn: async () => {
      const query: Record<string, string | number> = {};
      if (filter.from) query['from'] = filter.from;
      if (filter.to) query['to'] = filter.to;
      if (filter.clientId) query['clientId'] = filter.clientId;
      if (filter.page != null) query['page'] = filter.page;
      if (filter.pageSize != null) query['pageSize'] = filter.pageSize;
      const raw = await staffRequest('get', '/api/v1/visits', { query });
      return VisitsListResponseSchema.parse(raw).data;
    },
    staleTime: 30_000,
  });
}

/**
 * Fetch gym meta (GET /api/v1/visits/_meta).
 * Returns gym hours for pre-validation before check-in. Long staleTime (5 min).
 */
export function useGymMeta() {
  return useQuery({
    queryKey: visitsKeys.meta(),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/visits/_meta');
      return GymMetaSchema.parse(raw).data;
    },
    staleTime: 5 * 60_000, // 5 min — gym hours rarely change
  });
}

// ---------------------------------------------------------------------------
// Mutation — Check-in (OPTIMISTIC prepend + rollback)
// ---------------------------------------------------------------------------

type CheckInVars = { clientId: string; clientName: string; currentUserId: string };
type VisitsListPage = { items: VisitData[]; total: number; page: number; pageSize: number };
type CheckInCtx = {
  // Snapshots for ALL visits queries (lists + byClient families) for full rollback.
  allSnapshots: [readonly unknown[], VisitsListPage | undefined][];
};

/**
 * Post a visit check-in (POST /api/v1/visits {clientId}).
 *
 * Optimistic: prepends a placeholder row to all cached list queries; rolls back on error.
 * CR-03: cancel/snapshot/rollback/invalidate now covers visitsKeys.all (not just
 * visitsKeys.lists()) so the byClient family (useClientVisits on client-detail page)
 * is also cancelled, snapshotted, and refreshed after a successful check-in.
 *
 * 409 codes (outside_gym_hours / no_active_membership / duplicate_checkin) are NOT
 * toasted here — the caller (CheckInModal) catches ApiError.code and maps to specific
 * Russian copy. Pattern: bookings/api.ts useCreateBooking.
 *
 * The hook does NOT toast 409 errors. Caller shows Callout for specific 409 reason.
 */
export function useCheckIn() {
  const qc = useQueryClient();
  return useMutation<VisitData, Error, CheckInVars, CheckInCtx>({
    mutationFn: async ({ clientId }: CheckInVars) => {
      const raw = await staffRequest('post', '/api/v1/visits', { body: { clientId } });
      return VisitSchema.parse((raw as { data: unknown }).data);
    },
    onMutate: async ({ clientId, currentUserId }: CheckInVars) => {
      // CR-03: cancel ALL visits queries (lists + byClient) to prevent race conditions.
      await qc.cancelQueries({ queryKey: visitsKeys.all });

      // Snapshot all visits queries for full rollback on error.
      const allSnapshots = qc.getQueriesData<VisitsListPage>({
        queryKey: visitsKeys.all,
      });

      const optimisticRow = {
        id: `optimistic-${crypto.randomUUID()}`,
        clientId,
        membershipId: '',
        checkedInAt: new Date().toISOString(),
        gymDate: new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Moscow' }),
        channel: 'reception',
        checkedInBy: currentUserId,
        createdAt: new Date().toISOString(),
        _optimistic: true,
      } as VisitData & { _optimistic: boolean };

      // Prepend optimistic row only to list queries (paginated lists have .items).
      // byClient queries also have .items so they benefit from the same optimistic prepend.
      for (const [key, data] of allSnapshots) {
        // getQueriesData(visitsKeys.all) also matches the gym-meta query
        // (visitsKeys.meta() = [...all, '_meta']), whose cached data has no
        // `.items` — spreading it would throw before mutationFn runs and the
        // check-in POST would never fire. Skip non-list entries. (BUG-8)
        if (!data || !Array.isArray(data.items)) continue;
        qc.setQueryData(key, { ...data, items: [optimisticRow, ...data.items] });
      }

      return { allSnapshots };
    },
    onSuccess: () => {
      // Caller shows toast.success('Визит зафиксирован', { description: clientName }) and closes modal.
      // CR-03: invalidate all visits queries so byClient family also refreshes.
      void qc.invalidateQueries({ queryKey: visitsKeys.all });
    },
    onError: (_err, _vars, ctx) => {
      // Rollback all optimistic rows across all visits queries (pattern from memberships freeze/unfreeze).
      if (ctx) {
        for (const [key, data] of ctx.allSnapshots) {
          // Symmetric with onMutate: only list entries were optimistically
          // mutated, so only those need restoring. (BUG-8)
          if (!data || !Array.isArray(data.items)) continue;
          qc.setQueryData(key as readonly unknown[], data);
        }
      }
      // 409 code routing is handled by CheckInModal (catch ApiError.code)
      // Hook does NOT toast 409 — caller maps code → Callout heading/body
    },
  });
}

// ---------------------------------------------------------------------------
// Re-export for page/tab layers (ESLint import-boundary)
// ---------------------------------------------------------------------------

export { ApiError };
