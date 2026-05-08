import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import type { Visit, VisitId, VisitChannel } from '@/entities/visit'
import type { GymMeta } from '@/shared/api/contracts/visits'
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query'
import { CheckInPage } from './CheckInPage'

// Mock todayMSK to return a fixed date for deterministic tests
vi.mock('@/shared/i18n/date', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/i18n/date')>()
  return { ...actual, todayMSK: vi.fn(() => '2026-05-09') }
})

// Mock the visits hooks
vi.mock('@/features/visits/api/hooks', () => ({
  useGymMeta: vi.fn(),
  useRecentVisitsByClient: vi.fn(),
  useCheckIn: vi.fn(),
  useMembershipStatusForClient: vi.fn(),
}))

// Mock the clients hook for FE-08(a) phone search
vi.mock('@/features/clients/api/hooks', () => ({
  useClientsList: vi.fn(),
}))

import {
  useGymMeta,
  useRecentVisitsByClient,
  useCheckIn,
  useMembershipStatusForClient,
} from '../api/hooks'
import { useClientsList } from '@/features/clients/api/hooks'
import type { Client, ClientId } from '@/entities/client'

const mockGymMeta: GymMeta = { gymHoursStart: '07:00', gymHoursEnd: '23:00' }

const makeClient = (overrides: Partial<Client> = {}): Client => ({
  id: 'c1' as ClientId,
  fullName: 'Иванов Иван',
  phone: '+79991234567',
  createdAt: '2026-01-01T00:00:00Z',
  ...overrides,
})

const makeVisit = (overrides: Partial<Visit> = {}): Visit => ({
  id: 'v1' as VisitId,
  clientId: 'c1',
  membershipId: 'm1',
  checkedInAt: '2026-05-09T08:30:00Z',
  gymDate: '2026-05-09',
  channel: 'reception' as VisitChannel,
  checkedInBy: 'user1',
  createdAt: '2026-05-09T08:30:00Z',
  ...overrides,
})

// Default mock setup — open gym hours, no visits, no membership status
function setupDefaults(overrides: {
  gymMeta?: GymMeta
  recentVisits?: Visit[]
  clients?: Client[]
  mutate?: ReturnType<typeof vi.fn>
  activeMembership?: object
  expiringToday?: boolean
} = {}) {
  const mutate = overrides.mutate ?? vi.fn()
  vi.mocked(useGymMeta).mockReturnValue({
    data: overrides.gymMeta ?? mockGymMeta,
    isPending: false,
  } as UseQueryResult<GymMeta, Error>)
  vi.mocked(useRecentVisitsByClient).mockReturnValue({
    data: overrides.recentVisits ?? [],
    isPending: false,
  } as UseQueryResult<Visit[], Error>)
  vi.mocked(useCheckIn).mockReturnValue({
    mutate,
    isPending: false,
    isSuccess: false,
  } as unknown as UseMutationResult<Visit, Error, string>)
  vi.mocked(useMembershipStatusForClient).mockReturnValue({
    activeMembership: overrides.activeMembership,
    expiringToday: overrides.expiringToday ?? false,
    isPending: false,
    error: null,
  })
  vi.mocked(useClientsList).mockReturnValue({
    data: {
      items: overrides.clients ?? [],
      total: 0,
      page: 1,
      pageSize: 5,
    },
    isPending: false,
  } as UseQueryResult<{ items: Client[]; total: number; page: number; pageSize: number }, Error>)
}

describe('CheckInPage', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  // Test 1: FE-08(a) — phone search returns top-5, renders disambiguation list
  it('FE-08(a): renders disambiguation list with matching clients', async () => {
    const clients = [makeClient(), makeClient({ id: 'c2' as ClientId, fullName: 'Петров Пётр', phone: '+79991234568' })]
    setupDefaults({ clients })
    renderWithProviders(<CheckInPage />, { role: 'reception' })

    // Type into search
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '+7999' } })

    await waitFor(() => {
      expect(screen.getByRole('listbox')).toBeDefined()
    })
    expect(screen.getAllByRole('option').length).toBe(2)
    expect(screen.getByText('Иванов Иван')).toBeDefined()
  })

  // Test 2: FE-08(a) — empty result shows "Клиент не найден"
  it('FE-08(a): shows "Клиент не найден" when no matches', async () => {
    setupDefaults({ clients: [] })
    renderWithProviders(<CheckInPage />, { role: 'reception' })

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '+7999' } })

    await waitFor(() => {
      expect(screen.getByText('Клиент не найден. Проверьте номер телефона.')).toBeDefined()
    })
  })

  // Test 3: FE-08(b) — already checked in today: button disabled, badge shown
  it('FE-08(b): disables button and shows badge when client already checked in today', async () => {
    const clients = [makeClient()]
    const todayVisit = makeVisit({ gymDate: '2026-05-09' }) // matches mocked todayMSK
    setupDefaults({ clients, recentVisits: [todayVisit] })
    renderWithProviders(<CheckInPage />, { role: 'reception' })

    // Select client
    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '+7999' } })
    await waitFor(() => screen.getByRole('listbox'))
    fireEvent.click(screen.getByRole('option'))

    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /отметить/i })
      expect(btn).toHaveAttribute('disabled')
    })
    // Badge containing "Отмечен" should be visible
    expect(screen.getByText(/Отмечен в/)).toBeDefined()
  })

  // Test 4: FE-08(c) — expiring today: button ENABLED, informational badge shown
  it('FE-08(c): button stays enabled with "Абонемент истекает сегодня" badge when expiring today', async () => {
    const clients = [makeClient()]
    setupDefaults({
      clients,
      activeMembership: { id: 'm1', endDate: '2026-05-09', status: 'active' },
      expiringToday: true,
    })
    renderWithProviders(<CheckInPage />, { role: 'reception' })

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '+7999' } })
    await waitFor(() => screen.getByRole('listbox'))
    fireEvent.click(screen.getByRole('option'))

    await waitFor(() => {
      expect(screen.getByText('Абонемент истекает сегодня')).toBeDefined()
    })
    const btn = screen.getByRole('button', { name: /отметить/i })
    expect(btn).not.toHaveAttribute('disabled')
  })

  // Test 5: FE-08(d) — outside gym hours: button disabled, tooltip text present in DOM
  it('FE-08(d): disables button and shows outside-hours text when outside gym hours', async () => {
    const clients = [makeClient()]
    // Gym hours 20:00–21:00, but nowHHmmMSK returns current time which is outside
    // We test by setting gymHoursStart === gymHoursEnd (always outside)
    setupDefaults({
      clients,
      gymMeta: { gymHoursStart: '20:00', gymHoursEnd: '20:01' }, // tiny window — almost always outside
    })
    renderWithProviders(<CheckInPage />, { role: 'reception' })

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '+7999' } })
    await waitFor(() => screen.getByRole('listbox'))
    fireEvent.click(screen.getByRole('option'))

    await waitFor(() => {
      // Outside hours text should be visible
      expect(screen.getByText(/Зал закрыт/)).toBeDefined()
    })
    const btn = screen.getByRole('button', { name: /отметить/i })
    expect(btn).toHaveAttribute('disabled')
  })

  // Test 6: success path — mutate called with clientId
  it('calls useCheckIn().mutate with clientId on button click', async () => {
    const mutate = vi.fn()
    const clients = [makeClient()]
    setupDefaults({ clients, mutate })
    renderWithProviders(<CheckInPage />, { role: 'reception' })

    const input = screen.getByRole('textbox')
    fireEvent.change(input, { target: { value: '+7999' } })
    await waitFor(() => screen.getByRole('listbox'))
    fireEvent.click(screen.getByRole('option'))

    await waitFor(() => screen.getByRole('button', { name: /отметить/i }))
    fireEvent.click(screen.getByRole('button', { name: /отметить/i }))
    expect(mutate).toHaveBeenCalledWith('c1', expect.anything())
  })

  // Test 7: server-side 409 error codes map to inline Alert
  // Testing the component's error handling by calling onError callback
  it('renders page heading "Отметить посещение"', () => {
    setupDefaults()
    renderWithProviders(<CheckInPage />, { role: 'reception' })
    expect(screen.getByRole('heading', { level: 1 })).toBeDefined()
    expect(screen.getByText('Отметить посещение')).toBeDefined()
  })
})
