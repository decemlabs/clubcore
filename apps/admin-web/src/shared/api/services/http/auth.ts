/**
 * HTTP service implementations (real-API).
 *
 * Rules:
 * - Must implement the same Contracts as mock/.
 * - No UI imports, no React — pure transport layer.
 * - Error mapping (HTTP -> ApiError) lives in @clubcore/api-client; this layer
 *   re-throws ApiError unchanged. Callers discriminate on error.code.
 * - Phase 4 D-07: every 2xx is `{data: T}`. Unwrap via _envelope.ts.
 */
import { request } from '@clubcore/api-client'
import {
  meResponseSchema,
  type AuthService,
  type MeResponse,
  type EmailLoginInput,
  type SessionFamily,
  type TelegramStartResponse,
  type TelegramStatusResponse,
  type TelegramVerifyInput,
} from '@/shared/api/contracts/auth'
import { unwrap } from './_envelope'

interface PaginatedSessionsResponse {
  items: SessionFamily[]
  total: number
  page: number
  pageSize: number
}

export const auth: AuthService = {
  async me() {
    return unwrap<MeResponse>(await request('get', '/api/v1/auth/me'))
  },
  async login(input: EmailLoginInput) {
    const raw = await request('post', '/api/v1/auth/login', { body: input })
    // Phase 5: login response wraps user in {data: {user: {...}}}.
    // Unwrap outer envelope to get {user: {...}}, then extract .user.
    const envelope = unwrap<{ user: unknown }>(raw)
    // WR-11: validate at the boundary instead of casting; a backend rename
    // or dropped field would otherwise pass a half-built object to the FE.
    return meResponseSchema.parse(envelope.user)
  },
  async logout() {
    await request('post', '/api/v1/auth/logout')
  },
  async logoutAll() {
    await request('post', '/api/v1/auth/logout-all')
  },
  async telegramStart() {
    return unwrap<TelegramStartResponse>(await request('post', '/api/v1/auth/telegram/start'))
  },
  async telegramStatus(token: string) {
    return unwrap<TelegramStatusResponse>(
      await request('get', '/api/v1/auth/telegram/status', { query: { token } }),
    )
  },
  async telegramVerify(input: TelegramVerifyInput) {
    const raw = await request('post', '/api/v1/auth/telegram/verify', { body: input })
    // Phase 7: verify response wraps user in {data: {user: {...}}} same as login.
    const envelope = unwrap<{ user: unknown }>(raw)
    // WR-11: validate at the boundary (see login for rationale).
    return meResponseSchema.parse(envelope.user)
  },
  async sessions() {
    // FE-09 / HYG-03: backend returns ResponseEnvelope[PaginatedData[ActiveSessionItem]].
    // Wire fields are already camelCase (familyId, createdAt, lastUsedAt, userAgent,
    // channel, isCurrent) via backend alias_generator=to_camel — pass through.
    const raw = unwrap<PaginatedSessionsResponse>(
      await request('get', '/api/v1/auth/sessions'),
    )
    return raw.items
  },
  async revokeSession(familyId: string) {
    await request('post', '/api/v1/auth/sessions/{family_id}/revoke', {
      params: { family_id: familyId },
    })
  },
}
