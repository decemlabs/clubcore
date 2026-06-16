/**
 * TrainerDetailSheet tests (Phase 88 TRNR-04).
 *
 * Covers:
 *   (1) Loaded state renders fullName + "БИОГРАФИЯ" section + bio text
 *   (2) Loading state shows skeleton aria-label, no trainer name
 *   (3) Error state renders the error copy
 *   (4) Null bio renders "Информация скоро появится."
 *   (5) XSS guard: javascript: photoUrl does NOT appear in an img src (Avatar fallback)
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ─── Wrap with QueryClientProvider ───────────────────────────────────────────
function renderSheet(ui) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

// ─── Mock @/data: useClientTrainerDetail ─────────────────────────────────────
const useClientTrainerDetail = vi.fn()

vi.mock('@/data', async () => {
  const actual = await vi.importActual('@/data')
  return {
    ...actual,
    useClientTrainerDetail: (...args) => useClientTrainerDetail(...args),
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

import { TrainerDetailSheet } from './TrainerDetailSheet.jsx'

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

// Sample trainer prop (from TRAINERS list — has .id, .bg, .color)
const TRAINER_PROP = {
  id: 'aaaaaaaa-0000-0000-0000-000000000001',
  name: 'Аня Соколова',
  bg: '#3f4444',
  color: '#ffffff',
}

// Sample full detail data matching TrainerDetailData interface
const TRAINER_DATA = {
  id: 'aaaaaaaa-0000-0000-0000-000000000001',
  fullName: 'Аня Соколова',
  photoUrl: null,
  specialization: 'Силовые, функционал',
  bio: 'Аня Соколова — силовые и функциональный тренинг, 7 лет опыта.',
}

// ─── Tests ────────────────────────────────────────────────────────────────────
describe('TrainerDetailSheet', () => {

  beforeEach(() => {
    vi.clearAllMocks()
  })

  // (1) Loaded state renders fullName + "БИОГРАФИЯ" + bio text
  it('renders trainer full name, БИОГРАФИЯ section, and bio text when loaded', () => {
    useClientTrainerDetail.mockReturnValue(makeQuery({ data: TRAINER_DATA }))
    renderSheet(
      <TrainerDetailSheet trainer={TRAINER_PROP} onClose={vi.fn()} onBook={vi.fn()} />,
    )

    expect(screen.getByText('Аня Соколова')).toBeInTheDocument()
    expect(screen.getByText('БИОГРАФИЯ')).toBeInTheDocument()
    expect(screen.getByText('Аня Соколова — силовые и функциональный тренинг, 7 лет опыта.')).toBeInTheDocument()
  })

  // (2) Loading state shows skeleton aria-label, no trainer name text
  it('shows skeleton aria-label and no trainer name when loading', () => {
    useClientTrainerDetail.mockReturnValue(makeQuery({ isLoading: true, data: undefined }))
    renderSheet(
      <TrainerDetailSheet trainer={TRAINER_PROP} onClose={vi.fn()} onBook={vi.fn()} />,
    )

    expect(screen.getByLabelText('Загрузка профиля тренера…')).toBeInTheDocument()
    expect(screen.queryByText('Аня Соколова')).not.toBeInTheDocument()
  })

  // (3) Error state renders the error copy
  it('renders error copy when query fails', () => {
    useClientTrainerDetail.mockReturnValue(makeQuery({ isError: true, data: undefined }))
    renderSheet(
      <TrainerDetailSheet trainer={TRAINER_PROP} onClose={vi.fn()} onBook={vi.fn()} />,
    )

    expect(
      screen.getByText('Не удалось загрузить профиль тренера. Потяните вниз, чтобы повторить.'),
    ).toBeInTheDocument()
  })

  // (4) Null bio renders "Информация скоро появится."
  it('renders empty bio hint when bio is null', () => {
    const dataNoBio = { ...TRAINER_DATA, bio: null }
    useClientTrainerDetail.mockReturnValue(makeQuery({ data: dataNoBio }))
    renderSheet(
      <TrainerDetailSheet trainer={TRAINER_PROP} onClose={vi.fn()} onBook={vi.fn()} />,
    )

    expect(screen.getByText('Информация скоро появится.')).toBeInTheDocument()
    expect(screen.getByText('БИОГРАФИЯ')).toBeInTheDocument()
  })

  // (5) XSS guard: javascript: photoUrl must NOT appear in an img src
  it('does NOT render javascript: photoUrl in an img src — falls back to Avatar initials', () => {
    const xssData = { ...TRAINER_DATA, photoUrl: 'javascript:alert(1)' }
    useClientTrainerDetail.mockReturnValue(makeQuery({ data: xssData }))
    renderSheet(
      <TrainerDetailSheet trainer={TRAINER_PROP} onClose={vi.fn()} onBook={vi.fn()} />,
    )

    // No img element at all — unsafe URL must produce zero <img> elements (WR-02).
    // A forEach on an empty NodeList is vacuous; use a direct null assertion instead.
    expect(document.querySelector('img')).toBeNull()
    // The avatar initials (АС) should be rendered instead
    expect(screen.getByText('АС')).toBeInTheDocument()
  })

  // Also verify data: scheme is rejected (belt-and-suspenders for T-88-03)
  it('does NOT render data: photoUrl in an img src — falls back to Avatar initials', () => {
    const dataUrl = 'data:text/html,<script>alert(1)</script>'
    const xssData = { ...TRAINER_DATA, photoUrl: dataUrl }
    useClientTrainerDetail.mockReturnValue(makeQuery({ data: xssData }))
    renderSheet(
      <TrainerDetailSheet trainer={TRAINER_PROP} onClose={vi.fn()} onBook={vi.fn()} />,
    )

    // No img element at all — unsafe URL must produce zero <img> elements (WR-02).
    expect(document.querySelector('img')).toBeNull()
    expect(screen.getByText('АС')).toBeInTheDocument()
  })

  // CTA "Записаться" is always present
  it('renders "Записаться" CTA in all states', () => {
    useClientTrainerDetail.mockReturnValue(makeQuery({ isLoading: true, data: undefined }))
    renderSheet(
      <TrainerDetailSheet trainer={TRAINER_PROP} onClose={vi.fn()} onBook={vi.fn()} />,
    )

    expect(screen.getByRole('button', { name: 'Записаться' })).toBeInTheDocument()
  })

  // "Записаться" disabled when onBook is absent
  it('renders "Записаться" CTA as disabled when onBook prop is absent', () => {
    useClientTrainerDetail.mockReturnValue(makeQuery({ data: TRAINER_DATA }))
    renderSheet(
      <TrainerDetailSheet trainer={TRAINER_PROP} onClose={vi.fn()} />,
    )

    expect(screen.getByRole('button', { name: 'Записаться' })).toBeDisabled()
  })

  // http: photoUrl IS rendered in an img src (positive control for XSS guard)
  it('renders http: photoUrl in an img src (positive control)', () => {
    const httpData = { ...TRAINER_DATA, photoUrl: 'https://cdn.example.com/anya.jpg' }
    useClientTrainerDetail.mockReturnValue(makeQuery({ data: httpData }))
    renderSheet(
      <TrainerDetailSheet trainer={TRAINER_PROP} onClose={vi.fn()} onBook={vi.fn()} />,
    )

    const img = document.querySelector('img')
    expect(img).not.toBeNull()
    expect(img.getAttribute('src')).toBe('https://cdn.example.com/anya.jpg')
  })

})
