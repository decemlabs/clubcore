import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { membershipsKeys } from './keys'
import {
  useMembershipsByClient,
  useMembershipPlans,
  useCreateMembership,
  useCancelMembership,
} from './hooks'
import type { Membership, MembershipId, MembershipPlan, Pagination } from '@/entities/membership'

// Mock the services module
vi.mock('@/shared/api/services', () => ({
  services: {
    memberships: {
      byClient: vi.fn(),
      listPlans: vi.fn(),
      create: vi.fn(),
      cancel: vi.fn(),
      list: vi.fn(),
      get: vi.fn(),
      getPlan: vi.fn(),
      createPlan: vi.fn(),
      updatePlan: vi.fn(),
      deletePlan: vi.fn(),
    },
  },
}))

import { services } from '@/shared/api/services'

function wrapper(qc: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return createElement(QueryClientProvider, { client: qc }, children)
  }
}

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

const mockMembership: Membership = {
  id: 'mem-1' as MembershipId,
  clientId: 'client-1',
  planId: 'plan-1' as import('@/entities/membership').MembershipPlanId,
  planNameSnapshot: 'Test Plan',
  durationDaysSnapshot: 30,
  priceKopecksSnapshot: 100000,
  startDate: '2026-01-01',
  endDate: '2026-01-30',
  status: 'active',
  paidAt: null,
  notes: null,
  cancelledAt: null,
  cancelReason: null,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
}

const mockPlan: MembershipPlan = {
  id: 'plan-1' as import('@/entities/membership').MembershipPlanId,
  name: 'Test Plan',
  durationDays: 30,
  priceKopecks: 100000,
  active: true,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
}

describe('features/memberships/api/hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // Test 1: useMembershipsByClient calls services.memberships.byClient
  it('useMembershipsByClient calls services.memberships.byClient(clientId)', async () => {
    const qc = makeQueryClient()
    const mockResult: Pagination<Membership> = {
      items: [mockMembership],
      total: 1,
      page: 1,
      pageSize: 1,
    }
    vi.mocked(services.memberships.byClient).mockResolvedValue(mockResult)

    const { result } = renderHook(() => useMembershipsByClient('client-1'), {
      wrapper: wrapper(qc),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(services.memberships.byClient).toHaveBeenCalledWith('client-1')
    expect(result.current.data).toEqual(mockResult)
  })

  // Test 2: useMembershipPlans calls listPlans with active:true by default
  it('useMembershipPlans calls services.memberships.listPlans({active:true}) by default', async () => {
    const qc = makeQueryClient()
    const mockResult: Pagination<MembershipPlan> = {
      items: [mockPlan],
      total: 1,
      page: 1,
      pageSize: 20,
    }
    vi.mocked(services.memberships.listPlans).mockResolvedValue(mockResult)

    const { result } = renderHook(() => useMembershipPlans(), { wrapper: wrapper(qc) })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(services.memberships.listPlans).toHaveBeenCalledWith({ active: true })
    expect(result.current.data?.items).toHaveLength(1)
  })

  // Test 3: useCreateMembership mutation invalidates on settle
  it('useCreateMembership invalidates membershipsKeys.lists() and byClient on settle', async () => {
    const qc = makeQueryClient()
    vi.mocked(services.memberships.create).mockResolvedValue(mockMembership)
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const { result } = renderHook(() => useCreateMembership(), { wrapper: wrapper(qc) })

    result.current.mutate({ clientId: 'client-1', planId: 'plan-1' as import('@/entities/membership').MembershipPlanId })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: membershipsKeys.lists() }),
    )
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: membershipsKeys.byClient('client-1') }),
    )
  })

  // Test 4: useCancelMembership does optimistic update and rollback on error
  it('useCancelMembership optimistically flips status to cancelled', async () => {
    const qc = makeQueryClient()
    const listKey = membershipsKeys.list({ page: 1, pageSize: 20 })

    // Pre-populate the cache
    qc.setQueryData(listKey, {
      items: [mockMembership],
      total: 1,
      page: 1,
      pageSize: 20,
    } as Pagination<Membership>)

    vi.mocked(services.memberships.cancel).mockRejectedValue(new Error('Server error'))

    const { result } = renderHook(() => useCancelMembership(), { wrapper: wrapper(qc) })

    result.current.mutate({ membershipId: 'mem-1' as MembershipId })

    // Optimistic update should flip status
    await waitFor(() => {
      const cached = qc.getQueryData<Pagination<Membership>>(listKey)
      return cached?.items[0]?.status === 'cancelled' || result.current.isError
    })

    // On error, should rollback
    await waitFor(() => expect(result.current.isError).toBe(true))
    const rolled = qc.getQueryData<Pagination<Membership>>(listKey)
    expect(rolled?.items[0]?.status).toBe('active')
  })
})
