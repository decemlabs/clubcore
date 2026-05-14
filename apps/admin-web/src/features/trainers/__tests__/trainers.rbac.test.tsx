import { describe, it, expect } from 'vitest'
import { isRedirect } from '@tanstack/react-router'
import { Route } from '@/routes/_protected/trainers'

/**
 * RBAC unit tests for the /trainers route.
 *
 * These tests exercise the route's beforeLoad function directly
 * without requiring a full render. The beforeLoad guard MUST redirect
 * reception to '/' with search.forbidden containing '/trainers' (D-31-19).
 *
 * TanStack Router's redirect() returns a Response with options.to + options.search.
 */

function makeContext(role: 'owner' | 'reception') {
  return {
    getSession: () => ({ role }),
    queryClient: {} as never,
  }
}

function makeLocation(pathname: string, searchStr = '') {
  return {
    pathname,
    searchStr,
    href: pathname + searchStr,
    search: {},
    state: {},
    hash: '',
  }
}

describe('trainers route RBAC (beforeLoad)', () => {
  it('beforeLoad redirects reception to "/" with search.forbidden containing "/trainers"', () => {
    const ctx = makeContext('reception')
    const location = makeLocation('/trainers')

    let thrownError: unknown
    try {
      Route.options.beforeLoad?.({
        context: ctx,
        location,
      } as never)
    } catch (e) {
      thrownError = e
    }

    // TanStack Router redirect() returns a Response with .options
    expect(thrownError).toBeDefined()
    expect(isRedirect(thrownError)).toBe(true)

    const response = thrownError as Response & { options: Record<string, unknown> }
    expect(response.options['to']).toBe('/')

    const search = response.options['search'] as Record<string, unknown>
    expect(String(search['forbidden'])).toContain('/trainers')
  })

  it('beforeLoad returns undefined (no throw) for owner', () => {
    const ctx = makeContext('owner')
    const location = makeLocation('/trainers')

    let thrownError: unknown = null
    let result: unknown = undefined
    try {
      result = Route.options.beforeLoad?.({
        context: ctx,
        location,
      } as never)
    } catch (e) {
      thrownError = e
    }

    expect(thrownError).toBeNull()
    expect(result).toBeUndefined()
  })

  it('reception beforeLoad throws redirect with to="/" regardless of searchStr', () => {
    const ctx = makeContext('reception')
    const location = makeLocation('/trainers', '?active=true')

    let thrownError: unknown
    try {
      Route.options.beforeLoad?.({
        context: ctx,
        location,
      } as never)
    } catch (e) {
      thrownError = e
    }

    expect(isRedirect(thrownError)).toBe(true)
    const response = thrownError as Response & { options: Record<string, unknown> }
    expect(response.options['to']).toBe('/')
    const search = response.options['search'] as Record<string, unknown>
    expect(String(search['forbidden'])).toContain('/trainers')
  })
})
