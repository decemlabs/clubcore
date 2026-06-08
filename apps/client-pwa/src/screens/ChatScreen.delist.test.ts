/**
 * Phase 94 (PWA-01) — D-71-09 graduation guard for ChatScreen.
 *
 * ChatScreen graduated out of the D-71-09 net-new placeholder ESLint zone in
 * Phase 94: it is now a real data-backed screen importing the messaging hooks
 * via @/data. This test is the grep-returns-0 gate — it asserts the eslint
 * config no longer references ChatScreen in any of the D-71-09 spots.
 *
 * Phase 98 note: ReferralSheet also graduated (REFER-05). The regression guard
 * that asserted ReferralSheet was still in the zone has been removed — it is now
 * covered by ReferralSheet.delist.test.ts (its own grep-returns-0 guard).
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const eslintConfig = readFileSync(resolve(process.cwd(), 'eslint.config.js'), 'utf8')

describe('D-71-09 graduation: ChatScreen', () => {
  it('contains zero occurrences of ChatScreen (de-listed from all zone spots)', () => {
    const occurrences = eslintConfig.split('ChatScreen').length - 1
    expect(occurrences).toBe(0)
  })
})
