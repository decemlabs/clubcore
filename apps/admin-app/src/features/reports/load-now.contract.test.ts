/**
 * Contract test: load/now real backend JSON × FE Zod LoadNowSchema (Phase 117 Plan 02).
 *
 * Loads the captured ASGITransport response (GET /api/v1/reports/load/now)
 * from the backend capture test and parses it with the REAL runtime schema that
 * the useLoadNow() hook uses.
 *
 * Representative capture for the cohort/anomaly/at-risk/load-now analytics group
 * (per 117-CONTEXT.md: "CONTEXT permits one analytics capture").
 *
 * Failure = backend serializer changed a field name without a matching FE Zod update.
 */
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { LoadNowSchema } from './schemas'

const captured = JSON.parse(
  readFileSync(join(__dirname, 'capture/load-now-response.json'), 'utf-8'),
) as unknown

describe('load-now contract — real backend JSON × FE Zod schema', () => {
  it('parses captured load/now response with LoadNowSchema', () => {
    expect(() => LoadNowSchema.parse(captured)).not.toThrow()
    const result = LoadNowSchema.parse(captured).data
    expect(typeof result.count).toBe('number')
    expect(result.count).toBeGreaterThanOrEqual(0)
    expect(typeof result.asOf).toBe('string')
    expect(typeof result.windowMinutes).toBe('number')
    expect(result.windowMinutes).toBeGreaterThan(0)
  })
})
