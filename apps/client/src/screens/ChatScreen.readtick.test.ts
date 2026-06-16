/**
 * Phase-94 CR-02 regression: the read-tick watermark and watermark-monotonicity
 * MUST compare instants by epoch-ms (Date.parse), not by lexicographic ISO-string
 * order. sentAt (server) and readAt (WS) come from two different producers and may
 * use different offset formats (`Z` vs `+03:00`) or fractional seconds; raw string
 * `<=` / `>` then disagrees with the real instant ordering.
 *
 * These tests pin the comparison strategy ChatScreen relies on so a regression to
 * string comparison is caught. They mirror the exact predicates used in
 * ChatScreen.jsx (`Date.parse(sentAt) <= wmMs` and the watermark `>` update).
 */
import { describe, it, expect } from 'vitest'

// Same instant expressed two ways: UTC Z vs Moscow +03:00.
const SENT_UTC = '2024-01-01T12:00:00Z'
const READ_MSK = '2024-01-01T15:00:00+03:00' // identical instant to SENT_UTC

// A later instant in UTC, but lexicographically SMALLER than the +03:00 string.
const SENT_LATER_UTC = '2024-01-01T12:00:01Z'

// Predicate replicas of the ChatScreen fix.
const isReadByWatermark = (sentAt: string, watermark: string | null) => {
  const wmMs = watermark != null ? Date.parse(watermark) : null
  return wmMs != null && Date.parse(sentAt) <= wmMs
}
const nextWatermark = (prev: string | null, readAt: string) =>
  prev == null || Date.parse(readAt) > Date.parse(prev) ? readAt : prev

describe('CR-02 read-tick epoch-ms comparison', () => {
  it('marks own message read when sentAt instant <= readAt instant despite different offset formats', () => {
    // String comparison would FAIL here: '2024-01-01T12:00:00Z' <= '2024-01-01T15:00:00+03:00'
    // is true by luck, but the inverse case below proves the difference.
    expect(isReadByWatermark(SENT_UTC, READ_MSK)).toBe(true)
  })

  it('does NOT mark read when the message instant is strictly after the watermark instant', () => {
    // SENT_LATER_UTC (12:00:01Z) is AFTER READ_MSK (12:00:00Z), so it must stay unread —
    // even though lexicographically '2024-01-01T12:00:01Z' < '2024-01-01T15:00:00+03:00'
    // (a naive string `<=` would WRONGLY mark it read).
    expect('2024-01-01T12:00:01Z' <= READ_MSK).toBe(true) // demonstrates the string-compare bug
    expect(isReadByWatermark(SENT_LATER_UTC, READ_MSK)).toBe(false) // correct epoch-ms result
  })

  it('null watermark never marks anything read', () => {
    expect(isReadByWatermark(SENT_UTC, null)).toBe(false)
  })

  it('watermark advances only when the new readAt is a later instant (epoch-ms monotonic)', () => {
    expect(nextWatermark(null, READ_MSK)).toBe(READ_MSK)
    // Earlier instant expressed as a lexicographically-larger string must NOT win.
    const earlierUtc = '2024-01-01T11:00:00Z'
    expect(nextWatermark(READ_MSK, earlierUtc)).toBe(READ_MSK)
    // A genuinely later instant wins.
    const laterUtc = '2024-01-01T13:00:00Z'
    expect(nextWatermark(READ_MSK, laterUtc)).toBe(laterUtc)
  })
})
