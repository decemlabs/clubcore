/**
 * Staff-scoped typed transport (Phase 100 FND-02).
 *
 * Staff principal specialisation of the @clubcore/api-client transport:
 *
 *  - T-100-06: reads only `clubcore_csrf` (JS-readable double-submit token).
 *    `cc_access`/`cc_refresh` are httpOnly — JS never reads them, they travel
 *    via `credentials:'include'`.
 *  - T-100-03: CSRF double-submit — X-CSRF-Token on every POST/PUT/PATCH/DELETE.
 *  - T-100-04: single-flight refresh to /api/v1/auth/refresh ONLY (staff path).
 *    Never /api/v1/client/session/refresh (cross-principal cookie rotation risk).
 *  - T-100-05: second 401 throws ApiError('session_expired') → QueryClient publishes
 *    once via authBus → app navigates to /login.
 *
 * `mockResponse()` is PRESERVED so non-auth feature api.ts swap-seam files
 * continue to resolve mock data unchanged until their domain is wired.
 */
import { ApiError } from '@clubcore/api-client'
import type { paths } from '@clubcore/api-client'

// Re-export ApiError so all admin-app consumers (and query-client.ts) share ONE class identity.
export { ApiError } from '@clubcore/api-client'

// Staff-scoped CSRF cookie name (T-100-06 / T-100-03).
// NOT 'clubcore_client_csrf' — that belongs to the client-PWA transport.
const STAFF_CSRF_COOKIE = 'clubcore_csrf'

// Paths where a 401 must NOT trigger the refresh flow (pre-auth / the refresh
// itself / logout). Compared against the path portion only (query stripped).
export const STAFF_AUTH_EXEMPT_PATHS: readonly string[] = [
  '/api/v1/auth/login',
  '/api/v1/auth/refresh',
  '/api/v1/auth/logout',
  '/api/v1/auth/password-reset/request',
  '/api/v1/auth/password-reset/confirm',
]

function isStaffAuthExempt(path: string): boolean {
  const pathname = path.split('?')[0] ?? path
  return STAFF_AUTH_EXEMPT_PATHS.includes(pathname)
}

// Mirror server _SAFE_METHODS = {GET, HEAD, OPTIONS, TRACE}.
function isMutating(method: string): boolean {
  return method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS' && method !== 'TRACE'
}

/**
 * Read the staff-scoped CSRF cookie (clubcore_csrf).
 * This is the ONLY cookie JS is allowed to read for auth purposes (T-100-06).
 */
export function readStaffCsrfCookie(): string | undefined {
  const prefix = `${STAFF_CSRF_COOKIE}=`
  const cookies = document.cookie.split(';')
  for (const raw of cookies) {
    const c = raw.trim()
    if (c.startsWith(prefix)) return c.slice(prefix.length)
  }
  return undefined
}

// Module-scoped single-flight promise for the staff session refresh (T-100-04).
// Concurrent awaiters share the same promise; slot cleared on next microtask after settle.
let inFlightStaffRefresh: Promise<Response> | null = null

/**
 * Single-flight refresh to /api/v1/auth/refresh (T-100-04).
 * Never calls /api/v1/client/session/refresh — prevents cross-principal cookie rotation.
 */
export function staffRefreshOnce(): Promise<Response> {
  if (inFlightStaffRefresh) return inFlightStaffRefresh
  inFlightStaffRefresh = fetch('/api/v1/auth/refresh', {
    method: 'POST',
    credentials: 'include',
  }).finally(() => {
    queueMicrotask(() => {
      inFlightStaffRefresh = null
    })
  })
  return inFlightStaffRefresh
}

export async function parseErrorBody(
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

export interface StaffRequestInit extends Omit<RequestInit, 'method' | 'body'> {
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

export function appendQuery(url: string, query?: Record<string, string | number | boolean>): string {
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
 * Staff-scoped typed transport (FND-02).
 *
 * Mirrors clientRequest() from client-pwa but uses:
 *  - clubcore_csrf CSRF cookie (not clubcore_client_csrf)
 *  - /api/v1/auth/refresh for token rotation (not /api/v1/client/session/refresh)
 *  - STAFF_AUTH_EXEMPT_PATHS for refresh bypass
 *
 * URL paths are used as-is (same-origin Vite proxy handles /api/* in dev).
 * Do NOT prefix VITE_API_BASE_URL here.
 */
export async function staffRequest<
  P extends keyof paths,
  M extends keyof paths[P] & string,
>(method: M, path: P, init?: StaffRequestInit): Promise<unknown> {
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

  // T-100-03: CSRF double-submit on every mutating request.
  if (isMutating(upper)) {
    const csrf = readStaffCsrfCookie()
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
    credentials: 'include', // T-100-06: send cc_access/cc_refresh httpOnly cookies
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

  if (res.status !== 401 || isStaffAuthExempt(url)) {
    return finishResponse(res)
  }

  // T-100-04: single-flight refresh for non-exempt 401s (T-100-05: session_expired on failure)
  let refreshRes: Response
  try {
    refreshRes = await staffRefreshOnce()
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

  // Retry the original request once with freshly-read CSRF cookie (rotation may have changed value)
  const retryHeaders = new Headers(headers)
  if (isMutating(upper)) {
    const csrf = readStaffCsrfCookie()
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

/**
 * Helper for the mock swap-seam layer: simulates an async response.
 * PRESERVED: all non-auth feature api.ts files import this and continue
 * to resolve mock data until their domain is wired to the real backend.
 */
export function mockResponse<T>(value: T, delay = 0): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), delay))
}
