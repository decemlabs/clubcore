/**
 * Client-PWA typed transport (Phase 69 PWA-03).
 *
 * Thin specialization of @clubcore/api-client's request() for the cc_client_*
 * cookie stack:
 *
 *  - D-A3 equivalent: /api/v1/client/otp/* and /api/v1/client/session/* are
 *    refresh-exempt (mirrors staff AUTH_EXEMPT_PATHS).
 *  - D-11 equivalent: reads `clubcore_client_csrf` cookie (NOT `clubcore_csrf`).
 *  - D-A1 equivalent: single-flight refresh hits /api/v1/client/session/refresh
 *    (NOT /api/v1/auth/refresh).
 *  - T-69-08: CSRF spoofing mitigated by using the client-scoped cookie name,
 *    isolating it from the staff `clubcore_csrf` cookie (CISO-05).
 *  - T-69-09: refresh single-flights to /api/v1/client/session/refresh only —
 *    never the staff /api/v1/auth/refresh (prevents cross-principal cookie rotation).
 */
import { ApiError } from '@clubcore/api-client'
import type { paths } from '@clubcore/api-client'

// Client-scoped CSRF cookie name (D-11 / Phase 68 CISO-02)
const CLIENT_CSRF_COOKIE = 'clubcore_client_csrf'

// Client-side refresh-exempt paths (mirror staff AUTH_EXEMPT_PATHS shape — D-A3 equivalent)
export const CLIENT_AUTH_EXEMPT_PATHS: readonly string[] = [
  '/api/v1/client/otp/request',
  '/api/v1/client/otp/verify',
  '/api/v1/client/session/refresh',
  '/api/v1/client/session/logout',
  '/api/v1/client/me',
]

function isClientAuthExempt(path: string): boolean {
  const pathname = path.split('?')[0] ?? path
  return CLIENT_AUTH_EXEMPT_PATHS.includes(pathname)
}

// D-11 equivalent: mirror server _SAFE_METHODS = {GET, HEAD, OPTIONS, TRACE}.
function isMutating(method: string): boolean {
  return method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS'
}

/**
 * Read the client-scoped CSRF cookie (clubcore_client_csrf).
 * NOT `clubcore_csrf` — that belongs to the staff/admin transport.
 */
export function readClientCsrfCookie(): string | undefined {
  const prefix = `${CLIENT_CSRF_COOKIE}=`
  const cookies = document.cookie.split(';')
  for (const raw of cookies) {
    const c = raw.trim()
    if (c.startsWith(prefix)) return c.slice(prefix.length)
  }
  return undefined
}

// D-A4 equivalent: module-scoped single-flight promise for the client session refresh.
// Concurrent awaiters share the same promise; slot cleared on next microtask after settle.
let inFlightClientRefresh: Promise<Response> | null = null

/**
 * Single-flight refresh to /api/v1/client/session/refresh (T-69-09).
 * Never calls the staff /api/v1/auth/refresh — prevents cross-principal cookie rotation.
 */
export function clientRefreshOnce(): Promise<Response> {
  if (inFlightClientRefresh) return inFlightClientRefresh
  inFlightClientRefresh = fetch('/api/v1/client/session/refresh', {
    method: 'POST',
    credentials: 'include',
  }).finally(() => {
    queueMicrotask(() => {
      inFlightClientRefresh = null
    })
  })
  return inFlightClientRefresh
}

async function parseErrorBody(
  res: Response,
): Promise<{ code: string; message: string; fields?: Record<string, unknown> }> {
  try {
    const body = (await res.json()) as {
      code?: unknown
      message?: unknown
      fields?: unknown
    }
    return {
      code: typeof body.code === 'string' ? body.code : 'unknown_error',
      message: typeof body.message === 'string' ? body.message : '',
      fields:
        typeof body.fields === 'object' && body.fields !== null
          ? (body.fields as Record<string, unknown>)
          : undefined,
    }
  } catch {
    return { code: 'unknown_error', message: res.statusText }
  }
}

export interface ClientRequestInit extends Omit<RequestInit, 'method' | 'body'> {
  body?: unknown
  params?: Record<string, string | number>
  query?: Record<string, string | number | boolean>
}

function interpolatePath(path: string, params?: Record<string, string | number>): string {
  if (!path.includes('{')) return path
  return path.replace(/\{(\w+)\}/g, (_, key: string) => {
    const v = params?.[key]
    if (v === undefined) {
      throw new ApiError('client_error', `Missing path param '${key}' for ${path}`)
    }
    return encodeURIComponent(String(v))
  })
}

function appendQuery(url: string, query?: Record<string, string | number | boolean>): string {
  if (!query) return url
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    sp.set(k, String(v))
  }
  const qs = sp.toString()
  if (!qs) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}${qs}`
}

async function finishResponse(res: Response): Promise<unknown> {
  if (res.ok) {
    if (res.status === 204) return undefined
    const ct = res.headers.get('content-type') ?? ''
    if (ct.includes('application/json')) {
      const text = await res.text()
      if (!text) return undefined
      try {
        return JSON.parse(text) as unknown
      } catch (err) {
        throw new ApiError('unknown_error', 'Failed to parse JSON response', undefined, {
          cause: err,
        })
      }
    }
    return undefined
  }
  const body = await parseErrorBody(res)
  throw new ApiError(body.code, body.message, body.fields)
}

/**
 * Client-scoped typed transport.
 *
 * Mirrors the staff request() contract from @clubcore/api-client but uses:
 *  - clubcore_client_csrf CSRF cookie (not clubcore_csrf)
 *  - /api/v1/client/session/refresh for token rotation (not /api/v1/auth/refresh)
 *  - CLIENT_AUTH_EXEMPT_PATHS for refresh bypass
 */
export async function clientRequest<
  P extends keyof paths,
  M extends keyof paths[P] & string,
>(method: M, path: P, init?: ClientRequestInit): Promise<unknown> {
  const url = appendQuery(
    interpolatePath(path as unknown as string, init?.params),
    init?.query,
  )
  const upper = (method as string).toUpperCase()
  const headers = new Headers(init?.headers)
  headers.set('Accept', 'application/json')

  let bodyPayload: BodyInit | undefined
  if (init?.body !== undefined) {
    const b = init.body
    if (
      b instanceof FormData ||
      b instanceof Blob ||
      b instanceof URLSearchParams ||
      b instanceof ArrayBuffer ||
      ArrayBuffer.isView(b) ||
      b instanceof ReadableStream
    ) {
      bodyPayload = b as BodyInit
    } else {
      headers.set('Content-Type', 'application/json')
      bodyPayload = JSON.stringify(b)
    }
  }

  if (isMutating(upper)) {
    const csrf = readClientCsrfCookie()
    if (csrf) headers.set('X-CSRF-Token', csrf)
  }

  const {
    params: _params,
    body: _body,
    headers: _headers,
    query: _query,
    ...restInit
  } = init ?? {}
  void _params
  void _body
  void _headers
  void _query

  const baseInit: RequestInit = {
    ...restInit,
    method: upper,
    credentials: 'include',
    headers,
    body: bodyPayload,
  }

  let res: Response
  try {
    res = await fetch(url, baseInit)
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    throw new ApiError('network_error', message)
  }

  if (res.status !== 401 || isClientAuthExempt(url)) {
    return finishResponse(res)
  }

  // D-A4 equivalent: single-flight refresh for non-exempt 401s
  let refreshRes: Response
  try {
    refreshRes = await clientRefreshOnce()
  } catch (err) {
    throw new ApiError(
      'session_expired',
      'Session expired, please log in again.',
      undefined,
      { cause: err },
    )
  }
  if (!refreshRes.ok) {
    throw new ApiError('session_expired', 'Session expired, please log in again.')
  }

  // Retry the original request once with freshly-set CSRF cookie
  const retryHeaders = new Headers(headers)
  if (isMutating(upper)) {
    const csrf = readClientCsrfCookie()
    if (csrf) retryHeaders.set('X-CSRF-Token', csrf)
    else retryHeaders.delete('X-CSRF-Token')
  }
  let retryRes: Response
  try {
    retryRes = await fetch(url, { ...baseInit, headers: retryHeaders })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    throw new ApiError('network_error', message)
  }
  if (retryRes.status === 401) {
    throw new ApiError('session_expired', 'Session expired, please log in again.')
  }
  return finishResponse(retryRes)
}
