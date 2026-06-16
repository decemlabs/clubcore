/**
 * Auth domain zod contract tests (Phase 100 FND-03; extended Phase 109 PROF-01/02).
 *
 * Pure zod parse assertions — no network, no React.
 * Validates that schemas correctly accept and reject backend wire shapes.
 */
import { describe, it, expect } from 'vitest'
import {
  LoginRequestSchema,
  LoginResponseSchema,
  MeResponseSchema,
  ApiErrorEnvelopeSchema,
  PasswordResetRequestSchema,
  PasswordResetConfirmSchema,
  ProfileUpdateSchema,
  ChangePasswordSchema,
} from './schemas'

describe('LoginRequestSchema', () => {
  it('rejects email without @', () => {
    const result = LoginRequestSchema.safeParse({ email: 'notanemail', password: 'StrongPass123!' })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.email).toBeDefined()
    }
  })

  it('rejects password shorter than 12 chars with Russian message', () => {
    const result = LoginRequestSchema.safeParse({
      email: 'user@example.com',
      password: 'short',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const pwErrors = result.error.flatten().fieldErrors.password
      expect(pwErrors).toBeDefined()
      expect(pwErrors?.[0]).toContain('12')
    }
  })

  it('accepts a valid email + password pair (>= 12 chars)', () => {
    const result = LoginRequestSchema.safeParse({
      email: 'admin@moizal.ru',
      password: 'SuperSecure123!',
    })
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.email).toBe('admin@moizal.ru')
    }
  })
})

describe('LoginResponseSchema', () => {
  const validPayload = {
    data: {
      user: {
        id: '00000000-0000-0000-0000-000000000001',
        role: 'owner' as const,
        fullName: 'Иван Иванов',
      },
    },
  }

  it('parses valid login response and exposes .data.user', () => {
    const result = LoginResponseSchema.parse(validPayload)
    expect(result.data.user.role).toBe('owner')
    expect(result.data.user.fullName).toBe('Иван Иванов')
  })

  it('rejects an unknown role', () => {
    const bad = { data: { user: { id: 'x', role: 'superadmin', fullName: 'X' } } }
    expect(() => LoginResponseSchema.parse(bad)).toThrow()
  })

  it('accepts reception role', () => {
    const payload = {
      data: { user: { id: '00000000-0000-0000-0000-000000000002', role: 'reception', fullName: 'Маша' } },
    }
    const result = LoginResponseSchema.parse(payload)
    expect(result.data.user.role).toBe('reception')
  })
})

describe('MeResponseSchema', () => {
  const validPayload = {
    data: {
      id: '00000000-0000-0000-0000-000000000001',
      role: 'reception' as const,
      fullName: 'Мария Иванова',
      email: 'maria@moizal.ru',
      hasTelegram: false,
    },
  }

  it('parses valid /auth/me response and yields the user data', () => {
    const result = MeResponseSchema.parse(validPayload)
    expect(result.data.role).toBe('reception')
    expect(result.data.hasTelegram).toBe(false)
    expect(result.data.email).toBe('maria@moizal.ru')
  })

  it('rejects response missing hasTelegram', () => {
    const bad = {
      data: {
        id: 'x',
        role: 'owner',
        fullName: 'X',
        email: 'x@x.ru',
        // hasTelegram intentionally omitted
      },
    }
    expect(() => MeResponseSchema.parse(bad)).toThrow()
  })

  it('rejects unknown role in me response', () => {
    expect(() =>
      MeResponseSchema.parse({
        data: { id: 'x', role: 'manager', fullName: 'X', email: 'x@x.ru', hasTelegram: false },
      }),
    ).toThrow()
  })
})

describe('ApiErrorEnvelopeSchema', () => {
  it('parses a minimal error envelope', () => {
    const result = ApiErrorEnvelopeSchema.parse({
      code: 'invalid_credentials',
      message: 'Неверный email или пароль',
    })
    expect(result.code).toBe('invalid_credentials')
    expect(result.fields).toBeUndefined()
  })

  it('parses error with optional fields map', () => {
    const result = ApiErrorEnvelopeSchema.parse({
      code: 'validation_error',
      message: 'Ошибка валидации',
      fields: { email: 'Некорректный адрес' },
    })
    expect(result.fields?.['email']).toBe('Некорректный адрес')
  })
})

describe('PasswordResetRequestSchema', () => {
  it('accepts a valid email', () => {
    const result = PasswordResetRequestSchema.safeParse({ email: 'reset@moizal.ru' })
    expect(result.success).toBe(true)
  })

  it('rejects invalid email format', () => {
    const result = PasswordResetRequestSchema.safeParse({ email: 'notanemail' })
    expect(result.success).toBe(false)
  })
})

describe('PasswordResetConfirmSchema', () => {
  it('accepts a valid token and newPassword (>= 12 chars)', () => {
    const result = PasswordResetConfirmSchema.safeParse({
      token: 'abc123token',
      newPassword: 'NewStrongPass1!',
    })
    expect(result.success).toBe(true)
    if (result.success) {
      expect(result.data.newPassword).toBe('NewStrongPass1!')
    }
  })

  it('rejects newPassword shorter than 12 chars', () => {
    const result = PasswordResetConfirmSchema.safeParse({
      token: 'abc123token',
      newPassword: 'short',
    })
    expect(result.success).toBe(false)
  })

  it('rejects empty token', () => {
    const result = PasswordResetConfirmSchema.safeParse({
      token: '',
      newPassword: 'ValidPassword123!',
    })
    expect(result.success).toBe(false)
  })

  it('uses newPassword key (not password) for the confirm field', () => {
    // Verify that the `password` key is rejected (wrong field name)
    const result = PasswordResetConfirmSchema.safeParse({
      token: 'abc123',
      password: 'ValidPassword123!',
    })
    // This will still pass if newPassword is missing — zod won't find newPassword
    expect(result.success).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Phase 109 PROF-01/02 — ProfileUpdateSchema + ChangePasswordSchema
// ---------------------------------------------------------------------------

describe('ProfileUpdateSchema', () => {
  it('accepts valid fullName (>= 2 chars) and email', () => {
    const result = ProfileUpdateSchema.safeParse({ fullName: 'Ab', email: 'a@b.co' })
    expect(result.success).toBe(true)
  })

  it('rejects fullName shorter than 2 chars', () => {
    const result = ProfileUpdateSchema.safeParse({ fullName: 'A', email: 'a@b.co' })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.flatten().fieldErrors.fullName).toBeDefined()
    }
  })

  it('rejects a malformed email', () => {
    const result = ProfileUpdateSchema.safeParse({ fullName: 'Иван', email: 'notanemail' })
    expect(result.success).toBe(false)
    if (!result.success) {
      const emailErrors = result.error.flatten().fieldErrors.email
      expect(emailErrors).toBeDefined()
      expect(emailErrors?.[0]).toBe('Введите корректный адрес почты')
    }
  })

  it('has no confirmPassword field in the schema (wire schema — no UI-only confirm)', () => {
    // The schema must not have a confirm field — confirm is UI-only (Plan 04).
    // An object with an extra confirmPassword is valid (zod strips unknown fields by default).
    const result = ProfileUpdateSchema.safeParse({
      fullName: 'Иван Иванов',
      email: 'ivan@example.ru',
      confirmPassword: 'ignored',
    })
    expect(result.success).toBe(true)
    if (result.success) {
      // confirmPassword must not appear in the parsed output
      expect('confirmPassword' in result.data).toBe(false)
    }
  })
})

describe('ChangePasswordSchema', () => {
  it('accepts valid currentPassword (>= 1 char) and newPassword (>= 12 chars)', () => {
    const result = ChangePasswordSchema.safeParse({
      currentPassword: 'x',
      newPassword: 'twelvecharss',
    })
    expect(result.success).toBe(true)
  })

  it('rejects empty currentPassword with Russian message', () => {
    const result = ChangePasswordSchema.safeParse({
      currentPassword: '',
      newPassword: 'ValidPassword123!',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const errors = result.error.flatten().fieldErrors.currentPassword
      expect(errors).toBeDefined()
      expect(errors?.[0]).toBe('Введите текущий пароль')
    }
  })

  it('rejects newPassword shorter than 12 chars with existing Russian message', () => {
    const result = ChangePasswordSchema.safeParse({
      currentPassword: 'anypassword',
      newPassword: 'short',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const errors = result.error.flatten().fieldErrors.newPassword
      expect(errors).toBeDefined()
      expect(errors?.[0]).toBe('Пароль должен содержать не менее 12 символов')
    }
  })

  it('has no confirmPassword field (wire schema — no UI-only confirm)', () => {
    const result = ChangePasswordSchema.safeParse({
      currentPassword: 'validpass',
      newPassword: 'ValidPassword123!',
      confirmPassword: 'ignored',
    })
    expect(result.success).toBe(true)
    if (result.success) {
      expect('confirmPassword' in result.data).toBe(false)
    }
  })
})
