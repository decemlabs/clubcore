import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { MembershipsBlock } from './MembershipsBlock'
import type { Membership, MembershipId, MembershipPlanId, Pagination } from '@/entities/membership'
import type { UseQueryResult } from '@tanstack/react-query'

// Mock todayMSK so D-3 badge tests are deterministic
const mockTodayMSK = vi.fn(() => '2026-05-08')
vi.mock('@/shared/i18n/date', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/i18n/date')>()
  return { ...actual, todayMSK: () => mockTodayMSK() }
})

// Mock useMembershipsByClient so we control query state
vi.mock('../api/hooks', () => ({
  useMembershipsByClient: vi.fn(),
}))

import { useMembershipsByClient } from '../api/hooks'

const TODAY = '2026-05-08'
const PAST = '2026-05-07'
const FUTURE = '2026-05-09'

function makeQuery(items: Membership[]): UseQueryResult<Pagination<Membership>> {
  return {
    data: { items, total: items.length, page: 1, pageSize: 20 },
    isError: false,
    isLoading: false,
    isPending: false,
    isSuccess: true,
    refetch: () => Promise.resolve(undefined),
  } as unknown as UseQueryResult<Pagination<Membership>>
}

function makeMembership(
  overrides: Partial<Membership> = {},
): Membership {
  return {
    id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' as MembershipId,
    clientId: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
    planId: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc' as MembershipPlanId,
    planNameSnapshot: 'Test Plan',
    durationDaysSnapshot: 30,
    priceKopecksSnapshot: 250000,
    startDate: '2026-04-08',
    endDate: TODAY,
    status: 'active',
    createdAt: '2026-04-08T00:00:00.000Z',
    updatedAt: '2026-04-08T00:00:00.000Z',
    ...overrides,
  }
}

describe('MembershipsBlock D-3 badge (истёк сегодня)', () => {
  beforeEach(() => {
    mockTodayMSK.mockReturnValue(TODAY)
  })

  it('Test 1: renders destructive badge when status=active AND endDate === todayMSK()', () => {
    const membership = makeMembership({ endDate: TODAY, status: 'active' })
    vi.mocked(useMembershipsByClient).mockReturnValue(makeQuery([membership]))

    renderWithProviders(<MembershipsBlock clientId="client-1" />, { role: 'owner' })

    expect(screen.getByText('истёк сегодня')).toBeInTheDocument()
  })

  it('Test 2: does NOT render badge when endDate < todayMSK() (past)', () => {
    const membership = makeMembership({ endDate: PAST, status: 'active' })
    vi.mocked(useMembershipsByClient).mockReturnValue(makeQuery([membership]))

    renderWithProviders(<MembershipsBlock clientId="client-1" />, { role: 'owner' })

    expect(screen.queryByText('истёк сегодня')).not.toBeInTheDocument()
  })

  it('Test 3: does NOT render badge when endDate > todayMSK() (future active)', () => {
    const membership = makeMembership({ endDate: FUTURE, status: 'active' })
    vi.mocked(useMembershipsByClient).mockReturnValue(makeQuery([membership]))

    renderWithProviders(<MembershipsBlock clientId="client-1" />, { role: 'owner' })

    expect(screen.queryByText('истёк сегодня')).not.toBeInTheDocument()
  })

  it('Test 4: does NOT render badge when status=cancelled even if endDate === today', () => {
    const membership = makeMembership({ endDate: TODAY, status: 'cancelled' })
    vi.mocked(useMembershipsByClient).mockReturnValue(makeQuery([membership]))

    renderWithProviders(<MembershipsBlock clientId="client-1" />, { role: 'owner' })

    expect(screen.queryByText('истёк сегодня')).not.toBeInTheDocument()
  })
})
