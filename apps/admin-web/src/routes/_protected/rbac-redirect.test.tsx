import { describe, it, expect, beforeEach } from 'vitest'
import type { QueryClient } from '@tanstack/react-query'
import { Route as FinanceRoute } from './finance'
import { Route as SettingsRoute } from './settings'
import { useSessionStore } from '@/shared/session/store'

/**
 * Regression test for Plan 10-08: protected-route RBAC redirects must NOT coerce
 * `ParsedLocation.search` (parsed object) to a string. The fix is to use
 * `location.searchStr` (encoded string form) instead. This file locks in that
 * contract by invoking the route's `beforeLoad` directly with synthetic
 * locations and asserting the redirect payload — without crashing on
 * Symbol.toPrimitive.
 */

type FinanceBeforeLoadArg = Parameters<NonNullable<typeof FinanceRoute.options.beforeLoad>>[0]

function loc(pathname: string, searchStr: string) {
  return {
    href: pathname + searchStr,
    pathname,
    search: {} as Record<string, unknown>,
    searchStr,
    hash: '',
    state: {},
    maskedLocation: undefined,
  } as unknown as FinanceBeforeLoadArg['location']
}

function ctx() {
  return {
    queryClient: undefined as unknown as QueryClient,
    getSession: () => ({ role: 'reception' as const, setRole: () => {} }),
  }
}

async function captureRedirect(fn: () => unknown | Promise<unknown>): Promise<unknown> {
  try {
    const r = fn()
    if (r && typeof (r as Promise<unknown>).then === 'function') {
      return await (r as Promise<unknown>).then(
        () => {
          throw new Error('expected redirect, got resolve')
        },
        (e) => e,
      )
    }
    throw new Error('expected redirect, got sync return')
  } catch (e) {
    return e
  }
}

function readForbidden(err: unknown): string | undefined {
  const direct = (err as { search?: { forbidden?: string } }).search
  const nested = (err as { options?: { search?: { forbidden?: string } } }).options?.search
  return direct?.forbidden ?? nested?.forbidden
}

function readTo(err: unknown): string | undefined {
  return (
    (err as { to?: string }).to ?? (err as { options?: { to?: string } }).options?.to
  )
}

describe('protected-route RBAC redirect — searchStr (no object coercion)', () => {
  beforeEach(() => {
    useSessionStore.setState({ role: 'reception' })
  })

  it('reception → /finance produces forbidden=/finance redirect, no TypeError', async () => {
    const err = await captureRedirect(() =>
      FinanceRoute.options.beforeLoad!({
        context: ctx(),
        location: loc('/finance', ''),
      } as never),
    )
    expect(err).toBeDefined()
    expect((err as Error).message ?? '').not.toMatch(/Cannot convert object to primitive value/)
    expect(readTo(err)).toBe('/')
    expect(readForbidden(err)).toBe('/finance')
  })

  it('reception → /settings produces forbidden=/settings redirect', async () => {
    const err = await captureRedirect(() =>
      SettingsRoute.options.beforeLoad!({
        context: ctx(),
        location: loc('/settings', ''),
      } as never),
    )
    expect(err).toBeDefined()
    expect((err as Error).message ?? '').not.toMatch(/Cannot convert object to primitive value/)
    expect(readTo(err)).toBe('/')
    expect(readForbidden(err)).toBe('/settings')
  })

  it('preserves searchStr in the forbidden value', async () => {
    const err = await captureRedirect(() =>
      FinanceRoute.options.beforeLoad!({
        context: ctx(),
        location: loc('/finance', '?page=2'),
      } as never),
    )
    expect(readForbidden(err)).toBe('/finance?page=2')
  })

  it('does not coerce parsed `search` object (regression for the CR-01-fix bug)', async () => {
    // Simulate TanStack Router's parsed-search proxy: any attempt to call
    // Symbol.toPrimitive / toString / valueOf throws — exactly the failure mode
    // that crashed the route under `location.pathname + location.search`.
    const trapping = new Proxy(
      {},
      {
        get(_t, p) {
          if (p === Symbol.toPrimitive || p === 'toString' || p === 'valueOf') {
            return () => {
              throw new TypeError('Cannot convert object to primitive value')
            }
          }
          return undefined
        },
      },
    )
    const location = {
      href: '/finance',
      pathname: '/finance',
      search: trapping,
      searchStr: '',
      hash: '',
      state: {},
    } as unknown as FinanceBeforeLoadArg['location']

    const err = await captureRedirect(() =>
      FinanceRoute.options.beforeLoad!({ context: ctx(), location } as never),
    )
    expect((err as Error).message ?? '').not.toMatch(/Cannot convert object to primitive value/)
    expect(readForbidden(err)).toBe('/finance')
  })
})
