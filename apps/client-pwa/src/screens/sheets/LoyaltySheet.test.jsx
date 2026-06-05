/**
 * LoyaltySheet tests (Phase 82 LOYL-01 / LOYL-02).
 *
 * Covers:
 *   1. LoyaltyBalanceCard renders formatted balance + eyebrow copy
 *   2. LoyaltyBalanceCard in loading state shows skeleton, no amount
 *   3. LoyaltyBalanceCard in error state renders nothing
 *   4. BonusHistorySheet welcome item: label "Приветственный бонус" + '+' prefix + date
 *   5. BonusHistorySheet redemption item: U+2212 minus prefix + danger styling marker
 *   6. Empty history renders "Бонусов пока нет"
 *   7. Load-more button present when items.length < total; click advances page
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

// ─── Mock @/data hooks ────────────────────────────────────────────────────────
const useClientLoyaltyBalance = vi.fn()
const useClientLoyaltyHistory = vi.fn()

vi.mock('@/data', async () => {
  const actual = await vi.importActual('@/data')
  return {
    ...actual,
    useClientLoyaltyBalance: (...args) => useClientLoyaltyBalance(...args),
    useClientLoyaltyHistory: (...args) => useClientLoyaltyHistory(...args),
  }
})

// ─── Stub sub-components not under test ──────────────────────────────────────
vi.mock('@/components/Icon.jsx', () => ({
  Icon: ({ name }) => <span data-testid={`icon-${name}`} />,
}))
vi.mock('@/components/StatusBar.jsx', () => ({
  StatusBar: () => null,
}))
vi.mock('@/components/PullToRefresh.jsx', () => ({
  PullToRefresh: ({ children }) => <div>{children}</div>,
}))
vi.mock('@/screens/sheets/ProfileExtraSheets.jsx', async () => {
  const actual = await vi.importActual('@/screens/sheets/ProfileExtraSheets.jsx')
  return {
    ...actual,
    SubSheetHeader: ({ title, onClose }) => (
      <div>
        <span>{title}</span>
        <button onClick={onClose}>Закрыть</button>
      </div>
    ),
  }
})

import { LoyaltyBalanceCard, BonusHistorySheet } from './LoyaltySheet.jsx'

// ─── Helpers ─────────────────────────────────────────────────────────────────
function makeQuery(overrides = {}) {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

const WELCOME_ITEM = {
  id: 'item-1',
  type: 'welcome',
  amountKopecks: 50000,
  createdAt: '2026-06-01T10:00:00Z',
}

const REDEMPTION_ITEM = {
  id: 'item-2',
  type: 'redemption',
  amountKopecks: -20000,
  createdAt: '2026-06-02T10:00:00Z',
}

const BALANCE_DATA = { balanceKopecks: 50000 }

const PAGE_ONE = { items: [WELCOME_ITEM], total: 1, page: 1, pageSize: 10 }

// ─── LoyaltyBalanceCard ───────────────────────────────────────────────────────
describe('LoyaltyBalanceCard', () => {
  beforeEach(() => {
    useClientLoyaltyHistory.mockReturnValue(makeQuery())
  })

  it('renders formatted balance amount and eyebrow copy', () => {
    useClientLoyaltyBalance.mockReturnValue(
      makeQuery({ data: BALANCE_DATA })
    )
    render(<LoyaltyBalanceCard onOpen={vi.fn()} />)

    // Eyebrow text (uppercase in DOM)
    expect(screen.getByText(/доступно бонусов/i)).toBeInTheDocument()
    // formatMoney(50000) = "500 ₽" (Intl may use NBSP — test for substring)
    const balanceEl = screen.getByText(/500/)
    expect(balanceEl).toBeInTheDocument()
  })

  it('shows a skeleton and no amount when loading', () => {
    useClientLoyaltyBalance.mockReturnValue(
      makeQuery({ isLoading: true, data: undefined })
    )
    render(<LoyaltyBalanceCard onOpen={vi.fn()} />)

    // Skeleton aria-label present
    expect(screen.getByLabelText('Загрузка бонусов…')).toBeInTheDocument()
    // No numeric amount rendered
    expect(screen.queryByText(/₽/)).not.toBeInTheDocument()
  })

  it('renders nothing when in error state', () => {
    useClientLoyaltyBalance.mockReturnValue(
      makeQuery({ isError: true, data: undefined })
    )
    const { container } = render(<LoyaltyBalanceCard onOpen={vi.fn()} />)
    expect(container.firstChild).toBeNull()
  })

  it('calls onOpen when the card is tapped', () => {
    const onOpen = vi.fn()
    useClientLoyaltyBalance.mockReturnValue(
      makeQuery({ data: BALANCE_DATA })
    )
    render(<LoyaltyBalanceCard onOpen={onOpen} />)
    fireEvent.click(screen.getByRole('generic', { hidden: true, name: /бонусный счёт/i }))
    // The card div is the click target
    const card = screen.getByLabelText('Бонусный счёт')
    fireEvent.click(card)
    expect(onOpen).toHaveBeenCalled()
  })
})

// ─── BonusHistorySheet ────────────────────────────────────────────────────────
describe('BonusHistorySheet', () => {
  beforeEach(() => {
    useClientLoyaltyBalance.mockReturnValue(
      makeQuery({ data: BALANCE_DATA })
    )
  })

  it('renders welcome item with label, + prefix, and formatted date', () => {
    useClientLoyaltyHistory.mockReturnValue(
      makeQuery({ data: PAGE_ONE })
    )
    render(<BonusHistorySheet onClose={vi.fn()} />)

    expect(screen.getByText('Приветственный бонус')).toBeInTheDocument()
    // Amount: '+' prefix followed by formatted money substring
    const amountEl = screen.getByText(content => content.startsWith('+') && content.includes('500'))
    expect(amountEl).toBeInTheDocument()
    // Date: some form of "1 июн" / "1 июня" — Intl formatting is locale-dependent
    // We assert that a date string containing "2026" appears for the item
    expect(screen.getByText(content => content.includes('2026') && content.includes('1'))).toBeInTheDocument()
  })

  it('renders redemption item with U+2212 minus prefix', () => {
    useClientLoyaltyHistory.mockReturnValue(
      makeQuery({ data: { items: [REDEMPTION_ITEM], total: 1, page: 1, pageSize: 10 } })
    )
    render(<BonusHistorySheet onClose={vi.fn()} />)

    expect(screen.getByText('Списание за оплату')).toBeInTheDocument()
    // Amount should start with U+2212 (−) not hyphen (-)
    const amountEl = screen.getByText(content => content.startsWith('−') && content.includes('200'))
    expect(amountEl).toBeInTheDocument()
  })

  it('shows "Бонусов пока нет" empty state when no items', () => {
    useClientLoyaltyHistory.mockReturnValue(
      makeQuery({ data: { items: [], total: 0, page: 1, pageSize: 10 } })
    )
    render(<BonusHistorySheet onClose={vi.fn()} />)
    expect(screen.getByText('Бонусов пока нет')).toBeInTheDocument()
    expect(screen.getByText(/После первой активности/)).toBeInTheDocument()
  })

  it('shows "Загрузить ещё" button when items.length < total', () => {
    const twoItemPage = {
      items: [WELCOME_ITEM],
      total: 5, // more than 1 item in list
      page: 1,
      pageSize: 10,
    }
    useClientLoyaltyHistory.mockReturnValue(
      makeQuery({ data: twoItemPage })
    )
    render(<BonusHistorySheet onClose={vi.fn()} />)
    expect(screen.getByText('Загрузить ещё')).toBeInTheDocument()
  })

  it('advances the page when "Загрузить ещё" is clicked', () => {
    // First page: 1 item out of 3 total
    const firstPage = { items: [WELCOME_ITEM], total: 3, page: 1, pageSize: 10 }
    // Capture calls to useClientLoyaltyHistory to verify page advance
    const calls = []
    useClientLoyaltyHistory.mockImplementation((page) => {
      calls.push(page)
      return makeQuery({ data: firstPage })
    })

    render(<BonusHistorySheet onClose={vi.fn()} />)
    const loadMoreBtn = screen.getByText('Загрузить ещё')
    fireEvent.click(loadMoreBtn)

    // After click, the hook should have been called with page > 1
    expect(calls.some(p => p > 1)).toBe(true)
  })

  it('shows error message when history fetch fails', () => {
    useClientLoyaltyHistory.mockReturnValue(
      makeQuery({ isError: true, data: undefined })
    )
    render(<BonusHistorySheet onClose={vi.fn()} />)
    expect(screen.getByText(/Не удалось загрузить историю/)).toBeInTheDocument()
  })
})
