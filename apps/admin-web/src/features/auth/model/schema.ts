// Schemas live in src/shared/api/contracts/authSchema.ts so mock services can
// validate the same shape the form submits without crossing the features → shared
// boundary in reverse.
export {
  emailLoginSchema,
  telegramOtpSchema,
  type EmailLoginFormInput,
  type TelegramOtpFormInput,
} from '@/shared/api/contracts/authSchema'

import type { EmailLoginFormInput, TelegramOtpFormInput } from '@/shared/api/contracts/authSchema'

export type EmailLoginInput = EmailLoginFormInput
export type TelegramOtpInput = TelegramOtpFormInput
