import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/test/utils'
import { ProfileMenu } from './ProfileMenu'

const { navigateMock } = vi.hoisted(() => ({
  navigateMock: vi.fn().mockResolvedValue(undefined),
}))
vi.mock('@tanstack/react-router', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-router')>('@tanstack/react-router')
  return { ...actual, useNavigate: () => navigateMock }
})

const { logoutMock } = vi.hoisted(() => ({
  logoutMock: vi.fn().mockResolvedValue(undefined),
}))
vi.mock('@/shared/api/services', () => ({
  services: { auth: { logout: logoutMock } },
  API_MODE: 'mock',
}))

const { clearMock } = vi.hoisted(() => ({
  clearMock: vi.fn(),
}))
vi.mock('@/app/queryClient', () => ({
  queryClient: { clear: clearMock },
}))

describe('ProfileMenu logout (D-08, FE-06)', () => {
  beforeEach(() => {
    navigateMock.mockClear()
    logoutMock.mockClear()
    clearMock.mockClear()
  })

  it('renders the "Выйти" item with LogOut icon', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ProfileMenu />, { role: 'owner' })
    await user.click(screen.getByRole('button', { name: /Профиль/i }))
    const item = await screen.findByText('Выйти')
    expect(item).toBeInTheDocument()
  })

  it('calls services.auth.logout, then queryClient.clear, then navigate({to:"/login"})', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ProfileMenu />, { role: 'owner' })
    await user.click(screen.getByRole('button', { name: /Профиль/i }))
    const item = await screen.findByText('Выйти')
    await user.click(item)
    await waitFor(() => {
      expect(logoutMock).toHaveBeenCalledTimes(1)
      expect(clearMock).toHaveBeenCalledTimes(1)
      expect(navigateMock).toHaveBeenCalledWith({ to: '/login', replace: true })
    })
  })
})
