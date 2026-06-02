/**
 * Unit tests for useClientTrainers hook (D-76-01, NHOME-01).
 * RED phase: asserts the hook and key factory exist before implementation.
 */
import { describe, it, expect } from 'vitest'

describe('clientPortalKeys.trainers (D-76-01)', () => {
  it('exports useClientTrainers from @/data', async () => {
    const mod = await import('@/data')
    expect(typeof mod.useClientTrainers).toBe('function')
  })

  it('clientPortalKeys.trainers() returns a key containing "trainers"', async () => {
    const { clientPortalKeys } = await import('@/lib/clientQueries')
    expect(clientPortalKeys.trainers()).toContain('trainers')
  })
})
