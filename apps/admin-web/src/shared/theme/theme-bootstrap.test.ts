import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const html = readFileSync(resolve(__dirname, '../../../index.html'), 'utf8')

describe('theme bootstrap IIFE in index.html', () => {
  it('reads the versioned sportzal:ui:v1 key', () => {
    expect(html).toContain("localStorage.getItem('sportzal:ui:v1')")
  })

  it('defaults to system and applies .dark class before React', () => {
    expect(html).toContain("var theme = 'system';")
    expect(html).toContain("document.documentElement.classList.add('dark')")
  })

  it('honours prefers-color-scheme for theme=system', () => {
    expect(html).toContain("'(prefers-color-scheme: dark)'")
  })

  it('is self-contained and before the React mount script', () => {
    const bootstrapIdx = html.indexOf("localStorage.getItem('sportzal:ui:v1')")
    const mountIdx = html.indexOf('/src/app/main.tsx')
    expect(bootstrapIdx).toBeGreaterThan(0)
    expect(mountIdx).toBeGreaterThan(bootstrapIdx)
  })

  it('is wrapped in try/catch so storage access can never FOUC-block', () => {
    expect(html).toMatch(/try\s*{[\s\S]*catch\s*\(_e\)\s*{\s*}/)
  })
})
