import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { SessionsList } from './SessionsList'
import type { SessionFamily } from '@/shared/api/contracts/auth'

const { sessionsMock, revokeMock, logoutAllMock } = vi.hoisted(() => ({
  sessionsMock: vi.fn(),
  revokeMock: vi.fn(),
  logoutAllMock: vi.fn(),
}))

vi.mock('@/shared/api/services', () => ({
  services: {
    auth: {
      sessions: sessionsMock,
      revokeSession: revokeMock,
      logoutAll: logoutAllMock,
    },
  },
  API_MODE: 'http',
}))

const { navigateMock } = vi.hoisted(() => ({
  navigateMock: vi.fn().mockResolvedValue(undefined),
}))
vi.mock('@tanstack/react-router', async () => {
  const actual =
    await vi.importActual<typeof import('@tanstack/react-router')>('@tanstack/react-router')
  return { ...actual, useNavigate: () => navigateMock }
})

const { toastSuccessMock, toastErrorMock } = vi.hoisted(() => ({
  toastSuccessMock: vi.fn(),
  toastErrorMock: vi.fn(),
}))
vi.mock('sonner', () => ({
  toast: { success: toastSuccessMock, error: toastErrorMock },
}))

const sample: SessionFamily[] = [
  {
    familyId: 'fam-current',
    createdAt: '2026-05-01T12:00:00Z',
    lastUsedAt: '2026-05-08T09:00:00Z',
    userAgent: 'Mozilla/5.0 (Macintosh)',
    channel: 'email',
    isCurrent: true,
  },
  {
    familyId: 'fam-other',
    createdAt: '2026-05-03T15:30:00Z',
    lastUsedAt: '2026-05-07T10:00:00Z',
    userAgent: null,
    channel: 'telegram_bot',
    isCurrent: false,
  },
]

describe('SessionsList (FE-09)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders skeleton rows while pending', () => {
    sessionsMock.mockImplementation(() => new Promise(() => {}))
    const { container } = renderWithProviders(<SessionsList />, { role: 'owner' })
    // 3 skeleton wrappers expected per UI-SPEC
    const skeletons = container.querySelectorAll('[data-slot="skeleton"]')
    expect(skeletons.length).toBeGreaterThanOrEqual(3)
  })

  it('renders empty state when sessions list is empty', async () => {
    sessionsMock.mockResolvedValue([])
    renderWithProviders(<SessionsList />, { role: 'owner' })
    expect(await screen.findByText('Активных сессий не найдено.')).toBeInTheDocument()
  })

  it('renders one row per session with channel + "Текущая" badge for the current session', async () => {
    sessionsMock.mockResolvedValue(sample)
    renderWithProviders(<SessionsList />, { role: 'owner' })
    expect(await screen.findByText('Email')).toBeInTheDocument()
    expect(screen.getByText('Telegram')).toBeInTheDocument()
    expect(screen.getByText('Текущая')).toBeInTheDocument()
    // Both sessions show their createdAt formatted DD.MM.YYYY
    expect(screen.getByText('01.05.2026')).toBeInTheDocument()
    expect(screen.getByText('03.05.2026')).toBeInTheDocument()
  })

  it('clicking "Отозвать" calls revokeSession and shows success toast', async () => {
    sessionsMock.mockResolvedValue(sample)
    revokeMock.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderWithProviders(<SessionsList />, { role: 'owner' })
    await screen.findByText('Текущая')
    const buttons = screen.getAllByRole('button', { name: /Отозвать fam-/ })
    expect(buttons).toHaveLength(2)
    await user.click(buttons[1]!)
    await waitFor(() => {
      expect(revokeMock).toHaveBeenCalledWith('fam-other')
      expect(toastSuccessMock).toHaveBeenCalledWith('Сессия отозвана')
    })
  })

  it('clicking "Выйти со всех устройств" opens the LogoutAllDialog', async () => {
    sessionsMock.mockResolvedValue(sample)
    const user = userEvent.setup()
    renderWithProviders(<SessionsList />, { role: 'owner' })
    await screen.findByText('Текущая')
    await user.click(screen.getByRole('button', { name: 'Выйти со всех устройств' }))
    expect(await screen.findByText('Выйти со всех устройств?')).toBeInTheDocument()
  })
})
