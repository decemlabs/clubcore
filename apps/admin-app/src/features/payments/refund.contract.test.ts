/**
 * Contract test: refund real backend JSON × FE Zod PaymentSchema (Phase 117 Plan 02).
 *
 * Loads the captured ASGITransport response from the backend capture test
 * (apps/backend/tests/integration/payments/test_refund_capture.py) and parses it
 * with the REAL runtime schema that the useRefundPayment hook uses.
 *
 * Failure = the backend serializer changed a field name (e.g. snake_case drift,
 * missing field, type change) without a matching FE Zod update.
 */
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { PaymentSchema } from './schemas'

const captured = JSON.parse(
  readFileSync(join(__dirname, 'capture/refund-response.json'), 'utf-8'),
) as unknown

describe('refund contract — real backend JSON × FE Zod schema', () => {
  it('parses captured ASGITransport response with PaymentSchema', () => {
    // The refund endpoint returns ResponseEnvelope[PaymentResponse]: { data: { ...payment } }
    // The hook extracts .data and parses it with PaymentSchema.
    const envelope = captured as { data: unknown }
    expect(() => PaymentSchema.parse(envelope.data)).not.toThrow()
    const result = PaymentSchema.parse(envelope.data)
    expect(result.subjectKind).toBe('refund')
    expect(result.amountKopecks).toBeLessThan(0)
    expect(typeof result.refundOf).toBe('string')
  })
})
