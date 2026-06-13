/**
 * Bookings domain Zod contract layer (Phase 102-03 SCH-02).
 *
 * Wire shapes mirror the backend camelCase alias_generator.
 * BookingDetailResponse includes optional slot, ptPackage, and clientFullName snapshots.
 *
 * Status enum: confirmed | cancelled | no_show | completed.
 *
 * Mutation input schemas:
 *   BookingCreateSchema   — POST /api/v1/bookings {slotId, clientId, ptPackageId}
 *   CancelBookingSchema   — POST /api/v1/bookings/{id}/cancel {reason 1-200}
 *   CompletePtSessionSchema — POST /api/v1/pt-sessions {ptPackageId, trainerId, performedAt, bookingId}
 *                             NOTE: no clientId (backend extra='forbid' — T-102-BK-COMPLETE)
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Booking (wire shape + optional detail snapshots)
// ---------------------------------------------------------------------------

export const BookingSchema = z.object({
  id: z.string(),
  slotId: z.string(),
  clientId: z.string(),
  ptPackageId: z.string(),
  status: z.enum(['confirmed', 'cancelled', 'no_show', 'completed']),
  // BookingDetailResponse adds slot + ptPackage snapshots + clientFullName
  slot: z
    .object({
      trainerId: z.string(),
      startTime: z.string(),
      endTime: z.string(),
      trainerFullName: z.string().optional(),
    })
    .optional(),
  ptPackage: z
    .object({
      id: z.string(),
      planName: z.string(),
      sessionsRemaining: z.number(),
      sessionsTotal: z.number(),
    })
    .optional(),
  clientFullName: z.string().optional(),
  createdAt: z.string(),
});
export type BookingData = z.infer<typeof BookingSchema>;

export const BookingsListResponseSchema = z.object({
  data: z.object({
    items: z.array(BookingSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

// ---------------------------------------------------------------------------
// Mutation input schemas
// ---------------------------------------------------------------------------

/** POST /api/v1/bookings */
export const BookingCreateSchema = z.object({
  slotId: z.string().min(1),
  clientId: z.string().min(1, 'Клиент обязателен'),
  ptPackageId: z.string().min(1, 'Выберите PT-пакет'),
});
export type BookingCreateInput = z.infer<typeof BookingCreateSchema>;

/** POST /api/v1/bookings/{booking_id}/cancel */
export const CancelBookingSchema = z.object({
  reason: z.string().min(1).max(200),
});
export type CancelBookingInput = z.infer<typeof CancelBookingSchema>;

/**
 * POST /api/v1/pt-sessions body when completing a booking.
 * NOTE: clientId is intentionally absent — backend extra='forbid' will reject it (T-102-BK-COMPLETE).
 * performedAt is set to now inside the mutationFn.
 */
export const CompletePtSessionSchema = z.object({
  ptPackageId: z.string().min(1),
  trainerId: z.string().min(1),
  performedAt: z.string(),
  bookingId: z.string().min(1),
});
export type CompletePtSessionInput = z.infer<typeof CompletePtSessionSchema>;
