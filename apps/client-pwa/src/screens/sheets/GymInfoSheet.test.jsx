/**
 * GymInfoSheet tests (Phase 86 GYM-01).
 *
 * Covers:
 *   (a) Loaded state renders gym name + section eyebrow + amenity label
 *   (b) Loading state shows skeleton aria-label, no error copy
 *   (c) Error state renders "Не удалось загрузить информацию о зале"
 *   (d) Open/closed badge — open branch "Сейчас открыто", closed branch "Закрыто"
 *   (e) Social section hidden when social:[] and shown when present
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ─── Wrap with QueryClientProvider (required by sheet shell) ─────────────────
function renderSheet(ui) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

// ─── Mock @/lib/clientQueries: useClientGymInfo ──────────────────────────────
// The sheet imports the hook directly from @/lib/clientQueries (D-71-09 swap-seam
// boundary — net-new sheets must not import through the @/data barrel).
const useClientGymInfo = vi.fn()

vi.mock('@/lib/clientQueries', async () => {
  const actual = await vi.importActual('@/lib/clientQueries')
  return {
    ...actual,
    useClientGymInfo: (...args) => useClientGymInfo(...args),
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

import { GymInfoSheet } from './GymInfoSheet.jsx'

// ─── Helpers ──────────────────────────────────────────────────────────────────
function makeQuery(overrides = {}) {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    refetch: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

// Full sample gym data matching GymInfoData interface
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
    { icon: 'wifi',    label: 'Wi-Fi' },
  ],
  rules: [
    'Спортивная форма обязательна',
    'Берите полотенце',
  ],
  social: [
    { kind: 'tg', label: 'Telegram', handle: '@mygym_test' },
  ],
}

// ─── Tests ────────────────────────────────────────────────────────────────────
describe('GymInfoSheet', () => {

  beforeEach(() => {
    vi.clearAllMocks()
  })

  // (a) Loaded state
  it('renders gym name, hours section eyebrow, and amenity label when loaded', () => {
    useClientGymInfo.mockReturnValue(makeQuery({ data: GYM_DATA }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)

    expect(screen.getByText('Тестовый зал')).toBeInTheDocument()
    expect(screen.getByText('ЧАСЫ РАБОТЫ')).toBeInTheDocument()
    expect(screen.getByText('Парковка')).toBeInTheDocument()
  })

  // (b) Loading state
  it('shows skeleton aria-label and no error copy when loading', () => {
    useClientGymInfo.mockReturnValue(makeQuery({ isLoading: true, data: undefined }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)

    expect(screen.getByLabelText('Загрузка информации о зале…')).toBeInTheDocument()
    expect(screen.queryByText('Не удалось загрузить информацию о зале')).not.toBeInTheDocument()
  })

  // (c) Error state
  it('renders error heading when query fails', () => {
    useClientGymInfo.mockReturnValue(makeQuery({ isError: true, data: undefined }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)

    expect(screen.getByText('Не удалось загрузить информацию о зале')).toBeInTheDocument()
    expect(screen.getByText('Потяните вниз, чтобы попробовать снова.')).toBeInTheDocument()
  })

  // (d) Open/closed badge — open branch
  it('shows "Сейчас открыто" badge when current Moscow time is within open hours', () => {
    // Mock Date to be Mon 10:00 Moscow time — inside Mon 07:00–23:00
    // getMoscowNow() uses Intl.DateTimeFormat to get weekday+time in Europe/Moscow.
    // We override Date constructor to return a fixed ISO time that maps to Mon 10:00 MSK.
    // 2026-06-01 is a Monday. 07:00 UTC = 10:00 MSK.
    const FIXED_DATE = new Date('2026-06-01T07:00:00Z')
    const OrigDate = globalThis.Date
    vi.spyOn(globalThis, 'Date').mockImplementation((...args) => {
      if (args.length === 0) return FIXED_DATE
      // @ts-ignore: test helper
      return new OrigDate(...args)
    })

    useClientGymInfo.mockReturnValue(makeQuery({ data: GYM_DATA }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)

    expect(screen.getByText('Сейчас открыто')).toBeInTheDocument()

    vi.restoreAllMocks()
  })

  // (d) Open/closed badge — closed branch
  it('shows "Закрыто" badge when current Moscow time is outside open hours', () => {
    // 2026-06-01 (Monday) at 00:00 UTC = 03:00 MSK — before 07:00 open
    const FIXED_DATE = new Date('2026-06-01T00:00:00Z')
    const OrigDate = globalThis.Date
    vi.spyOn(globalThis, 'Date').mockImplementation((...args) => {
      if (args.length === 0) return FIXED_DATE
      // @ts-ignore: test helper
      return new OrigDate(...args)
    })

    useClientGymInfo.mockReturnValue(makeQuery({ data: GYM_DATA }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)

    expect(screen.getByText('Закрыто')).toBeInTheDocument()

    vi.restoreAllMocks()
  })

  // (e) Social section hidden when social is empty
  it('does not render social section when social is empty', () => {
    const dataNoSocial = { ...GYM_DATA, social: [] }
    useClientGymInfo.mockReturnValue(makeQuery({ data: dataNoSocial }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)

    expect(screen.queryByText('МЫ В СОЦСЕТЯХ')).not.toBeInTheDocument()
  })

  // (e) Social section shown when social is present
  it('renders social section with handle text when social data is present', () => {
    useClientGymInfo.mockReturnValue(makeQuery({ data: GYM_DATA }))
    renderSheet(<GymInfoSheet onClose={vi.fn()} />)

    expect(screen.getByText('МЫ В СОЦСЕТЯХ')).toBeInTheDocument()
    expect(screen.getByText('Telegram')).toBeInTheDocument()
    expect(screen.getByText('@mygym_test')).toBeInTheDocument()
  })

})
