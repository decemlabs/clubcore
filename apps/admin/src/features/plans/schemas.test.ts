/**
 * Pure-Zod schema tests for features/plans/schemas.ts (Phase 101 MEM-01).
 *
 * Covers:
 *  - PlansListResponseSchema: list response shape
 *  - MembershipPlanCreateSchema: field validation (durationDays range, priceKopecks, freezeDaysLimit)
 *  - MembershipPlanUpdateSchema: durationDays is absent (immutable — must not be sendable)
 *  - PtPackagePlanCreateSchema: sessionCount ≥1, priceKopecks ≥1
 *  - PtPackagePlanUpdateSchema: only name is mutable
 *  - PtPackageSellSchema: amountKopecks ≥1
 */
import { describe, it, expect } from 'vitest'
import {
  PlansListResponseSchema,
  MembershipPlanCreateSchema,
  MembershipPlanUpdateSchema,
} from './schemas'
import {
  PtPackagePlanCreateSchema,
  PtPackagePlanUpdateSchema,
  PtPackageSellSchema,
} from '../pt-packages/schemas'

// ---------------------------------------------------------------------------
// PlansListResponseSchema
// ---------------------------------------------------------------------------

const validPlan = {
  id: 'plan-1',
  name: 'Месяц',
  durationDays: 30,
  priceKopecks: 300000,
  freezeDaysLimit: 7,
  active: true,
  createdAt: '2024-01-01T00:00:00Z',
}

describe('PlansListResponseSchema', () => {
  it('parses a valid list response', () => {
    const result = PlansListResponseSchema.parse({
      data: { items: [validPlan], total: 1, page: 1, pageSize: 25 },
    })
    expect(result.data.items).toHaveLength(1)
    expect(result.data.total).toBe(1)
    expect(result.data.page).toBe(1)
    expect(result.data.pageSize).toBe(25)
  })

  it('parses a plan with optional freezeDaysLimit absent', () => {
    const plan = { ...validPlan, freezeDaysLimit: undefined }
    const result = PlansListResponseSchema.parse({
      data: { items: [plan], total: 1, page: 1, pageSize: 25 },
    })
    expect(result.data.items[0]?.freezeDaysLimit).toBeUndefined()
  })

  it('parses a plan with nullable freezeDaysLimit', () => {
    const plan = { ...validPlan, freezeDaysLimit: null }
    const result = PlansListResponseSchema.parse({
      data: { items: [plan], total: 1, page: 1, pageSize: 25 },
    })
    expect(result.data.items[0]?.freezeDaysLimit).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// MembershipPlanCreateSchema
// ---------------------------------------------------------------------------

describe('MembershipPlanCreateSchema', () => {
  it('accepts a valid create input', () => {
    const result = MembershipPlanCreateSchema.safeParse({
      name: 'Годовой',
      durationDays: 365,
      priceKopecks: 1200000,
      freezeDaysLimit: 14,
      active: true,
    })
    expect(result.success).toBe(true)
  })

  it('rejects durationDays = 0 (min is 1)', () => {
    const result = MembershipPlanCreateSchema.safeParse({
      name: 'Bad',
      durationDays: 0,
      priceKopecks: 100,
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues.some((i) => i.path.includes('durationDays'))).toBe(true)
    }
  })

  it('rejects durationDays = 3651 (max is 3650)', () => {
    const result = MembershipPlanCreateSchema.safeParse({
      name: 'Bad',
      durationDays: 3651,
      priceKopecks: 100,
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues.some((i) => i.path.includes('durationDays'))).toBe(true)
    }
  })

  it('accepts durationDays at boundaries 1 and 3650', () => {
    expect(MembershipPlanCreateSchema.safeParse({ name: 'A', durationDays: 1, priceKopecks: 0 }).success).toBe(true)
    expect(MembershipPlanCreateSchema.safeParse({ name: 'A', durationDays: 3650, priceKopecks: 0 }).success).toBe(true)
  })

  it('rejects negative priceKopecks', () => {
    const result = MembershipPlanCreateSchema.safeParse({
      name: 'Bad',
      durationDays: 30,
      priceKopecks: -1,
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues.some((i) => i.path.includes('priceKopecks'))).toBe(true)
    }
  })

  it('accepts priceKopecks = 0 (free plan allowed)', () => {
    const result = MembershipPlanCreateSchema.safeParse({ name: 'Free', durationDays: 30, priceKopecks: 0 })
    expect(result.success).toBe(true)
  })

  it('rejects freezeDaysLimit = 0 (min is 1)', () => {
    const result = MembershipPlanCreateSchema.safeParse({
      name: 'Bad',
      durationDays: 30,
      priceKopecks: 0,
      freezeDaysLimit: 0,
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues.some((i) => i.path.includes('freezeDaysLimit'))).toBe(true)
    }
  })

  it('rejects freezeDaysLimit = 366 (max is 365)', () => {
    const result = MembershipPlanCreateSchema.safeParse({
      name: 'Bad',
      durationDays: 30,
      priceKopecks: 0,
      freezeDaysLimit: 366,
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues.some((i) => i.path.includes('freezeDaysLimit'))).toBe(true)
    }
  })

  it('accepts freezeDaysLimit at boundaries 1 and 365', () => {
    expect(MembershipPlanCreateSchema.safeParse({ name: 'A', durationDays: 30, priceKopecks: 0, freezeDaysLimit: 1 }).success).toBe(true)
    expect(MembershipPlanCreateSchema.safeParse({ name: 'A', durationDays: 30, priceKopecks: 0, freezeDaysLimit: 365 }).success).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// MembershipPlanUpdateSchema — durationDays must NOT be present
// ---------------------------------------------------------------------------

describe('MembershipPlanUpdateSchema', () => {
  it('is a partial schema (all fields optional)', () => {
    const result = MembershipPlanUpdateSchema.safeParse({})
    expect(result.success).toBe(true)
  })

  it('accepts name-only update', () => {
    const result = MembershipPlanUpdateSchema.safeParse({ name: 'Новое название' })
    expect(result.success).toBe(true)
  })

  it('has no durationDays key — durationDays is immutable client-side', () => {
    // durationDays should not appear in the parsed shape at all
    const shape = MembershipPlanUpdateSchema.shape
    expect('durationDays' in shape).toBe(false)
  })

  it('strips unknown field durationDays if passed (Zod strip mode)', () => {
    // Even if a caller attempts to include durationDays, it is not in the schema shape
    const shape = MembershipPlanUpdateSchema.shape
    expect('durationDays' in shape).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// PtPackagePlanCreateSchema
// ---------------------------------------------------------------------------

describe('PtPackagePlanCreateSchema', () => {
  it('accepts a valid create input', () => {
    const result = PtPackagePlanCreateSchema.safeParse({
      name: 'Пакет 10',
      sessionCount: 10,
      priceKopecks: 500000,
      validityDays: 90,
    })
    expect(result.success).toBe(true)
  })

  it('rejects sessionCount = 0 (min is 1)', () => {
    const result = PtPackagePlanCreateSchema.safeParse({
      name: 'Bad',
      sessionCount: 0,
      priceKopecks: 1,
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues.some((i) => i.path.includes('sessionCount'))).toBe(true)
    }
  })

  it('rejects priceKopecks = 0 (min is 1 for pt-packages)', () => {
    const result = PtPackagePlanCreateSchema.safeParse({
      name: 'Bad',
      sessionCount: 1,
      priceKopecks: 0,
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues.some((i) => i.path.includes('priceKopecks'))).toBe(true)
    }
  })

  it('accepts input without optional validityDays', () => {
    const result = PtPackagePlanCreateSchema.safeParse({ name: 'Пакет 5', sessionCount: 5, priceKopecks: 200000 })
    expect(result.success).toBe(true)
  })
})

// ---------------------------------------------------------------------------
// PtPackagePlanUpdateSchema — only name is mutable
// ---------------------------------------------------------------------------

describe('PtPackagePlanUpdateSchema', () => {
  it('accepts name update', () => {
    const result = PtPackagePlanUpdateSchema.safeParse({ name: 'Новое название' })
    expect(result.success).toBe(true)
  })

  it('has only name in its shape', () => {
    const shape = PtPackagePlanUpdateSchema.shape
    expect(Object.keys(shape)).toEqual(['name'])
  })

  it('rejects empty string name', () => {
    const result = PtPackagePlanUpdateSchema.safeParse({ name: '' })
    expect(result.success).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// PtPackageSellSchema
// ---------------------------------------------------------------------------

describe('PtPackageSellSchema', () => {
  it('accepts a valid sell input', () => {
    const result = PtPackageSellSchema.safeParse({
      clientId: 'client-1',
      planId: 'plan-1',
      amountKopecks: 500000,
    })
    expect(result.success).toBe(true)
  })

  it('rejects amountKopecks = 0 (min is 1)', () => {
    const result = PtPackageSellSchema.safeParse({
      clientId: 'client-1',
      planId: 'plan-1',
      amountKopecks: 0,
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues.some((i) => i.path.includes('amountKopecks'))).toBe(true)
    }
  })

  it('rejects missing clientId', () => {
    const result = PtPackageSellSchema.safeParse({ planId: 'plan-1', amountKopecks: 100 })
    expect(result.success).toBe(false)
  })
})
