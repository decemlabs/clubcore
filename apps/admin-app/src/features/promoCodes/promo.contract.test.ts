/**
 * Contract test: promo codes real backend JSON × FE Zod PromoCodesListResponseSchema (Phase 117 Plan 02).
 *
 * Loads the captured ASGITransport response (GET /api/v1/promo-codes)
 * from the backend capture test and parses it with the REAL runtime schema that
 * the usePromoCodes() hook uses.
 *
 * Failure = backend serializer changed a field name (e.g. discount_type vs discountType)
 * without a matching FE Zod update — the exact drift mode that caused v3.0/v3.1 browser-UAT failures.
 */
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { PromoCodesListResponseSchema } from './schemas'

const captured = JSON.parse(
  readFileSync(join(__dirname, 'capture/promo-codes-list-response.json'), 'utf-8'),
) as unknown

describe('promo contract — real backend JSON × FE Zod schema', () => {
  it('parses captured promo codes list response with PromoCodesListResponseSchema', () => {
    expect(() => PromoCodesListResponseSchema.parse(captured)).not.toThrow()
    const result = PromoCodesListResponseSchema.parse(captured).data
    expect(Array.isArray(result.items)).toBe(true)
    expect(typeof result.total).toBe('number')
    // At least the seeded CAPTURE117 code must appear.
    expect(result.items.length).toBeGreaterThan(0)
    const captureCode = result.items.find((c) => c.code === 'CAPTURE117')
    expect(captureCode).toBeDefined()
    expect(captureCode?.discountType).toBe('percentage')
  })
})
