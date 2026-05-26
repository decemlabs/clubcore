import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ApiError } from '@clubcore/api-client'
import {
  redirectOnSessionExpired,
  __resetRedirectingFlagForTests,
  __getRedirectingForTests,
} from './redirect-on-session-expired'

// Use vi.hoisted so the mock factories can reference these before initialization.
const { navigateMock, clearMock } = vi.hoisted(() => {
  return {
    navigateMock: vi.fn().mockResolvedValue(undefined),
    clearMock: vi.fn(),
  }
})

// Mock the router module (lazy-imported by the helper)
vi.mock('@/app/router', () => ({
  router: {
    // WARNING #4: TanStack Router serializes; pass raw pathname + search.
    state: { location: { pathname: '/clients', search: '?q=foo' } },
    navigate: navigateMock,
  },
}))

// Mock the queryClient (referenced statically by the helper)
vi.mock('@/app/queryClient', () => ({
  queryClient: { clear: clearMock },
}))

describe('redirectOnSessionExpired', () => {
  beforeEach(() => {
    __resetRedirectingFlagForTests()
    navigateMock.mockClear()
    clearMock.mockClear()
  })

  it('navigates to /login on ApiError(session_expired)', async () => {
    redirectOnSessionExpired(new ApiError('session_expired', 'expired'))
    // Lazy import + .then chain resolves across multiple microtask ticks
    await new Promise((r) => setTimeout(r, 0))
    expect(clearMock).toHaveBeenCalledTimes(1)
    expect(navigateMock).toHaveBeenCalledTimes(1)
    const call = navigateMock.mock.calls[0]![0]
    expect(call.to).toBe('/login')
    expect(call.replace).toBe(true)
    // WARNING #4: raw -- TanStack handles encoding/decoding on serialize.
    expect(call.search.next).toBe('/clients?q=foo')
  })

  it('suppresses concurrent session_expired calls (single-flight)', async () => {
    redirectOnSessionExpired(new ApiError('session_expired', 'a'))
    redirectOnSessionExpired(new ApiError('session_expired', 'b'))
    redirectOnSessionExpired(new ApiError('session_expired', 'c'))
    await new Promise((r) => setTimeout(r, 0))
    expect(navigateMock).toHaveBeenCalledTimes(1)
  })

  it('passes through non-session_expired ApiError codes', () => {
    redirectOnSessionExpired(new ApiError('invalid_credentials', 'bad'))
    redirectOnSessionExpired(new ApiError('forbidden', 'no'))
    redirectOnSessionExpired(new ApiError('csrf_mismatch', 'csrf'))
    expect(navigateMock).not.toHaveBeenCalled()
    expect(clearMock).not.toHaveBeenCalled()
  })

  it('passes through non-ApiError errors', () => {
    redirectOnSessionExpired(new Error('boom'))
    redirectOnSessionExpired('not an error')
    redirectOnSessionExpired(undefined)
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('resets the flag after navigation settles', async () => {
    redirectOnSessionExpired(new ApiError('session_expired', 'a'))
    // wait for the dynamic import + .then + navigate + .finally chain
    await new Promise((r) => setTimeout(r, 0))
    expect(__getRedirectingForTests()).toBe(false)
  })

  it('resets the flag and skips queryClient.clear when navigate rejects', async () => {
    navigateMock.mockRejectedValueOnce(new Error('navigate failed'))
    redirectOnSessionExpired(new ApiError('session_expired', 'a'))
    await new Promise((r) => setTimeout(r, 0))
    expect(__getRedirectingForTests()).toBe(false)
    expect(navigateMock).toHaveBeenCalledTimes(1)
    // CR-04 fix: cache is cleared only after navigate succeeds.
    expect(clearMock).not.toHaveBeenCalled()
  })
})
