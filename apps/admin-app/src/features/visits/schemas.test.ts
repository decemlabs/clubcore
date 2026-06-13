/**
 * TDD tests for visits domain Zod schemas (Phase 101-04).
 * RED phase: written before schemas.ts exists.
 */
import { describe, expect, it } from 'vitest'
import { VisitSchema, VisitsListResponseSchema } from './schemas'

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
