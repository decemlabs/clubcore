/**
 * AuthContext tests (Plan 71-07).
 *
 * Asserts:
 *  (a) /client/me probe 200 → status 'authed'
 *  (b) /client/me probe rejects (401) → status 'anon' (no throw)
 *  (c) publishSessionExpired() flips an authed context to 'anon'
 */
import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from './AuthContext.jsx'

// ---------------------------------------------------------------------------
// Mock clientFetcher — controls whether the /client/me probe succeeds or fails
// ---------------------------------------------------------------------------
vi.mock('@/lib/clientFetcher', () => ({
  clientRequest: vi.fn(),
  readClientCsrfCookie: vi.fn(() => undefined),
  CLIENT_AUTH_EXEMPT_PATHS: [],
  clientRefreshOnce: vi.fn(),
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
}

function StatusDisplay() {
  const { status } = useAuth()
  return <div data-testid="status">{status}</div>
}

function renderWithAuth(mockFn) {
  const qc = makeQueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <StatusDisplay />
      </AuthProvider>
    </QueryClientProvider>,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AuthContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('(a) probe 200 → status becomes authed', async () => {
    const { clientRequest } = await import('@/lib/clientFetcher')
    clientRequest.mockResolvedValueOnce({ data: { id: 'c1', name: 'Test' } })

    renderWithAuth()

    // Initially unknown while probe is pending
    expect(screen.getByTestId('status').textContent).toBe('unknown')

    // After probe resolves → authed
    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('authed')
    })
  })

  it('(b) probe rejects (401) → status becomes anon (no throw)', async () => {
    const { clientRequest } = await import('@/lib/clientFetcher')
    clientRequest.mockRejectedValueOnce(new Error('401 Unauthorized'))

    renderWithAuth()

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('anon')
    })
  })

  it('(c) publishSessionExpired flips authed context to anon', async () => {
    const { clientRequest } = await import('@/lib/clientFetcher')
    // Start authed
    clientRequest.mockResolvedValueOnce({ data: { id: 'c1' } })

    renderWithAuth()

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('authed')
    })

    // Simulate session expiry from authBus
    const { publishSessionExpired } = await import('@/lib/authBus')
    await act(async () => {
      publishSessionExpired()
    })

    await waitFor(() => {
      expect(screen.getByTestId('status').textContent).toBe('anon')
    })
  })
})
