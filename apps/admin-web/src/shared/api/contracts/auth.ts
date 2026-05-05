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

export interface AuthService {
  me(): Promise<MeResponse>
  login(input: EmailLoginInput): Promise<MeResponse>
  logout(): Promise<void>
  telegramStart(): Promise<TelegramStartResponse>
  telegramStatus(token: string): Promise<TelegramStatusResponse>
  telegramVerify(input: TelegramVerifyInput): Promise<MeResponse>
}
