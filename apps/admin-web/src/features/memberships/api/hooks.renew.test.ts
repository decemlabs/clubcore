import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import type { ReactNode } from 'react'
import { useRenewMembership } from './hooks'
import { DomainError } from '@/shared/api/errors'
import type { Membership, MembershipId, MembershipPlanId } from '@/entities/membership'

const navigateMock = vi.fn()

vi.mock('@/shared/api/services', () => ({
  services: { memberships: { renew: vi.fn() } },
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock('@tanstack/react-router', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-router')>('@tanstack/react-router')
  return { ...actual, useNavigate: () => navigateMock }
})

import { services } from '@/shared/api/services'
import { toast } from 'sonner'

function makeMembership(overrides: Partial<Membership> = {}): Membership {
  return {
    id: 'm-source' as MembershipId,
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

describe('useRenewMembership', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    navigateMock.mockReset()
  })

  it('on success calls toast.success and navigates to the new membership', async () => {
    const source = makeMembership()
    const newRow = makeMembership({
      id: 'm-new' as MembershipId,
      previousMembershipId: source.id,
      startDate: '2026-01-31',
      endDate: '2026-03-01',
    })
    vi.mocked(services.memberships.renew).mockResolvedValueOnce(newRow)
    const { wrapper } = setupClient()
    const { result } = renderHook(() => useRenewMembership(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ membershipId: source.id, clientId: source.clientId })
    })
    expect(toast.success).toHaveBeenCalled()
    expect(navigateMock).toHaveBeenCalledWith({
      to: '/memberships/$membershipId',
      params: { membershipId: 'm-new' },
    })
  })

  it('on DomainError cannot_renew_cancelled calls toast.error with the mapped key', async () => {
    vi.mocked(services.memberships.renew).mockRejectedValueOnce(
      new DomainError('cannot_renew_cancelled', 'Нельзя продлить отменённый абонемент.'),
    )
    const { wrapper } = setupClient()
    const { result } = renderHook(() => useRenewMembership(), { wrapper })
    await act(async () => {
      try {
        await result.current.mutateAsync({ membershipId: 'm-1' as MembershipId, clientId: 'c-1' })
      } catch {
        // expected to throw
      }
    })
    expect(toast.error).toHaveBeenCalled()
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('on DomainError plan_archived calls toast.error', async () => {
    vi.mocked(services.memberships.renew).mockRejectedValueOnce(
      new DomainError('plan_archived', 'Тариф архивирован — продление недоступно.'),
    )
    const { wrapper } = setupClient()
    const { result } = renderHook(() => useRenewMembership(), { wrapper })
    await act(async () => {
      try {
        await result.current.mutateAsync({ membershipId: 'm-1' as MembershipId, clientId: 'c-1' })
      } catch {
        // expected to throw
      }
    })
    expect(toast.error).toHaveBeenCalled()
  })

  it('on settle invalidates lists + byClient + detail of source', async () => {
    const source = makeMembership()
    const newRow = makeMembership({ id: 'm-new' as MembershipId, previousMembershipId: source.id })
    vi.mocked(services.memberships.renew).mockResolvedValueOnce(newRow)
    const { qc, wrapper } = setupClient()
    const spy = vi.spyOn(qc, 'invalidateQueries')
    const { result } = renderHook(() => useRenewMembership(), { wrapper })
    await act(async () => {
      await result.current.mutateAsync({ membershipId: source.id, clientId: source.clientId })
    })
    const calls = spy.mock.calls.map((c) => JSON.stringify(c[0]))
    expect(calls.some((s) => s.includes('list'))).toBe(true)
    expect(calls.some((s) => s.includes('byClient'))).toBe(true)
    expect(calls.some((s) => s.includes('detail'))).toBe(true)
  })
})
