/**
 * Typed transport for the Sportzal backend (Phase 9 — API-06).
 *
 * Public surface: only `request<P, M>(method, path, init?)`.
 *
 * Contracts (do NOT change without updating the corresponding decision):
 *  - D-A1 / D-A4: single-flight `/api/v1/auth/refresh` on 401, max 1 refresh
 *    per failed call. Refresh failure → throw ApiError('session_expired').
 *  - D-A2: framework-agnostic. NO router/window/redirect logic here.
 *  - D-A3: 401 from /auth/* paths is pass-through (no refresh attempt).
 *  - D-11: X-CSRF-Token only on mutating methods; cookie name `sportzal_csrf`
 *    matches server constant in app/core/dependencies.py.
 *  - D-12: ApiError shape mirrors backend AppError JSON envelope.
 */
import { ApiError } from './errors'
import type { paths } from './schema'

// D-A3: server-side CSRF/refresh exempt paths under /api/v1 prefix.
// Exact list verified against apps/backend/app/modules/auth/router.py.
const AUTH_EXEMPT_PATHS: readonly string[] = [
  '/api/v1/auth/login',
  '/api/v1/auth/refresh',
  '/api/v1/auth/me',
  '/api/v1/auth/logout',
  '/api/v1/auth/logout-all',
  '/api/v1/auth/telegram/start',
  '/api/v1/auth/telegram/status',
  '/api/v1/auth/telegram/verify',
]

function isAuthExempt(path: string): boolean {
  const pathname = path.split('?')[0] ?? path
  return AUTH_EXEMPT_PATHS.includes(pathname)
}

// D-11: mirror server _SAFE_METHODS = {GET, HEAD, OPTIONS, TRACE}.
// TRACE is dropped — browsers do not issue it.
function isMutating(method: string): boolean {
  return method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS'
}

// D-11: cookie name `sportzal_csrf` MUST be byte-equal to server constant
// in apps/backend/app/core/dependencies.py:194.
function readCsrfCookie(): string | undefined {
  const prefix = 'sportzal_csrf='
  const cookies = document.cookie.split(';')
  for (const raw of cookies) {
    const c = raw.trim()
    if (c.startsWith(prefix)) return c.slice(prefix.length)
  }
  return undefined
}

// D-A4: module-scoped single-flight promise. Concurrent awaiters share the
// same promise. The slot is cleared on the *next microtask* after settle so
// that a 401 storm arriving in the same tick latches onto the in-flight
// promise instead of triggering a second refresh (CR-02).
// No Subject / EventEmitter — plain shared promise, as decided.
let inFlightRefresh: Promise<Response> | null = null

function refreshOnce(): Promise<Response> {
  if (inFlightRefresh) return inFlightRefresh
  inFlightRefresh = fetch('/api/v1/auth/refresh', {
    method: 'POST',
    credentials: 'include',
  }).finally(() => {
    // Defer slot reset so concurrent awaiters in the same microtask
    // observe the in-flight promise rather than starting a fresh refresh.
    queueMicrotask(() => {
      inFlightRefresh = null
    })
  })
  return inFlightRefresh
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

export interface RequestInitWithBody extends Omit<RequestInit, 'method' | 'body'> {
  body?: unknown
  /**
   * Path-parameter values for templated `paths` keys (e.g. `{client_id}`).
   * Each value is `encodeURIComponent`-escaped before being substituted into
   * the URL. A missing key throws `ApiError('client_error', ...)` so the
   * failure is loud, not silent.
   */
  params?: Record<string, string | number>
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

export async function request<
  P extends keyof paths,
  M extends keyof paths[P] & string,
>(method: M, path: P, init?: RequestInitWithBody): Promise<unknown> {
  const url = interpolatePath(path as unknown as string, init?.params)
  const upper = (method as string).toUpperCase()
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...((init?.headers as Record<string, string> | undefined) ?? {}),
  }
  let bodyPayload: BodyInit | undefined
  if (init?.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    bodyPayload = JSON.stringify(init.body)
  }
  if (isMutating(upper)) {
    const csrf = readCsrfCookie()
    if (csrf) headers['X-CSRF-Token'] = csrf
    // D-11: missing-cookie → still send; server returns 403 csrf_mismatch via standard error path.
  }
  // Strip `params` (and the existing `body` rebind) from the RequestInit spread —
  // they are not recognized by fetch().
  const { params: _params, body: _body, headers: _headers, ...restInit } = init ?? {}
  void _params
  void _body
  void _headers
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

  if (res.status !== 401 || isAuthExempt(url)) {
    return finishResponse(res)
  }

  // D-A4: single-flight refresh attempt for non-/auth/* 401s.
  let refreshRes: Response
  try {
    refreshRes = await refreshOnce()
  } catch (err) {
    // WR-01: preserve the original network error as `cause` so consumers
    // can distinguish offline / DNS failures from a genuine token-expired
    // refresh response.
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

  // D-A4: retry original ONCE. Refresh-cookies just rotated; rebuild CSRF
  // header from the freshly-set cookie.
  const retryHeaders: Record<string, string> = { ...headers }
  if (isMutating(upper)) {
    const csrf = readCsrfCookie()
    if (csrf) retryHeaders['X-CSRF-Token'] = csrf
    else delete retryHeaders['X-CSRF-Token']
  }
  let retryRes: Response
  try {
    retryRes = await fetch(url, { ...baseInit, headers: retryHeaders })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    throw new ApiError('network_error', message)
  }
  if (retryRes.status === 401) {
    // D-A4: max 1 refresh per failed call — no second cycle.
    throw new ApiError('session_expired', 'Session expired, please log in again.')
  }
  return finishResponse(retryRes)
}

async function finishResponse(res: Response): Promise<unknown> {
  if (res.ok) {
    if (res.status === 204) return undefined
    const ct = res.headers.get('content-type') ?? ''
    if (ct.includes('application/json')) {
      return (await res.json()) as unknown
    }
    return undefined
  }
  const body = await parseErrorBody(res)
  throw new ApiError(body.code, body.message, body.fields)
}
