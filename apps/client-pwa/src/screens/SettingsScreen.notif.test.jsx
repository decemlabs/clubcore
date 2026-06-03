/**
 * SettingsScreen notification toggle tests (Plan 78-02 / NOTIF-01).
 *
 * Covers:
 *  - Hydration: toggles reflect useClientMe().notifPrefs (not localStorage / NOTIF_DEFAULTS)
 *  - Full-replace save: tap fires mutateAsync with all 4 notifPrefs keys
 *  - Optimistic flip: switch reflects new value immediately (before promise resolves)
 *  - Revert on error: failed mutateAsync reverts the flip + shows error toast
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

// ─── Mock swap-seam data hooks ───────────────────────────────────────────────
const useClientMe = vi.fn()
const useUpdateClientProfile = vi.fn()
vi.mock('@/data', () => ({
  useClientMe: (...args) => useClientMe(...args),
  useUpdateClientProfile: (...args) => useUpdateClientProfile(...args),
  useClientPaymentMethod: () => ({ data: null }),
}))

// ─── Mock AuthContext ────────────────────────────────────────────────────────
vi.mock('@/context/AuthContext.jsx', () => ({
  useAuth: () => ({ logout: () => {} }),
}))

// ─── Mock react-router-dom (useNavigate) ────────────────────────────────────
vi.mock('react-router-dom', () => ({
  useNavigate: () => () => {},
}))

// ─── Mock local components that have no testing value here ──────────────────
vi.mock('@/components/Avatar.jsx', () => ({
  Avatar: ({ initials }) => <span data-testid="avatar">{initials}</span>,
}))
vi.mock('@/components/Icon.jsx', () => ({
  Icon: () => null,
}))
vi.mock('@/components/StatusBar.jsx', () => ({
  StatusBar: () => null,
}))

import { SettingsScreen } from './SettingsScreen.jsx'

// ─── Shared test helpers ─────────────────────────────────────────────────────
const noop = () => {}
const baseProps = {
  tweaks: {},
  setTweak: noop,
  onOpenPlans: noop,
  onOpenPersonalData: noop,
  onOpenCard: noop,
  onOpenFAQ: noop,
}

// Default idle mutation stub
const idleMutateAsync = vi.fn().mockResolvedValue({})
const idleMutation = { mutateAsync: idleMutateAsync, isPending: false }

const meWithNotifPrefs = (notifPrefs) => ({
  data: {
    id: 'client-1',
    firstName: 'Иван',
    lastName: 'Петров',
    phone: '+79991234567',
    email: null,
    goal: null,
    heightCm: null,
    weightKg: null,
    onboardingCompletedAt: null,
    notifPrefs,
  },
})

beforeEach(() => {
  useClientMe.mockReset()
  useUpdateClientProfile.mockReset()
  idleMutateAsync.mockReset()
  idleMutateAsync.mockResolvedValue({})
  useUpdateClientProfile.mockReturnValue(idleMutation)
})

// ─── Hydration from useClientMe().notifPrefs ────────────────────────────────

describe('SettingsScreen notif hydration from GET /client/me (NOTIF-01 D-78-04)', () => {
  it('four switches reflect notifPrefs from server', async () => {
    useClientMe.mockReturnValue(meWithNotifPrefs({
      promo: true,
      schedule: false,
      trainer: true,
      sound: false,
    }))

    await act(async () => { render(<SettingsScreen {...baseProps} />) })

    expect(screen.getByRole('switch', { name: 'Акции и скидки' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('switch', { name: 'Изменения расписания' })).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByRole('switch', { name: 'Сообщения от тренера' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('switch', { name: 'Звук уведомлений' })).toHaveAttribute('aria-checked', 'false')
  })

  it('uses NOTIF_DEFAULTS when notifPrefs is null (loading state)', async () => {
    // notifPrefs null → server hasn't returned yet; defaults applied
    useClientMe.mockReturnValue(meWithNotifPrefs(null))

    await act(async () => { render(<SettingsScreen {...baseProps} />) })

    // NOTIF_DEFAULTS: promo=true, schedule=true, trainer=true, sound=false
    expect(screen.getByRole('switch', { name: 'Акции и скидки' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('switch', { name: 'Звук уведомлений' })).toHaveAttribute('aria-checked', 'false')
  })
})

// ─── Optimistic flip (before promise resolves) ──────────────────────────────

describe('SettingsScreen notif optimistic flip (D-78-06)', () => {
  it('switch reflects new value immediately after tap (before mutateAsync resolves)', async () => {
    // Hang the promise so we can inspect intermediate state
    let resolvePromise
    const hangingMutate = vi.fn().mockReturnValue(new Promise((res) => { resolvePromise = res }))
    useUpdateClientProfile.mockReturnValue({ mutateAsync: hangingMutate, isPending: false })
    useClientMe.mockReturnValue(meWithNotifPrefs({
      promo: true,
      schedule: false,
      trainer: true,
      sound: false,
    }))

    await act(async () => { render(<SettingsScreen {...baseProps} />) })

    const scheduleSwitch = screen.getByRole('switch', { name: 'Изменения расписания' })
    expect(scheduleSwitch).toHaveAttribute('aria-checked', 'false')

    // Tap — optimistic flip should be immediate
    fireEvent.click(scheduleSwitch)

    // Immediately after click, before promise resolves
    expect(scheduleSwitch).toHaveAttribute('aria-checked', 'true')

    // Resolve the pending mutation cleanly
    await act(async () => { resolvePromise({}) })
  })
})

// ─── Full 4-key replace save ─────────────────────────────────────────────────

describe('SettingsScreen notif full-replace PATCH (NOTIF-01 D-78-06)', () => {
  it('mutateAsync called with all 4 notifPrefs keys when toggling schedule', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({})
    useUpdateClientProfile.mockReturnValue({ mutateAsync, isPending: false })
    useClientMe.mockReturnValue(meWithNotifPrefs({
      promo: true,
      schedule: false,
      trainer: true,
      sound: false,
    }))

    await act(async () => { render(<SettingsScreen {...baseProps} />) })

    const scheduleSwitch = screen.getByRole('switch', { name: 'Изменения расписания' })
    await act(async () => { fireEvent.click(scheduleSwitch) })

    expect(mutateAsync).toHaveBeenCalledTimes(1)
    expect(mutateAsync).toHaveBeenCalledWith({
      notifPrefs: { promo: true, schedule: true, trainer: true, sound: false },
    })
  })

  it('mutateAsync payload contains all 4 keys when toggling promo', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({})
    useUpdateClientProfile.mockReturnValue({ mutateAsync, isPending: false })
    useClientMe.mockReturnValue(meWithNotifPrefs({
      promo: false,
      schedule: true,
      trainer: false,
      sound: true,
    }))

    await act(async () => { render(<SettingsScreen {...baseProps} />) })

    const promoSwitch = screen.getByRole('switch', { name: 'Акции и скидки' })
    await act(async () => { fireEvent.click(promoSwitch) })

    const call = mutateAsync.mock.calls[0]?.[0]
    expect(call).toMatchObject({
      notifPrefs: { promo: true, schedule: true, trainer: false, sound: true },
    })
    // Assert all 4 keys present
    const keys = Object.keys(call.notifPrefs)
    expect(keys).toContain('promo')
    expect(keys).toContain('schedule')
    expect(keys).toContain('trainer')
    expect(keys).toContain('sound')
  })
})

// ─── Revert on error + error toast ───────────────────────────────────────────

describe('SettingsScreen notif revert on mutation failure (D-78-06)', () => {
  it('reverts optimistic flip and shows error toast when mutateAsync rejects', async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error('network error'))
    useUpdateClientProfile.mockReturnValue({ mutateAsync, isPending: false })
    useClientMe.mockReturnValue(meWithNotifPrefs({
      promo: true,
      schedule: false,
      trainer: true,
      sound: false,
    }))

    await act(async () => { render(<SettingsScreen {...baseProps} />) })

    const scheduleSwitch = screen.getByRole('switch', { name: 'Изменения расписания' })
    expect(scheduleSwitch).toHaveAttribute('aria-checked', 'false')

    // Tap and wait for rejection to settle
    await act(async () => { fireEvent.click(scheduleSwitch) })

    // Switch reverted to prior value
    expect(scheduleSwitch).toHaveAttribute('aria-checked', 'false')

    // Error toast visible
    expect(screen.getByText('Не удалось сохранить настройки. Попробуйте ещё раз.')).toBeInTheDocument()
  })
})
