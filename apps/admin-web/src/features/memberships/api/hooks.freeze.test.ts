import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import type { ReactNode } from 'react'
import { useFreezeMembership, useUnfreezeMembership } from './hooks'
import { membershipsKeys } from './keys'
import { DomainError } from '@/shared/api/errors'
import type { Membership, MembershipId, MembershipPlanId } from '@/entities/membership'

vi.mock('@/shared/api/services', () => ({
  services: { memberships: { freeze: vi.fn(), unfreeze: vi.fn() } },
}))
vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }))

import { services } from '@/shared/api/services'
import { toast } from 'sonner'

function makeMembership(overrides: Partial<Membership> = {}): Membership {
  return {
    id: 'm-1' as MembershipId,
    clientId: 'c-1',
    planId: 'p-1' as MembershipPlanId,
    planNameSnapshot: 'Стандарт',
    durationDaysSnapshot: 30,
    priceKopecksSnapshot: 100000,
    startDate: '2026-01-01',
    endDate: '2026-01-30',
    status: 'active',
    paidAt: null,
    notes: null,
    cancelledAt: null,
    cancelReason: null,
    freezeDaysLimitSnapshot: 14,
    freezeDaysUsed: 0,
    freezeDaysRemaining: 14,
    currentFreezePeriod: null,
    previousMembershipId: null,
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function setupClient() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: qc }, children)
  return { qc, wrapper }
}

describe('useFreezeMembership', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('optimistically patches detail cache to frozen', async () => {
    const m = makeMembership()
    const { qc, wrapper } = setupClient()
    qc.setQueryData(membershipsKeys.detail(m.id), m)
    vi.mocked(services.memberships.freeze).mockImplementation(
      () => new Promise(() => {}), // never resolves — keeps optimistic state visible
    )
    const { result } = renderHook(() => useFreezeMembership(), { wrapper })
    act(() => {
      result.current.mutate({ membershipId: m.id, clientId: m.clientId })
    })
    await waitFor(() => {
      const cached = qc.getQueryData<Membership>(membershipsKeys.detail(m.id))
      expect(cached?.status).toBe('frozen')
    })
  })

  it('rolls back detail cache on DomainError', async () => {
    const m = makeMembership()
    const { qc, wrapper } = setupClient()
    qc.setQueryData(membershipsKeys.detail(m.id), m)
    vi.mocked(services.memberships.freeze).mockRejectedValueOnce(
      new DomainError('freeze_limit_exceeded', 'Лимит дней заморозки исчерпан.'),
    )
    const { result } = renderHook(() => useFreezeMembership(), { wrapper })
    await act(async () => {
      try {
        await result.current.mutateAsync({ membershipId: m.id, clientId: m.clientId })
      } catch {
        // expected to throw
      }
    })
    const cached = qc.getQueryData<Membership>(membershipsKeys.detail(m.id))
    expect(cached?.status).toBe('active')
    expect(toast.error).toHaveBeenCalled()
  })

  it('on settle invalidates lists + detail + byClient', async () => {
    const m = makeMembership()
    const { qc, wrapper } = setupClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    vi.mocked(services.memberships.freeze).mockResolvedValueOnce({ ...m, status: 'frozen' })
    const { result } = renderHook(() => useFreezeMembership(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ membershipId: m.id, clientId: m.clientId })
    })
    const calls = spy.mock.calls.map((c) => JSON.stringify(c[0]))
    expect(calls.some((s) => s.includes('list'))).toBe(true)
    expect(calls.some((s) => s.includes('detail'))).toBe(true)
    expect(calls.some((s) => s.includes('byClient'))).toBe(true)
  })
})

describe('useUnfreezeMembership', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('optimistically patches detail to active and clears currentFreezePeriod', async () => {
    const m = makeMembership({
      status: 'frozen',
      currentFreezePeriod: {
        id: 'p',
        startedAt: '2026-01-01T00:00:00Z',
        startedBy: 'owner',
        endedAt: null,
        endedBy: null,
      },
    })
    const { qc, wrapper } = setupClient()
    qc.setQueryData(membershipsKeys.detail(m.id), m)
    vi.mocked(services.memberships.unfreeze).mockImplementation(
      () => new Promise(() => {}),
    )
    const { result } = renderHook(() => useUnfreezeMembership(), { wrapper })
    act(() => {
      result.current.mutate({ membershipId: m.id, clientId: m.clientId })
    })
    await waitFor(() => {
      const cached = qc.getQueryData<Membership>(membershipsKeys.detail(m.id))
      expect(cached?.status).toBe('active')
      expect(cached?.currentFreezePeriod).toBeNull()
    })
  })
})
