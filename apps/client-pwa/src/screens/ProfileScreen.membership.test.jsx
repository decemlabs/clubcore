/**
 * ProfileScreen membership render tests (Plan 78-01, Task 2).
 *
 * Asserts the PMEM-01 price/auto-renew rows in the .membership-hero card:
 *  (a) priceKopecks → formatted ₽ row renders; autoRenew null → no indicator.
 *  (b) membership null → no price row and no auto-renew indicator.
 *  (c) autoRenew true → both price and indicator render.
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// ─── Swap-seam mocks ──────────────────────────────────────────────────────────
const useClientMembership = vi.fn()
const useClientMe = vi.fn()
const useClientHome = vi.fn()
const emptyList = { data: { items: [], total: 0 }, isLoading: false, isError: false, refetch: () => {} }
vi.mock('@/data', () => ({
  useClientMe: (...args) => useClientMe(...args),
  useClientHome: (...args) => useClientHome(...args),
  useClientMembership: (...args) => useClientMembership(...args),
  useClientVisitHistory: () => emptyList,
  useClientPtHistory: () => emptyList,
  useClientPaymentHistory: () => emptyList,
  useClientWeeklyActivity: () => ({ data: undefined }),
}))
vi.mock('@/context/AuthContext.jsx', () => ({
  useAuth: () => ({ logout: () => {} }),
}))

import { ProfileScreen } from './ProfileScreen.jsx'

const noop = () => {}
const baseProps = {
  tweaks: {},
  setTweak: noop,
  onOpenSettings: noop,
  onOpenPlans: noop,
  onOpenReferral: noop,
  onOpenGymInfo: noop,
  onOpenPersonalData: noop,
  onOpenCard: noop,
  onOpenFAQ: noop,
  onOpenVisitHistory: noop,
  onOpenTrainingHistory: noop,
}

/** Membership fixture with a real priceKopecks. */
const MEMBERSHIP_WITH_PRICE = {
  id: 'mem-1',
  planNameSnapshot: 'Стандарт',
  startDate: '2026-05-01',
  endDate: '2026-06-01',
  status: 'active',
  daysUntilEnd: 14,
  expiringSoon: false,
  priceKopecks: 490000,
  autoRenew: null,
}

beforeEach(() => {
  useClientMe.mockReset()
  useClientHome.mockReset()
  useClientMembership.mockReset()

  // Default identity setup common to all membership tests
  useClientMe.mockReturnValue({
    data: { firstName: 'Тест', lastName: 'Пользователь', phone: '+70000000000', email: null },
  })
  useClientHome.mockReturnValue({
    data: {
      membership: {
        status: 'active',
        planNameSnapshot: 'Стандарт',
        daysUntilExpiry: 14,
        startDate: '2026-05-01',
        endDate: '2026-06-01',
      },
    },
  })
})

describe('ProfileScreen membership price row (PMEM-01)', () => {
  it('renders formatted price when priceKopecks is present and autoRenew is null', () => {
    useClientMembership.mockReturnValue({ data: MEMBERSHIP_WITH_PRICE })

    render(<ProfileScreen {...baseProps} />)

    // formatMoney(490000) → "4 900 ₽" (ru-RU uses NBSP between digits and before ₽)
    // Match with regex to tolerate NBSP vs regular space differences
    expect(screen.getByText(/4[\s ]900[\s ]₽/)).toBeInTheDocument()

    // Auto-renew row must NOT appear when autoRenew is null
    expect(screen.queryByLabelText('auto-renew-indicator')).not.toBeInTheDocument()
    expect(screen.queryByText('Автопродление')).not.toBeInTheDocument()
  })

  it('renders no price row and no auto-renew indicator when membership is null', () => {
    useClientMembership.mockReturnValue({ data: null })

    render(<ProfileScreen {...baseProps} />)

    expect(screen.queryByText('Стоимость')).not.toBeInTheDocument()
    expect(screen.queryByText(/4[\s ]900[\s ]₽/)).not.toBeInTheDocument()
    expect(screen.queryByText('Автопродление')).not.toBeInTheDocument()
  })

  it('renders both price and auto-renew indicator when autoRenew is a real boolean (forward-compat)', () => {
    useClientMembership.mockReturnValue({
      data: { ...MEMBERSHIP_WITH_PRICE, autoRenew: true },
    })

    render(<ProfileScreen {...baseProps} />)

    // Price row renders
    expect(screen.getByText(/4[\s ]900[\s ]₽/)).toBeInTheDocument()

    // Auto-renew indicator renders (autoRenew is not null)
    expect(screen.getByLabelText('auto-renew-indicator')).toBeInTheDocument()
    expect(screen.getByText('Включено')).toBeInTheDocument()
  })

  it('renders no price row when membership data is undefined (loading state)', () => {
    useClientMembership.mockReturnValue({ data: undefined })

    render(<ProfileScreen {...baseProps} />)

    expect(screen.queryByText('Стоимость')).not.toBeInTheDocument()
    expect(screen.queryByText('Автопродление')).not.toBeInTheDocument()
  })
})
