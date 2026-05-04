import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { ClientsTable } from './ClientsTable'
import type { Client, ClientId, Pagination } from '@/entities/client'
import type { UseQueryResult } from '@tanstack/react-query'

// Avoid having to spin up the real route file in test
vi.mock('@/routes/_protected/clients', () => ({
  Route: { fullPath: '/clients', useSearch: () => ({ page: 1, pageSize: 20 }) },
}))

function makeQuery(items: Client[]): UseQueryResult<Pagination<Client>> {
  return {
    data: { items, total: items.length, page: 1, pageSize: 20 },
    isError: false,
    isLoading: false,
    isPending: false,
    isSuccess: true,
    refetch: () => Promise.resolve(undefined),
  } as unknown as UseQueryResult<Pagination<Client>>
}

const sample: Client[] = [
  {
    id: '11111111-1111-4111-8111-111111111111' as ClientId,
    fullName: 'Тест Тест',
    phone: '+79991234567',
    createdAt: '2026-01-01T00:00:00.000Z',
  },
]

describe('ClientsTable RBAC', () => {
  const props = () => ({
    query: makeQuery(sample),
    search: { page: 1, pageSize: 20 },
    onEdit: () => undefined,
    onDelete: () => undefined,
    onRetry: () => undefined,
    onCreateFromEmpty: () => undefined,
  })

  it('shows the delete button for owner', () => {
    renderWithProviders(<ClientsTable {...props()} />, { role: 'owner' })
    expect(screen.queryByLabelText('Удалить клиента')).toBeInTheDocument()
  })

  it('hides the delete button for reception (D-11 — RoleGate returns null)', () => {
    renderWithProviders(<ClientsTable {...props()} />, { role: 'reception' })
    expect(screen.queryByLabelText('Удалить клиента')).not.toBeInTheDocument()
  })

  it('shows the edit button for both roles', () => {
    const { unmount } = renderWithProviders(<ClientsTable {...props()} />, { role: 'owner' })
    expect(screen.queryByLabelText('Редактировать клиента')).toBeInTheDocument()
    unmount()
    renderWithProviders(<ClientsTable {...props()} />, { role: 'reception' })
    expect(screen.queryByLabelText('Редактировать клиента')).toBeInTheDocument()
  })
})
