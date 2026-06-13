/**
 * Clients domain zod contract layer (Phase 101 CLI-01, CLI-03).
 *
 * Wire shapes mirror backend camelCase aliases (Pydantic alias_generator=to_camel).
 *
 *  - ClientSchema: GET /api/v1/clients/{id} → {data: Client}
 *  - ClientsListResponseSchema: GET /api/v1/clients → {data:{items,total,page,pageSize}}
 *  - ClientCreateSchema: POST /api/v1/clients body validation + form validation
 *  - ClientUpdateSchema: PATCH /api/v1/clients/{id} body (all fields partial)
 *
 * Phone regex: ^\+[1-9]\d{1,14}$ (E.164 without leading zeros) — mirrors backend.
 * Email: accepts empty string '' (cleared field) via .or(z.literal('')) — mirrors UX.
 * Tags: ≤16 items, each ≤32 chars, lowercase/digits/cyrillic/hyphen/underscore.
 * Notes: ≤4096 chars.
 */
import { z } from 'zod'

// ---------------------------------------------------------------------------
// Client wire shape (used in list items + detail response)
// ---------------------------------------------------------------------------

export const ClientSchema = z.object({
  id: z.string(),
  lastName: z.string(),
  firstName: z.string(),
  middleName: z.string().nullable().optional(),
  phone: z.string(),
  email: z.string().nullable().optional(),
  birthday: z.string().nullable().optional(),
  gender: z.enum(['male', 'female']).nullable().optional(),
  tags: z.array(z.string()),
  notes: z.string().nullable().optional(),
  telegramUserId: z.string().nullable().optional(),
  createdAt: z.string(),
})
export type ClientData = z.infer<typeof ClientSchema>

// ---------------------------------------------------------------------------
// List response envelope
// ---------------------------------------------------------------------------

export const ClientsListResponseSchema = z.object({
  data: z.object({
    items: z.array(ClientSchema),
    total: z.number(),
    page: z.number(),
    pageSize: z.number(),
  }),
})

// ---------------------------------------------------------------------------
// Create input (client-side Zod for form + submit validation)
// ---------------------------------------------------------------------------

export const ClientCreateSchema = z.object({
  lastName: z.string().min(1, 'Фамилия обязательна'),
  firstName: z.string().min(1, 'Имя обязательно'),
  middleName: z.string().optional(),
  phone: z
    .string()
    .regex(/^\+[1-9]\d{1,14}$/, 'Введите телефон в формате +7XXXXXXXXXX'),
  email: z
    .string()
    .email('Введите корректный адрес почты')
    .optional()
    .or(z.literal('')),
  birthday: z.string().optional(),
  gender: z.enum(['male', 'female']).optional(),
  tags: z
    .array(
      z
        .string()
        .max(32, 'Тег не может быть длиннее 32 символов')
        .regex(/^[a-z0-9а-я\-_]+$/, 'Тег содержит недопустимые символы'),
    )
    .max(16, 'Не более 16 тегов')
    .optional(),
  notes: z.string().max(4096, 'Заметка не может превышать 4096 символов').optional(),
  telegramUserId: z.string().optional(),
})
export type ClientCreateInput = z.infer<typeof ClientCreateSchema>

// PATCH — same schema but every field is optional
export const ClientUpdateSchema = ClientCreateSchema.partial()
export type ClientUpdateInput = z.infer<typeof ClientUpdateSchema>
