/**
 * HTTP service implementations (real-API).
 *
 * Rules:
 * - Must implement the same Contracts as mock/.
 * - No UI imports, no React — pure transport layer.
 * - Error mapping (HTTP -> ApiError) lives in @sportzal/api-client; this layer
 *   re-throws ApiError unchanged. Callers discriminate on error.code.
 * - Phase 4 D-07: every 2xx is `{data: T}`. Unwrap via _envelope.ts.
 */
import { request } from '@sportzal/api-client'
import type {
  AuthService,
  MeResponse,
  EmailLoginInput,
  TelegramStartResponse,
  TelegramStatusResponse,
  TelegramVerifyInput,
} from '@/shared/api/contracts/auth'
import { unwrap } from './_envelope'

export const auth: AuthService = {
  async me() {
    return unwrap<MeResponse>(await request('get', '/api/v1/auth/me'))
  },
  async login(input: EmailLoginInput) {
    const raw = await request('post', '/api/v1/auth/login', { body: input })
    // Phase 5: login response wraps user in {data: {user: {...}}}.
    // Unwrap outer envelope to get {user: {...}}, then extract .user.
    const envelope = unwrap<{ user: MeResponse }>(raw)
    // The LoginResponse shape has {user: UserPublic} -- map to MeResponse shape.
    return envelope.user as MeResponse
  },
  async logout() {
    await request('post', '/api/v1/auth/logout')
  },
  async telegramStart() {
    return unwrap<TelegramStartResponse>(await request('post', '/api/v1/auth/telegram/start'))
  },
  async telegramStatus(token: string) {
    // telegram/status uses query param `token` -- append to URL since RequestInitWithBody
    // has no `query` field. The `as never` is safe here because:
    //   1. token is encoded via encodeURIComponent (no injection),
    //   2. the path prefix is a literal string controlled by us,
    //   3. the openapi-fetch typed paths map cannot represent dynamic query strings yet.
    // TODO: replace with typed query params when @sportzal/api-client adds a `query` field.
    const url = `/api/v1/auth/telegram/status?token=${encodeURIComponent(token)}`
    return unwrap<TelegramStatusResponse>(await request('get', url as never))
  },
  async telegramVerify(input: TelegramVerifyInput) {
    const raw = await request('post', '/api/v1/auth/telegram/verify', { body: input })
    // Phase 7: verify response wraps user in {data: {user: {...}}} same as login.
    const envelope = unwrap<{ user: MeResponse }>(raw)
    return envelope.user as MeResponse
  },
}
