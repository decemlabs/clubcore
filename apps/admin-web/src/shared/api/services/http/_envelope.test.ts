import { describe, it, expect } from 'vitest'
import { unwrap } from './_envelope'

describe('unwrap', () => {
  it('strips the {data: T} envelope (Phase 4 D-07)', () => {
    expect(unwrap<{ x: number }>({ data: { x: 1 } })).toEqual({ x: 1 })
  })

  it('returns undefined for 204 No Content (request resolves to undefined)', () => {
    expect(unwrap<void>(undefined)).toBeUndefined()
  })

  it('passes through values that have no `data` key (defensive — test mocks may bypass envelope)', () => {
    expect(unwrap<{ x: number }>({ x: 1 } as unknown)).toEqual({ x: 1 })
  })

  it('passes through null / primitive values', () => {
    expect(unwrap<null>(null)).toBeNull()
    expect(unwrap<number>(42 as unknown)).toBe(42)
  })
})
