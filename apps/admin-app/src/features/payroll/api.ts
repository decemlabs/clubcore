/**
 * Payroll domain TanStack Query hooks (Phase 102-04 TRN-02).
 *
 * ALL OWNER_ONLY — every hook is enabled-gated by can(role,'view','payroll').
 * Reception session makes ZERO payroll API calls (T-102-PAY-RBAC).
 *
 * Money integrity (T-102-PAY-MONEY): wire amounts are integer kopecks/bps.
 * No Idempotency-Key for payroll endpoints (not required per backend contract).
 *
 * 409 handling (T-102-PAY-TERMINAL):
 *   - payroll_period_already_run → toast «Период уже обработан» (no crash)
 *   - already_paid → toast «Уже выплачено» (no crash)
 *
 * ApiError re-exported (D-100-03) so page/modal layers can `instanceof ApiError`
 * without importing @/api/client directly (ESLint import-boundary).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { staffRequest, ApiError } from '@/api/client';
import { useSession } from '@/features/auth/api';
import { can } from '@/shared/session/can';
import { payrollKeys } from './keys';
import {
  PayrollConfigSchema,
  AccrualPreviewSchema,
  AccrualSchema,
  AccrualsListResponseSchema,
  type PayrollConfigInput,
  type RunAccrualInput,
} from './schemas';

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/**
 * GET active comp-config for a trainer (GET /api/v1/payroll/trainer-configs/{trainer_id}).
 * 404 comp_config_missing is an expected state — surfaced to the caller, NOT toasted.
 * Enabled only when trainerId present AND owner role (T-102-PAY-RBAC).
 */
export function usePayrollConfig(trainerId: string) {
  const session = useSession();
  const role = session.data?.role ?? 'reception';
  return useQuery({
    queryKey: payrollKeys.config(trainerId),
    queryFn: async () => {
      const raw = await staffRequest(
        'get',
        '/api/v1/payroll/trainer-configs/{trainer_id}',
        { params: { trainer_id: trainerId } },
      );
      return PayrollConfigSchema.parse((raw as { data: unknown }).data);
    },
    enabled: !!trainerId && can(role, 'view', 'payroll'),
    staleTime: 30_000,
  });
}

/**
 * GET accrual preview for a period (GET /api/v1/payroll/preview?trainerId&periodStart&periodEnd).
 * Zero-persistence — call refetch manually on demand.
 * 422 comp_config_missing surfaced to caller via query error.
 * Enabled only for owner role; additionally gated by period params.
 */
export function useAccrualPreview(params: {
  trainerId: string;
  periodStart: string;
  periodEnd: string;
  enabled?: boolean;
}) {
  const session = useSession();
  const role = session.data?.role ?? 'reception';
  const { trainerId, periodStart, periodEnd, enabled = true } = params;
  return useQuery({
    queryKey: payrollKeys.preview(trainerId, { periodStart, periodEnd }),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/payroll/preview', {
        query: { trainerId, periodStart, periodEnd } as Record<string, string>,
      });
      return AccrualPreviewSchema.parse((raw as { data: unknown }).data);
    },
    enabled:
      !!trainerId &&
      !!periodStart &&
      !!periodEnd &&
      enabled &&
      can(role, 'view', 'payroll'),
    staleTime: 0, // preview is always fresh
    retry: false, // 422 comp_config_missing should surface immediately
  });
}

/**
 * GET paginated accruals list (GET /api/v1/payroll/accruals?trainerId, accrued_at DESC).
 * Enabled only when trainerId present AND owner role.
 */
export function useAccruals(trainerId: string) {
  const session = useSession();
  const role = session.data?.role ?? 'reception';
  return useQuery({
    queryKey: payrollKeys.accruals(trainerId),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/payroll/accruals', {
        query: { trainerId } as Record<string, string>,
      });
      return AccrualsListResponseSchema.parse(raw).data;
    },
    enabled: !!trainerId && can(role, 'view', 'payroll'),
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/**
 * PUT comp-config — INSERT-only versioned; each save creates a new version.
 * Never updates in-place. (T-102-PAY-VERSION)
 */
export function useSetPayrollConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      trainerId,
      body,
    }: {
      trainerId: string;
      body: PayrollConfigInput;
    }) => {
      const raw = await staffRequest(
        'put',
        '/api/v1/payroll/trainer-configs/{trainer_id}',
        {
          params: { trainer_id: trainerId },
          body,
        },
      );
      return PayrollConfigSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: (_data, vars) => {
      toast.success('Конфигурация сохранена');
      void qc.invalidateQueries({ queryKey: payrollKeys.config(vars.trainerId) });
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
 * POST run accrual (POST /api/v1/payroll/accruals, append-only).
 * 409 payroll_period_already_run → friendly toast, no crash (T-102-PAY-TERMINAL).
 * 422 comp_config_missing → surfaced via mutation error for inline Callout.
 */
export function useRunAccrual() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: RunAccrualInput) => {
      const raw = await staffRequest('post', '/api/v1/payroll/accruals', { body });
      return AccrualSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: (_data, vars) => {
      toast.success('Начисление выполнено');
      void qc.invalidateQueries({ queryKey: payrollKeys.accruals(vars.trainerId) });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'payroll_period_already_run') {
        toast.error('Период уже обработан', {
          description: 'Начисление за этот период уже выполнено.',
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
 * POST mark-paid (POST /api/v1/payroll/accruals/{accrual_id}/mark-paid, terminal).
 * 409 already_paid → friendly toast + refetch accruals list (no crash, T-102-PAY-TERMINAL).
 */
export function useMarkAccrualPaid() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      accrualId,
    }: {
      accrualId: string;
      trainerId: string; // needed for invalidation in onSuccess/onError
    }) => {
      await staffRequest('post', '/api/v1/payroll/accruals/{accrual_id}/mark-paid', {
        params: { accrual_id: accrualId },
      });
    },
    onSuccess: (_data, vars) => {
      toast.success('Выплата зафиксирована');
      void qc.invalidateQueries({ queryKey: payrollKeys.accruals(vars.trainerId) });
    },
    onError: (err, vars) => {
      if (err instanceof ApiError && err.code === 'already_paid') {
        toast.error('Уже выплачено', {
          description: 'Это начисление уже отмечено как выплаченное.',
        });
        // Refetch accruals so the list reflects the already-paid state
        void qc.invalidateQueries({ queryKey: payrollKeys.accruals(vars.trainerId) });
      } else {
        const msg = err instanceof ApiError ? err.message : undefined;
        toast.error(
          msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
        );
      }
    },
  });
}

// ---------------------------------------------------------------------------
// Re-exports (D-100-03 ESLint import-boundary)
// ---------------------------------------------------------------------------

export { ApiError };
