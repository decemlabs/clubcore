import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const html = readFileSync(resolve(__dirname, '../../../index.html'), 'utf8')

describe('theme bootstrap IIFE in index.html', () => {
  it('reads the clubcore:ui:v2 key first', () => {
    expect(html).toContain("localStorage.getItem('clubcore:ui:v2')")
  })

  it('falls back to legacy sportzal:ui:v1 key for one-boot v1.10 shim', () => {
    // Bootstrap runs BEFORE main.tsx migrator; without the fallback, returning
    // users would FOUC for one boot. Removal target: Phase 67 / RUN-07.
    expect(html).toContain("localStorage.getItem('sportzal:ui:v1')")
    // The fallback chain must use || so the new key takes precedence.
    expect(html).toMatch(
      /localStorage\.getItem\('clubcore:ui:v2'\)\s*\|\|\s*localStorage\.getItem\('sportzal:ui:v1'\)/,
    )
  })

  it('annotates the legacy fallback with a Phase 67 / RUN-07 removal TODO', () => {
    expect(html).toMatch(/TODO Phase 67\s*\/\s*RUN-07/)
  })

  it('title is lowercase "clubcore"', () => {
    expect(html).toContain('<title>clubcore</title>')
  })

  it('defaults to system and applies .dark class before React', () => {
    expect(html).toContain("var theme = 'system';")
    expect(html).toContain("document.documentElement.classList.add('dark')")
  })

  it('honours prefers-color-scheme for theme=system', () => {
    expect(html).toContain("'(prefers-color-scheme: dark)'")
  })

  it('is self-contained and before the React mount script', () => {
    const bootstrapIdx = html.indexOf("localStorage.getItem('clubcore:ui:v2')")
    const mountIdx = html.indexOf('/src/app/main.tsx')
    expect(bootstrapIdx).toBeGreaterThan(0)
    expect(mountIdx).toBeGreaterThan(bootstrapIdx)
  })

  it('is wrapped in try/catch so storage access can never FOUC-block', () => {
    expect(html).toMatch(/try\s*{[\s\S]*catch\s*\(_e\)\s*{\s*}/)
  })
})
