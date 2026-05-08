import { z } from 'zod'

export const phoneSearchSchema = z.object({
  query: z.string().min(2, 'Введите минимум 2 символа').max(20),
})

export type PhoneSearchInput = z.infer<typeof phoneSearchSchema>
