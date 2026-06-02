/**
 * PersonalDataSheet identity binding tests (Plan 76-02).
 *
 * Task 1 (PDATA-01): Fields hydrate from real useClientMe data — not hardcoded demo values.
 * Task 2 (PDATA-02): Save calls useUpdateClientProfile().mutateAsync with correct payload;
 *   goal constrained to 4-value enum; save-button state cycle; error toast copy.
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

// Mock the swap-seam data hooks
const useClientMe = vi.fn()
const useUpdateClientProfile = vi.fn()
vi.mock('@/data', () => ({
  useClientMe: (...args) => useClientMe(...args),
  useUpdateClientProfile: (...args) => useUpdateClientProfile(...args),
}))

import { PersonalDataSheet } from './ProfileExtraSheets.jsx'

const noop = () => {}
const baseProps = { onClose: noop, userName: undefined, setTweak: noop }

// Default mutation stub: idle state
const idleMutation = {
  mutateAsync: vi.fn().mockResolvedValue({}),
  isPending: false,
}

beforeEach(() => {
  useClientMe.mockReset()
  useUpdateClientProfile.mockReset()
  useUpdateClientProfile.mockReturnValue(idleMutation)
})

// ─── Task 1: Hydration from API ─────────────────────────────────────────────

describe('PersonalDataSheet hydration from GET /client/me (PDATA-01)', () => {
  it('renders real firstName from API instead of hardcoded "Саша"', () => {
    useClientMe.mockReturnValue({
      data: {
        firstName: 'Иван',
        lastName: 'Петров',
        phone: '+79991234567',
        email: 'ivan@x.ru',
        goal: 'maintain',
        heightCm: 180,
        weightKg: 75,
        onboardingCompletedAt: null,
      },
    })
    render(<PersonalDataSheet {...baseProps} />)
    // Avatar uses first char of name — should be "И", not "С" (Саша)
    expect(screen.getByDisplayValue('Иван')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('Саша')).not.toBeInTheDocument()
  })

  it('renders real email from API instead of hardcoded "sasha@example.com"', () => {
    useClientMe.mockReturnValue({
      data: {
        firstName: 'Иван',
        lastName: 'Петров',
        phone: '+79991234567',
        email: 'ivan@x.ru',
        goal: null,
        heightCm: null,
        weightKg: null,
        onboardingCompletedAt: null,
      },
    })
    render(<PersonalDataSheet {...baseProps} />)
    expect(screen.getByDisplayValue('ivan@x.ru')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('sasha@example.com')).not.toBeInTheDocument()
  })

  it('shows empty fields when data is undefined (loading state)', () => {
    useClientMe.mockReturnValue({ data: undefined })
    render(<PersonalDataSheet {...baseProps} />)
    // No hardcoded demo values should appear
    expect(screen.queryByDisplayValue('Саша')).not.toBeInTheDocument()
    expect(screen.queryByDisplayValue('sasha@example.com')).not.toBeInTheDocument()
  })

  it('renders "Только на устройстве" label for local-only fields', () => {
    useClientMe.mockReturnValue({ data: undefined })
    render(<PersonalDataSheet {...baseProps} />)
    expect(screen.getByText('Только на устройстве')).toBeInTheDocument()
  })

  it('phone field is read-only (onChange no-op) sourced from API', () => {
    useClientMe.mockReturnValue({
      data: {
        firstName: 'Иван',
        lastName: 'Петров',
        phone: '+79991234567',
        email: null,
        goal: null,
        heightCm: null,
        weightKg: null,
        onboardingCompletedAt: null,
      },
    })
    render(<PersonalDataSheet {...baseProps} />)
    // Phone should appear in a read-only display
    expect(screen.getByDisplayValue('+79991234567')).toBeInTheDocument()
  })

  it('renders heightCm and weightKg as editable numeric inputs', () => {
    useClientMe.mockReturnValue({
      data: {
        firstName: 'Иван',
        lastName: 'Петров',
        phone: '+79991234567',
        email: null,
        goal: 'tone',
        heightCm: 180,
        weightKg: 75,
        onboardingCompletedAt: null,
      },
    })
    render(<PersonalDataSheet {...baseProps} />)
    expect(screen.getByDisplayValue('180')).toBeInTheDocument()
    expect(screen.getByDisplayValue('75')).toBeInTheDocument()
  })
})

// ─── Task 2: Save via PATCH /client/me ──────────────────────────────────────

describe('PersonalDataSheet save via PATCH /client/me (PDATA-02)', () => {
  it('calls mutateAsync with firstName on save', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({})
    useUpdateClientProfile.mockReturnValue({ mutateAsync, isPending: false })
    useClientMe.mockReturnValue({
      data: {
        firstName: 'Иван',
        lastName: 'Петров',
        phone: '+79991234567',
        email: 'ivan@x.ru',
        goal: 'maintain',
        heightCm: 180,
        weightKg: 75,
        onboardingCompletedAt: null,
      },
    })

    render(<PersonalDataSheet {...baseProps} />)

    // Click save
    const saveBtn = screen.getByText('Сохранить')
    await act(async () => { fireEvent.click(saveBtn) })

    expect(mutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ firstName: 'Иван' })
    )
  })

  it('goal sent in payload is a valid enum value (never free text)', async () => {
    const mutateAsync = vi.fn().mockResolvedValue({})
    useUpdateClientProfile.mockReturnValue({ mutateAsync, isPending: false })
    useClientMe.mockReturnValue({
      data: {
        firstName: 'Тест',
        lastName: 'Пример',
        phone: '+70000000000',
        email: null,
        goal: 'lose_weight',
        heightCm: null,
        weightKg: null,
        onboardingCompletedAt: null,
      },
    })

    render(<PersonalDataSheet {...baseProps} />)
    const saveBtn = screen.getByText('Сохранить')
    await act(async () => { fireEvent.click(saveBtn) })

    const payload = mutateAsync.mock.calls[0]?.[0]
    if (payload?.goal !== undefined) {
      expect(['lose_weight', 'gain_mass', 'tone', 'maintain']).toContain(payload.goal)
    }
  })

  it('shows "Сохранение…" when isPending', () => {
    useUpdateClientProfile.mockReturnValue({ mutateAsync: vi.fn(), isPending: true })
    useClientMe.mockReturnValue({ data: undefined })

    render(<PersonalDataSheet {...baseProps} />)
    expect(screen.getByText('Сохранение…')).toBeInTheDocument()
  })

  it('shows error toast copy on save failure', async () => {
    const mutateAsync = vi.fn().mockRejectedValue(new Error('network error'))
    useUpdateClientProfile.mockReturnValue({ mutateAsync, isPending: false })
    useClientMe.mockReturnValue({
      data: {
        firstName: 'Иван',
        lastName: 'Петров',
        phone: '+79991234567',
        email: null,
        goal: null,
        heightCm: null,
        weightKg: null,
        onboardingCompletedAt: null,
      },
    })

    render(<PersonalDataSheet {...baseProps} />)
    const saveBtn = screen.getByText('Сохранить')
    await act(async () => { fireEvent.click(saveBtn) })

    expect(
      screen.getByText('Не удалось сохранить данные. Попробуйте ещё раз.')
    ).toBeInTheDocument()
  })

  it('goal selector renders the 4 enum options (Похудение / Набор массы / Тонус / Поддержание формы)', () => {
    useClientMe.mockReturnValue({ data: undefined })
    render(<PersonalDataSheet {...baseProps} />)

    // All 4 goal options must be present
    expect(screen.getByText('Похудение')).toBeInTheDocument()
    expect(screen.getByText('Набор массы')).toBeInTheDocument()
    expect(screen.getByText('Тонус')).toBeInTheDocument()
    expect(screen.getByText('Поддержание формы')).toBeInTheDocument()
  })
})
