/**
 * Trainers domain Zod contract layer (Phase 102-02 TRN-01).
 *
 * Wire shapes mirror the backend camelCase alias_generator.
 * All nullable optional fields use z.string().nullable().optional() to handle
 * both null (backend explicit null) and absent fields gracefully.
 *
 * TrainerUpdateSchema — all fields optional for PATCH semantics (omit = no change).
 * TrainerCreateSchema — fullName required, phone optional.
 */
import { z } from 'zod';

// ---------------------------------------------------------------------------
// Trainer wire shape (GET /api/v1/trainers, GET /api/v1/trainers/{trainer_id})
// ---------------------------------------------------------------------------

export const TrainerSchema = z.object({
  id: z.string(),
  fullName: z.string(),
  phone: z.string().nullable().optional(),
  isActive: z.boolean(),
  bio: z.string().nullable().optional(),
  specialization: z.string().nullable().optional(),
  photoUrl: z.string().nullable().optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
});
export type TrainerData = z.infer<typeof TrainerSchema>;

// ---------------------------------------------------------------------------
// List response
// ---------------------------------------------------------------------------

export const TrainersListResponseSchema = z.object({
  data: z.object({
    items: z.array(TrainerSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
});

// ---------------------------------------------------------------------------
// PATCH — all optional; omit = no change per backend contract
// ---------------------------------------------------------------------------

export const TrainerUpdateSchema = z.object({
  fullName: z.string().min(1).optional(),
  phone: z.string().nullable().optional(),
  isActive: z.boolean().optional(),
  bio: z.string().nullable().optional(),
  specialization: z.string().nullable().optional(),
  photoUrl: z.string().nullable().optional(),
});
export type TrainerUpdateInput = z.infer<typeof TrainerUpdateSchema>;

// ---------------------------------------------------------------------------
// POST — fullName required, phone optional
// ---------------------------------------------------------------------------

export const TrainerCreateSchema = z.object({
  fullName: z.string().min(1, 'Имя обязательно'),
  phone: z.string().optional(),
});
export type TrainerCreateInput = z.infer<typeof TrainerCreateSchema>;
