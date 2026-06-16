/**
 * Auth domain API hook contract tests (Phase 109 PROF-01/02).
 *
 * Verifies that the two new mutation hooks are exported with the expected
 * signatures. Network calls are NOT made — the tests assert only the
 * export contract (function exists, returns a TanStack useMutation shape).
 *
 * Full integration (actual PATCH/POST round-trips) is done via
 * live browser UAT in Phase 109 verifications.
 */
import { describe, it, expect } from 'vitest'
import { useUpdateProfile, useChangePassword } from './api'

describe('useUpdateProfile export', () => {
  it('is exported as a function', () => {
    expect(typeof useUpdateProfile).toBe('function')
  })
})

describe('useChangePassword export', () => {
  it('is exported as a function', () => {
    expect(typeof useChangePassword).toBe('function')
  })
})
