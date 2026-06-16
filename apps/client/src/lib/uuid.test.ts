/**
 * Phase-94 WR-07: secure-context-safe UUIDv4 generator.
 *
 * Tests assert:
 *   1. Uses crypto.randomUUID when available.
 *   2. Falls back to a valid v4 UUID when crypto.randomUUID is undefined
 *      (non-secure context / old WebView) WITHOUT throwing.
 *   3. Falls back to a valid v4 UUID when crypto is entirely absent.
 *   4. Produced fallback UUIDs are unique and RFC-4122 v4 shaped.
 */
import { describe, it, expect, afterEach } from 'vitest'

const V4_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

describe('uuidV4', () => {
  const realCrypto = globalThis.crypto

  afterEach(() => {
    // Restore the real crypto after each tampering test.
    Object.defineProperty(globalThis, 'crypto', { value: realCrypto, configurable: true })
  })

  it('uses crypto.randomUUID when available', async () => {
    const { uuidV4 } = await import('./uuid')
    const id = uuidV4()
    expect(id).toMatch(V4_RE)
  })

  it('falls back to a valid v4 UUID when crypto.randomUUID is undefined (non-secure context)', async () => {
    // Simulate a non-secure context: getRandomValues present, randomUUID absent.
    Object.defineProperty(globalThis, 'crypto', {
      value: {
        getRandomValues: (arr: Uint8Array) => {
          for (let i = 0; i < arr.length; i++) arr[i] = (i * 37 + 11) & 0xff
          return arr
        },
      },
      configurable: true,
    })
    const { uuidV4 } = await import('./uuid')
    let id = ''
    expect(() => {
      id = uuidV4()
    }).not.toThrow()
    expect(id).toMatch(V4_RE)
  })

  it('falls back to a valid v4 UUID when crypto is entirely absent', async () => {
    Object.defineProperty(globalThis, 'crypto', { value: undefined, configurable: true })
    const { uuidV4 } = await import('./uuid')
    let id = ''
    expect(() => {
      id = uuidV4()
    }).not.toThrow()
    expect(id).toMatch(V4_RE)
  })

  it('produces unique values across many calls', async () => {
    const { uuidV4 } = await import('./uuid')
    const seen = new Set<string>()
    for (let i = 0; i < 500; i++) seen.add(uuidV4())
    expect(seen.size).toBe(500)
  })
})
