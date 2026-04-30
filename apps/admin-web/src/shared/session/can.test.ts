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
})
