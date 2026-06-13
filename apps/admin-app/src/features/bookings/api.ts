/**
 * Bookings domain TanStack Query hooks (Phase 102-03 SCH-02).
 *
 * Queries:
 *   useBookingsByWeek({trainerId?, fromTime, toTime})  — GET /api/v1/bookings for calendar merge
 *   useBookingsByTrainer(trainerId, {fromTime,toTime}, status)  — GET /api/v1/bookings (trainer today-schedule)
 *   useBooking(id)  — GET /api/v1/bookings/{id} (detail with slot+ptPackage snapshots)
 *
 * Mutations:
 *   useCreateBooking   — POST /api/v1/bookings + Idempotency-Key (reception+owner)
 *                        409 slot_already_booked / slot_not_available → NOT toasted (caller handles inline)
 *                        All other errors → caller also handles; hook only invalidates on success.
 *   useCancelBooking   — POST /api/v1/bookings/{id}/cancel + Idempotency-Key
 *                        409 cancel_window_expired → special-cased toast (UI-SPEC copy)
 *                        Success → invalidate schedule + bookings + toast
 *   useCompleteBooking — POST /api/v1/pt-sessions {ptPackageId,trainerId,performedAt,bookingId}
 *                        + Idempotency-Key (T-102-BK-COMPLETE)
 *                        409 booking_not_confirmed / booking_mismatch → special-cased toast
 *                        NOTE: clientId is NEVER sent (backend extra='forbid')
 *
 * Idempotency-Key: crypto.randomUUID() called INSIDE mutationFn at submit time
 * (per-attempt UUID). Never called at hook init (T-102-BK-IDEM).
 *
 * cross-invalidates scheduleKeys on success (calendar refetches).
 *
 * ApiError re-exported for page/modal layers (ESLint import-boundary — D-100-03-APIERROR-REEXPORT).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { staffRequest, ApiError } from '@/api/client'
import { scheduleKeys } from '@/features/schedule/keys'
import { bookingsKeys } from './keys'
import {
  BookingSchema,
  BookingsListResponseSchema,
  type BookingCreateInput,
  type CancelBookingInput,
} from './schemas'

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/** Fetch bookings for the visible week window (used by calendar merge). */
export function useBookingsByWeek(params: {
  trainerId?: string
  fromTime: string
  toTime: string
}) {
  return useQuery({
    queryKey: bookingsKeys.byWeek(params),
    queryFn: async () => {
      const query: Record<string, string> = {
        fromTime: params.fromTime,
        toTime: params.toTime,
      }
      if (params.trainerId) query['trainerId'] = params.trainerId
      const raw = await staffRequest('get', '/api/v1/bookings', { query })
      return BookingsListResponseSchema.parse(raw).data
    },
    staleTime: 30_000,
  })
}

/**
 * Fetch confirmed bookings for a specific trainer in a time range.
 * Used by OverviewTab today-schedule (UI-SPEC §7.1).
 */
export function useBookingsByTrainer(
  trainerId: string,
  range: { fromTime: string; toTime: string },
  status: string = 'confirmed',
) {
  return useQuery({
    queryKey: bookingsKeys.byTrainer(trainerId, range),
    queryFn: async () => {
      const query: Record<string, string> = {
        trainerId,
        fromTime: range.fromTime,
        toTime: range.toTime,
        status,
      }
      const raw = await staffRequest('get', '/api/v1/bookings', { query })
      return BookingsListResponseSchema.parse(raw).data
    },
    enabled: !!trainerId,
    staleTime: 30_000,
  })
}

/** Fetch a single booking by id (GET /api/v1/bookings/{booking_id}). */
export function useBooking(id: string) {
  return useQuery({
    queryKey: bookingsKeys.detail(id),
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/bookings/{booking_id}', {
        params: { booking_id: id },
      })
      return BookingSchema.parse((raw as { data: unknown }).data)
    },
    enabled: !!id,
    staleTime: 30_000,
  })
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/**
 * Create a booking (POST /api/v1/bookings).
 * reception+owner. Idempotency-Key per attempt (T-102-BK-IDEM).
 *
 * SPECIAL: 409 slot_already_booked / slot_not_available are NOT toasted here —
 * the caller (BookingModal) catches them and shows an inline Callout + invalidates
 * the calendar. Generic errors (pt_package_* etc.) are also NOT toasted here —
 * BookingModal maps all ApiErrors from useCreateBooking to inline Callouts.
 * (T-102-BK-RACE, T-102-BK-IDOR)
 *
 * On success: invalidate scheduleKeys.all + bookingsKeys.lists() so the calendar
 * and booking lists refetch automatically.
 */
export function useCreateBooking() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: BookingCreateInput) => {
      // crypto.randomUUID() called at submit time — fresh key per attempt (T-102-BK-IDEM)
      const raw = await staffRequest('post', '/api/v1/bookings', {
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      })
      return BookingSchema.parse((raw as { data: unknown }).data)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: scheduleKeys.all })
      void qc.invalidateQueries({ queryKey: bookingsKeys.lists() })
    },
    // onError: NOT defined here — caller inspects ApiError.code for all slot/pt-package errors
    // and renders inline Callouts (T-102-BK-RACE). Do NOT toast here.
  })
}

/**
 * Cancel a booking (POST /api/v1/bookings/{booking_id}/cancel).
 * reception+owner. Idempotency-Key per attempt. 24h-window enforced server-side.
 *
 * 409 cancel_window_expired → Sonner toast with UI-SPEC copy (okno-otmeny-zakryto).
 * Other errors → generic fallback toast.
 * Success → toast «Бронирование отменено» + invalidate schedule + bookings.
 */
export function useCancelBooking() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      bookingId,
      body,
    }: {
      bookingId: string
      body: CancelBookingInput
    }) => {
      // crypto.randomUUID() called at submit time — fresh key per attempt (T-102-BK-IDEM)
      await staffRequest('post', '/api/v1/bookings/{booking_id}/cancel', {
        params: { booking_id: bookingId },
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      })
    },
    onSuccess: () => {
      toast.success('Бронирование отменено')
      void qc.invalidateQueries({ queryKey: scheduleKeys.all })
      void qc.invalidateQueries({ queryKey: bookingsKeys.lists() })
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'cancel_window_expired') {
        // UI-SPEC Copywriting Contract — cancel_window_expired special-case
        toast.error('Окно отмены закрыто', {
          description: 'До занятия менее 24 часов. Отмена доступна только владельцу.',
        })
      } else {
        const msg = err instanceof ApiError ? err.message : undefined
        toast.error(
          msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
        )
      }
    },
  })
}

/**
 * Complete a booking by recording a PT-session (POST /api/v1/pt-sessions).
 *
 * Body: {ptPackageId, trainerId, performedAt, bookingId}
 * NOTE: clientId is NEVER included (backend extra='forbid' — T-102-BK-COMPLETE).
 * performedAt is set to now (ISO string) inside the mutationFn.
 * Idempotency-Key per attempt (T-102-BK-IDEM).
 *
 * 409 booking_not_confirmed / booking_mismatch → friendly inline toast.
 * Success → toast «Сессия записана» + invalidate schedule + bookings.
 */
export function useCompleteBooking() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      ptPackageId,
      trainerId,
      bookingId,
    }: {
      ptPackageId: string
      trainerId: string
      bookingId: string
    }) => {
      // crypto.randomUUID() called at submit time — fresh key per attempt (T-102-BK-IDEM)
      // performedAt = now (ISO string). clientId intentionally absent (T-102-BK-COMPLETE).
      const body = {
        ptPackageId,
        trainerId,
        performedAt: new Date().toISOString(),
        bookingId,
      }
      const raw = await staffRequest('post', '/api/v1/pt-sessions', {
        body,
        headers: { 'Idempotency-Key': crypto.randomUUID() },
      })
      return raw
    },
    onSuccess: () => {
      toast.success('Сессия записана')
      void qc.invalidateQueries({ queryKey: scheduleKeys.all })
      void qc.invalidateQueries({ queryKey: bookingsKeys.lists() })
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === 'booking_not_confirmed') {
        toast.error('Бронирование не подтверждено', {
          description: 'Для записи сессии бронирование должно быть в статусе «Подтверждено».',
        })
      } else if (err instanceof ApiError && err.code === 'booking_mismatch') {
        toast.error('Несоответствие данных', {
          description: 'Тренер или пакет не совпадают с данными бронирования.',
        })
      } else {
        const msg = err instanceof ApiError ? err.message : undefined
        toast.error(
          msg ?? 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.',
        )
      }
    },
  })
}

// ---------------------------------------------------------------------------
// Re-export for page/modal layers (ESLint import-boundary — D-100-03-APIERROR-REEXPORT)
// ---------------------------------------------------------------------------

export { ApiError }
