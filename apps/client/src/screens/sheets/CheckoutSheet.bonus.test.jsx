/**
 * CheckoutSheet bonus redemption tests (Phase 83 REDM-03).
 *
 * Covers:
 *   (a) When balanceKopecks > 0, the subtitle renders the formatted balance
 *       and BONUS_PLACEHOLDER text is absent
 *   (b) Toggling bonus ON renders the bonus discount row with ~ chip
 *   (c) Submitting checkout calls mutateAsync with loyaltyRedeemKopecks = balanceKopecks
 *   (d) When balance = 0 the bonus section does not render at all
 *   (e) With bonus OFF the request body omits loyaltyRedeemKopecks
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

// ─── Mock @/data hooks ────────────────────────────────────────────────────────
const useClientCheckoutMembership = vi.fn()
const useClientCheckoutPtPackage = vi.fn()
const usePromoValidate = vi.fn()
const useClientMe = vi.fn()
const useClientLoyaltyBalance = vi.fn()

vi.mock('@/data', async () => {
  const actual = await vi.importActual('@/data')
  return {
    ...actual,
    useClientCheckoutMembership: (...args) => useClientCheckoutMembership(...args),
    useClientCheckoutPtPackage: (...args) => useClientCheckoutPtPackage(...args),
    usePromoValidate: (...args) => usePromoValidate(...args),
    useClientMe: (...args) => useClientMe(...args),
    useClientLoyaltyBalance: (...args) => useClientLoyaltyBalance(...args),
  }
})

// ─── Stub sub-components not under test ───────────────────────────────────────
vi.mock('@/components/Icon.jsx', () => ({
  Icon: () => null,
}))
vi.mock('@/components/StatusBar.jsx', () => ({
  StatusBar: () => null,
}))
vi.mock('./ReceiptEmailGate.jsx', () => ({
  ReceiptEmailGate: () => null,
}))

import { CheckoutSheet } from './CheckoutSheet.jsx'

// ─── jsdom matchMedia stub (not implemented in jsdom) ────────────────────────
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  configurable: true,
  value: (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

// ─── Standard mutation stub factory ──────────────────────────────────────────
function makeMutation({ mutateAsync = vi.fn().mockResolvedValue({ confirmationUrl: 'https://pay.example.com' }) } = {}) {
  return { mutateAsync, isPending: false }
}

const noop = () => {}

// D-03: provide email so the email-gate is skipped in startPay
const CLIENT_WITH_EMAIL = { email: 'test@example.com' }

// Minimal sub ctx with a real planId (avoids the demo-guard early return)
const SUB_CTX = {
  kind: 'sub',
  planId: '11111111-1111-1111-1111-111111111111',
  title: 'Стандарт 1 месяц',
  subtitle: '1',
  amount: 350000, // 3 500 ₽ in kopecks
}

// PT ctx
const PT_CTX = {
  kind: 'pt',
  planId: '22222222-2222-2222-2222-222222222222',
  title: '10 тренировок',
  subtitle: null,
  amount: 1200000, // 12 000 ₽ in kopecks
}

// Balance of 1 080 ₽ = 108 000 kopecks
const BALANCE_KOPECKS = 108000

beforeEach(() => {
  useClientMe.mockReturnValue({ data: CLIENT_WITH_EMAIL })
  useClientCheckoutMembership.mockReturnValue(makeMutation())
  useClientCheckoutPtPackage.mockReturnValue(makeMutation())
  usePromoValidate.mockReturnValue(makeMutation({ mutateAsync: vi.fn().mockResolvedValue({}) }))
  // Default: positive balance, not loading
  useClientLoyaltyBalance.mockReturnValue({ data: { balanceKopecks: BALANCE_KOPECKS }, isLoading: false })
})

// ─── Stub window.location.href ────────────────────────────────────────────────
function stubLocation() {
  Object.defineProperty(window, 'location', {
    value: { href: '' },
    writable: true,
    configurable: true,
  })
}

// ---------------------------------------------------------------------------
// (a) Subtitle shows real balance; BONUS_PLACEHOLDER text is absent
// ---------------------------------------------------------------------------
describe('CheckoutSheet bonus — (a) real balance display', () => {
  it('subtitle shows formatted balanceKopecks and no "до Gold" text', () => {
    render(<CheckoutSheet ctx={SUB_CTX} onClose={noop} onDone={noop} />)

    // "На счёте" text should be visible — the bonus section renders with real data
    expect(screen.getByText(/На счёте/)).toBeTruthy()

    // "до Gold" text from old BONUS_PLACEHOLDER must be absent (deferred to TIER-01)
    expect(screen.queryByText(/до Gold/)).toBeNull()

    // The balance should be rendered as a monetary value (formatMoney output contains ₽)
    // 108000 kopecks → "1 080 ₽" — the <b> element wrapping the amount should be present
    const boldElements = document.querySelectorAll('.co-bonus-sub b')
    expect(boldElements.length).toBeGreaterThan(0)
    // The formatted amount contains the ₽ sign
    const balanceText = boldElements[0].textContent
    expect(balanceText).toMatch(/₽/)
  })
})

// ---------------------------------------------------------------------------
// (b) Toggling bonus ON renders the bonus discount row
// ---------------------------------------------------------------------------
describe('CheckoutSheet bonus — (b) discount row after toggle ON', () => {
  it('bonus discount row appears after toggling ON', async () => {
    render(<CheckoutSheet ctx={SUB_CTX} onClose={noop} onDone={noop} />)

    // Bonus section should be visible (balance > 0)
    const bonusSwitch = screen.getByRole('switch', { name: 'Списать бонусы' })
    expect(bonusSwitch).toBeTruthy()

    // Toggle ON
    await act(async () => {
      fireEvent.click(bonusSwitch)
    })

    // "Бонусы" discount row label should appear
    expect(screen.getAllByText(/Бонусы/).length).toBeGreaterThan(0)

    // The ~ chip (estimate marker) should be present
    expect(screen.getAllByText('~').length).toBeGreaterThan(0)
  })
})

// ---------------------------------------------------------------------------
// (c) Submitting checkout includes loyaltyRedeemKopecks = balanceKopecks
// ---------------------------------------------------------------------------
describe('CheckoutSheet bonus — (c) request body wiring (sub)', () => {
  it('membership mutateAsync includes loyaltyRedeemKopecks when bonus ON', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ confirmationUrl: 'https://pay.example.com' })
    useClientCheckoutMembership.mockReturnValue({ mutateAsync, isPending: false })
    stubLocation()

    render(<CheckoutSheet ctx={SUB_CTX} onClose={noop} onDone={noop} />)

    // Toggle bonus ON
    const bonusSwitch = screen.getByRole('switch', { name: 'Списать бонусы' })
    await act(async () => {
      fireEvent.click(bonusSwitch)
    })

    // Click pay
    const payBtn = screen.getByText(/Оплатить/)
    await act(async () => {
      fireEvent.click(payBtn)
    })

    expect(mutateAsync).toHaveBeenCalledOnce()
    const arg = mutateAsync.mock.calls[0][0]
    expect(arg).toHaveProperty('loyaltyRedeemKopecks', BALANCE_KOPECKS)
  })
})

describe('CheckoutSheet bonus — (c) request body wiring (PT)', () => {
  it('PT mutateAsync includes loyaltyRedeemKopecks when bonus ON', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ confirmationUrl: 'https://pay.example.com' })
    useClientCheckoutPtPackage.mockReturnValue({ mutateAsync, isPending: false })
    stubLocation()

    render(<CheckoutSheet ctx={PT_CTX} onClose={noop} onDone={noop} />)

    // Toggle bonus ON
    const bonusSwitch = screen.getByRole('switch', { name: 'Списать бонусы' })
    await act(async () => {
      fireEvent.click(bonusSwitch)
    })

    // Click pay
    const payBtn = screen.getByText(/Оплатить/)
    await act(async () => {
      fireEvent.click(payBtn)
    })

    expect(mutateAsync).toHaveBeenCalledOnce()
    const arg = mutateAsync.mock.calls[0][0]
    expect(arg).toHaveProperty('loyaltyRedeemKopecks', BALANCE_KOPECKS)
  })
})

// ---------------------------------------------------------------------------
// (d) When balance = 0 the bonus section does not render
// ---------------------------------------------------------------------------
describe('CheckoutSheet bonus — (d) hidden when balance = 0', () => {
  it('bonus section is not rendered when balanceKopecks = 0', () => {
    useClientLoyaltyBalance.mockReturnValue({ data: { balanceKopecks: 0 }, isLoading: false })

    render(<CheckoutSheet ctx={SUB_CTX} onClose={noop} onDone={noop} />)

    // The "Списать бонусы" switch must not be rendered
    expect(screen.queryByRole('switch', { name: 'Списать бонусы' })).toBeNull()

    // "Бонусы клуба" section label must not be rendered
    expect(screen.queryByText('Бонусы клуба')).toBeNull()
  })

  it('bonus section is not rendered while loading', () => {
    useClientLoyaltyBalance.mockReturnValue({ data: undefined, isLoading: true })

    render(<CheckoutSheet ctx={SUB_CTX} onClose={noop} onDone={noop} />)

    expect(screen.queryByRole('switch', { name: 'Списать бонусы' })).toBeNull()
  })

  it('bonus section is not rendered on fetch error (data undefined after load)', () => {
    useClientLoyaltyBalance.mockReturnValue({ data: undefined, isLoading: false })

    render(<CheckoutSheet ctx={SUB_CTX} onClose={noop} onDone={noop} />)

    expect(screen.queryByRole('switch', { name: 'Списать бонусы' })).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// (e) With bonus OFF the request body omits loyaltyRedeemKopecks
// ---------------------------------------------------------------------------
describe('CheckoutSheet bonus — (e) request body omits loyaltyRedeemKopecks when OFF', () => {
  it('membership mutateAsync has no loyaltyRedeemKopecks when bonus is OFF (default)', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ confirmationUrl: 'https://pay.example.com' })
    useClientCheckoutMembership.mockReturnValue({ mutateAsync, isPending: false })
    stubLocation()

    render(<CheckoutSheet ctx={SUB_CTX} onClose={noop} onDone={noop} />)

    // Do NOT toggle bonus — leave OFF
    const payBtn = screen.getByText(/Оплатить/)
    await act(async () => {
      fireEvent.click(payBtn)
    })

    expect(mutateAsync).toHaveBeenCalledOnce()
    const arg = mutateAsync.mock.calls[0][0]
    // loyaltyRedeemKopecks must be absent when bonus is OFF
    expect(arg).not.toHaveProperty('loyaltyRedeemKopecks')
  })
})
