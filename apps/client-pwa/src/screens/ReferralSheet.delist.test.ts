/**
 * Phase 98 (REFER-05) — D-71-09 graduation guard for ReferralSheet.
 *
 * ReferralSheet graduated out of the D-71-09 net-new placeholder ESLint zone in
 * Phase 98: it is now a real data-backed screen importing the referral summary
 * hook via @/data (useClientReferralSummary). This test is the grep-returns-0
 * gate — it asserts the eslint config no longer references ReferralSheet in any
 * of the 3 D-71-09 spots (negated ignore, dedicated no-restricted-paths block,
 * and related comments).
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const eslintConfig = readFileSync(resolve(process.cwd(), 'eslint.config.js'), 'utf8')

describe('D-71-09 graduation: ReferralSheet', () => {
  it('contains zero occurrences of ReferralSheet (de-listed from all 3 zone spots)', () => {
    const occurrences = eslintConfig.split('ReferralSheet').length - 1
    expect(occurrences).toBe(0)
  })
})
