/**
 * GymInfoSheet tests — redesigned «О зале» (quick 260606-uxo).
 *
 * Covers:
 *   (a) Loaded state renders gym name + «Часы работы» + «Что есть в зале» + amenity label
 *   (b) Loading state shows the loading copy, no error copy
 *   (c) Error state renders "Не удалось загрузить информацию о зале"
 *   (d) Open/closed copy — open branch "Сейчас открыто", closed branch "Закрыто"
 *   (e) Contacts: social handle hidden when social:[] and shown when present
 *   (f) Back button calls onClose
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

function renderSheet(ui) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

// ─── Mock @/data: useClientGymInfo (swap seam) ───────────────────────────────
const useClientGymInfo = vi.fn()
vi.mock('@/data', async () => {
  const actual = await vi.importActual('@/data')
  return { ...actual, useClientGymInfo: (...args) => useClientGymInfo(...args) }
})

// ─── Stub sub-components not under test ──────────────────────────────────────
vi.mock('@/components/Icon.jsx', () => ({
  Icon: ({ name }) => <span data-testid={`icon-${name}`} />,
}))
vi.mock('@/components/StatusBar.jsx', () => ({ StatusBar: () => null }))
vi.mock('@/components/PullToRefresh.jsx', () => ({
  PullToRefresh: ({ children }) => <div>{children}</div>,
}))

import { GymInfoSheet } from './GymInfoSheet.jsx'

function makeQuery(overrides = {}) {
  return { data: undefined, isLoading: false, isError: false, refetch: vi.fn().mockResolvedValue(undefined), ...overrides }
}

const GYM_DATA = {
  name: 'Тестовый зал',
  tagline: 'Лучший зал города',
  address: 'Тверская, 18, 3 этаж',
  city: 'Москва',
  metro: '5 мин от м. Пушкинская',
  phone: '+7 495 123-45-67',
  email: 'test@gym.ru',
  hours: [
    { d: 'Пн', open: '07:00', close: '23:00' },
    { d: 'Вт', open: '07:00', close: '23:00' },
    { d: 'Ср', open: '07:00', close: '23:00' },
    { d: 'Чт', open: '07:00', close: '23:00' },
    { d: 'Пт', open: '07:00', close: '22:00' },
    { d: 'Сб', open: '09:00', close: '22:00' },
    { d: 'Вс', open: '09:00', close: '21:00' },
  ],
  amenities: [
    { icon: 'parking', label: 'Парковка' },
    { icon: 'wifi', label: 'Wi-Fi' },
  ],
  rules: ['Спортивная форма обязательна', 'Берите полотенце'],
  social: [{ kind: 'tg', label: 'Telegram', handle: '@mygym_test' }],
}

describe('GymInfoSheet (redesigned «О зале»)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  // (a)
  it('renders gym name, sections, and amenity label when loaded', () => {
    useClientGymInfo.mockReturnValue(makeQuery({ data: GYM_DATA }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)
    expect(screen.getByText('Тестовый зал')).toBeInTheDocument()
    expect(screen.getByText('Часы работы')).toBeInTheDocument()
    expect(screen.getByText('Что есть в зале')).toBeInTheDocument()
    expect(screen.getByText('Парковка')).toBeInTheDocument()
  })

  // (b)
  it('shows loading copy and no error copy when loading', () => {
    useClientGymInfo.mockReturnValue(makeQuery({ isLoading: true, data: undefined }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)
    expect(screen.getByText('Загрузка информации о зале…')).toBeInTheDocument()
    expect(screen.queryByText('Не удалось загрузить информацию о зале')).not.toBeInTheDocument()
  })

  // (c)
  it('renders error heading when query fails', () => {
    useClientGymInfo.mockReturnValue(makeQuery({ isError: true, data: undefined }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)
    expect(screen.getByText('Не удалось загрузить информацию о зале')).toBeInTheDocument()
    expect(screen.getByText('Потяните вниз, чтобы попробовать снова.')).toBeInTheDocument()
  })

  // (d) open branch — Mon 10:00 MSK (07:00 UTC), inside 07:00–23:00
  it('shows "Сейчас открыто" when current Moscow time is within open hours', () => {
    const FIXED = new Date('2026-06-01T07:00:00Z')
    const OrigDate = globalThis.Date
    vi.spyOn(globalThis, 'Date').mockImplementation((...args) => (args.length === 0 ? FIXED : new OrigDate(...args)))
    useClientGymInfo.mockReturnValue(makeQuery({ data: GYM_DATA }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)
    expect(screen.getByText(/Сейчас открыто/)).toBeInTheDocument()
    vi.restoreAllMocks()
  })

  // (d) closed branch — Mon 03:00 MSK (00:00 UTC), before 07:00 open
  it('shows "Закрыто" when current Moscow time is outside open hours', () => {
    const FIXED = new Date('2026-06-01T00:00:00Z')
    const OrigDate = globalThis.Date
    vi.spyOn(globalThis, 'Date').mockImplementation((...args) => (args.length === 0 ? FIXED : new OrigDate(...args)))
    useClientGymInfo.mockReturnValue(makeQuery({ data: GYM_DATA }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)
    expect(screen.getByText(/Закрыто/)).toBeInTheDocument()
    vi.restoreAllMocks()
  })

  // (e) social handle hidden when empty, shown when present
  it('hides the social handle when social is empty', () => {
    useClientGymInfo.mockReturnValue(makeQuery({ data: { ...GYM_DATA, social: [] } }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)
    expect(screen.queryByText('@mygym_test')).not.toBeInTheDocument()
    expect(screen.getByText('Связаться')).toBeInTheDocument() // contacts still render (phone/email)
  })

  it('renders the social handle when social data is present', () => {
    useClientGymInfo.mockReturnValue(makeQuery({ data: GYM_DATA }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)
    expect(screen.getByText('Telegram')).toBeInTheDocument()
    expect(screen.getByText('@mygym_test')).toBeInTheDocument()
  })

  // (f) back button → onClose
  it('calls onClose when the back button is pressed', () => {
    const onClose = vi.fn()
    useClientGymInfo.mockReturnValue(makeQuery({ data: GYM_DATA }))
    renderSheet(<GymInfoSheet onClose={onClose} />)
    fireEvent.click(screen.getByLabelText('Назад'))
    expect(onClose).toHaveBeenCalled()
  })
})
