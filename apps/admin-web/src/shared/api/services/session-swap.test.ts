import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const seam = readFileSync(resolve(__dirname, './index.ts'), 'utf8')

describe('swap seam (services/index.ts)', () => {
  it('branches on API_MODE from @/shared/api/config/env', () => {
    expect(seam).toContain("from '../config/env'")
    expect(seam).toContain('API_MODE')
  })

  it('eagerly imports both mock and http bundles (tree-shake friendly)', () => {
    expect(seam).toContain("from './mock'")
    expect(seam).toContain("from './http'")
    // must NOT use dynamic imports — code-splitting would defeat tree-shaking the unused bundle
    expect(seam).not.toMatch(/import\s*\(/)
  })

  it('selects httpServices when API_MODE === "http", else mockServices', () => {
    expect(seam).toMatch(/API_MODE\s*===\s*['"]http['"]\s*\?\s*httpServices\s*:\s*mockServices/)
  })

  it('re-exports API_MODE so consumers can branch without reading env again', () => {
    expect(seam).toMatch(/export\s*{\s*API_MODE\s*}/)
  })
})
