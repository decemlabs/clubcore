import { z } from 'zod'

// E.164 regex — matches backend PHONE_REGEX (D-31-05 reuse)
const PHONE_REGEX = /^\+[1-9]\d{1,14}$/

export const createTrainerSchema = z.object({
  fullName: z.string().min(1, 'Укажите ФИО').max(200),
  phone: z
    .string()
    .transform((v) => (v === '' ? undefined : v))
    .pipe(
      z
        .string()
        .regex(PHONE_REGEX, 'Введите телефон в формате +7XXXXXXXXXX')
        .nullable()
        .optional(),
    )
    .optional(),
})

export const updateTrainerSchema = createTrainerSchema.extend({
  isActive: z.boolean(),
})

export type CreateTrainerInput = z.infer<typeof createTrainerSchema>
export type UpdateTrainerInput = z.infer<typeof updateTrainerSchema>
