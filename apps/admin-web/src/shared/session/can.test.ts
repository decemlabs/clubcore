import { describe, expect, it } from 'vitest'
import { OWNER_ONLY, can } from './can'

describe('can()', () => {
  it('allows owner any (action, resource) pair', () => {
    for (const entry of OWNER_ONLY) {
      expect(can('owner', entry.action, entry.resource)).toBe(true)
    }
    expect(can('owner', 'view', 'dashboard')).toBe(true)
    expect(can('owner', 'edit', 'clients')).toBe(true)
  })

  it('blocks reception from every OWNER_ONLY pair', () => {
    for (const entry of OWNER_ONLY) {
      expect(can('reception', entry.action, entry.resource)).toBe(false)
    }
  })

  it('allows reception non-owner-only actions', () => {
    expect(can('reception', 'view', 'dashboard')).toBe(true)
    expect(can('reception', 'view', 'clients')).toBe(true)
    expect(can('reception', 'view', 'schedule')).toBe(true)
    expect(can('reception', 'view', 'staff')).toBe(true)
    expect(can('reception', 'create', 'clients')).toBe(true)
    expect(can('reception', 'edit', 'clients')).toBe(true)
  })

  it('OWNER_ONLY covers ROLE-02/03/04 pairs', () => {
    const pairs = OWNER_ONLY.map((e) => `${e.action}:${e.resource}`)
    expect(pairs).toContain('view:finance')
    expect(pairs).toContain('view:reports')
    expect(pairs).toContain('view:settings')
    expect(pairs).toContain('delete:clients')
    expect(pairs).toContain('refund:finance')
  })

  // Phase 22 FE-09 (Warning 2 fix): /profile is the both-roles surface for SessionsList.
  // Reception cannot reach /settings (owner-only) but must manage their own sessions.
  it('allows both roles to view profile', () => {
    expect(can('owner', 'view', 'profile')).toBe(true)
    expect(can('reception', 'view', 'profile')).toBe(true)
  })

  it('OWNER_ONLY does NOT include any pair with profile', () => {
    expect(OWNER_ONLY.some((e) => e.resource === 'profile')).toBe(false)
  })

  it('OWNER_ONLY has exactly 25 entries (Phase 34 D-34-09a removed cancel:pt-sessions)', () => {
    expect(OWNER_ONLY).toHaveLength(25)
  })

  it('OWNER_ONLY covers Phase 30 INFRA-19 v1.4 owner-only pairs', () => {
    const pairs = OWNER_ONLY.map((e) => `${e.action}:${e.resource}`)
    // positive: owner-only writes (mirror permissions.py OWNER_ONLY v1.4 additions)
    expect(pairs).toContain('create:trainers')
    expect(pairs).toContain('edit:trainers')
    expect(pairs).toContain('delete:trainers')
    expect(pairs).toContain('view:pt-package-plans')
    expect(pairs).toContain('create:pt-package-plans')
    expect(pairs).toContain('edit:pt-package-plans')
    expect(pairs).toContain('delete:pt-package-plans')
    expect(pairs).toContain('view:payments')
    expect(pairs).toContain('cancel:pt-packages')
    expect(pairs).toContain('delete:pt-packages')
  })

  it('OWNER_ONLY does NOT include reception-retained Phase 30/34 rights', () => {
    const pairs = OWNER_ONLY.map((e) => `${e.action}:${e.resource}`)
    // reception RETAINS these per REQ INFRA-19 / B-07 / TRN-04 / PAY-04 / PT-07 / PT-15
    // Phase 34 D-34-09a also grants reception 'cancel:pt-sessions' — 24h cancel
    // window enforced server-side via `cancel_window_expired` 403, not RBAC.
    expect(pairs).not.toContain('view:trainers')
    expect(pairs).not.toContain('create:payments')
    expect(pairs).not.toContain('refund:memberships')
    expect(pairs).not.toContain('create:pt-packages')
    expect(pairs).not.toContain('refund:pt-packages')
    expect(pairs).not.toContain('create:pt-sessions')
    expect(pairs).not.toContain('cancel:pt-sessions')
  })
})
