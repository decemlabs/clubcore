/**
 * HomeScreen identity binding tests (Plan 71-10, Task 1).
 * Extended in Plan 999.3-02 Task 3: shared mock + 3 render-gate tests.
 *
 * Asserts the wired Home screen reflects the real /client/me principal and the
 * genuine empty-membership state — not the mock 'Саша' / demo active card:
 *  (a) /client/me { firstName: 'Иван' } → header greeting shows "Иван".
 *  (b) /client/home membership=null → "Нет абонемента" empty state + "Выбрать тариф"
 *      CTA renders (toSubInfo(null) danger path), NOT a fake active card.
 *  (c) membershipState==='newbie' → newbie onboarding renders (D-01/D-02).
 *  (d) membershipState==='lapsed' → existing flow, no newbie copy.
 *  (e) membershipState==='active' → existing flow, no newbie CTA.
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock the swap-seam data hooks so the render reflects controlled API truth.
const useClientMe = vi.fn()
const useClientHome = vi.fn()
const useClientBookings = vi.fn()
vi.mock('@/data', () => ({
  useClientMe: (...args) => useClientMe(...args),
  useClientHome: (...args) => useClientHome(...args),
  useClientBookings: (...args) => useClientBookings(...args),
}))

import { HomeScreen } from './HomeScreen.jsx'

const noop = () => {}
const baseProps = {
  tweaks: {},
  onOpenQR: noop,
  onOpenPlans: noop,
  onOpenManage: noop,
  onOpenReferral: noop,
  onOpenGymInfo: noop,
  onOpenNotifications: noop,
  onTab: noop,
  setTweak: noop,
}

beforeEach(() => {
  useClientMe.mockReset()
  useClientHome.mockReset()
  useClientBookings.mockReset()
  // Safe default so pre-existing tests (which never set bookings) keep passing
  useClientBookings.mockReturnValue({ data: { items: [], total: 0 } })
})

describe('HomeScreen identity + empty-membership (real /client/me)', () => {
  it('shows the real first name from /client/me in the greeting', () => {
    useClientMe.mockReturnValue({ data: { firstName: 'Иван', lastName: 'Петров' } })
    useClientHome.mockReturnValue({
      data: { membership: null, nextBooking: null },
      isLoading: false,
      isError: false,
      refetch: noop,
    })

    render(<HomeScreen {...baseProps} />)
    expect(screen.getByText('Иван')).toBeInTheDocument()
    expect(screen.queryByText('Саша')).not.toBeInTheDocument()
  })

  it('renders the real "Нет абонемента" empty state when membership is null', () => {
    useClientMe.mockReturnValue({ data: { firstName: 'Иван' } })
    useClientHome.mockReturnValue({
      data: { membership: null, nextBooking: null },
      isLoading: false,
      isError: false,
      refetch: noop,
    })

    render(<HomeScreen {...baseProps} />)
    expect(screen.getByText('Нет абонемента')).toBeInTheDocument()
    expect(screen.getByText('Выбрать тариф')).toBeInTheDocument()
    expect(screen.queryByText('Годовой')).not.toBeInTheDocument()
  })
})

// ─── Render-gate tests — Plan 999.3-02 (D-01/D-02) ───────────────────────────
describe('HomeScreen render gate (membershipState newbie vs lapsed vs active)', () => {
  it('renders newbie onboarding when membershipState === "newbie"', () => {
    useClientMe.mockReturnValue({ data: { firstName: 'Иван', lastName: 'Петров' } })
    useClientHome.mockReturnValue({
      data: { membershipState: 'newbie', membership: null, nextBooking: null },
      isLoading: false,
      isError: false,
      refetch: noop,
    })
    useClientBookings.mockReturnValue({ data: { items: [], total: 0 } })

    render(<HomeScreen {...baseProps} />)

    // Newbie copy must be present
    expect(screen.getByText('Остался один шаг до зала')).toBeInTheDocument()
    expect(screen.getByText('Выбрать абонемент')).toBeInTheDocument()
    // Non-newbie copy must NOT be present
    expect(screen.queryByText('Нет абонемента')).not.toBeInTheDocument()
    expect(screen.queryByText('Годовой')).not.toBeInTheDocument()
  })

  it('does NOT render newbie copy when membershipState === "lapsed"', () => {
    useClientMe.mockReturnValue({ data: { firstName: 'Иван' } })
    useClientHome.mockReturnValue({
      data: { membershipState: 'lapsed', membership: null, nextBooking: null },
      isLoading: false,
      isError: false,
      refetch: noop,
    })
    useClientBookings.mockReturnValue({ data: { items: [], total: 0 } })

    render(<HomeScreen {...baseProps} />)

    // Newbie onboarding hero must NOT appear for lapsed members
    expect(screen.queryByText('Остался один шаг до зала')).not.toBeInTheDocument()
  })

  it('does NOT render newbie CTA when membershipState === "active"', () => {
    useClientMe.mockReturnValue({ data: { firstName: 'Иван' } })
    useClientHome.mockReturnValue({
      data: {
        membershipState: 'active',
        membership: {
          id: 'm1', planNameSnapshot: 'Годовой', daysUntilEnd: 100,
          startDate: '2026-01-01', endDate: '2026-12-31', expiringSoon: false, status: 'active',
        },
        nextBooking: null,
      },
      isLoading: false,
      isError: false,
      refetch: noop,
    })
    useClientBookings.mockReturnValue({ data: { items: [], total: 0 } })

    render(<HomeScreen {...baseProps} />)

    // Newbie CTA must NOT appear for active members
    expect(screen.queryByText('Выбрать абонемент')).not.toBeInTheDocument()
  })
})
