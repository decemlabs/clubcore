/**
 * HomeScreen identity binding tests (Plan 71-10, Task 1).
 *
 * Asserts the wired Home screen reflects the real /client/me principal and the
 * genuine empty-membership state — not the mock 'Саша' / demo active card:
 *  (a) /client/me { firstName: 'Иван' } → header greeting shows "Иван".
 *  (b) /client/home membership=null → "Нет абонемента" empty state + "Выбрать тариф"
 *      CTA renders (toSubInfo(null) danger path), NOT a fake active card.
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock the swap-seam data hooks so the render reflects controlled API truth.
const useClientMe = vi.fn()
const useClientHome = vi.fn()
vi.mock('@/data', () => ({
  useClientMe: (...args) => useClientMe(...args),
  useClientHome: (...args) => useClientHome(...args),
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
