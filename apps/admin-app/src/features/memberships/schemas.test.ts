/**
 * Membership domain schemas — Zod contract tests (Phase 101-03).
 *
 * Pure Zod schema validation — no network, no React.
 */
import { describe, it, expect } from 'vitest'
import {
  MembershipSchema,
  MembershipsListResponseSchema,
  MembershipSellSchema,
  MembershipCancelSchema,
  MembershipRefundSchema,
} from './schemas'
import { PtPackageCancelSchema, PtPackageSellSchema } from '../pt-packages/schemas'

// ---------------------------------------------------------------------------
// MembershipSchema
// ---------------------------------------------------------------------------

describe('MembershipSchema', () => {
  const validPlanSnapshot = {
    id: 'plan-1',
    name: '1 месяц',
    durationDays: 30,
    priceKopecks: 350000,
    freezeDaysLimit: 10,
    active: true,
    createdAt: '2026-01-01T00:00:00Z',
  }

  const validMembership = {
    id: 'mem-1',
    clientId: 'client-1',
    status: 'active' as const,
    planSnapshot: validPlanSnapshot,
    paidAmountKopecks: 350000,
    paidAt: '2026-04-01T10:00:00Z',
    startDate: '2026-04-01',
    endDate: '2026-05-01',
    freezeDaysUsed: 0,
    freezeDaysRemaining: 10,
    currentFreezePeriod: null,
    previousMembershipId: null,
    notes: null,
    createdAt: '2026-04-01T10:00:00Z',
  }

  it('parses a valid membership with planSnapshot', () => {
    const result = MembershipSchema.parse(validMembership)
    expect(result.id).toBe('mem-1')
    expect(result.planSnapshot.name).toBe('1 месяц')
    expect(result.planSnapshot.durationDays).toBe(30)
  })

  it('validates status enum values', () => {
    for (const status of ['active', 'frozen', 'expired', 'cancelled'] as const) {
      const result = MembershipSchema.parse({ ...validMembership, status })
      expect(result.status).toBe(status)
    }
  })

  it('rejects invalid status', () => {
    expect(() => MembershipSchema.parse({ ...validMembership, status: 'deleted' })).toThrow()
  })

  it('accepts nullable currentFreezePeriod', () => {
    const result = MembershipSchema.parse({ ...validMembership, currentFreezePeriod: null })
    expect(result.currentFreezePeriod).toBeNull()
  })

  it('accepts currentFreezePeriod with freeze period object', () => {
    const result = MembershipSchema.parse({
      ...validMembership,
      currentFreezePeriod: {
        id: 'freeze-1',
        startedAt: '2026-04-10T00:00:00Z',
        startedBy: 'staff-1',
        endedAt: null,
        endedBy: null,
      },
    })
    expect(result.currentFreezePeriod?.id).toBe('freeze-1')
    expect(result.currentFreezePeriod?.endedAt).toBeNull()
  })

  it('accepts optional/missing optional fields', () => {
    const minimal = {
      id: 'mem-2',
      clientId: 'client-1',
      status: 'active' as const,
      planSnapshot: validPlanSnapshot,
      paidAmountKopecks: 350000,
      startDate: '2026-04-01',
      endDate: '2026-05-01',
      freezeDaysUsed: 0,
      createdAt: '2026-04-01T10:00:00Z',
    }
    const result = MembershipSchema.parse(minimal)
    expect(result.id).toBe('mem-2')
  })
})

// ---------------------------------------------------------------------------
// MembershipsListResponseSchema
// ---------------------------------------------------------------------------

describe('MembershipsListResponseSchema', () => {
  it('parses a valid list response', () => {
    const raw = {
      data: {
        items: [],
        total: 0,
        page: 1,
        pageSize: 25,
      },
    }
    const result = MembershipsListResponseSchema.parse(raw)
    expect(result.data.total).toBe(0)
    expect(result.data.items).toHaveLength(0)
  })
})

// ---------------------------------------------------------------------------
// MembershipSellSchema
// ---------------------------------------------------------------------------

describe('MembershipSellSchema', () => {
  it('accepts valid sell input with required fields', () => {
    const result = MembershipSellSchema.parse({
      clientId: 'client-1',
      planId: 'plan-1',
    })
    expect(result.clientId).toBe('client-1')
    expect(result.planId).toBe('plan-1')
  })

  it('accepts optional paidAt and notes', () => {
    const result = MembershipSellSchema.parse({
      clientId: 'client-1',
      planId: 'plan-1',
      paidAt: '2026-04-01T10:00:00Z',
      notes: 'VIP клиент',
    })
    expect(result.paidAt).toBe('2026-04-01T10:00:00Z')
    expect(result.notes).toBe('VIP клиент')
  })

  it('rejects missing clientId', () => {
    expect(() => MembershipSellSchema.parse({ planId: 'plan-1' })).toThrow()
  })

  it('rejects missing planId', () => {
    expect(() => MembershipSellSchema.parse({ clientId: 'client-1' })).toThrow()
  })

  it('rejects empty clientId', () => {
    expect(() => MembershipSellSchema.parse({ clientId: '', planId: 'plan-1' })).toThrow()
  })
})

// ---------------------------------------------------------------------------
// MembershipCancelSchema
// ---------------------------------------------------------------------------

describe('MembershipCancelSchema', () => {
  it('accepts cancel without reason (reason is optional)', () => {
    const result = MembershipCancelSchema.parse({})
    expect(result.reason).toBeUndefined()
  })

  it('accepts cancel with reason up to 500 chars', () => {
    const reason = 'a'.repeat(500)
    const result = MembershipCancelSchema.parse({ reason })
    expect(result.reason).toBe(reason)
  })

  it('rejects reason longer than 500 chars', () => {
    const reason = 'a'.repeat(501)
    expect(() => MembershipCancelSchema.parse({ reason })).toThrow()
  })
})

// ---------------------------------------------------------------------------
// MembershipRefundSchema
// ---------------------------------------------------------------------------

describe('MembershipRefundSchema', () => {
  it('accepts valid reason 1-200 chars', () => {
    const result = MembershipRefundSchema.parse({ reason: 'Клиент передумал' })
    expect(result.reason).toBe('Клиент передумал')
  })

  it('rejects empty reason', () => {
    expect(() => MembershipRefundSchema.parse({ reason: '' })).toThrow(
      'Причина обязательна для возврата',
    )
  })

  it('rejects missing reason', () => {
    expect(() => MembershipRefundSchema.parse({})).toThrow()
  })

  it('rejects reason longer than 200 chars', () => {
    const reason = 'a'.repeat(201)
    expect(() => MembershipRefundSchema.parse({ reason })).toThrow()
  })

  it('accepts exactly 200 chars reason', () => {
    const reason = 'a'.repeat(200)
    const result = MembershipRefundSchema.parse({ reason })
    expect(result.reason).toBe(reason)
  })
})

// ---------------------------------------------------------------------------
// PtPackageCancelSchema — reason MANDATORY (unlike membership cancel)
// ---------------------------------------------------------------------------

describe('PtPackageCancelSchema', () => {
  it('rejects missing reason', () => {
    expect(() => PtPackageCancelSchema.parse({})).toThrow()
  })

  it('rejects empty reason', () => {
    expect(() => PtPackageCancelSchema.parse({ reason: '' })).toThrow('Причина обязательна')
  })

  it('accepts valid reason', () => {
    const result = PtPackageCancelSchema.parse({ reason: 'Клиент отказался' })
    expect(result.reason).toBe('Клиент отказался')
  })

  it('rejects reason longer than 200 chars', () => {
    const reason = 'a'.repeat(201)
    expect(() => PtPackageCancelSchema.parse({ reason })).toThrow()
  })
})

// ---------------------------------------------------------------------------
// PtPackageSellSchema — amountKopecks required
// ---------------------------------------------------------------------------

describe('PtPackageSellSchema', () => {
  it('requires amountKopecks >= 1', () => {
    expect(() => PtPackageSellSchema.parse({ clientId: 'c1', planId: 'p1', amountKopecks: 0 })).toThrow()
  })

  it('accepts valid sell input', () => {
    const result = PtPackageSellSchema.parse({ clientId: 'c1', planId: 'p1', amountKopecks: 100000 })
    expect(result.amountKopecks).toBe(100000)
  })

  it('rejects missing amountKopecks', () => {
    expect(() => PtPackageSellSchema.parse({ clientId: 'c1', planId: 'p1' })).toThrow()
  })
})
