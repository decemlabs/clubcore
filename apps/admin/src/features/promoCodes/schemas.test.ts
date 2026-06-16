/**
 * Promo codes Zod contract tests (Phase 113 CR-01 drift regression).
 *
 * CR-01: the create/update mutation hooks parse the backend write response
 * (`PromoCodeResponse`), which deliberately OMITS the `usedCount` aggregate.
 * Reusing the list-shaped `PromoCodeSchema` (which requires `usedCount`) threw
 * a ZodError on every successful write. These tests round-trip realistic
 * backend create/update response payloads (NO usedCount) through the EXACT
 * schema the hooks use (`PromoCodeWriteResponseSchema`) — the drift-catching
 * regression test the integration suite misses because it never drives the FE
 * parse path.
 */
import { describe, it, expect } from 'vitest'
import { PromoCodeSchema, PromoCodeWriteResponseSchema } from './schemas'

// Realistic PromoCodeResponse payload (camelCase wire, NO usedCount field) —
// mirrors apps/backend/app/modules/promo_codes/schemas.py PromoCodeResponse.
const backendWriteResponse = {
  id: '11111111-1111-1111-1111-111111111111',
  code: 'SUMMER25',
  discountType: 'percentage',
  discountValue: 1000,
  maxUses: 100,
  perClientLimit: null,
  validFrom: null,
  validUntil: null,
  isActive: true,
  applicableTo: null,
  description: 'Летняя скидка',
  createdAt: '2026-06-15T00:00:00Z',
} as const

describe('PromoCodeWriteResponseSchema (CR-01 drift guard)', () => {
  it('parses a backend create response that omits usedCount', () => {
    const result = PromoCodeWriteResponseSchema.safeParse(backendWriteResponse)
    expect(result.success).toBe(true)
  })

  it('parses a backend update (PATCH) response that omits usedCount', () => {
    const updateResponse = {
      ...backendWriteResponse,
      description: 'new desc',
      maxUses: 5,
    }
    const result = PromoCodeWriteResponseSchema.safeParse(updateResponse)
    expect(result.success).toBe(true)
  })

  it('does NOT carry a usedCount key (write response shape has no aggregate)', () => {
    const parsed = PromoCodeWriteResponseSchema.parse(backendWriteResponse)
    expect('usedCount' in parsed).toBe(false)
  })

  it('regression: the list schema REJECTS the write response (proves the drift)', () => {
    // This is exactly what CR-01 was: parsing the write response with the
    // list schema throws because usedCount is required there.
    const result = PromoCodeSchema.safeParse(backendWriteResponse)
    expect(result.success).toBe(false)
  })
})
