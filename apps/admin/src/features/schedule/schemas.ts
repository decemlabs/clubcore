/**
 * Schedule domain Zod contract layer (Phase 102-01 SCH-01).
 *
 * Wire shapes mirror the backend camelCase alias_generator.
 * Covers trainer-slots, recurring-templates, and time-off domains.
 *
 * All mutation schemas enforce business rules client-side as defense-in-depth;
 * the backend is the authority.
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// TrainerSlot (wire shape)
// ---------------------------------------------------------------------------

export const TrainerSlotSchema = z.object({
  id: z.string(),
  trainerId: z.string(),
  startTime: z.string(),
  endTime: z.string(),
  status: z.enum(['active', 'cancelled', 'booked']),
  createdAt: z.string(),
});
export type TrainerSlotData = z.infer<typeof TrainerSlotSchema>;

export const TrainerSlotListResponseSchema = z.object({
  data: z.object({
    items: z.array(TrainerSlotSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

// ---------------------------------------------------------------------------
// RecurringTemplate (wire shape)
// ---------------------------------------------------------------------------

export const RecurringTemplateSchema = z.object({
  id: z.string(),
  trainerId: z.string(),
  dayOfWeek: z.number().int().min(0).max(6),
  startTime: z.string(),
  endTime: z.string(),
  validFrom: z.string(),
  validUntil: z.string().nullable().optional(),
  isActive: z.boolean(),
});
export type RecurringTemplateData = z.infer<typeof RecurringTemplateSchema>;

export const RecurringTemplateListResponseSchema = z.object({
  data: z.object({
    items: z.array(RecurringTemplateSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

// ---------------------------------------------------------------------------
// TimeOff (wire shape)
// ---------------------------------------------------------------------------

export const TimeOffSchema = z.object({
  id: z.string(),
  trainerId: z.string(),
  blockStart: z.string(),
  blockEnd: z.string(),
  reason: z.string().nullable().optional(),
  createdAt: z.string(),
});
export type TimeOffData = z.infer<typeof TimeOffSchema>;

export const TimeOffListResponseSchema = z.object({
  data: z.object({
    items: z.array(TimeOffSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

// ---------------------------------------------------------------------------
// Mutation input schemas
// ---------------------------------------------------------------------------

/** POST /api/v1/trainer-slots */
export const PublishSlotSchema = z.object({
  trainerId: z.string().min(1, 'Выберите тренера'),
  startTime: z.string().min(1),
  endTime: z.string().min(1),
});
export type PublishSlotInput = z.infer<typeof PublishSlotSchema>;

/** PATCH /api/v1/trainer-slots/{slot_id}/cancel */
export const CancelSlotSchema = z.object({
  cancelReason: z.string().min(1).max(200),
});
export type CancelSlotInput = z.infer<typeof CancelSlotSchema>;

/** POST /api/v1/recurring-templates */
export const CreateTemplateSchema = z.object({
  trainerId: z.string().min(1, 'Выберите тренера'),
  dayOfWeek: z.number().int().min(0).max(6),
  startTime: z.string().min(1),
  endTime: z.string().min(1),
  validFrom: z.string().min(1),
  validUntil: z.string().optional(),
});
export type CreateTemplateInput = z.infer<typeof CreateTemplateSchema>;

/** POST /api/v1/time-off */
export const CreateTimeOffSchema = z.object({
  trainerId: z.string().min(1, 'Выберите тренера'),
  blockStart: z.string().min(1),
  blockEnd: z.string().min(1),
  reason: z.string().optional(),
});
export type CreateTimeOffInput = z.infer<typeof CreateTimeOffSchema>;
