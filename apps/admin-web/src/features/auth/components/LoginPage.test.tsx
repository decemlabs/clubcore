import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { LoginPage } from './LoginPage'

// Mock the login route so LoginPage can call Route.useSearch() in tests
// (TanStack Router's useSearch() requires a router context that isn't present in unit tests)
vi.mock('@/routes/_public/login', () => ({
  Route: { useSearch: () => ({}) },
}))

// Mock navigate — LoginPage calls useNavigate() from @tanstack/react-router
vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  }
})

describe('LoginPage', () => {
  it('renders heading "Войти в систему"', () => {
    renderWithProviders(<LoginPage />)
    expect(screen.getByText('Войти в систему')).toBeInTheDocument()
  })

  it('renders both tab triggers', () => {
    renderWithProviders(<LoginPage />)
    expect(screen.getByRole('tab', { name: /Email/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Telegram/i })).toBeInTheDocument()
  })

  it('defaults to the Email tab (D-02)', () => {
    renderWithProviders(<LoginPage />)
    const emailTab = screen.getByRole('tab', { name: /Email/i })
    // base-ui tabs use aria-selected instead of data-state
    expect(emailTab).toHaveAttribute('aria-selected', 'true')
  })

  it('shows the email + password fields by default', () => {
    renderWithProviders(<LoginPage />)
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Пароль')).toBeInTheDocument()
  })
})
