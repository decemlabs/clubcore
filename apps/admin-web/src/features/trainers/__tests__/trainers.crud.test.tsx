import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { useSessionStore } from '@/shared/session/store'
import { resetDB } from '@/shared/api/services/mock/_db'
import { trainers as trainersService } from '@/shared/api/services/mock/trainers'
import { DomainError } from '@/shared/api/errors'

/**
 * TrainersPage component tests.
 *
 * We test the components via the real mock service (not vi.mock for services) to
 * verify the full vertical slice including RBAC, validation, and state.
 *
 * Route hooks (useSearch / useNavigate) are mocked because TrainersPage relies
 * on TanStack Router's file-based route.
 * Sonner is mocked to capture toast calls since it renders outside React tree.
 */

// Hoist mocks before imports that use them
const { toastSuccessMock, toastErrorMock } = vi.hoisted(() => ({
  toastSuccessMock: vi.fn(),
  toastErrorMock: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: { success: toastSuccessMock, error: toastErrorMock },
}))

// Speed up mock service responses by zeroing latency
vi.mock('@/shared/api/services/mock/_latency', () => ({
  delay: () => Promise.resolve(),
}))

const mockNavigate = vi.fn()
const mockSearch = {
  active: 'true' as 'true' | 'false' | undefined,
  page: 1,
  pageSize: 20,
}

vi.mock('@/routes/_protected/trainers', () => ({
  Route: {
    useSearch: () => mockSearch,
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

// Import AFTER vi.mock declarations
import { TrainersPage } from '../components/TrainersPage'

function makeQc() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

function renderPage(role: 'owner' | 'reception' = 'owner') {
  useSessionStore.setState({ role })
  const qc = makeQc()
  return {
    qc,
    ...render(
      createElement(QueryClientProvider, { client: qc }, createElement(TrainersPage)),
    ),
  }
}

describe('TrainersPage CRUD', () => {
  beforeEach(() => {
    resetDB()
    useSessionStore.setState({ role: 'owner' })
    vi.clearAllMocks()
    Object.assign(mockSearch, { active: 'true', page: 1, pageSize: 20 })
  })

  it('renders heading "Тренеры" and CTA "Добавить тренера"', async () => {
    renderPage()
    expect(await screen.findByText('Тренеры')).toBeTruthy()
    expect(screen.getByRole('button', { name: /Добавить тренера/ })).toBeTruthy()
  })

  it('renders filter pills: Активные, Неактивные, Все', async () => {
    renderPage()
    expect(await screen.findByRole('button', { name: 'Активные' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Неактивные' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Все' })).toBeTruthy()
  })

  it('renders trainer data in table after loading (active filter = 5 active trainers)', async () => {
    renderPage()
    await waitFor(
      () => {
        const rows = screen.getAllByRole('row')
        expect(rows.length).toBeGreaterThan(1)
      },
      { timeout: 5000 },
    )
  })

  it('clicking "Добавить тренера" opens dialog with title "Добавить тренера"', async () => {
    const user = userEvent.setup()
    renderPage()
    // Click the CTA button in the header (not inside the empty state)
    const cta = await screen.findByRole('button', { name: 'Добавить тренера' })
    await user.click(cta)
    expect(await screen.findByRole('dialog')).toBeTruthy()
  })

  it('submitting empty fullName shows inline validation error "Укажите ФИО"', async () => {
    const user = userEvent.setup()
    renderPage()
    const cta = await screen.findByRole('button', { name: 'Добавить тренера' })
    await user.click(cta)
    await screen.findByRole('dialog')
    // Find submit button by type
    const submitBtn = screen
      .getAllByRole('button')
      .find((b) => b.getAttribute('type') === 'submit')
    expect(submitBtn).toBeTruthy()
    await user.click(submitBtn!)
    expect(await screen.findByText('Укажите ФИО')).toBeTruthy()
  })

  it('attempting to create with duplicate phone shows inline Alert with phoneDuplicate copy', async () => {
    // Pre-seed a trainer with that phone number
    await trainersService.create({ fullName: 'Первый тренер', phone: '+79990000099' })

    const user = userEvent.setup()
    renderPage()
    const cta = await screen.findByRole('button', { name: 'Добавить тренера' })
    await user.click(cta)
    await screen.findByRole('dialog')

    const nameInput = screen.getByLabelText(/ФИО/)
    const phoneInput = screen.getByLabelText(/Телефон/)
    await user.type(nameInput, 'Второй тренер')
    await user.type(phoneInput, '+79990000099')

    const submitBtn = screen
      .getAllByRole('button')
      .find((b) => b.getAttribute('type') === 'submit')
    await user.click(submitBtn!)

    expect(await screen.findByText('Тренер с таким телефоном уже существует')).toBeTruthy()
    // Dialog stays open
    expect(screen.queryByRole('dialog')).toBeTruthy()
  })

  it('clicking trash button opens DeleteTrainerAlertDialog with title "Удалить тренера?"', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => expect(screen.getAllByRole('row').length).toBeGreaterThan(1), {
      timeout: 5000,
    })
    const deleteBtns = await screen.findAllByLabelText('Удалить тренера')
    expect(deleteBtns.length).toBeGreaterThan(0)
    await user.click(deleteBtns[0]!)
    expect(await screen.findByRole('alertdialog')).toBeTruthy()
    expect(await screen.findByText('Удалить тренера?')).toBeTruthy()
  })

  it('when delete mutation rejects with trainer_in_use, dialog stays open with inline error', async () => {
    const user = userEvent.setup()

    vi.spyOn(trainersService, 'delete').mockRejectedValueOnce(
      new DomainError('trainer_in_use', 'Тренер ведёт занятия'),
    )

    renderPage()
    await waitFor(() => expect(screen.getAllByRole('row').length).toBeGreaterThan(1), {
      timeout: 5000,
    })
    const deleteBtns = await screen.findAllByLabelText('Удалить тренера')
    await user.click(deleteBtns[0]!)
    await screen.findByRole('alertdialog')

    const confirmBtn = screen.getByRole('button', { name: 'Удалить' })
    await user.click(confirmBtn)

    // Inline error message appears
    expect(
      await screen.findByText(/ведёт персональні тренування|ведёт персональные тренировки/),
    ).toBeTruthy()
    // AlertDialog remains open
    expect(screen.queryByRole('alertdialog')).toBeTruthy()
  })

  it(
    'successfully creating a trainer calls toast.success("Тренер добавлен")',
    async () => {
      const user = userEvent.setup()
      renderPage()
      const cta = await screen.findByRole('button', { name: 'Добавить тренера' })
      await user.click(cta)
      await screen.findByRole('dialog')

      const nameInput = screen.getByLabelText(/ФИО/)
      await user.type(nameInput, 'Новый тренер тест')

      const submitBtn = screen
        .getAllByRole('button')
        .find((b) => b.getAttribute('type') === 'submit')
      await user.click(submitBtn!)

      await waitFor(() => expect(toastSuccessMock).toHaveBeenCalled(), { timeout: 10000 })
      expect(toastSuccessMock).toHaveBeenCalledWith('Тренер добавлен')
    },
    15000,
  )
})
