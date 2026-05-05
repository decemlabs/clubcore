/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Permanent regression tests for the typed fetcher.
 *
 * Covers:
 *  - Phase 13 SC #2: typed `query` field serialization (replaces the
 *    `as never` URL-build casts in admin-web http services).
 *  - CR-01 / CR-02 (Phase 9): error envelope unwrap + D-A3 auth-exempt
 *    pass-through (no refresh attempt on 401 from /auth/* paths).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { request } from './fetcher'
import { ApiError } from './errors'

type FetchMock = ReturnType<typeof vi.fn>

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

let fetchMock: FetchMock

beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue(jsonResponse({ data: null }))
  vi.stubGlobal('fetch', fetchMock)
  // Stub document.cookie for CSRF reads (jsdom not loaded in node env).
  Object.defineProperty(globalThis, 'document', {
    value: { cookie: '' },
    configurable: true,
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('fetcher: query serialization (Phase 13 SC #2 regression)', () => {
  it('serializes query params via URLSearchParams', async () => {
    await request('get' as any, '/x' as any, {
      query: { a: 1, b: 'two', c: true },
    } as any)
    const url = fetchMock.mock.calls[0]![0] as string
    const parsed = new URL(url, 'http://localhost')
    expect(parsed.searchParams.get('a')).toBe('1')
    expect(parsed.searchParams.get('b')).toBe('two')
    expect(parsed.searchParams.get('c')).toBe('true')
  })

  it('omits query string when query is undefined', async () => {
    await request('get' as any, '/x' as any)
    expect(fetchMock.mock.calls[0]![0]).toBe('/x')
  })

  it('omits query string when query is an empty object', async () => {
    await request('get' as any, '/x' as any, { query: {} } as any)
    expect(fetchMock.mock.calls[0]![0]).toBe('/x')
  })

  it('URL-encodes values with whitespace', async () => {
    await request('get' as any, '/x' as any, {
      query: { q: 'a b' },
    } as any)
    const url = fetchMock.mock.calls[0]![0] as string
    const parsed = new URL(url, 'http://localhost')
    expect(parsed.searchParams.get('q')).toBe('a b')
  })

  it('composes path params + query', async () => {
    await request('get' as any, '/x/{id}' as any, {
      params: { id: 'abc' },
      query: { tab: 'main' },
    } as any)
    const url = fetchMock.mock.calls[0]![0] as string
    expect(url.startsWith('/x/abc')).toBe(true)
    const parsed = new URL(url, 'http://localhost')
    expect(parsed.searchParams.get('tab')).toBe('main')
  })

  it('does not forward `query` field to fetch RequestInit', async () => {
    await request('get' as any, '/x' as any, { query: { a: 1 } } as any)
    const init = fetchMock.mock.calls[0]![1] as RequestInit & { query?: unknown }
    expect((init as { query?: unknown }).query).toBeUndefined()
  })
})

describe('fetcher: error envelope (CR-01/CR-02 regression)', () => {
  it('throws ApiError with code/message from JSON body on non-2xx', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ code: 'invalid_credentials', message: 'wrong' }, 401),
    )
    await expect(
      request('post' as any, '/api/v1/auth/login' as any, {
        body: { email: 'a', password: 'b' },
      } as any),
    ).rejects.toMatchObject({
      code: 'invalid_credentials',
      message: 'wrong',
    })
  })

  it('does NOT attempt refresh on 401 from /api/v1/auth/* paths (D-A3)', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ code: 'invalid_credentials', message: '' }, 401),
    )
    await expect(
      request('post' as any, '/api/v1/auth/login' as any, {
        body: {},
      } as any),
    ).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).toHaveBeenCalledTimes(1) // no refresh call
  })
})
