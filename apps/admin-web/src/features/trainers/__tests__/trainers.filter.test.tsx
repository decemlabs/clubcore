import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { useSessionStore } from '@/shared/session/store'
import { resetDB } from '@/shared/api/services/mock/_db'

/**
 * Filter URL parity tests for the /trainers route.
 *
 * Tests verify that:
 * 1. All 3 filter buttons are rendered
 * 2. Clicking 'Неактивные' triggers navigate with active='false'
 * 3. Clicking 'Все' triggers navigate with active=undefined
 * 4. Clicking 'Активные' triggers navigate with active='true'
 */

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const mockNavigate = vi.fn()

// Mutable search state controlled per test
const currentSearch: {
  active: 'true' | 'false' | undefined
  page: number
  pageSize: number
} = {
  active: 'true',
  page: 1,
  pageSize: 20,
}

vi.mock('@/routes/_protected/trainers', () => ({
  Route: {
    useSearch: () => currentSearch,
    fullPath: '/_protected/trainers',
  },
}))

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    redirect: actual.redirect,
  }
})

import { TrainersPage } from '../components/TrainersPage'

function makeQc() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

function renderPage() {
  const qc = makeQc()
  return render(
    createElement(QueryClientProvider, { client: qc }, createElement(TrainersPage)),
  )
}

describe('TrainersPage filter URL parity', () => {
  beforeEach(() => {
    resetDB()
    useSessionStore.setState({ role: 'owner' })
    vi.clearAllMocks()
    currentSearch.active = 'true'
    currentSearch.page = 1
    currentSearch.pageSize = 20
  })

  it('renders all 3 filter buttons: Активные, Неактивные, Все', async () => {
    renderPage()
    expect(await screen.findByRole('button', { name: 'Активные' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Неактивные' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Все' })).toBeTruthy()
  })

  it('clicking "Неактивные" calls navigate with search { active: "false", page: 1 }', async () => {
    const user = userEvent.setup()
    renderPage()
    const inactiveBtn = await screen.findByRole('button', { name: 'Неактивные' })
    await user.click(inactiveBtn)

    expect(mockNavigate).toHaveBeenCalled()
    const callArgs = mockNavigate.mock.calls[0]?.[0] as {
      search: (prev: Record<string, unknown>) => Record<string, unknown>
    }
    const result = callArgs.search({ active: 'true', page: 1, pageSize: 20 })
    expect(result['active']).toBe('false')
    expect(result['page']).toBe(1)
  })

  it('clicking "Все" calls navigate with search { active: undefined, page: 1 }', async () => {
    const user = userEvent.setup()
    renderPage()
    const allBtn = await screen.findByRole('button', { name: 'Все' })
    await user.click(allBtn)

    expect(mockNavigate).toHaveBeenCalled()
    const callArgs = mockNavigate.mock.calls[0]?.[0] as {
      search: (prev: Record<string, unknown>) => Record<string, unknown>
    }
    const result = callArgs.search({ active: 'true', page: 1, pageSize: 20 })
    expect(result['active']).toBeUndefined()
    expect(result['page']).toBe(1)
  })

  it('clicking "Активные" calls navigate with search { active: "true", page: 1 }', async () => {
    const user = userEvent.setup()
    currentSearch.active = undefined
    renderPage()
    const activeBtn = await screen.findByRole('button', { name: 'Активные' })
    await user.click(activeBtn)

    expect(mockNavigate).toHaveBeenCalled()
    const callArgs = mockNavigate.mock.calls[0]?.[0] as {
      search: (prev: Record<string, unknown>) => Record<string, unknown>
    }
    const result = callArgs.search({ active: undefined, page: 1, pageSize: 20 })
    expect(result['active']).toBe('true')
    expect(result['page']).toBe(1)
  })
})
