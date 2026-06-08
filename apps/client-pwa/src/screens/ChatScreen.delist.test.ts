/**
 * Phase 94 (PWA-01) — D-71-09 graduation guard for ChatScreen.
 *
 * ChatScreen graduated out of the D-71-09 net-new placeholder ESLint zone in
 * Phase 94: it is now a real data-backed screen importing the messaging hooks
 * via @/data. This test is the grep-returns-0 gate — it asserts the eslint
 * config no longer references ChatScreen in any of the 3 D-71-09 spots, while
 * the still-placeholder ReferralSheet remains in the zone (regression guard so
 * only ChatScreen was removed, not the whole block).
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const eslintConfig = readFileSync(resolve(process.cwd(), 'eslint.config.js'), 'utf8')

describe('D-71-09 graduation: ChatScreen', () => {
  it('contains zero occurrences of ChatScreen (de-listed from all 3 zone spots)', () => {
    const occurrences = eslintConfig.split('ChatScreen').length - 1
    expect(occurrences).toBe(0)
  })

  it('still references ReferralSheet (only ChatScreen was removed from the zone)', () => {
    expect(eslintConfig).toContain('ReferralSheet')
  })
})
