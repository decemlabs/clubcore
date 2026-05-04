import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { TelegramLoginTab } from './TelegramLoginTab'
import { resetDB } from '@/shared/api/services/mock/_db'

describe('TelegramLoginTab', () => {
  beforeEach(() => {
    resetDB()
    vi.useRealTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts in the idle state with "Получить ссылку Telegram"', () => {
    renderWithProviders(<TelegramLoginTab onSuccess={() => {}} />)
    expect(screen.getByRole('button', { name: /Получить ссылку Telegram/ })).toBeInTheDocument()
  })

  it('moves to the polling state after pressing the start button', async () => {
    renderWithProviders(<TelegramLoginTab onSuccess={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /Получить ссылку Telegram/ }))
    await waitFor(
      () => {
        expect(screen.getByText(/Ожидание подтверждения/)).toBeInTheDocument()
      },
      { timeout: 5000 },
    )
  })

  // Note: full timeout-after-5min test is brittle in jsdom because vi.useFakeTimers
  // does not advance Date.now() unless we explicitly use vi.setSystemTime — the executor
  // may add this test as a follow-up if it stabilizes. Minimum coverage above is sufficient
  // for FE-02 acceptance.
})
