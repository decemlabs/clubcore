/**
 * HomeScreen identity binding tests (Plan 71-10, Task 1).
 * Extended in Plan 999.3-02 Task 3: shared mock + 3 render-gate tests.
 *
 * Asserts the wired Home screen reflects the real /client/me principal and the
 * genuine empty-membership state — not the mock 'Саша' / demo active card:
 *  (a) /client/me { firstName: 'Иван' } → header avatar initial shows "И"
 *      (Phase 73: classic HomeHeroCard is a gym card, not a greeting line).
 *  (b) /client/home membership=null → "Нет абонемента" empty state + "Выбрать тариф"
 *      CTA renders (toSubInfo(null) danger path), NOT a fake active card.
 *  (c) membershipState==='newbie' → newbie onboarding renders (D-01/D-02).
 *  (d) membershipState==='lapsed' → existing flow, no newbie copy.
 *  (e) membershipState==='active' → existing flow, no newbie CTA.
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// Mock the swap-seam data hooks so the render reflects controlled API truth.
const useClientMe = vi.fn()
const useClientHome = vi.fn()
const useClientBookings = vi.fn()
vi.mock('@/data', () => ({
  useClientMe: (...args) => useClientMe(...args),
  useClientHome: (...args) => useClientHome(...args),
  useClientBookings: (...args) => useClientBookings(...args),
  // Newbie trainers tile reads TRAINERS (mock catalog) for the avatar stack.
  TRAINERS: [
    { id: 't1', name: 'Аня Соколова' },
    { id: 't2', name: 'Марк Левин' },
    { id: 't3', name: 'Лиза Орлова' },
    { id: 't4', name: 'Денис Кравцов' },
  ],
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

// HomeScreen calls useNavigate() (the newbie → /onboarding redirect, Phase 999.5),
// so it must render inside a Router.
const renderHome = () => render(
  <MemoryRouter>
    <HomeScreen {...baseProps} />
  </MemoryRouter>,
)

beforeEach(() => {
  useClientMe.mockReset()
  useClientHome.mockReset()
  useClientBookings.mockReset()
  // Safe default so pre-existing tests (which never set bookings) keep passing
  useClientBookings.mockReturnValue({ data: { items: [], total: 0 } })
})

describe('HomeScreen identity + empty-membership (real /client/me)', () => {
  it('reflects the real /client/me principal in the header avatar initial', () => {
    // Phase 73 restyle: the classic HomeHeroCard header is a gym card (title +
    // status + occupancy), not a greeting line — the real principal now surfaces
    // via the avatar initial derived from me.firstName, not full-name text.
    // The mock 'Саша' (initial 'С') still fails this, guarding the same regression.
    useClientMe.mockReturnValue({ data: { firstName: 'Иван', lastName: 'Петров' } })
    useClientHome.mockReturnValue({
      data: { membership: null, nextBooking: null },
      isLoading: false,
      isError: false,
      refetch: noop,
    })

    renderHome()
    expect(screen.getByText('И')).toBeInTheDocument()
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

    renderHome()
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

    renderHome()

    // Newbie copy must be present (v2 plan-card title + CTA)
    expect(screen.getByText('Выбери свой абонемент')).toBeInTheDocument()
    expect(screen.getByText('Оформить абонемент')).toBeInTheDocument()
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

    renderHome()

    // Newbie onboarding hero must NOT appear for lapsed members
    expect(screen.queryByText('Выбери свой абонемент')).not.toBeInTheDocument()
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

    renderHome()

    // Newbie CTA must NOT appear for active members
    expect(screen.queryByText('Оформить абонемент')).not.toBeInTheDocument()
  })
})
