/**
 * Auth domain zod contract layer (Phase 100 FND-03).
 *
 * These schemas define the verified wire shapes for the auth/session domain:
 *  - LoginRequestSchema: mirrors backend LoginRequest (password min_length=12)
 *  - LoginResponseSchema: POST /auth/login → {data:{user:{id,role,fullName}}}
 *  - MeResponseSchema: GET /auth/me → {data:{id,role,fullName,email,hasTelegram}}
 *  - ApiErrorEnvelopeSchema: top-level {code,message,fields?} (NOT wrapped in data)
 *  - PasswordResetRequestSchema: POST /auth/password-reset/request
 *  - PasswordResetConfirmSchema: POST /auth/password-reset/confirm — body key is `newPassword`
 *
 * Backend wire format is camelCase (alias_generator=to_camel on ContractModel).
 * CRITICAL: the confirm body uses `newPassword` (wire camelCase of `new_password`).
 *
 * Each domain repeating this pattern in Phase 101+ should:
 *   1. Create features/<domain>/schemas.ts with zod contracts matching the backend wire shape.
 *   2. In features/<domain>/api.ts, replace mockResponse() queryFn with staffRequest + Schema.parse.
 *   See features/auth/ as the worked example (FND-03 seam).
 */
import { z } from 'zod'

// ---------------------------------------------------------------------------
// Login
// ---------------------------------------------------------------------------

export const LoginRequestSchema = z.object({
  email: z.string().email('Введите корректный адрес почты'),
  password: z.string().min(12, 'Пароль должен содержать не менее 12 символов'),
})
export type LoginRequest = z.infer<typeof LoginRequestSchema>

export const LoginResponseSchema = z.object({
  data: z.object({
    user: z.object({
      id: z.string(),
      role: z.enum(['owner', 'reception']),
      fullName: z.string(),
    }),
  }),
})
export type LoginResponse = z.infer<typeof LoginResponseSchema>

// ---------------------------------------------------------------------------
// Me (session)
// ---------------------------------------------------------------------------

export const MeResponseSchema = z.object({
  data: z.object({
    id: z.string(),
    role: z.enum(['owner', 'reception']),
    fullName: z.string(),
    email: z.string(),
    hasTelegram: z.boolean(),
  }),
})
export type MeResponse = z.infer<typeof MeResponseSchema>
export type MeData = MeResponse['data']

// ---------------------------------------------------------------------------
// Error envelope (top-level, NOT wrapped in data)
// ---------------------------------------------------------------------------

export const ApiErrorEnvelopeSchema = z.object({
  code: z.string(),
  message: z.string(),
  fields: z.record(z.string()).optional(),
})
export type ApiErrorEnvelope = z.infer<typeof ApiErrorEnvelopeSchema>

// ---------------------------------------------------------------------------
// Password reset
// ---------------------------------------------------------------------------

/**
 * Client-side validation schema for password reset request.
 * Note: backend accepts a loose string (anti-oracle — 202 always returned);
 * the client is intentionally stricter to provide UX feedback before submission.
 */
export const PasswordResetRequestSchema = z.object({
  email: z.string().email('Введите корректный адрес почты'),
})
export type PasswordResetRequest = z.infer<typeof PasswordResetRequestSchema>

/**
 * Password reset confirm schema.
 * CRITICAL: body field name is `newPassword` (wire camelCase of backend `new_password`).
 * The `password` key from the PATTERNS sketch was incorrect — confirmed against schemas.py.
 */
export const PasswordResetConfirmSchema = z.object({
  token: z.string().min(1, 'Токен не может быть пустым'),
  newPassword: z.string().min(12, 'Пароль должен содержать не менее 12 символов'),
})
export type PasswordResetConfirm = z.infer<typeof PasswordResetConfirmSchema>
