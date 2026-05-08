import { describe, it, expect } from 'vitest'
import { can } from '@/shared/session/can'

/**
 * FE-09 / Warning 2: /profile route is the both-roles surface for SessionsList.
 *
 * The route's `beforeLoad` mirrors settings.tsx structure but uses the
 * 'profile' resource. `can(role, 'view', 'profile')` returns true for both
 * roles, so reception is NOT redirected (unlike /settings).
 *
 * The visual rendering of the page (SessionsList inside a Card with
 * "Активные сессии" heading) is exercised via the SessionsList component
 * tests; these gate-tests cover the routing/RBAC dimension.
 */
describe('/_protected/profile route gate (FE-09)', () => {
  it('owner can view profile', () => {
    expect(can('owner', 'view', 'profile')).toBe(true)
  })

  it('reception can view profile (NOT owner-only)', () => {
    expect(can('reception', 'view', 'profile')).toBe(true)
  })

  it('reception is BLOCKED from /settings (sanity — confirms /profile separation is needed)', () => {
    expect(can('reception', 'view', 'settings')).toBe(false)
  })
})
