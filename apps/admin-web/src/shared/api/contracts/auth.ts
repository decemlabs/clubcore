import type { Role } from '@/shared/session/types'

export interface MeResponse {
  id: string
  role: Role
  fullName: string
  email?: string
  hasTelegram?: boolean
}

export interface EmailLoginInput {
  email: string
  password: string
}

export interface TelegramStartResponse {
  deepLinkUrl: string
  deepLinkToken: string
}

export interface TelegramStatusResponse {
  bound: boolean
}

export interface TelegramVerifyInput {
  token: string
  code: string
}

/**
 * FE-09 / HYG-03 — active session families.
 *
 * Wire shape mirrors backend `ActiveSessionItem` (camelCase via alias_generator).
 * Phase 23 D-23-3: `isCurrent` is resolved server-side via sha256(sz_refresh)
 * token_hash lookup; FE never computes it.
 */
export type SessionChannel = 'email' | 'telegram_bot' | string

export interface SessionFamily {
  familyId: string // UUID
  createdAt: string // ISO datetime
  lastUsedAt: string // ISO datetime
  userAgent: string | null
  channel: SessionChannel
  isCurrent: boolean
}

export interface AuthService {
  me(): Promise<MeResponse>
  login(input: EmailLoginInput): Promise<MeResponse>
  logout(): Promise<void>
  logoutAll(): Promise<void>
  telegramStart(): Promise<TelegramStartResponse>
  telegramStatus(token: string): Promise<TelegramStatusResponse>
  telegramVerify(input: TelegramVerifyInput): Promise<MeResponse>
  // Phase 22 FE-09 / HYG-03 consumer (D-22-2: http-only)
  sessions(): Promise<SessionFamily[]>
  revokeSession(familyId: string): Promise<void>
}
