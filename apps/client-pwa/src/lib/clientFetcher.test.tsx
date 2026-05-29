/**
 * Smoke tests for clientFetcher (Phase 69 PWA-03, D-69-09).
 *
 * Note: react-router-dom v6 JSX types are incompatible with @types/react@18's
 * ReactPortal.children constraint — a known type-only mismatch. We cast to
 * React.ElementType to work around it without affecting runtime behavior.
 */
import React from 'react'
import { describe, it, expect, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { readClientCsrfCookie, CLIENT_AUTH_EXEMPT_PATHS } from './clientFetcher'

// Dynamic imports for JSX modules — required so Vitest/Vite can transform
// the .jsx files properly through the react() plugin transform pipeline.
type TweaksProviderType = React.ComponentType<{ children: React.ReactNode }>
type UIProviderType = React.ComponentType<{ children: React.ReactNode }>
type AppType = React.ComponentType

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

    // Cast via React.ElementType to work around react-router-dom v6 + @types/react@18 mismatch.
    const Router = MemoryRouter as React.ElementType
    const Tweaks = TweaksProvider as React.ElementType
    const UI = UIProvider as React.ElementType
    const AppComp = App as React.ElementType

    expect(() =>
      render(
        <Router initialEntries={['/home']}>
          <Tweaks>
            <UI>
              <AppComp />
            </UI>
          </Tweaks>
        </Router>,
      ),
    ).not.toThrow()
  })
})
