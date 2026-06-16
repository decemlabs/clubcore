/**
 * PT-packages domain TanStack Query hooks (Phase 101 MEM-01 + MEM-02/MEM-03).
 *
 * Plan-CRUD portion (Phase 101 MEM-01):
 *   usePtPackagePlans         — GET  /api/v1/pt-package-plans
 *   useCreatePtPackagePlan    — POST /api/v1/pt-package-plans (OWNER_ONLY)
 *   useUpdatePtPackagePlan    — PATCH /api/v1/pt-package-plans/{id} (name only, OWNER_ONLY)
 *   useDeletePtPackagePlan    — DELETE /api/v1/pt-package-plans/{id} (OWNER_ONLY)
 *
 * Instance lifecycle portion (Phase 101 MEM-02/MEM-03):
 *   usePtPackagesByClient     — GET  /api/v1/pt-packages?clientId=
 *   useSellPtPackage          — POST /api/v1/pt-packages + Idempotency-Key (reception+owner)
 *   useCancelPtPackage        — POST /api/v1/pt-packages/{id}/cancel + Idempotency-Key (OWNER_ONLY)
 *   useRefundPtPackage        — POST /api/v1/pt-packages/{id}/refund + Idempotency-Key (reception+owner)
 *
 * NOTE: PT-package plan list uses `includeArchived` query param (NOT `active`).
 * NOTE: PATCH sends only {name} — sessionCount/priceKopecks/validityDays are immutable.
 * NOTE: PT-package cancel reason is REQUIRED (unlike memberships cancel where reason is optional).
 * NOTE: All instance mutations carry Idempotency-Key (including refund, unlike memberships refund).
 * NOTE: No freeze/unfreeze on pt-packages.
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) so page/modal layers can
 * `instanceof ApiError` without importing @/api/client directly (ESLint boundary).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { staffRequest, ApiError } from '@/api/client';
import {
  PtPackagePlansListResponseSchema,
  PtPackagePlanSchema,
  PtPackageSchema,
  PtPackagesListResponseSchema,
  type PtPackagePlanCreateInput,
  type PtPackagePlanUpdateInput,
  type PtPackagePlanData,
  type PtPackageSellInput,
  type PtPackageCancelInput,
  type PtPackageRefundInput,
} from './schemas';

// ---------------------------------------------------------------------------
// Key factory
// ---------------------------------------------------------------------------

export const ptPackagesKeys = {
  all: ['pt-packages'] as const,
  plans: () => [...ptPackagesKeys.all, 'plans'] as const,
  planList: (filter?: { includeArchived?: boolean }) =>
    [...ptPackagesKeys.plans(), filter] as const,
  planDetail: (id: string) => [...ptPackagesKeys.plans(), 'detail', id] as const,
  // Instance keys (for 101-03 sell/lifecycle hooks)
  instances: () => [...ptPackagesKeys.all, 'instances'] as const,
  instanceList: (filter?: { clientId?: string }) =>
    [...ptPackagesKeys.instances(), filter] as const,
  instanceDetail: (id: string) => [...ptPackagesKeys.instances(), 'detail', id] as const,
};

// ---------------------------------------------------------------------------
// Queries — PT-Package Plans (catalog)
// ---------------------------------------------------------------------------

export function usePtPackagePlans(opts?: { includeArchived?: boolean }) {
  return useQuery({
    queryKey: ptPackagesKeys.planList(opts),
    // NOTE: query param is `includeArchived` (not `active`) per backend PtPackagePlanListQuery
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/pt-package-plans', {
        query: opts ?? {},
      });
      return PtPackagePlansListResponseSchema.parse(raw).data;
    },
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations — PT-Package Plans (CRUD, OWNER_ONLY)
// ---------------------------------------------------------------------------

export function useCreatePtPackagePlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PtPackagePlanCreateInput): Promise<PtPackagePlanData> => {
      const raw = await staffRequest('post', '/api/v1/pt-package-plans', { body });
      return PtPackagePlanSchema.parse((raw as { data: unknown }).data);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.plans() });
    },
  });
}

export function useUpdatePtPackagePlan() {
  const qc = useQueryClient();
  return useMutation({
    // Only {name} is sent — other fields are immutable (extra='forbid' on backend)
    mutationFn: async ({
      id,
      body,
    }: {
      id: string;
      body: PtPackagePlanUpdateInput;
    }): Promise<PtPackagePlanData> => {
      const raw = await staffRequest('patch', '/api/v1/pt-package-plans/{plan_id}', {
        params: { plan_id: id },
        body,
      });
      return PtPackagePlanSchema.parse((raw as { data: unknown }).data);
    },
    onSettled: (_data, _err, vars) => {
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.plans() });
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.planDetail(vars.id) });
    },
  });
}

export function useDeletePtPackagePlan() {
  const qc = useQueryClient();
  return useMutation({
    // DELETE /pt-package-plans/{plan_id} → 204 No Content (no body to parse)
    mutationFn: (id: string) =>
      staffRequest('delete', '/api/v1/pt-package-plans/{plan_id}', { params: { plan_id: id } }),
    onSettled: (_data, _err, id) => {
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.plans() });
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.planDetail(id) });
    },
  });
}

// ---------------------------------------------------------------------------
// ── 101-03 section: PT-Package Instance hooks ────────────────────────────
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Queries — PT-Package Instances
// ---------------------------------------------------------------------------

/** Fetch all PT-packages for a client (GET /api/v1/pt-packages?clientId=). */
export function usePtPackagesByClient(clientId: string) {
  return useQuery({
    queryKey: ptPackagesKeys.instanceList({ clientId }),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/pt-packages', {
        query: { clientId },
      });
      return PtPackagesListResponseSchema.parse(raw).data;
    },
    enabled: !!clientId,
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations — PT-Package Instance lifecycle
// ---------------------------------------------------------------------------

/**
 * Sell a PT-package (POST /api/v1/pt-packages).
 * amountKopecks is required; backend validates 422 amount_mismatch if it
 * differs from plan price. Pre-fill from selected plan on the UI.
 * Idempotency-Key generated per attempt (T-101-08-DOUBLECHARGE).
 */
export function useSellPtPackage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PtPackageSellInput) => {
      const raw = await staffRequest('post', '/api/v1/pt-packages', {
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      });
      return PtPackageSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: (data) => {
      toast.success('Пакет тренировок оформлен', { description: 'Оплата принята.' });
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.instances() });
      void qc.invalidateQueries({
        queryKey: ptPackagesKeys.instanceList({ clientId: data.clientId }),
      });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      );
    },
  });
}

/**
 * Cancel a PT-package (POST /api/v1/pt-packages/{id}/cancel).
 * OWNER_ONLY — can(role,'cancel','pt-packages') gates the button.
 * Reason is REQUIRED (1-200 chars), unlike memberships cancel.
 */
export function useCancelPtPackage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ packageId, body }: { packageId: string; body: PtPackageCancelInput }) => {
      const raw = await staffRequest('post', '/api/v1/pt-packages/{pt_package_id}/cancel', {
        params: { pt_package_id: packageId },
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      });
      return PtPackageSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: (data) => {
      toast.success('Пакет тренировок отменён');
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.instances() });
      void qc.invalidateQueries({
        queryKey: ptPackagesKeys.instanceList({ clientId: data.clientId }),
      });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'forbidden') {
        toast.error('Недостаточно прав', {
          description: 'Отмена пакета доступна только владельцу.',
        });
      } else {
        const msg = err instanceof ApiError ? err.message : undefined;
        toast.error(
          msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
        );
      }
    },
  });
}

/**
 * Refund a PT-package (POST /api/v1/pt-packages/{id}/refund).
 * Reception+owner (B-07). Reason required 1-200 chars.
 * Carries Idempotency-Key (unlike memberships refund).
 */
export function useRefundPtPackage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ packageId, body }: { packageId: string; body: PtPackageRefundInput }) => {
      const raw = await staffRequest('post', '/api/v1/pt-packages/{pt_package_id}/refund', {
        params: { pt_package_id: packageId },
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      });
      return PtPackageSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: (data) => {
      toast.success('Возврат оформлен', { description: 'Средства будут возвращены клиенту.' });
      void qc.invalidateQueries({ queryKey: ptPackagesKeys.instances() });
      void qc.invalidateQueries({
        queryKey: ptPackagesKeys.instanceList({ clientId: data.clientId }),
      });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      );
    },
  });
}

// ---------------------------------------------------------------------------
// Re-export for page/modal layers (ESLint import-boundary — D-100-03-APIERROR-REEXPORT)
// ---------------------------------------------------------------------------

export { ApiError };
