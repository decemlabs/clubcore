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
      if (filter.page) query['page'] = filter.page;
      if (filter.pageSize) query['pageSize'] = filter.pageSize;
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
type CheckInCtx = {
  listSnapshots: [
    readonly unknown[],
    { items: VisitData[]; total: number; page: number; pageSize: number } | undefined,
  ][];
};

/**
 * Post a visit check-in (POST /api/v1/visits {clientId}).
 *
 * Optimistic: prepends a placeholder row to all cached lists; rolls back on error.
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
      await qc.cancelQueries({ queryKey: visitsKeys.lists() });
      const listSnapshots = qc.getQueriesData<{
        items: VisitData[];
        total: number;
        page: number;
        pageSize: number;
      }>({
        queryKey: visitsKeys.lists(),
      });

      const optimisticRow = {
        id: `optimistic-${crypto.randomUUID()}`,
        clientId,
        membershipId: '',
        checkedInAt: new Date().toISOString(),
        gymDate: new Date().toISOString().slice(0, 10),
        channel: 'reception',
        checkedInBy: currentUserId,
        createdAt: new Date().toISOString(),
        _optimistic: true,
      } as VisitData & { _optimistic: boolean };

      // Prepend optimistic row to each cached list
      for (const [key, data] of listSnapshots) {
        if (!data) continue;
        qc.setQueryData(key, { ...data, items: [optimisticRow, ...data.items] });
      }

      return { listSnapshots };
    },
    onSuccess: () => {
      // Caller shows toast.success('Визит зафиксирован', { description: clientName }) and closes modal
      void qc.invalidateQueries({ queryKey: visitsKeys.lists() });
    },
    onError: (_err, _vars, ctx) => {
      // Rollback optimistic rows (pattern from memberships freeze/unfreeze)
      if (ctx) {
        for (const [key, data] of ctx.listSnapshots) {
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
