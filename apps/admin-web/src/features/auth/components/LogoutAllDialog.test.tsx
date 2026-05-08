import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { LogoutAllDialog } from './LogoutAllDialog'

const { logoutAllMock } = vi.hoisted(() => ({ logoutAllMock: vi.fn() }))
vi.mock('@/shared/api/services', () => ({
  services: { auth: { logoutAll: logoutAllMock } },
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

describe('LogoutAllDialog (FE-09)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders title + body + action + cancel when open', () => {
    renderWithProviders(<LogoutAllDialog open onClose={() => {}} />, { role: 'owner' })
    expect(screen.getByText('Выйти со всех устройств?')).toBeInTheDocument()
    expect(
      screen.getByText('Все активные сессии будут завершены. Вам потребуется войти снова.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Выйти' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Отмена' })).toBeInTheDocument()
  })

  it('confirm calls logoutAll, shows success toast, and navigates to /login', async () => {
    logoutAllMock.mockResolvedValue(undefined)
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderWithProviders(<LogoutAllDialog open onClose={onClose} />, { role: 'owner' })
    await user.click(screen.getByRole('button', { name: 'Выйти' }))
    await waitFor(() => {
      expect(logoutAllMock).toHaveBeenCalledTimes(1)
      expect(toastSuccessMock).toHaveBeenCalledWith('Выполнен выход со всех устройств')
      expect(navigateMock).toHaveBeenCalledWith({ to: '/login', replace: true })
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('cancel closes the dialog without calling logoutAll', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    renderWithProviders(<LogoutAllDialog open onClose={onClose} />, { role: 'owner' })
    await user.click(screen.getByRole('button', { name: 'Отмена' }))
    expect(logoutAllMock).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalled()
  })
})
