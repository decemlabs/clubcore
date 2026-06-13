/**
 * Unit tests for api/client.ts (Phase 100 FND-02).
 *
 * Covers:
 *  - CSRF injection: mutating request sets X-CSRF-Token from clubcore_csrf cookie
 *  - Safe request: GET does NOT set X-CSRF-Token
 *  - 401 → refresh → retry flow (single-flight, returns retry body)
 *  - 401 → refresh 401 → throws ApiError('session_expired')
 *  - 401 → refresh ok → retry 401 → throws ApiError('session_expired')
 *  - Exempt path: 401 on login path is NOT retried
 *  - mockResponse: resolves to the given value
 *
 * All tests mock global.fetch — no real network.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ApiError, mockResponse, staffRequest, readStaffCsrfCookie } from './client'

// ── helpers ──────────────────────────────────────────────────────────────────

function makeJsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function make204Response(): Response {
  return new Response(null, { status: 204 })
}

function make401Response(body?: unknown): Response {
  return new Response(JSON.stringify(body ?? { code: 'unauthorized', message: 'Unauthorized' }), {
    status: 401,
    headers: { 'Content-Type': 'application/json' },
  })
}

// Seed the CSRF cookie before each test; clear after.
const CSRF_TOKEN = 'tok-test-123'

function seedCsrfCookie(): void {
  document.cookie = `clubcore_csrf=${CSRF_TOKEN}; path=/`
}

function clearCsrfCookie(): void {
  document.cookie = 'clubcore_csrf=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT'
}

// ── setup ────────────────────────────────────────────────────────────────────

// We need to reset the module-scoped inFlightStaffRefresh between tests.
// Since we can't reach the module-private var, we just let concurrent tests
// not share the same fetch mock state (beforeEach restores vi.fn).
beforeEach(() => {
  vi.spyOn(globalThis, 'fetch')
  seedCsrfCookie()
})

afterEach(() => {
  vi.restoreAllMocks()
  clearCsrfCookie()
})

// ── readStaffCsrfCookie ───────────────────────────────────────────────────────

describe('readStaffCsrfCookie', () => {
  it('returns the csrf token when cookie is present', () => {
    expect(readStaffCsrfCookie()).toBe(CSRF_TOKEN)
  })

  it('returns undefined when cookie is absent', () => {
    clearCsrfCookie()
    expect(readStaffCsrfCookie()).toBeUndefined()
  })
})

// ── CSRF injection ────────────────────────────────────────────────────────────

describe('staffRequest — CSRF injection', () => {
  it('sets X-CSRF-Token header on POST (mutating)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(make204Response())

    await staffRequest('post', '/api/v1/auth/login', { body: { email: 'x@x.com', password: 'pw' } })

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    const headers = init?.headers instanceof Headers ? init.headers : new Headers(init?.headers as HeadersInit | undefined)
    expect(headers.get('X-CSRF-Token')).toBe(CSRF_TOKEN)
  })

  it('sets X-CSRF-Token on POST (second mutating verb check — matches production password-reset/confirm)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(make204Response())

    await staffRequest('post', '/api/v1/auth/password-reset/confirm', {
      body: { token: 't', newPassword: 'StrongPass123!' },
    })

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    const headers = init?.headers instanceof Headers ? init.headers : new Headers(init?.headers as HeadersInit | undefined)
    expect(headers.get('X-CSRF-Token')).toBe(CSRF_TOKEN)
  })

  it('does NOT set X-CSRF-Token on GET (safe)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeJsonResponse({ data: { id: '1' } }))

    await staffRequest('get', '/api/v1/auth/me')

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    const headers = init?.headers instanceof Headers ? init.headers : new Headers(init?.headers as HeadersInit | undefined)
    expect(headers.get('X-CSRF-Token')).toBeNull()
  })

  it('does not set X-CSRF-Token when cookie is absent', async () => {
    clearCsrfCookie()
    vi.mocked(fetch).mockResolvedValueOnce(make204Response())

    await staffRequest('post', '/api/v1/auth/login', { body: {} })

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    const headers = init?.headers instanceof Headers ? init.headers : new Headers(init?.headers as HeadersInit | undefined)
    expect(headers.get('X-CSRF-Token')).toBeNull()
  })
})

// ── credentials ──────────────────────────────────────────────────────────────

describe('staffRequest — credentials', () => {
  it('always sends credentials: include', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeJsonResponse({ data: {} }))

    await staffRequest('get', '/api/v1/auth/me')

    const [, init] = vi.mocked(fetch).mock.calls[0]!
    expect(init?.credentials).toBe('include')
  })
})

// ── 401 → refresh → retry ────────────────────────────────────────────────────

describe('staffRequest — 401 → refresh → retry', () => {
  it('refreshes on non-exempt 401 and returns retry body', async () => {
    const retryBody = { data: { id: '42' } }
    vi.mocked(fetch)
      .mockResolvedValueOnce(make401Response())                // initial 401
      .mockResolvedValueOnce(new Response(null, { status: 200 })) // refresh ok
      .mockResolvedValueOnce(makeJsonResponse(retryBody))     // retry 200

    const result = await staffRequest('get', '/api/v1/auth/me')

    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(3)
    // Second call must be the refresh endpoint
    const [refreshUrl] = vi.mocked(fetch).mock.calls[1]!
    expect(refreshUrl).toBe('/api/v1/auth/refresh')
    expect(result).toEqual(retryBody)
  })

  it('re-reads CSRF cookie on retry for mutating request', async () => {
    // Change CSRF after initial request (simulating rotation)
    const rotatedToken = 'rotated-tok-456'
    vi.mocked(fetch)
      .mockImplementationOnce(async () => {
        // After first call, rotate the cookie
        document.cookie = `clubcore_csrf=${rotatedToken}; path=/`
        return make401Response()
      })
      .mockResolvedValueOnce(new Response(null, { status: 200 })) // refresh
      .mockResolvedValueOnce(make204Response())                    // retry

    await staffRequest('post', '/api/v1/clients', { body: { name: 'test' } })

    // Third call (retry) should have the rotated token
    const [, retryInit] = vi.mocked(fetch).mock.calls[2]!
    const headers = retryInit?.headers instanceof Headers ? retryInit.headers : new Headers(retryInit?.headers as HeadersInit | undefined)
    expect(headers.get('X-CSRF-Token')).toBe(rotatedToken)
  })

  it('throws session_expired when refresh itself returns 401', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(make401Response())                // initial 401
      .mockResolvedValueOnce(make401Response())                // refresh 401

    await expect(staffRequest('get', '/api/v1/auth/me')).rejects.toMatchObject({
      code: 'session_expired',
    })
    // No third call (retry must not happen after failed refresh)
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(2)
  })

  it('throws session_expired when retry still 401s after successful refresh', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(make401Response())                      // initial 401
      .mockResolvedValueOnce(new Response(null, { status: 200 }))   // refresh ok
      .mockResolvedValueOnce(make401Response())                      // retry 401

    await expect(staffRequest('get', '/api/v1/auth/me')).rejects.toMatchObject({
      code: 'session_expired',
    })
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(3)
  })

  it('does NOT attempt refresh on exempt path (login 401)', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      make401Response({ code: 'invalid_credentials', message: 'Bad creds' }),
    )

    await expect(
      staffRequest('post', '/api/v1/auth/login', { body: { email: 'x@x.com', password: 'bad' } }),
    ).rejects.toMatchObject({ code: 'invalid_credentials' })

    // Only one fetch call — no refresh attempted
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1)
  })
})

// ── ApiError identity ────────────────────────────────────────────────────────

describe('staffRequest — ApiError', () => {
  it('throws ApiError with code field on non-2xx non-401', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      makeJsonResponse({ code: 'not_found', message: 'Not found' }, 404),
    )

    await expect(staffRequest('get', '/api/v1/auth/me')).rejects.toMatchObject({
      code: 'not_found',
    })
  })

  it('throws ApiError network_error when fetch rejects', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch'))

    await expect(staffRequest('get', '/api/v1/auth/me')).rejects.toMatchObject({
      code: 'network_error',
    })
  })

  it('exported ApiError is the same class as thrown by the transport', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      makeJsonResponse({ code: 'test_code', message: 'test' }, 400),
    )

    let caught: unknown
    try {
      await staffRequest('get', '/api/v1/auth/me')
    } catch (e) {
      caught = e
    }
    expect(caught).toBeInstanceOf(ApiError)
  })
})

// ── mockResponse ─────────────────────────────────────────────────────────────

describe('mockResponse', () => {
  it('resolves to the given value', async () => {
    const value = { id: '1', name: 'Alice' }
    expect(await mockResponse(value)).toEqual(value)
  })

  it('resolves after specified delay', async () => {
    vi.useFakeTimers()
    const p = mockResponse('hello', 100)
    vi.advanceTimersByTime(100)
    expect(await p).toBe('hello')
    vi.useRealTimers()
  })
})
