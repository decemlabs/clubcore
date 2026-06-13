/**
 * TDD tests for visits domain Zod schemas (Phase 101-04, extended Phase 103-01).
 * RED phase: written before schemas.ts exists.
 */
import { describe, expect, it } from 'vitest'
import { VisitSchema, VisitsListResponseSchema, VisitsListQuerySchema, GymMetaSchema, CheckInInputSchema } from './schemas'

describe('VisitSchema', () => {
  const baseVisit = {
    id: 'visit-1',
    clientId: 'client-1',
    membershipId: 'mem-1',
    checkedInAt: '2026-06-13T10:00:00Z',
    gymDate: '2026-06-13',
    channel: 'qr',
    checkedInBy: null,
    createdAt: '2026-06-13T10:00:00Z',
  }

  it('accepts a valid visit with null checkedInBy', () => {
    expect(() => VisitSchema.parse(baseVisit)).not.toThrow()
  })

  it('accepts a valid visit with string checkedInBy', () => {
    const visit = { ...baseVisit, checkedInBy: 'staff-user-id' }
    expect(() => VisitSchema.parse(visit)).not.toThrow()
  })

  it('accepts gymDate as ISO date string', () => {
    const result = VisitSchema.parse(baseVisit)
    expect(result.gymDate).toBe('2026-06-13')
  })

  it('accepts channel as string', () => {
    const result = VisitSchema.parse(baseVisit)
    expect(result.channel).toBe('qr')
  })

  it('parses id, clientId, membershipId correctly', () => {
    const result = VisitSchema.parse(baseVisit)
    expect(result.id).toBe('visit-1')
    expect(result.clientId).toBe('client-1')
    expect(result.membershipId).toBe('mem-1')
  })

  it('rejects missing required fields', () => {
    expect(() => VisitSchema.parse({ id: 'visit-1' })).toThrow()
  })
})

describe('VisitsListResponseSchema', () => {
  const baseResponse = {
    data: {
      items: [
        {
          id: 'visit-1',
          clientId: 'client-1',
          membershipId: 'mem-1',
          checkedInAt: '2026-06-13T10:00:00Z',
          gymDate: '2026-06-13',
          channel: 'qr',
          checkedInBy: null,
          createdAt: '2026-06-13T10:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      pageSize: 25,
    },
  }

  it('accepts a valid list response', () => {
    expect(() => VisitsListResponseSchema.parse(baseResponse)).not.toThrow()
  })

  it('returns data.items array', () => {
    const result = VisitsListResponseSchema.parse(baseResponse)
    expect(result.data.items).toHaveLength(1)
    expect(result.data.items[0]?.id).toBe('visit-1')
  })

  it('returns total, page, pageSize', () => {
    const result = VisitsListResponseSchema.parse(baseResponse)
    expect(result.data.total).toBe(1)
    expect(result.data.page).toBe(1)
    expect(result.data.pageSize).toBe(25)
  })

  it('rejects missing data field', () => {
    expect(() => VisitsListResponseSchema.parse({ items: [] })).toThrow()
  })
})

describe('VisitsListQuerySchema', () => {
  it('accepts an empty object (all fields optional)', () => {
    expect(() => VisitsListQuerySchema.parse({})).not.toThrow()
  })

  it('accepts a full filter object', () => {
    const filter = {
      from: '2026-06-01',
      to: '2026-06-30',
      clientId: 'client-1',
      page: 1,
      pageSize: 25,
    }
    expect(() => VisitsListQuerySchema.parse(filter)).not.toThrow()
  })

  it('returns typed fields when provided', () => {
    const result = VisitsListQuerySchema.parse({ from: '2026-06-01', page: 2 })
    expect(result.from).toBe('2026-06-01')
    expect(result.page).toBe(2)
    expect(result.clientId).toBeUndefined()
  })
})

describe('GymMetaSchema', () => {
  it('accepts a valid data-wrapped gym meta shape', () => {
    const meta = {
      data: {
        gymHoursStart: '07:00',
        gymHoursEnd: '23:00',
      },
    }
    expect(() => GymMetaSchema.parse(meta)).not.toThrow()
  })

  it('returns gymHoursStart and gymHoursEnd from data', () => {
    const result = GymMetaSchema.parse({ data: { gymHoursStart: '08:00', gymHoursEnd: '22:00' } })
    expect(result.data.gymHoursStart).toBe('08:00')
    expect(result.data.gymHoursEnd).toBe('22:00')
  })

  it('rejects missing data field', () => {
    expect(() => GymMetaSchema.parse({ gymHoursStart: '07:00' })).toThrow()
  })
})

describe('CheckInInputSchema', () => {
  it('rejects empty clientId', () => {
    expect(() => CheckInInputSchema.parse({ clientId: '' })).toThrow()
  })

  it('rejects missing clientId', () => {
    expect(() => CheckInInputSchema.parse({})).toThrow()
  })

  it('accepts a valid non-empty clientId', () => {
    expect(() => CheckInInputSchema.parse({ clientId: 'client-123' })).not.toThrow()
  })

  it('returns the clientId value', () => {
    const result = CheckInInputSchema.parse({ clientId: 'client-abc' })
    expect(result.clientId).toBe('client-abc')
  })
})
