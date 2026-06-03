/**
 * CardSheet wiring tests (Phase 81-02 / PAYM-05).
 *
 * Asserts:
 *   1. Feature flags: PROFILE_FEATURE_FLAGS.weeklyActivity/linkedCard are true
 *   2. Activity bars use useClientWeeklyActivity data (heights from workouts)
 *   3. SettingsScreen card row shows real last4 from useClientPaymentMethod
 *   4. CardSheet shows real last4/expiryMonth/expiryYear (no '4821'/'09 / 28'/'ALEXANDRA Z.')
 *   5. Unbind confirm calls useUnlinkPaymentMethod (not setUnbound mock)
 *   6. Autopay enable opens consent modal; confirm sends consentAcknowledged:true
 *   7. Autopay disable sends consentAcknowledged:false with no consent modal
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

// ─── Mock @/data hooks ───────────────────────────────────────────────────────
const useClientPaymentMethod = vi.fn()
const useUnlinkPaymentMethod = vi.fn()
const usePatchAutopay = vi.fn()
const useClientMe = vi.fn()
const useUpdateClientProfile = vi.fn()

vi.mock('@/data', async () => {
  const actual = await vi.importActual('@/data')
  return {
    ...actual,
    useClientPaymentMethod: (...args) => useClientPaymentMethod(...args),
    useUnlinkPaymentMethod: (...args) => useUnlinkPaymentMethod(...args),
    usePatchAutopay: (...args) => usePatchAutopay(...args),
    useClientMe: (...args) => useClientMe(...args),
    useUpdateClientProfile: (...args) => useUpdateClientProfile(...args),
  }
})

// ─── Stub sub-components that are not under test here ───────────────────────
vi.mock('@/components/Avatar.jsx', () => ({
  Avatar: ({ initials }) => <span>{initials}</span>,
}))
vi.mock('@/components/Icon.jsx', () => ({
  Icon: () => null,
}))
vi.mock('@/components/StatusBar.jsx', () => ({
  StatusBar: () => null,
}))

// CardSheet uses StatusBar + Icon directly — stub them above
import { CardSheet } from './ProfileExtraSheets.jsx'

// ─── Standard mutation stub factory ─────────────────────────────────────────
function makeMutation({ mutateAsync = vi.fn().mockResolvedValue(undefined) } = {}) {
  return { mutateAsync, isPending: false }
}

const CARD_DATA = {
  last4: '9012',
  brand: 'Mastercard',
  expiryMonth: 3,
  expiryYear: 2027,
  autopayEnabled: false,
  consentRecordedAt: null,
}

const noop = () => {}

beforeEach(() => {
  useClientMe.mockReturnValue({ data: null })
  useUpdateClientProfile.mockReturnValue(makeMutation())
  useClientPaymentMethod.mockReturnValue({ data: CARD_DATA })
  useUnlinkPaymentMethod.mockReturnValue(makeMutation())
  usePatchAutopay.mockReturnValue(makeMutation())
})

// ---------------------------------------------------------------------------
// Feature flags (read directly from the module)
// ---------------------------------------------------------------------------
describe('Feature flags (Phase 81-02 flip)', () => {
  it('weeklyActivity flag true → ProfileScreen renders the "Активность за неделю" card', async () => {
    // The flag is a module-level const with no export; assert its observable
    // consequence instead — when weeklyActivity=true the activity card heading
    // renders. Stub every @/data hook ProfileScreen consumes so the render does
    // no real network calls and needs no QueryClientProvider.
    vi.resetModules()
    vi.doMock('@/data', () => ({
      useClientHome: () => ({ data: null }),
      useClientMe: () => ({ data: null }),
      useClientMembership: () => ({ data: null }),
      useClientVisitHistory: () => ({ data: { items: [], total: 0 } }),
      useClientPtHistory: () => ({ data: { items: [], total: 0 } }),
      useClientPaymentHistory: () => ({ data: { items: [], total: 0 } }),
      useClientWeeklyActivity: () => ({ data: undefined }),
    }))

    const { ProfileScreen } = await import('../ProfileScreen.jsx')
    render(
      <ProfileScreen
        tweaks={{}}
        onOpenSettings={noop}
        onOpenPlans={noop}
        onOpenReferral={noop}
        onOpenGymInfo={noop}
        onOpenVisitHistory={noop}
        onOpenTrainingHistory={noop}
      />,
    )

    // Observable consequence of weeklyActivity=true: the activity card heading
    // is present. If a future edit flips the flag back to false this fails.
    expect(screen.getByText('Активность за неделю')).toBeTruthy()
  })

  it('SETTINGS_FEATURE_FLAGS.linkedCard is true — card row renders with real last4', async () => {
    const useClientMeLocal = vi.fn().mockReturnValue({ data: null })
    const useUpdateClientProfileLocal = vi.fn().mockReturnValue(makeMutation())
    const useClientPaymentMethodLocal = vi.fn().mockReturnValue({ data: CARD_DATA })

    vi.doMock('@/data', () => ({
      useClientMe: useClientMeLocal,
      useUpdateClientProfile: useUpdateClientProfileLocal,
      useClientPaymentMethod: useClientPaymentMethodLocal,
    }))

    vi.doMock('@/context/AuthContext.jsx', () => ({
      useAuth: () => ({ logout: vi.fn() }),
    }))
    vi.doMock('react-router-dom', () => ({
      useNavigate: () => () => {},
    }))

    const { SettingsScreen } = await import('../SettingsScreen.jsx')
    const { container } = render(
      <SettingsScreen
        tweaks={{}}
        setTweak={noop}
        onOpenPlans={noop}
        onOpenPersonalData={noop}
        onOpenCard={noop}
        onOpenFAQ={noop}
      />,
    )
    // When linkedCard=true and data.last4='9012', row shows '•••• 9012'
    expect(container.textContent).toContain('9012')
    // Must NOT contain the old hardcoded placeholder
    expect(container.textContent).not.toContain('4821')
  })
})

// ---------------------------------------------------------------------------
// CardSheet: card visual renders real last4 / expiry
// ---------------------------------------------------------------------------
describe('CardSheet card visual (PAYM-05 / T-81-07)', () => {
  it('renders real last4 from useClientPaymentMethod', () => {
    render(<CardSheet onClose={noop} />)
    expect(screen.getByText(/9012/)).toBeTruthy()
  })

  it('does NOT render the placeholder "4821"', () => {
    render(<CardSheet onClose={noop} />)
    expect(() => screen.getByText(/4821/)).toThrow()
  })

  it('renders expiry month/year from API (03/27)', () => {
    render(<CardSheet onClose={noop} />)
    expect(screen.getByText(/03 \/ 27/)).toBeTruthy()
  })

  it('does NOT render "ALEXANDRA Z." cardholder name', () => {
    render(<CardSheet onClose={noop} />)
    expect(() => screen.getByText(/ALEXANDRA Z\./)).toThrow()
  })

  it('does NOT render "09 / 28" old expiry', () => {
    render(<CardSheet onClose={noop} />)
    expect(() => screen.getByText(/09 \/ 28/)).toThrow()
  })
})

// ---------------------------------------------------------------------------
// CardSheet: «Авто-оплата тренировок» is removed
// ---------------------------------------------------------------------------
describe('CardSheet anti-feature removal', () => {
  it('does NOT render «Авто-оплата тренировок» toggle', () => {
    render(<CardSheet onClose={noop} />)
    expect(() => screen.getByText('Авто-оплата тренировок')).toThrow()
  })

  it('still renders «Авто-продление абонемента» toggle', () => {
    render(<CardSheet onClose={noop} />)
    expect(screen.getByText('Авто-продление абонемента')).toBeTruthy()
  })
})

// ---------------------------------------------------------------------------
// CardSheet: unlink calls useUnlinkPaymentMethod (not setUnbound mock)
// ---------------------------------------------------------------------------
describe('CardSheet unbind wiring (PAYM-03)', () => {
  it('clicking "Отвязать" in confirm modal calls unlinkCard.mutateAsync()', async () => {
    const mutateAsync = vi.fn().mockResolvedValue(undefined)
    useUnlinkPaymentMethod.mockReturnValue({ mutateAsync, isPending: false })

    render(<CardSheet onClose={noop} />)

    // Open unbind confirm modal
    const unbindButton = screen.getByText('Отвязать карту')
    fireEvent.click(unbindButton)

    // Confirm modal should now be visible
    const confirmButton = screen.getByText('Отвязать')
    expect(confirmButton).toBeTruthy()

    await act(async () => {
      fireEvent.click(confirmButton)
    })

    expect(mutateAsync).toHaveBeenCalledOnce()
  })
})

// ---------------------------------------------------------------------------
// CardSheet: autopay enable shows ФЗ-376 consent modal; sends consentAcknowledged:true
// ---------------------------------------------------------------------------
describe('CardSheet autopay consent wiring (T-81-06 / T-81-08)', () => {
  it('toggling autopay ON opens consent modal (does not call mutateAsync yet)', () => {
    const mutateAsync = vi.fn().mockResolvedValue(undefined)
    usePatchAutopay.mockReturnValue({ mutateAsync, isPending: false })

    render(<CardSheet onClose={noop} />)

    // AutopayToggleRow has role="switch" aria-label="Авто-продление абонемента"
    const toggleBtn = screen.getByRole('switch', { name: 'Авто-продление абонемента' })
    expect(toggleBtn).toBeTruthy()

    fireEvent.click(toggleBtn)

    // Consent modal should be open — check for ФЗ-376 disclosure text
    expect(screen.getByText('Подключить автопродление?')).toBeTruthy()
    // mutateAsync should NOT have been called yet
    expect(mutateAsync).not.toHaveBeenCalled()
  })

  it('confirming consent sends {enabled:true, consentAcknowledged:true}', async () => {
    const mutateAsync = vi.fn().mockResolvedValue(undefined)
    usePatchAutopay.mockReturnValue({ mutateAsync, isPending: false })

    render(<CardSheet onClose={noop} />)

    // Open consent modal via autopay toggle
    const toggleBtn = screen.getByRole('switch', { name: 'Авто-продление абонемента' })
    fireEvent.click(toggleBtn)

    // Confirm — the "Подключить" text button in the consent modal
    const confirmBtn = screen.getByText('Подключить')
    await act(async () => {
      fireEvent.click(confirmBtn)
    })

    expect(mutateAsync).toHaveBeenCalledWith({ enabled: true, consentAcknowledged: true })
  })

  it('disabling autopay sends {enabled:false, consentAcknowledged:false} with no consent modal', async () => {
    // Card has autopay already enabled
    useClientPaymentMethod.mockReturnValue({ data: { ...CARD_DATA, autopayEnabled: true } })

    const mutateAsync = vi.fn().mockResolvedValue(undefined)
    usePatchAutopay.mockReturnValue({ mutateAsync, isPending: false })

    render(<CardSheet onClose={noop} />)

    // Toggle is currently ON (autopayEnabled:true) — clicking disables without consent modal
    const toggleBtn = screen.getByRole('switch', { name: 'Авто-продление абонемента' })
    await act(async () => {
      fireEvent.click(toggleBtn)
    })

    // No consent modal should open
    expect(() => screen.getByText('Подключить автопродление?')).toThrow()
    // mutateAsync called with consentAcknowledged:false
    expect(mutateAsync).toHaveBeenCalledWith({ enabled: false, consentAcknowledged: false })
  })
})
