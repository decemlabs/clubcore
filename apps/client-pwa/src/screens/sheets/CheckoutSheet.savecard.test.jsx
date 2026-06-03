/**
 * CheckoutSheet save-card opt-in tests (Phase 81.1-01 / PAYM-01).
 *
 * Covers:
 *   1. Off-case (default): membership mutateAsync arg has no truthy savePaymentMethod key
 *   2. On-case: after toggling the opt-in, mutateAsync is called with savePaymentMethod:true
 *   3. PT on-case: same as (2) but for the PT-package path
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

// ─── Mock @/data hooks ────────────────────────────────────────────────────────
const useClientCheckoutMembership = vi.fn()
const useClientCheckoutPtPackage = vi.fn()
const usePromoValidate = vi.fn()
const useClientMe = vi.fn()

vi.mock('@/data', async () => {
  const actual = await vi.importActual('@/data')
  return {
    ...actual,
    useClientCheckoutMembership: (...args) => useClientCheckoutMembership(...args),
    useClientCheckoutPtPackage: (...args) => useClientCheckoutPtPackage(...args),
    usePromoValidate: (...args) => usePromoValidate(...args),
    useClientMe: (...args) => useClientMe(...args),
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
  amount: 350000,
}

// PT ctx
const PT_CTX = {
  kind: 'pt',
  planId: '22222222-2222-2222-2222-222222222222',
  title: '10 тренировок',
  subtitle: null,
  amount: 1200000,
}

beforeEach(() => {
  useClientMe.mockReturnValue({ data: CLIENT_WITH_EMAIL })
  useClientCheckoutMembership.mockReturnValue(makeMutation())
  useClientCheckoutPtPackage.mockReturnValue(makeMutation())
  usePromoValidate.mockReturnValue(makeMutation({ mutateAsync: vi.fn().mockResolvedValue({}) }))
})

// ---------------------------------------------------------------------------
// Membership (sub) path — opt-in OFF (default)
// ---------------------------------------------------------------------------
describe('CheckoutSheet save-card opt-in — membership (sub) OFF (default)', () => {
  it('membership mutateAsync arg has no truthy savePaymentMethod when opt-in is OFF', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ confirmationUrl: 'https://pay.example.com' })
    useClientCheckoutMembership.mockReturnValue({ mutateAsync, isPending: false })

    // Stub window.location.href assignment (jsdom does not follow redirects)
    const hrefDescriptor = Object.getOwnPropertyDescriptor(window, 'location')
    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
      configurable: true,
    })

    render(
      <CheckoutSheet ctx={SUB_CTX} onClose={noop} onDone={noop} />,
    )

    // Click pay — email present, so goes straight to launchCheckout
    const payBtn = screen.getByText(/Оплатить/)
    await act(async () => {
      fireEvent.click(payBtn)
    })

    expect(mutateAsync).toHaveBeenCalledOnce()
    const arg = mutateAsync.mock.calls[0][0]
    // Default OFF: savePaymentMethod must NOT be truthy (key absent or false)
    expect(arg).not.toHaveProperty('savePaymentMethod', true)

    // Restore
    if (hrefDescriptor) Object.defineProperty(window, 'location', hrefDescriptor)
  })
})

// ---------------------------------------------------------------------------
// Membership (sub) path — opt-in ON
// ---------------------------------------------------------------------------
describe('CheckoutSheet save-card opt-in — membership (sub) ON', () => {
  it('membership mutateAsync arg includes savePaymentMethod:true after toggle', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ confirmationUrl: 'https://pay.example.com' })
    useClientCheckoutMembership.mockReturnValue({ mutateAsync, isPending: false })

    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
      configurable: true,
    })

    render(
      <CheckoutSheet ctx={SUB_CTX} onClose={noop} onDone={noop} />,
    )

    // Toggle the save-card switch ON
    const saveSwitch = screen.getByRole('switch', { name: 'Сохранить карту для будущих оплат' })
    await act(async () => {
      fireEvent.click(saveSwitch)
    })

    // Now click pay
    const payBtn = screen.getByText(/Оплатить/)
    await act(async () => {
      fireEvent.click(payBtn)
    })

    expect(mutateAsync).toHaveBeenCalledOnce()
    const arg = mutateAsync.mock.calls[0][0]
    expect(arg).toHaveProperty('savePaymentMethod', true)
  })
})

// ---------------------------------------------------------------------------
// PT path — opt-in ON
// ---------------------------------------------------------------------------
describe('CheckoutSheet save-card opt-in — PT package ON', () => {
  it('PT mutateAsync arg includes savePaymentMethod:true after toggle', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ confirmationUrl: 'https://pay.example.com' })
    useClientCheckoutPtPackage.mockReturnValue({ mutateAsync, isPending: false })

    Object.defineProperty(window, 'location', {
      value: { href: '' },
      writable: true,
      configurable: true,
    })

    render(
      <CheckoutSheet ctx={PT_CTX} onClose={noop} onDone={noop} />,
    )

    // Toggle the save-card switch ON
    const saveSwitch = screen.getByRole('switch', { name: 'Сохранить карту для будущих оплат' })
    await act(async () => {
      fireEvent.click(saveSwitch)
    })

    // Now click pay
    const payBtn = screen.getByText(/Оплатить/)
    await act(async () => {
      fireEvent.click(payBtn)
    })

    expect(mutateAsync).toHaveBeenCalledOnce()
    const arg = mutateAsync.mock.calls[0][0]
    expect(arg).toHaveProperty('savePaymentMethod', true)
  })
})
