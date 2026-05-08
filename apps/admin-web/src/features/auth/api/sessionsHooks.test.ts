import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement, type ReactNode } from 'react'
import { authKeys } from './keys'
import { useActiveSessions, useLogoutAll, useRevokeSession } from './sessionsHooks'
import type { SessionFamily } from '@/shared/api/contracts/auth'

vi.mock('@/shared/api/services', () => ({
  services: {
    auth: {
      sessions: vi.fn(),
      revokeSession: vi.fn(),
      logoutAll: vi.fn(),
    },
  },
}))

import { services } from '@/shared/api/services'

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

function wrapper(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: qc }, children)
  }
}

const mockSession: SessionFamily = {
  familyId: '00000000-0000-4000-8000-000000000001',
  createdAt: '2026-05-01T12:00:00Z',
  lastUsedAt: '2026-05-08T09:00:00Z',
  userAgent: 'Mozilla/5.0',
  channel: 'email',
  isCurrent: true,
}

describe('features/auth/api/sessionsHooks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('useActiveSessions calls services.auth.sessions and uses authKeys.sessions', async () => {
    vi.mocked(services.auth.sessions).mockResolvedValue([mockSession])
    const qc = makeQueryClient()
    const { result } = renderHook(() => useActiveSessions(), { wrapper: wrapper(qc) })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(services.auth.sessions).toHaveBeenCalledTimes(1)
    expect(result.current.data).toEqual([mockSession])
    // queryKey wired to authKeys.sessions
    expect(qc.getQueryData(authKeys.sessions)).toEqual([mockSession])
  })

  it('useRevokeSession calls services.auth.revokeSession(familyId) and invalidates sessions key', async () => {
    vi.mocked(services.auth.revokeSession).mockResolvedValue(undefined)
    const qc = makeQueryClient()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    const { result } = renderHook(() => useRevokeSession(), { wrapper: wrapper(qc) })
    result.current.mutate('family-xyz')
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(services.auth.revokeSession).toHaveBeenCalledWith('family-xyz')
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: authKeys.sessions })
  })

  it('useLogoutAll calls services.auth.logoutAll and clears the QueryClient cache on success', async () => {
    vi.mocked(services.auth.logoutAll).mockResolvedValue(undefined)
    const qc = makeQueryClient()
    qc.setQueryData(['sentinel'], 'still here')
    const clearSpy = vi.spyOn(qc, 'clear')
    const { result } = renderHook(() => useLogoutAll(), { wrapper: wrapper(qc) })
    result.current.mutate()
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(services.auth.logoutAll).toHaveBeenCalledTimes(1)
    expect(clearSpy).toHaveBeenCalledTimes(1)
  })
})
