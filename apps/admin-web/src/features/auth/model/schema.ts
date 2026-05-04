import { z } from 'zod'

export const emailLoginSchema = z.object({
  email: z.string().email('Введите корректный email'),
  password: z.string().min(1, 'Введите пароль'),
})
export type EmailLoginInput = z.infer<typeof emailLoginSchema>

export const telegramOtpSchema = z.object({
  code: z.string().regex(/^\d{6}$/, 'Введите 6-значный код'),
})
export type TelegramOtpInput = z.infer<typeof telegramOtpSchema>
