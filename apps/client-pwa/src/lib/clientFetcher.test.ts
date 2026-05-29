import { describe, it, expect, beforeEach } from 'vitest'
import { readClientCsrfCookie, CLIENT_AUTH_EXEMPT_PATHS } from './clientFetcher'

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
    const { render } = await import('@testing-library/react')
    const { MemoryRouter } = await import('react-router-dom')
    const React = await import('react')
    const { default: App } = await import('../App')
    expect(() =>
      render(
        React.createElement(MemoryRouter, { initialEntries: ['/home'] },
          React.createElement(App),
        ),
      ),
    ).not.toThrow()
  })
})
