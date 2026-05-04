import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useDeleteClient } from './hooks'
import { clientsKeys } from './keys'
import type { Client, ClientId, Pagination } from '@/entities/client'
import { DomainError } from '@/shared/api/errors'

// Use vi.hoisted so removeMock is defined before vi.mock hoisting runs
const { removeMock } = vi.hoisted(() => ({ removeMock: vi.fn() }))

// Mock the swap-seam to control what services.clients.remove returns
vi.mock('@/shared/api/services', () => ({
  services: { clients: { remove: removeMock } },
  API_MODE: 'mock',
}))

function makeClient(idStr: string, name: string): Client {
  return {
    id: idStr as ClientId,
    fullName: name,
    phone: '+79991234567',
    createdAt: '2026-01-01T00:00:00.000Z',
  }
}

function makeWrapper(qc: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  }
}

describe('useDeleteClient — optimistic + rollback', () => {
  let qc: QueryClient
  const filter = { page: 1, pageSize: 20 }

  beforeEach(() => {
    removeMock.mockReset()
    qc = new QueryClient({ defaultOptions: { mutations: { retry: 0 }, queries: { retry: false } } })
    const seed: Pagination<Client> = {
      items: [
        makeClient('11111111-1111-4111-8111-111111111111', 'A'),
        makeClient('22222222-2222-4222-8222-222222222222', 'B'),
        makeClient('33333333-3333-4333-8333-333333333333', 'C'),
      ],
      total: 3,
      page: 1,
      pageSize: 20,
    }
    qc.setQueryData(clientsKeys.list(filter), seed)
  })

  it('optimistically removes the deleted client from the cached list', async () => {
    removeMock.mockResolvedValueOnce(undefined)
    const { result } = renderHook(() => useDeleteClient(), { wrapper: makeWrapper(qc) })
    await act(async () => {
      result.current.mutate('22222222-2222-4222-8222-222222222222' as ClientId)
    })
    // Check the cache during/after onMutate before settle
    await waitFor(() => {
      const cached = qc.getQueryData<Pagination<Client>>(clientsKeys.list(filter))
      expect(cached?.items.find((c) => c.fullName === 'B')).toBeUndefined()
    })
  })

  it('rolls back on error', async () => {
    removeMock.mockRejectedValueOnce(new DomainError('forbidden', 'No'))
    const { result } = renderHook(() => useDeleteClient(), { wrapper: makeWrapper(qc) })
    await act(async () => {
      result.current.mutate('22222222-2222-4222-8222-222222222222' as ClientId)
    })
    await waitFor(() => expect(result.current.isError).toBe(true))
    const cached = qc.getQueryData<Pagination<Client>>(clientsKeys.list(filter))
    expect(cached?.items.length).toBe(3)
    expect(cached?.items.find((c) => c.fullName === 'B')).toBeDefined()
  })

  it('decrements total on optimistic delete', async () => {
    removeMock.mockResolvedValueOnce(undefined)
    const { result } = renderHook(() => useDeleteClient(), { wrapper: makeWrapper(qc) })
    await act(async () => {
      result.current.mutate('22222222-2222-4222-8222-222222222222' as ClientId)
    })
    await waitFor(() => {
      const cached = qc.getQueryData<Pagination<Client>>(clientsKeys.list(filter))
      expect(cached?.total).toBe(2)
    })
  })
})
