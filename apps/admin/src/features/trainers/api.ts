/**
 * Trainers domain TanStack Query hooks (Phase 102-02 TRN-01).
 *
 * Flipped from mock→http over the P100 `staffRequest` transport seam.
 * Follows the features/clients/api.ts exemplar (staffRequest + Schema.parse(raw).data).
 *
 * Key factory:
 *   trainersKeys.all          → ['trainers']
 *   trainersKeys.lists()      → ['trainers', 'list']
 *   trainersKeys.list(filter) → ['trainers', 'list', filter]
 *   trainersKeys.details()    → ['trainers', 'detail']
 *   trainersKeys.detail(id)   → ['trainers', 'detail', id]
 *
 * Mutations:
 *   useCreateTrainer — POST /api/v1/trainers; 409 phone_exists → caller shows inline Callout
 *   useUpdateTrainer — PATCH /api/v1/trainers/{id}; PATCH semantics: omit = no change
 *   useDeleteTrainer — DELETE /api/v1/trainers/{id}; 409 trainer_in_use → friendly toast
 *
 * No Idempotency-Key required for trainer mutations per backend contract.
 *
 * ApiError re-exported (D-100-03-APIERROR-REEXPORT) so page/modal layers can
 * `instanceof ApiError` without importing @/api/client directly (ESLint boundary).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { staffRequest, ApiError } from '@/api/client';
import { trainersKeys, type TrainersListQuery } from './keys';
import {
  TrainersListResponseSchema,
  TrainerSchema,
  type TrainerData,
  type TrainerCreateInput,
  type TrainerUpdateInput,
} from './schemas';

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useTrainers(filter: TrainersListQuery = {}) {
  return useQuery({
    queryKey: trainersKeys.list(filter),
    queryFn: async () => {
      // Build explicit query record so TypeScript knows the shape
      const query: Record<string, string | number | boolean> = {};
      if (filter.active !== undefined) query['active'] = filter.active;
      const raw = await staffRequest('get', '/api/v1/trainers', { query });
      return TrainersListResponseSchema.parse(raw).data;
    },
    staleTime: 30_000,
  });
}

export function useTrainer(id: string) {
  return useQuery({
    queryKey: trainersKeys.detail(id),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/trainers/{trainer_id}', {
        params: { trainer_id: id },
      });
      return TrainerSchema.parse((raw as { data: unknown }).data);
    },
    enabled: !!id,
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreateTrainer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: TrainerCreateInput): Promise<TrainerData> => {
      const raw = await staffRequest('post', '/api/v1/trainers', { body });
      return TrainerSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: trainersKeys.lists() });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'phone_exists') {
        // Caller shows inline Callout — do NOT toast here
        return;
      }
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      );
    },
  });
}

export function useUpdateTrainer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      body,
    }: {
      id: string;
      body: TrainerUpdateInput;
    }): Promise<TrainerData> => {
      const raw = await staffRequest('patch', '/api/v1/trainers/{trainer_id}', {
        params: { trainer_id: id },
        body,
      });
      return TrainerSchema.parse((raw as { data: unknown }).data);
    },
    onSuccess: (data) => {
      toast.success('Изменения сохранены');
      void qc.invalidateQueries({ queryKey: trainersKeys.lists() });
      void qc.invalidateQueries({ queryKey: trainersKeys.detail(data.id) });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'phone_exists') {
        // Caller renders inline Callout — do NOT toast here
        return;
      }
      const msg = err instanceof ApiError ? err.message : undefined;
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      );
    },
  });
}

export function useDeleteTrainer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      staffRequest('delete', '/api/v1/trainers/{trainer_id}', {
        params: { trainer_id: id },
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: trainersKeys.lists() });
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'trainer_in_use') {
        toast.error('Нельзя удалить', {
          description: 'У тренера есть активные слоты или брони.',
        });
        return;
      }
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
