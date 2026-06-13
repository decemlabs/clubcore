/**
 * Schedule domain TanStack Query hooks (Phase 102-01 SCH-01).
 *
 * Replaces the mock useSchedule/scheduleKeys from Phase 37.
 *
 * Mutations implemented:
 *   usePublishSlot       — POST /api/v1/trainer-slots (OWNER_ONLY, Idempotency-Key)
 *   useCancelSlot        — PATCH /api/v1/trainer-slots/{slot_id}/cancel (OWNER_ONLY, Idempotency-Key)
 *   useCreateTemplate    — POST /api/v1/recurring-templates (OWNER_ONLY, Idempotency-Key)
 *   useDeactivateTemplate— POST /api/v1/recurring-templates/{id}/deactivate (OWNER_ONLY, Idempotency-Key)
 *   useCreateTimeOff     — POST /api/v1/time-off (OWNER_ONLY, Idempotency-Key)
 *                          409 time_off_booked_conflict → propagated un-toasted to caller
 *   useDeleteTimeOff     — DELETE /api/v1/time-off/{id} (OWNER_ONLY, Idempotency-Key)
 *
 * Idempotency-Key: crypto.randomUUID() called INSIDE mutationFn at submit time
 * (per-attempt UUID). Never called at hook init (T-102-IDEM).
 *
 * ApiError re-exported for page/modal layers (ESLint import-boundary — pages/modals
 * may not import @/api/client directly).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { staffRequest, ApiError } from '@/api/client'
import { scheduleKeys } from './keys'
import {
  TrainerSlotListResponseSchema,
  TrainerSlotSchema,
  RecurringTemplateSchema,
  RecurringTemplateListResponseSchema,
  TimeOffSchema,
  TimeOffListResponseSchema,
  type PublishSlotInput,
  type CancelSlotInput,
  type CreateTemplateInput,
  type CreateTimeOffInput,
} from './schemas'

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/**
 * Fetch trainer slots for the visible week range.
 * Reception+owner — no Idempotency-Key (GET is safe).
 */
export function useTrainerSlots(params: { trainerId?: string; fromTime: string; toTime: string }) {
  return useQuery({
    queryKey: scheduleKeys.week(params),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/trainer-slots', {
        query: params as Record<string, string>,
      })
      return TrainerSlotListResponseSchema.parse(raw).data
    },
    staleTime: 30_000,
  })
}

/**
 * Fetch recurring templates list.
 * Reception+owner.
 */
export function useRecurringTemplates() {
  return useQuery({
    queryKey: scheduleKeys.templates(),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/recurring-templates', {})
      return RecurringTemplateListResponseSchema.parse(raw).data
    },
    staleTime: 30_000,
  })
}

/**
 * Fetch time-off blocks list.
 * Reception+owner.
 */
export function useTimeOffBlocks() {
  return useQuery({
    queryKey: scheduleKeys.timeOff(),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/time-off', {})
      return TimeOffListResponseSchema.parse(raw).data
    },
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Mutations — Slots
// ---------------------------------------------------------------------------

/**
 * Publish a trainer slot (POST /api/v1/trainer-slots).
 * OWNER_ONLY. Idempotency-Key per attempt (T-102-IDEM).
 * 409 codes: slot_overlap / slot_too_close / slot_in_past / trainer_inactive.
 * All 409s are toasted as generic error — caller may show inline Callout from the thrown err.
 */
export function usePublishSlot() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: PublishSlotInput) => {
      // crypto.randomUUID() called at submit time — fresh key per attempt (T-102-IDEM)
      const raw = await staffRequest('post', '/api/v1/trainer-slots', {
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      })
      return TrainerSlotSchema.parse((raw as { data: unknown }).data)
    },
    onSuccess: () => {
      toast.success('Слот опубликован')
      void qc.invalidateQueries({ queryKey: scheduleKeys.all })
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      )
    },
  })
}

/**
 * Cancel a trainer slot (PATCH /api/v1/trainer-slots/{slot_id}/cancel).
 * OWNER_ONLY. Idempotency-Key per attempt.
 */
export function useCancelSlot() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ slotId, body }: { slotId: string; body: CancelSlotInput }) => {
      await staffRequest('patch', '/api/v1/trainer-slots/{slot_id}/cancel', {
        params: { slot_id: slotId },
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      })
    },
    onSuccess: () => {
      toast.success('Слот отменён')
      void qc.invalidateQueries({ queryKey: scheduleKeys.all })
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      )
    },
  })
}

// ---------------------------------------------------------------------------
// Mutations — Recurring Templates
// ---------------------------------------------------------------------------

/**
 * Create a recurring template (POST /api/v1/recurring-templates).
 * OWNER_ONLY. Idempotency-Key per attempt.
 */
export function useCreateTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: CreateTemplateInput) => {
      const raw = await staffRequest('post', '/api/v1/recurring-templates', {
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      })
      return RecurringTemplateSchema.parse((raw as { data: unknown }).data)
    },
    onSuccess: () => {
      toast.success('Шаблон создан')
      void qc.invalidateQueries({ queryKey: scheduleKeys.all })
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      )
    },
  })
}

/**
 * Deactivate a recurring template (POST /api/v1/recurring-templates/{id}/deactivate).
 * OWNER_ONLY. Idempotency-Key per attempt.
 */
export function useDeactivateTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (templateId: string) => {
      await staffRequest('post', '/api/v1/recurring-templates/{template_id}/deactivate', {
        params: { template_id: templateId },
        body: {},
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      })
    },
    onSuccess: () => {
      toast.success('Шаблон деактивирован')
      void qc.invalidateQueries({ queryKey: scheduleKeys.all })
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      )
    },
  })
}

// ---------------------------------------------------------------------------
// Mutations — Time-Off
// ---------------------------------------------------------------------------

/**
 * Create a time-off block (POST /api/v1/time-off).
 * OWNER_ONLY. Idempotency-Key per attempt.
 *
 * SPECIAL: 409 time_off_booked_conflict is NOT toasted here — the error is
 * propagated to the caller (ScheduleManagementModal) which renders the
 * force-override conflict state. Generic errors still toast. (T-102-FORCE)
 */
export function useCreateTimeOff() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ body, force }: { body: CreateTimeOffInput; force?: boolean }) => {
      const query = force ? { force: true } : undefined
      const raw = await staffRequest('post', '/api/v1/time-off', {
        body,
        query: query as Record<string, boolean> | undefined,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      })
      return TimeOffSchema.parse((raw as { data: unknown }).data)
    },
    onSuccess: (_data, vars) => {
      if (vars.force) {
        toast.success('Период заблокирован')
      } else {
        toast.success('Период заблокирован')
      }
      void qc.invalidateQueries({ queryKey: scheduleKeys.all })
    },
    onError: (err) => {
      // 409 time_off_booked_conflict — let caller handle (no toast)
      if (err instanceof ApiError && err.code === 'time_off_booked_conflict') {
        return
      }
      const msg = err instanceof ApiError ? err.message : undefined
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      )
    },
  })
}

/**
 * Delete a time-off block (DELETE /api/v1/time-off/{id}).
 * OWNER_ONLY. Idempotency-Key per attempt.
 */
export function useDeleteTimeOff() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (timeOffId: string) => {
      await staffRequest('delete', '/api/v1/time-off/{time_off_id}', {
        params: { time_off_id: timeOffId },
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      })
    },
    onSuccess: () => {
      toast.success('Блокировка удалена')
      void qc.invalidateQueries({ queryKey: scheduleKeys.all })
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : undefined
      toast.error(
        msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
      )
    },
  })
}

// ---------------------------------------------------------------------------
// Re-export for page/modal layers (ESLint import-boundary)
// ---------------------------------------------------------------------------

export { ApiError }
