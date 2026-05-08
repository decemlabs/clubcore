import { faker } from '@faker-js/faker'
import type {
  AuthService,
  MeResponse,
  EmailLoginInput,
  TelegramStartResponse,
  TelegramStatusResponse,
  TelegramVerifyInput,
} from '@/shared/api/contracts/auth'
import { DomainError } from '@/shared/api/errors'
import { useSessionStore } from '@/shared/session/store'
import { emailLoginSchema } from '@/shared/api/contracts/authSchema'
import { delay } from './_latency'

const MOCK_USER_ID = '00000000-0000-4000-8000-000000000001'
const MOCK_FULL_NAME = 'Owner Demo'
const TELEGRAM_BOUND_AFTER_POLLS = 3
const TELEGRAM_TOKEN_TTL_MS = 5 * 60 * 1000
const MOCK_OTP = '123456'

interface TelegramSessionState {
  token: string
  issuedAt: number
  pollCount: number
  bound: boolean
}
const telegramSessions = new Map<string, TelegramSessionState>()

function currentMe(): MeResponse {
  return {
    id: MOCK_USER_ID,
    role: useSessionStore.getState().role,
    fullName: MOCK_FULL_NAME,
    hasTelegram: false,
  }
}

export const auth: AuthService = {
  async me() {
    await delay()
    return currentMe()
  },

  async login(input: EmailLoginInput) {
    await delay()
    const parsed = emailLoginSchema.safeParse(input)
    if (!parsed.success) {
      const fields: Record<string, string[]> = {}
      for (const issue of parsed.error.issues) {
        const k = String(issue.path[0] ?? 'root')
        ;(fields[k] ??= []).push(issue.message)
      }
      throw new DomainError('validation_failed', 'Проверьте поля формы', fields)
    }
    // Mock has no real password check — return current "logged-in" user.
    return currentMe()
  },

  async logout() {
    await delay()
    // No state to clear in mock — RoleSwitcher controls Zustand role independently.
  },

  async logoutAll() {
    await delay()
    // No state to clear in mock — RoleSwitcher controls Zustand role independently.
  },

  async sessions() {
    await delay()
    // D-22-2: FE-09 is http-only. The mock does not implement sessions —
    // the real value is auditing real refresh-rotation families, not a pretty list.
    throw new DomainError(
      'mock_not_implemented',
      'Mock does not implement sessions — use VITE_API_MODE=http',
    )
  },

  async revokeSession(familyId: string) {
    await delay()
    void familyId
    throw new DomainError(
      'mock_not_implemented',
      'Mock does not implement sessions — use VITE_API_MODE=http',
    )
  },

  async telegramStart() {
    await delay()
    const token = faker.string.uuid()
    const issuedAt = Date.now()
    telegramSessions.set(token, { token, issuedAt, pollCount: 0, bound: false })
    const r: TelegramStartResponse = {
      deepLinkUrl: `https://t.me/sportzal_mock_bot?start=${token}`,
      deepLinkToken: token,
    }
    return r
  },

  async telegramStatus(token: string) {
    await delay()
    const session = telegramSessions.get(token)
    if (!session) {
      throw new DomainError('not_found', 'Сессия Telegram не найдена')
    }
    if (Date.now() - session.issuedAt > TELEGRAM_TOKEN_TTL_MS) {
      throw new DomainError('expired', 'Срок действия ссылки истёк')
    }
    session.pollCount += 1
    if (session.pollCount >= TELEGRAM_BOUND_AFTER_POLLS) {
      session.bound = true
    }
    const r: TelegramStatusResponse = {
      bound: session.bound,
    }
    return r
  },

  async telegramVerify({ token, code }: TelegramVerifyInput) {
    await delay()
    const session = telegramSessions.get(token)
    if (!session || !session.bound) {
      throw new DomainError('bot_not_started', 'Сначала начните чат с ботом')
    }
    if (code !== MOCK_OTP) {
      throw new DomainError('otp_invalid', 'Неверный код. Используйте 123456 в моке.')
    }
    telegramSessions.delete(token)
    return currentMe()
  },
}
