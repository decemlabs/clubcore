import { describe, it, expect } from 'vitest'
import { can, OWNER_ONLY } from './can'
import type { Action, Resource } from './registry'

describe('can()', () => {
  it('owner is allowed everything — all OWNER_ONLY pairs return true', () => {
    for (const { action, resource } of OWNER_ONLY) {
      expect(can('owner', action, resource)).toBe(true)
    }
  })

  it('owner is allowed arbitrary (action, resource) pairs', () => {
    expect(can('owner', 'view', 'finance')).toBe(true)
    expect(can('owner', 'delete', 'clients')).toBe(true)
    expect(can('owner', 'create', 'membership-plans')).toBe(true)
  })

  it('reception is denied owner-only pairs', () => {
    expect(can('reception', 'view', 'finance')).toBe(false)
    expect(can('reception', 'view', 'reports')).toBe(false)
    expect(can('reception', 'view', 'payroll')).toBe(false)
    expect(can('reception', 'view', 'settings')).toBe(false)
    expect(can('reception', 'delete', 'clients')).toBe(false)
  })

  it('reception is denied all 45 OWNER_ONLY pairs', () => {
    for (const { action, resource } of OWNER_ONLY) {
      expect(can('reception', action, resource)).toBe(false)
    }
  })

  it('reception retains non-owner-only pairs', () => {
    // Reception can view clients (not in OWNER_ONLY)
    expect(can('reception', 'view', 'clients')).toBe(true)
    // Reception can create memberships (sell flow — not in OWNER_ONLY)
    expect(can('reception', 'create', 'memberships')).toBe(true)
    // Reception can check_in visits
    expect(can('reception', 'check_in', 'visits')).toBe(true)
    // Reception can view trainers (not in OWNER_ONLY)
    expect(can('reception', 'view', 'trainers')).toBe(true)
    // Reception can view dashboard
    expect(can('reception', 'view', 'dashboard')).toBe(true)
    // Reception can view schedule
    expect(can('reception', 'view', 'schedule')).toBe(true)
    // Reception can list promo codes (Phase 113: list/view NOT in OWNER_ONLY)
    expect(can('reception', 'list', 'promo-codes')).toBe(true)
  })

  it('Phase 113 — promo-codes write actions are owner-only', () => {
    // Write actions are OWNER_ONLY
    expect(can('owner', 'create', 'promo-codes')).toBe(true)
    expect(can('owner', 'edit', 'promo-codes')).toBe(true)
    expect(can('owner', 'delete', 'promo-codes')).toBe(true)
    expect(can('reception', 'create', 'promo-codes')).toBe(false)
    expect(can('reception', 'edit', 'promo-codes')).toBe(false)
    expect(can('reception', 'delete', 'promo-codes')).toBe(false)
  })

  it('OWNER_ONLY matrix contains exactly 45 unique entries', () => {
    // Phase 113-01: added 3 promo-codes write pairs (create/edit/delete) — count 42 → 45
    const pairs = new Set(OWNER_ONLY.map((e) => `${e.action}|${e.resource}`))
    expect(pairs.size).toBe(45)
    expect(OWNER_ONLY.length).toBe(45)
  })
})

describe('can() type coverage', () => {
  it('accepts valid Action and Resource union values without type errors', () => {
    const actions: Action[] = ['view', 'create', 'edit', 'delete', 'refund', 'cancel', 'check_in', 'list', 'update']
    const resources: Resource[] = ['dashboard', 'clients', 'finance', 'memberships', 'trainers', 'visits']
    for (const action of actions) {
      for (const resource of resources) {
        // Just check no runtime error; type correctness checked by tsc
        expect(typeof can('owner', action, resource)).toBe('boolean')
        expect(typeof can('reception', action, resource)).toBe('boolean')
      }
    }
  })
})
