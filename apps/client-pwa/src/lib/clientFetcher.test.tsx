/**
 * Smoke tests for clientFetcher (Phase 69 PWA-03, D-69-09).
 *
 * Note: react-router-dom v6 JSX types are incompatible with @types/react@18's
 * ReactPortal.children constraint — a known type-only mismatch. We cast to
 * React.ElementType to work around it without affecting runtime behavior.
 *
 * Plan 71-07: QueryClientProvider moved from App.jsx to main.jsx; App now calls
 * useAuth() via AuthContext. Test wraps App in the full new provider tree with a
 * stub AuthContext so the render does not depend on network timing.
 */
import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render } from '@testing-library/react'
import { readClientCsrfCookie, CLIENT_AUTH_EXEMPT_PATHS } from './clientFetcher'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Mock clientRequest so the /client/me probe in AuthProvider resolves immediately
vi.mock('@/lib/clientFetcher', async (importOriginal) => {
  const original = await importOriginal<typeof import('./clientFetcher')>()
  return {
    ...original,
    clientRequest: vi.fn().mockRejectedValue(new Error('anon')),
  }
})

// Dynamic imports for JSX modules — required so Vitest/Vite can transform
// the .jsx files properly through the react() plugin transform pipeline.
type TweaksProviderType = React.ComponentType<{ children: React.ReactNode }>
type UIProviderType = React.ComponentType<{ children: React.ReactNode }>
type AppType = React.ComponentType
type AuthContextType = React.Context<{ status: string; login: () => Promise<void>; logout: () => Promise<void> } | null>

describe('clientFetcher', () => {
  beforeEach(() => {
    // Reset document.cookie between tests
    Object.defineProperty(document, 'cookie', {
      value: '',
      writable: true,
      configurable: true,
    })
  })

  it('reads clubcore_client_csrf cookie and NOT clubcore_csrf', () => {
    // Set both cookies — function must return only the client-scoped one
    document.cookie = 'clubcore_csrf=staff-token; clubcore_client_csrf=test-csrf-token'
    expect(readClientCsrfCookie()).toBe('test-csrf-token')
  })

  it('CLIENT_AUTH_EXEMPT_PATHS contains client OTP and session refresh paths', () => {
    expect(CLIENT_AUTH_EXEMPT_PATHS).toContain('/api/v1/client/otp/request')
    expect(CLIENT_AUTH_EXEMPT_PATHS).toContain('/api/v1/client/session/refresh')
  })

  it('App renders without throwing', async () => {
    const { MemoryRouter } = await import('react-router-dom')
    const { TweaksProvider } = (await import('../context/TweaksContext.jsx')) as {
      TweaksProvider: TweaksProviderType
    }
    const { UIProvider } = (await import('../context/UIContext.jsx')) as {
      UIProvider: UIProviderType
    }
    const { default: App } = (await import('../App')) as { default: AppType }
    // Import the raw AuthContext to provide a stub value (avoids network probe in test)
    const { default: AuthContext } = (await import('../context/AuthContext.jsx')) as {
      default: AuthContextType
    }

    // Cast via React.ElementType to work around react-router-dom v6 + @types/react@18 mismatch.
    const Router = MemoryRouter as React.ElementType
    const Tweaks = TweaksProvider as React.ElementType
    const UI = UIProvider as React.ElementType
    const AppComp = App as React.ElementType
    const AuthCtx = AuthContext as React.Context<unknown>

    // Stub auth value — status 'unknown' so RequireAuth shows spinner, no protected queries fire
    const stubAuth = { status: 'unknown', login: vi.fn(), logout: vi.fn() }

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })

    // Provider order mirrors main.jsx:
    // MemoryRouter → QueryClientProvider → AuthContext.Provider(stub) → TweaksProvider → UIProvider → App
    expect(() =>
      render(
        <Router initialEntries={['/home']}>
          <QueryClientProvider client={qc}>
            <AuthCtx.Provider value={stubAuth}>
              <Tweaks>
                <UI>
                  <AppComp />
                </UI>
              </Tweaks>
            </AuthCtx.Provider>
          </QueryClientProvider>
        </Router>,
      ),
    ).not.toThrow()
  })
})
