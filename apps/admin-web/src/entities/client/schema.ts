import { z } from 'zod'

// E.164: +<country><digits>, 10–15 digits total after the leading +
const E164 = /^\+\d{10,15}$/

export const clientCreateSchema = z.object({
  lastName: z.string().min(1, 'Укажите фамилию'),
  firstName: z.string().min(1, 'Укажите имя'),
  middleName: z.string().optional(),
  phone: z
    .string()
    .min(1, 'Укажите номер телефона')
    .regex(E164, 'Введите телефон в формате +7 (XXX) XXX-XX-XX'),
  email: z.string().email('Введите корректный email').optional().or(z.literal('')),
  birthDate: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, 'Дата в формате ГГГГ-ММ-ДД')
    .optional()
    .or(z.literal('')),
  notes: z.string().optional(),
})
export type ClientCreateFormInput = z.infer<typeof clientCreateSchema>

export const clientUpdateSchema = clientCreateSchema.partial()
export type ClientUpdateFormInput = z.infer<typeof clientUpdateSchema>

export const clientsListQuerySchema = z.object({
  q: z.string().optional(),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(10).max(100).default(20),
})
export type ClientsListQueryInput = z.infer<typeof clientsListQuerySchema>
