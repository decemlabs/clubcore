import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

/**
 * Phase 62 D-62-06 / G-2 — pre-rehydrate localStorage migrator (copy-on-read + delete-old)
 *
 * Source assertions (string-level): the migrator block must exist at the top of
 * `apps/admin-web/src/app/main.tsx`, declare a readonly STORE_MIGRATIONS tuple,
 * cover all three storage namespaces, and be annotated with the Phase 67 / RUN-07
 * removal target. Behavioural assertions (returning-user / greenfield / already-migrated /
 * quota-error) are exercised via a small JS sandbox that re-implements the same
 * migrator semantics — the source file uses top-level await, which would execute the
 * full bootstrap on import; lifting the loop into a re-executable form for this test
 * is sufficient to lock the invariants.
 *
 * Removal target: v1.11 / Phase 67 / RUN-07.
 */

const source = readFileSync(resolve(__dirname, 'main.tsx'), 'utf8')

describe('main.tsx pre-rehydrate localStorage migrator (source-level)', () => {
  it('declares a STORE_MIGRATIONS tuple', () => {
    expect(source).toMatch(/STORE_MIGRATIONS/)
  })

  it('covers the three sportzal:* → clubcore:* key pairs', () => {
    expect(source).toContain("'sportzal:session:v1'")
    expect(source).toContain("'clubcore:session:v2'")
    expect(source).toContain("'sportzal:ui:v1'")
    expect(source).toContain("'clubcore:ui:v2'")
    expect(source).toContain("'sportzal:mock:v1'")
    expect(source).toContain("'clubcore:mock:v2'")
  })

  it('appears before the persist.rehydrate() calls', () => {
    // Use the executable call site (useSessionStore.persist.rehydrate()) to skip
    // any doc-comment mentions of persist.rehydrate above the migrator block.
    const migratorIdx = source.indexOf('STORE_MIGRATIONS')
    const rehydrateIdx = source.indexOf('useSessionStore.persist.rehydrate()')
    expect(migratorIdx).toBeGreaterThan(0)
    expect(rehydrateIdx).toBeGreaterThan(0)
    expect(migratorIdx).toBeLessThan(rehydrateIdx)
  })

  it('is annotated with the Phase 67 / RUN-07 removal TODO', () => {
    expect(source).toMatch(/TODO Phase 67\s*\/\s*RUN-07/)
  })

  it('wraps each iteration in a try/catch noop swallow', () => {
    // The block must catch storage quota / disabled errors so a failing pair
    // does not block the others or prevent React boot.
    expect(source).toMatch(/catch\s*{[\s\S]*?\/\* noop/)
  })
})

/**
 * Behaviour-level sandbox: re-implement the migrator's contract in-test and
 * exercise the four documented scenarios against an in-memory Map shim.
 * This guards the algorithm even if main.tsx is reorganised later.
 */

function makeStorageShim(seed: Record<string, string> = {}): Storage {
  const store = new Map<string, string>(Object.entries(seed))
  return {
    get length() {
      return store.size
    },
    clear: () => store.clear(),
    getItem: (k) => (store.has(k) ? (store.get(k) as string) : null),
    key: (i) => Array.from(store.keys())[i] ?? null,
    removeItem: (k) => {
      store.delete(k)
    },
    setItem: (k, v) => {
      store.set(k, String(v))
    },
  }
}

const PAIRS: ReadonlyArray<readonly [string, string]> = [
  ['sportzal:session:v1', 'clubcore:session:v2'],
  ['sportzal:ui:v1', 'clubcore:ui:v2'],
  ['sportzal:mock:v1', 'clubcore:mock:v2'],
] as const

function runMigrator(ls: Storage): void {
  for (const [oldKey, newKey] of PAIRS) {
    try {
      if (ls.getItem(newKey) !== null) continue
      const legacy = ls.getItem(oldKey)
      if (legacy === null) continue
      ls.setItem(newKey, legacy)
      ls.removeItem(oldKey)
    } catch {
      /* noop — storage quota/disabled; let store re-seed */
    }
  }
}

describe('main.tsx pre-rehydrate localStorage migrator (behaviour)', () => {
  it('returning user: copies sportzal:session:v1 → clubcore:session:v2 and removes the legacy key', () => {
    const ls = makeStorageShim({
      'sportzal:session:v1': '{"state":{"role":"reception"},"version":1}',
    })
    runMigrator(ls)
    expect(ls.getItem('clubcore:session:v2')).toBe(
      '{"state":{"role":"reception"},"version":1}',
    )
    expect(ls.getItem('sportzal:session:v1')).toBeNull()
  })

  it('greenfield user: empty storage stays empty (no spurious sportzal:* writes)', () => {
    const ls = makeStorageShim({})
    runMigrator(ls)
    for (const [oldKey, newKey] of PAIRS) {
      expect(ls.getItem(oldKey)).toBeNull()
      expect(ls.getItem(newKey)).toBeNull()
    }
  })

  it('already migrated: clubcore:*:v2 present is left untouched even if sportzal:*:v1 lingers', () => {
    const ls = makeStorageShim({
      'sportzal:session:v1': '{"state":{"role":"reception"},"version":1}',
      'clubcore:session:v2': '{"state":{"role":"owner"},"version":2}',
    })
    runMigrator(ls)
    expect(ls.getItem('clubcore:session:v2')).toBe(
      '{"state":{"role":"owner"},"version":2}',
    )
    // legacy key is left alone in this branch — the next clean boot will not retry
    expect(ls.getItem('sportzal:session:v1')).toBe(
      '{"state":{"role":"reception"},"version":1}',
    )
  })

  it('storage quota / setItem throws: error is swallowed, other pairs still process', () => {
    const real = makeStorageShim({
      'sportzal:session:v1': 'session-payload',
      'sportzal:ui:v1': 'ui-payload',
      'sportzal:mock:v1': 'mock-payload',
    })
    // Wrap so the FIRST setItem throws (simulates quota); subsequent setItem calls succeed.
    let firstSetCall = true
    const ls: Storage = {
      get length() {
        return real.length
      },
      clear: () => real.clear(),
      getItem: (k) => real.getItem(k),
      key: (i) => real.key(i),
      removeItem: (k) => real.removeItem(k),
      setItem: (k, v) => {
        if (firstSetCall) {
          firstSetCall = false
          throw new Error('QuotaExceededError')
        }
        real.setItem(k, v)
      },
    }
    expect(() => runMigrator(ls)).not.toThrow()
    // First pair failed; its legacy key remains and new key is absent.
    expect(real.getItem('sportzal:session:v1')).toBe('session-payload')
    expect(real.getItem('clubcore:session:v2')).toBeNull()
    // Second and third pairs succeeded.
    expect(real.getItem('clubcore:ui:v2')).toBe('ui-payload')
    expect(real.getItem('sportzal:ui:v1')).toBeNull()
    expect(real.getItem('clubcore:mock:v2')).toBe('mock-payload')
    expect(real.getItem('sportzal:mock:v1')).toBeNull()
  })
})
